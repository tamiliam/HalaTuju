"""Post-award lifecycle S4 — the disbursement/tranche ledger (money OUT to the student).

A funded award is paid in TRANCHES (e.g. per semester). This module owns the writes:
schedule a tranche, mark it disbursed ('released'), withhold it, or return it. It is a
LEDGER, not custody — real money via toyyibPay is deferred (TD-075), so a release records
a 'released' row with a mock reference rather than moving funds.

The one behaviour that touches the application state machine: **the first released tranche
flips the application ``active`` → ``maintenance``** (the student enters the recurring
funded loop). Subsequent releases are no-ops on the status (already maintenance). The
maintenance sub-state LOOP (results → review → release/withhold the next tranche) is S5.

Import direction is one-way — ``disbursement → models`` — and it reuses ``pool.FUNDED_STATES``
for the in-programme gate so there is one source of truth for "is this student funded".
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import pool, staff_activity
from .models import Disbursement, ScholarshipApplication


class DisbursementError(Exception):
    """Raised by the tranche writers with a machine code for the view
    (e.g. 'not_in_programme', 'bad_amount', 'bad_state')."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


# A tranche can only be scheduled/acted on for a FUNDED application. 'active' =
# executed/awaiting first payout; 'maintenance' = the recurring funded loop.
def _require_funded(application):
    if application is None or application.status not in pool.FUNDED_STATES:
        raise DisbursementError('not_in_programme')


