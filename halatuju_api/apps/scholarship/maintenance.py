"""Post-award lifecycle S5 — the maintenance loop + operational sub-states.

A funded student sits in ``status='maintenance'`` (the recurring per-semester loop).
WITHIN maintenance an admin manages an operational sub-state, distinct from the
sponsor-facing ACADEMIC band (``pool.derive_progress_state``, derived from semester
results):

    on_track       — funded, in good standing (default)
    probation      — at-risk (a poor result / concern); support continues but flagged
    on_hold        — paused; a tranche RELEASE is blocked until resumed
    ready_to_close — support fulfilled / final result in; the S6 manual close reads this

The recurring loop is: record a SemesterResult (``in_programme.record_semester_result``)
→ the admin reviews it → sets the sub-state (e.g. probation on a poor CGPA) → releases or
withholds the next tranche (``disbursement.release_tranche`` / ``withhold_tranche``).
``on_hold`` makes the pause real — ``release_tranche`` refuses to pay an on-hold student.

Import direction is one-way (``maintenance → models``); ``disbursement`` reads
``BLOCKS_RELEASE`` from here for the on-hold guard (no cycle).
"""
from .models import ScholarshipApplication

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


def _require_maintenance(application):
    # Sub-states only apply to a student in the funded recurring loop.
    if application is None or application.status != 'maintenance':
        raise MaintenanceError('not_in_maintenance')


def set_substate(application, substate):
    """Set the maintenance sub-state. Requires ``status='maintenance'`` and a valid
    sub-state. Returns the application. Free movement between the four is allowed (an
    admin can put a student on probation, hold, resume to on_track, or mark ready to
    close, and reverse any of these) — the only terminal step out of maintenance is the
    S6 manual CLOSE, which is a separate action."""
    _require_maintenance(application)
    if substate not in SUBSTATES:
        raise MaintenanceError('bad_substate')
    if application.maintenance_substate != substate:
        application.maintenance_substate = substate
        application.save(update_fields=['maintenance_substate'])
    return application


def is_on_hold(application):
    """True iff the student's support is paused (a tranche release is blocked)."""
    return (application is not None
            and application.status == 'maintenance'
            and application.maintenance_substate == 'on_hold')


def sponsor_support_status(application):
    """A COARSE, non-identifying operational signal for the sponsor surface — distinct
    from the academic band. Only the two states a funder legitimately needs are exposed:
    ``paused`` (on_hold) and ``completing`` (ready_to_close). ``probation`` is internal
    (never surfaced to a sponsor — it isn't the funder's place to see an at-risk flag),
    and on_track returns None (the academic band already conveys good standing)."""
    if application is None or application.status != 'maintenance':
        return None
    sub = application.maintenance_substate
    if sub == 'on_hold':
        return 'paused'
    if sub == 'ready_to_close':
        return 'completing'
    return None


def ready_to_close_queryset(model=ScholarshipApplication):
    """Funded students an admin has marked ready to close (the S6 close worklist)."""
    return model.objects.filter(status='maintenance', maintenance_substate='ready_to_close')
