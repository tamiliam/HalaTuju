"""The student file's activity log — the writers (student maintenance Sprint 1, 2026-10-29).

Two doors, one table (``models/activity.py``, ``student_activity``):

  * ``log_event`` — a SYSTEM row, written by the code that did the thing: a sub-state change
    (``maintenance.set_substate``), a payment (``payments.complete``, ``disbursement.release_tranche``),
    a closure (``closure.close_application``), a semester result
    (``in_programme.record_semester_result``).
  * ``add_entry`` — a MANUAL row an officer writes (note / call / meeting / email). No endpoint
    calls it yet; the Scholars file's Activity tab does from Sprint 2.

⚠ TRANSACTION SEMANTICS (a decision, not an accident): ``log_event`` is a plain write, called
INSIDE the caller's own ``transaction.atomic`` block. The log is PART OF THE RECORD — a hold that
rolled back must leave no "put on hold" row, and a payment that committed must never be missing
its row. So it is not deferred to ``on_commit`` and it does not swallow its own errors: if the row
cannot be written the caller's change rolls back with it. The price is that the table must exist
before the code that writes it is deployed — MIGRATE FIRST (scholarship 0183), which is the house
rule anyway. ``meta`` is plain JSON (strings, numbers): a ``Decimal`` amount is written as a string.
"""
from .models import StudentActivity
from .models.activity import EVENTS, KIND_SYSTEM, MANUAL_KINDS

#: The longest manual entry an officer may write.
BODY_MAX = 5000


class ActivityError(Exception):
    """Raised by ``add_entry`` with a machine code: 'bad_kind', 'empty_body', 'too_long'."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def log_event(application, event, *, actor_email='', meta=None, body='', internal=False):
    """Write one SYSTEM row for ``application``. ``event`` must be one of ``EVENTS`` (a typo is a
    programming error, so it raises ``ValueError`` rather than writing a code nobody reads).
    ``internal`` marks a staff-only row (a sub-state change: probation is never the student's)."""
    if event not in EVENTS:
        raise ValueError(f'unknown activity event {event!r}')
    return StudentActivity.objects.create(
        application=application, kind=KIND_SYSTEM, event=event,
        body=(body or '')[:BODY_MAX], meta=dict(meta or {}),
        actor_email=(actor_email or '')[:254], internal=bool(internal))


def add_entry(application, kind, body, *, actor_email, internal=False):
    """Write one MANUAL row (note / call / meeting / email) by ``actor_email``."""
    if kind not in MANUAL_KINDS:
        raise ActivityError('bad_kind')
    text = (body or '').strip()
    if not text:
        raise ActivityError('empty_body')
    if len(text) > BODY_MAX:
        raise ActivityError('too_long')
    return StudentActivity.objects.create(
        application=application, kind=kind, body=text,
        actor_email=(actor_email or '')[:254], internal=bool(internal))