def _clean_amount(amount):
    """Validate/normalise a positive money amount to a 2dp Decimal."""
    try:
        value = Decimal(str(amount)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        raise DisbursementError('bad_amount')
    if value <= 0:
        raise DisbursementError('bad_amount')
    return value


def _current_sponsorship(application):
    """The student's live allocation (the active Sponsorship), or None. Used to link a
    tranche to the funder without the caller having to know about sponsorships."""
    return application.sponsorships.filter(status='active').order_by('-decided_at').first()


@transaction.atomic
def schedule_tranche(application, *, amount, sequence=None, label='',
                     scheduled_for=None, sponsorship=None):
    """Schedule one tranche against a funded application. ``sequence`` auto-increments
    from the application's existing tranches when omitted; ``sponsorship`` defaults to
    the live allocation. Returns the new (status='scheduled') Disbursement."""
    _require_funded(application)
    value = _clean_amount(amount)
    if sequence is None:
        top = application.disbursements.aggregate(m=Max('sequence'))['m'] or 0
        sequence = top + 1
    if sponsorship is None:
        sponsorship = _current_sponsorship(application)
    return Disbursement.objects.create(
        application=application,
        sponsorship=sponsorship,
        amount=value,
        status='scheduled',
        sequence=sequence,
        label=(label or '').strip()[:100],
        scheduled_for=scheduled_for,
    )


def _flip_to_maintenance(application):
    """First disbursement → the student enters the recurring funded loop:
    ``active`` → ``maintenance``. Idempotent (a no-op once already in maintenance/closed)."""
    if application.status == 'active':
        application.status = 'maintenance'
        fields = ['status']
        if application.stamp_first('maintenance_at'):
            fields.append('maintenance_at')
        application.save(update_fields=fields)


@transaction.atomic
def release_tranche(disbursement, *, by_email='', reference='mock', note='', actor=None):
    """Mark a tranche disbursed (mock — TD-075). Only a 'scheduled' or 'due' tranche can
    be released, and NOT while the student's support is on hold (S5). Records who/when +
    the (mock) payment reference, and **flips the application ``active`` → ``maintenance``
    on the first release**. Returns the row.

    TD-420 / TD-383: the application row is locked and re-read FIRST (status and the stored hold),
    then the tranche's own row, so a close or a hold that committed after the view loaded them is
    seen, and two presses of Release cannot both pay one tranche."""
    from .status_lock import StatusRefused, lock_application_for
    if disbursement.status not in ('scheduled', 'due'):
        raise DisbursementError('bad_state')
    if disbursement.application is None:
        raise DisbursementError('not_in_programme')
    # S6: never release money to a non-funded (e.g. closed) student — closure leaves any
    # leftover scheduled tranche un-releasable.
    try:
        lock_application_for(disbursement.application, pool.FUNDED_STATES)
    except StatusRefused:
        raise DisbursementError('not_in_programme')
    # released or withheld since the page loaded, or the row has gone (was a 500): bad_state
    _lock_tranche(disbursement, ('scheduled', 'due'), lock_application=False)
    # S5: an on-hold student's support is paused — no money goes out until resumed.
    from . import maintenance
    if maintenance.is_on_hold(disbursement.application):
        raise DisbursementError('on_hold')
    disbursement.status = 'released'
    disbursement.released_at = timezone.now()
    disbursement.actioned_by = (by_email or '')[:254]
    disbursement.reference = (reference or 'mock')[:100]
    if note:
        disbursement.note = note.strip()[:500]
    disbursement.save(update_fields=[
        'status', 'released_at', 'actioned_by', 'reference', 'note', 'updated_at'])
    _flip_to_maintenance(disbursement.application)
    # Student maintenance S1: the file's activity log records the money, in this transaction.
    from . import activity
    from .models.activity import EVENT_PAYMENT_RELEASED
    activity.log_event(disbursement.application, EVENT_PAYMENT_RELEASED, actor_email=by_email,
                       meta={'amount': str(disbursement.amount), 'disbursement_id': disbursement.id,
                             'reference': disbursement.reference})
    _record_tranche(actor, staff_activity.TRANCHE_RELEASED, disbursement)
    return disbursement


@transaction.atomic
def withhold_tranche(disbursement, *, by_email='', note='', actor=None):
    """Hold a tranche back (probation / failed results — the S5 loop leans on this).
    Only a not-yet-paid tranche ('scheduled'/'due') can be withheld. Does NOT change the
    application status (the student stays in maintenance/active). Returns the row."""
    if disbursement.status not in ('scheduled', 'due'):
        raise DisbursementError('bad_state')
    _lock_tranche(disbursement, ('scheduled', 'due'))   # TD-383: a Release in flight wins
    disbursement.status = 'withheld'
    disbursement.actioned_by = (by_email or '')[:254]
    if note:
        disbursement.note = note.strip()[:500]
    disbursement.save(update_fields=['status', 'actioned_by', 'note', 'updated_at'])
    _record_tranche(actor, staff_activity.TRANCHE_WITHHELD, disbursement)
    return disbursement


@transaction.atomic
def return_tranche(disbursement, *, by_email='', note='', actor=None):
    """Mark a released tranche's money as returned (withdrawal / termination). Only a
    'released' tranche can be returned. Ledger-only — no real refund. Returns the row."""
    if disbursement.status != 'released':
        raise DisbursementError('bad_state')
    _lock_tranche(disbursement, ('released',))   # TD-383: two Returns cannot both land
    disbursement.status = 'returned'
    disbursement.actioned_by = (by_email or '')[:254]
    if note:
        disbursement.note = note.strip()[:500]
    disbursement.save(update_fields=['status', 'actioned_by', 'note', 'updated_at'])
    _record_tranche(actor, staff_activity.TRANCHE_RETURNED, disbursement)
    return disbursement


def _lock_tranche(disbursement, allowed, *, lock_application=True):
    """TD-383 (A1.5): lock in the ONE order (``status_lock.py``), the application row and then the
    tranche row, and re-read the tranche's status, so two writers (Release and Mark due, Release and
    Withhold) cannot both act on one tranche. ``bad_state`` when the row has gone or its status is
    not in ``allowed``. The application lock takes any status (it gives the order, not a gate);
    ``release_tranche`` has locked it already for its funded gate and passes False."""
    from .status_lock import StatusRefused, lock_application_for
    if lock_application and disbursement.application_id is not None:
        try:
            lock_application_for(disbursement.application,
                                 [c for c, _ in ScholarshipApplication.STATUS_CHOICES])
        except StatusRefused:   # the application row has gone
            raise DisbursementError('bad_state')
    fresh = Disbursement.objects.select_for_update().filter(pk=disbursement.pk).values('status').first()
    if fresh is None or fresh['status'] not in allowed:
        raise DisbursementError('bad_state')
    disbursement.status = fresh['status']


def _record_tranche(actor, verb, disbursement):
    """Common profile S4: the person who pressed Release / Withhold / Return gets the row on their own
    activity list, inside this transaction (best-effort; never raises). The subject is the STUDENT
    (the application), so the reader's student rule (D8) decides what a later viewer is told. A
    payment run's payouts are NOT written here: the run's approval is that act (`payments_chain`)."""
    staff_activity.record(actor, verb, disbursement.application, meta={'tranche': disbursement})


@transaction.atomic
def mark_due(disbursement):
    """Move a 'scheduled' tranche to 'due' (payable). Intended for an admin/cron when a
    tranche's scheduled date arrives. Returns the row.

    TD-383 (A1.5): locked and re-read, so a Release that committed first is seen and 'due' is
    never written over 'released' (that made the tranche payable a second time)."""
    if disbursement.status != 'scheduled':
        raise DisbursementError('bad_state')
    _lock_tranche(disbursement, ('scheduled',))
    disbursement.status = 'due'
    disbursement.save(update_fields=['status', 'updated_at'])
    return disbursement


# Action name → writer, for the single admin action endpoint.
ACTIONS = {
    'release': release_tranche,
    'withhold': withhold_tranche,
    'return': return_tranche,
    'mark_due': lambda d, **kw: mark_due(d),
}


def disbursement_dict(d):
    """Plain serialisable view of a tranche for the admin cockpit. Admin-facing — carries
    the funder link by id only; never any sponsor identity (anonymity holds)."""
    return {
        'id': d.id,
        'sequence': d.sequence,
        'amount': str(d.amount),
        'status': d.status,
        'label': d.label,
        'scheduled_for': d.scheduled_for,
        'released_at': d.released_at,
        'actioned_by': d.actioned_by,
        'reference': d.reference,
        'note': d.note,
        'sponsorship_id': d.sponsorship_id,
        'created_at': d.created_at,
    }
