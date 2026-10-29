"""Post-award lifecycle S5 — the maintenance loop + operational sub-states.

A funded student is IN MAINTENANCE — ONE predicate, ``maintenance_scope.is_in_maintenance``
(student maintenance Sprint 1, owner ruling 2026-10-29): ``awarded`` with a live Vircle wallet, or
``active`` / ``maintenance``. WITHIN maintenance an admin manages an operational sub-state, distinct from the
sponsor-facing ACADEMIC band (``pool.derive_progress_state``, derived from semester
results):

    on_track       — funded, in good standing (default)
    probation      — at-risk (a poor result / concern); support continues but flagged
    on_hold        — paused; a tranche RELEASE is blocked until resumed
    ready_to_close — support fulfilled / final result in; the S6 manual close reads this

The recurring loop is: record a SemesterResult (``in_programme.record_semester_result``)
→ the admin reviews it → sets the sub-state (e.g. probation on a poor CGPA) → releases or
withholds the next tranche (``disbursement.release_tranche`` / ``withhold_tranche``).
``on_hold`` makes the pause real — ON HOLD STOPS MONEY at every door (owner, 2026-10-29):
``disbursement.release_tranche`` refuses; ``payments.eligibility`` leaves the student out of a new
run; ``set_substate`` takes her out of every editable run; ``payments.set_item`` will not put her
back; ``payments.complete`` refuses a run that still pays her. Lifting the hold re-includes
nobody — the maker does that by hand.

⚠ THE MONEY HOLD IS NOT THE FILE PREDICATE (lead review, maintenance S1). ``is_on_hold`` reads the
stored sub-state and a PAYABLE status only — never ``vircle_activated_at``, which is mirrored from
the Vircle relay sheet: if that stamp were cleared, a hold judged on the file predicate would
silently stop holding and the next run would pay her again. ``can_set_substate`` decides who may
be given (or lifted from) a sub-state.

Import direction: ``maintenance → maintenance_scope / activity / models``; ``payments`` is
imported lazily inside ``_exclude_from_open_runs`` (payments reads ``is_on_hold`` from here).
"""
import logging

from django.db import transaction
from django.utils import timezone

from . import activity
from .maintenance_scope import PAYABLE_STATUSES, in_maintenance_q, is_in_maintenance
from .models import ScholarshipApplication
from .models.activity import EVENT_SUBSTATE_CHANGED

#: ⚠ THE MODULE NAME, WRITTEN OUT: the hold's AUDIT line is what a person searches the logs for.
logger = logging.getLogger('apps.scholarship.maintenance')

# The valid sub-states (mirror the model choices).
SUBSTATES = ('on_track', 'probation', 'on_hold', 'ready_to_close')

# Sub-states that BLOCK a tranche release (the money pause). Read by
# disbursement.release_tranche.
BLOCKS_RELEASE = ('on_hold',)


