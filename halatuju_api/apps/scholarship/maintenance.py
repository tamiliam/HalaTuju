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

Import direction: ``maintenance → maintenance_scope / activity / models``; ``payments`` is
imported lazily inside ``_exclude_from_open_runs`` (payments reads ``is_on_hold`` from here).
"""
from django.db import transaction
from django.utils import timezone

from . import activity
from .maintenance_scope import in_maintenance_q, is_in_maintenance
from .models import ScholarshipApplication
from .models.activity import EVENT_SUBSTATE_CHANGED

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


def _require_maintenance(application):
    # Sub-states only apply to a student in the funded recurring loop (the ONE predicate).
    if not is_in_maintenance(application):
        raise MaintenanceError('not_in_maintenance')


def _exclude_from_open_runs(application):
    """ON HOLD STOPS MONEY, door (b): take the student's INCLUDED item out of every run that can
    still be edited (``payments.EDITABLE_STATUSES``), through ``payments.set_item`` — so a signed
    run reverts to draft and loses its signatures (D2: nobody signs one list and sends another;
    the approver signs the list without her). A run that completed meanwhile (``not_editable``,
    judged under the run's lock) is history: the money went before the hold. Returns the
    references of the runs she was taken out of."""
    from . import payments
    from .models import PaymentRunItem
    refs = []
    items = (PaymentRunItem.objects.select_related('run')
             .filter(application=application, included=True,
                     run__status__in=payments.EDITABLE_STATUSES).order_by('run_id'))
    for item in items:
        try:
            payments.set_item(item, included=False, exclude_reason=ON_HOLD_EXCLUDE_REASON)
        except payments.PaymentsError as e:
            if e.code != 'not_editable':
                raise
            continue
        refs.append(item.run.reference)
    return refs


def set_substate(application, substate, *, by_email=''):
    """Set the maintenance sub-state. Requires the student to be in maintenance
    (``maintenance_scope.is_in_maintenance``) and a valid sub-state. Returns the application.
    Free movement between the four is allowed (an admin can put a student on probation, hold,
    resume to on_track, or mark ready to close, and reverse any of these) — the only terminal
    step out of maintenance is the S6 manual CLOSE, which is a separate action.

    A real change stamps WHO and WHEN (``maintenance_substate_changed_by`` / ``_at``) and writes
    one ``substate_changed`` activity row (meta old/new, staff-only), all in ONE transaction.
    Moving TO ``on_hold`` first takes the student out of every editable payment run
    (``_exclude_from_open_runs``) — first, so this transaction takes the run's lock BEFORE the
    application's row, the same order ``payments.complete`` takes them (no deadlock). Lifting the
    hold re-includes nobody."""
    _require_maintenance(application)
    if substate not in SUBSTATES:
        raise MaintenanceError('bad_substate')
    old = application.maintenance_substate
    if old == substate:
        return application
    with transaction.atomic():
        meta = {'old': old, 'new': substate}
        if substate == 'on_hold':
            meta['excluded_from_runs'] = _exclude_from_open_runs(application)
        application.maintenance_substate = substate
        application.maintenance_substate_changed_at = timezone.now()
        application.maintenance_substate_changed_by = (by_email or '')[:254]
        application.save(update_fields=['maintenance_substate', 'maintenance_substate_changed_at',
                                        'maintenance_substate_changed_by'])
        activity.log_event(application, EVENT_SUBSTATE_CHANGED, actor_email=by_email, meta=meta,
                           internal=True)
    return application


def is_on_hold(application):
    """True iff the student's support is paused: in maintenance and on hold. THE one definition
    — ``payments`` and ``disbursement`` both read it, so on hold stops money at every door."""
    return is_in_maintenance(application) and application.maintenance_substate == 'on_hold'


def sponsor_support_status(application):
    """A COARSE, non-identifying operational signal for the sponsor surface — distinct
    from the academic band. Only the two states a funder legitimately needs are exposed:
    ``paused`` (on_hold) and ``completing`` (ready_to_close). ``probation`` is internal
    (never surfaced to a sponsor — it isn't the funder's place to see an at-risk flag),
    and on_track returns None (the academic band already conveys good standing)."""
    if not is_in_maintenance(application):
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
