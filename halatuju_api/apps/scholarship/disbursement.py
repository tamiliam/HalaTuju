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

from . import pool
from .models import Disbursement


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
        application.save(update_fields=['status'])


@transaction.atomic
def release_tranche(disbursement, *, by_email='', reference='mock', note=''):
    """Mark a tranche disbursed (mock — TD-075). Only a 'scheduled' or 'due' tranche can
    be released. Records who/when + the (mock) payment reference, and **flips the
    application ``active`` → ``maintenance`` on the first release**. Returns the row."""
    if disbursement.status not in ('scheduled', 'due'):
        raise DisbursementError('bad_state')
    disbursement.status = 'released'
    disbursement.released_at = timezone.now()
    disbursement.actioned_by = (by_email or '')[:254]
    disbursement.reference = (reference or 'mock')[:100]
    if note:
        disbursement.note = note.strip()[:500]
    disbursement.save(update_fields=[
        'status', 'released_at', 'actioned_by', 'reference', 'note', 'updated_at'])
    _flip_to_maintenance(disbursement.application)
    return disbursement


@transaction.atomic
def withhold_tranche(disbursement, *, by_email='', note=''):
    """Hold a tranche back (probation / failed results — the S5 loop leans on this).
    Only a not-yet-paid tranche ('scheduled'/'due') can be withheld. Does NOT change the
    application status (the student stays in maintenance/active). Returns the row."""
    if disbursement.status not in ('scheduled', 'due'):
        raise DisbursementError('bad_state')
    disbursement.status = 'withheld'
    disbursement.actioned_by = (by_email or '')[:254]
    if note:
        disbursement.note = note.strip()[:500]
    disbursement.save(update_fields=['status', 'actioned_by', 'note', 'updated_at'])
    return disbursement


@transaction.atomic
def return_tranche(disbursement, *, by_email='', note=''):
    """Mark a released tranche's money as returned (withdrawal / termination). Only a
    'released' tranche can be returned. Ledger-only — no real refund. Returns the row."""
    if disbursement.status != 'released':
        raise DisbursementError('bad_state')
    disbursement.status = 'returned'
    disbursement.actioned_by = (by_email or '')[:254]
    if note:
        disbursement.note = note.strip()[:500]
    disbursement.save(update_fields=['status', 'actioned_by', 'note', 'updated_at'])
    return disbursement


def mark_due(disbursement):
    """Move a 'scheduled' tranche to 'due' (payable). Intended for an admin/cron when a
    tranche's scheduled date arrives. Returns the row."""
    if disbursement.status != 'scheduled':
        raise DisbursementError('bad_state')
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