class MaintenanceError(Exception):
    """Raised by the maintenance writers with a machine code for the view
    (e.g. 'not_in_maintenance', 'bad_substate')."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


#: The exclusion reason a payment-run item carries when a hold took the student out of the run.
ON_HOLD_EXCLUDE_REASON = 'On hold'


def can_set_substate(application, substate=None):
    """May ``application`` be moved to ``substate`` (None = "to anything")? Only a PAYABLE status
    (``PAYABLE_STATUSES`` — the statuses a payment run pays) ever takes a sub-state, and then:

      * the student is in maintenance (``maintenance_scope.is_in_maintenance``), OR
      * she holds a Vircle eWallet ID (``vircle_id``) — a run pays on the ID, and the activation
        stamp is only advisory there, so an awarded student whose wallet Vircle has not yet
        reported live is PAID and must be holdable ("on hold stops money whatever the status"), OR
      * the move LEAVES a stored hold (``on_hold`` → anything else): a hold that is stored can
        always be lifted, whatever has happened to the wallet fields since it was placed.

    An awarded student with no wallet ID at all is not paid and takes no sub-state."""
    if application is None or application.status not in PAYABLE_STATUSES:
        return False
    if is_in_maintenance(application) or (application.vircle_id or '').strip():
        return True
    return (substate is not None and substate != 'on_hold'
            and application.maintenance_substate == 'on_hold')


def _require_maintenance(application, substate):
    if not can_set_substate(application, substate):
        raise MaintenanceError('not_in_maintenance')


def _exclude_from_open_runs(application):
    """ON HOLD STOPS MONEY, door (b): take the student's INCLUDED item out of every run that can
    still be edited (``payments.EDITABLE_STATUSES``), through ``payments.set_item`` — so a signed
    run reverts to draft and loses its signatures (D2: nobody signs one list and sends another;
    the approver signs the list without her). A run that completed meanwhile (``not_editable``,
    judged under the run's lock) is history: the money went before the hold.

    Returns ``[{'run': reference, 'signatures_cleared': bool}]``. ``PaymentRun`` keeps no audit
    trail of its own (its ``note`` is free text), so this list goes into the ``substate_changed``
    activity row, and a run whose signatures were cleared also gets a WARNING AUDIT log line —
    a finance sign-off undone by a hold must be findable (adversarial review M1)."""
    from . import payments
    from .models import PaymentRunItem
    refs = []
    items = (PaymentRunItem.objects.select_related('run')
             .filter(application=application, included=True,
                     run__status__in=payments.EDITABLE_STATUSES).order_by('run_id'))
    for item in items:
        was = item.run.status
        try:
            payments.set_item(item, included=False, exclude_reason=ON_HOLD_EXCLUDE_REASON)
        except payments.PaymentsError as e:
            if e.code != 'not_editable':
                raise
            continue
        cleared = was != 'draft'
        refs.append({'run': item.run.reference, 'signatures_cleared': cleared})
        if cleared:
            logger.warning('AUDIT hold_reverted_run app_id=%s run=%s from=%s — signatures cleared',
                           application.id, item.run.reference, was)
    return refs


def set_substate(application, substate, *, by_email=''):
    """Set the maintenance sub-state. Requires ``can_set_substate`` (a payable student in
    maintenance or holding a wallet ID; lifting a stored hold always) and a valid sub-state.
    Returns the application.
    Free movement between the four is allowed (an admin can put a student on probation, hold,
    resume to on_track, or mark ready to close, and reverse any of these) — the only terminal
    step out of maintenance is the S6 manual CLOSE, which is a separate action.

    A real change stamps WHO and WHEN (``maintenance_substate_changed_by`` / ``_at``) and writes
    one ``substate_changed`` activity row (meta old/new, staff-only), all in ONE transaction.
    Moving TO ``on_hold`` first takes the student out of every editable payment run
    (``_exclude_from_open_runs``) — first, so this transaction takes the run's lock BEFORE the
    application's row, the same order ``payments.complete`` takes them (no deadlock). Lifting the
    hold re-includes nobody.

    The STORED sub-state is re-read first (a plain read, no row lock — the run locks come first),
    so a stale in-memory copy cannot skip a real change or log the wrong ``old``; the write is
    CONDITIONAL on that value still being stored, so two officers racing cannot both "move" it —
    the loser gets ``changed_meanwhile`` and her whole change (run exclusions too) rolls back."""
    stored = (ScholarshipApplication.objects.filter(pk=application.pk)
              .values_list('maintenance_substate', flat=True).first())
    if stored is not None:
        application.maintenance_substate = stored
    _require_maintenance(application, substate)
    if substate not in SUBSTATES:
        raise MaintenanceError('bad_substate')
    old = application.maintenance_substate
    if old == substate:
        return application
    with transaction.atomic():
        meta = {'old': old, 'new': substate}
        if substate == 'on_hold':
            meta['excluded_from_runs'] = _exclude_from_open_runs(application)
        now, by = timezone.now(), (by_email or '')[:254]
        moved = ScholarshipApplication.objects.filter(pk=application.pk, maintenance_substate=old).update(
            maintenance_substate=substate, maintenance_substate_changed_at=now,
            maintenance_substate_changed_by=by)
        if not moved:
            raise MaintenanceError('changed_meanwhile')
        application.maintenance_substate = substate
        application.maintenance_substate_changed_at = now
        application.maintenance_substate_changed_by = by
        activity.log_event(application, EVENT_SUBSTATE_CHANGED, actor_email=by_email, meta=meta,
                           internal=True)
    return application


def reset_on_leaving(application, *, by_email='system', reason=''):
    """A case LEAVING the payable statuses (an award that falls through, ``award_revert``) starts
    clean: a stored sub-state other than ``on_track`` is reset, stamped and logged (adversarial
    review L1), so a later re-award never inherits an old hold or probation. Plain writes on the
    in-memory row — the CALLER saves; returns the field names to fold into its ``update_fields``.
    The activity row is written here, in the caller's transaction."""
    old = application.maintenance_substate
    if old in ('', 'on_track'):
        return []
    application.maintenance_substate = 'on_track'
    application.maintenance_substate_changed_at = timezone.now()
    application.maintenance_substate_changed_by = (by_email or '')[:254]
    activity.log_event(application, EVENT_SUBSTATE_CHANGED, actor_email=by_email, internal=True,
                       meta={'old': old, 'new': 'on_track', 'reason': reason or 'left_payable'})
    return ['maintenance_substate', 'maintenance_substate_changed_at',
            'maintenance_substate_changed_by']


def is_on_hold(application):
    """True iff the student's support is paused: the stored sub-state is ``on_hold`` and her status
    is one a payment run pays (``PAYABLE_STATUSES``). THE one definition — ``payments`` and
    ``disbursement`` both read it, so on hold stops money at every door. ⚠ Deliberately NOT the
    file predicate: it never reads the wallet stamp, so a cleared ``vircle_activated_at`` cannot
    release a hold (module docstring)."""
    return (application is not None and application.status in PAYABLE_STATUSES
            and application.maintenance_substate == 'on_hold')


def sponsor_support_status(application):
    """A COARSE, non-identifying operational signal for the sponsor surface — distinct
    from the academic band. Only the two states a funder legitimately needs are exposed:
    ``paused`` (on_hold) and ``completing`` (ready_to_close). ``probation`` is internal
    (never surfaced to a sponsor — it isn't the funder's place to see an at-risk flag),
    and on_track returns None (the academic band already conveys good standing).

    Judged like ``is_on_hold`` (a PAYABLE status, the stored sub-state), so a sponsor reads
    ``paused`` exactly when the money is stopped — the same answer ``pool.sponsor_portfolio_status``
    gives, which calls ``is_on_hold``."""
    if application is None or application.status not in PAYABLE_STATUSES:
        return None
    sub = application.maintenance_substate
    if sub == 'on_hold':
        return 'paused'
    if sub == 'ready_to_close':
        return 'completing'
    return None


def ready_to_close_queryset(model=ScholarshipApplication):
    """Funded students an admin has marked ready to close (the S6 close worklist)."""
    return model.objects.filter(in_maintenance_q(), maintenance_substate='ready_to_close')
