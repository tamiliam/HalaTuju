"""
Open clarification queries, the SLA clock on them, and assignment readiness.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.utils import timezone


# ── Check 2 STEP 2/3 — the query SLA clock (design §5) ───────────────────────
# Statuses where the post-submit query clock is live (submitted, not yet decided).
# V3 (#6): the query SLA / notify-email window. 'interviewed' DROPPED — once the case reaches
# interviewed the interview is concluded and querying is LOCKED (querying_locked), so the resolve
# endpoint refuses a clarify answer; a notify/reminder email to an interviewed student would invite
# an answer the API rejects. The window is now the answerable statuses only.
QUERY_SLA_ACTIVE_STATUSES = ('profile_complete', 'interviewing')


def open_clarify_queries(application):
    """The student's still-open Check-2 AI clarify queries (the ones the SLA governs)."""
    return application.resolution_items.filter(source='check2', kind='clarify', status='open')


def query_sla_days(application):
    return getattr(application.cohort, 'query_response_sla_days', 5) or 5


def query_sla(application, now=None):
    """The Check-2 query SLA clock. V3 (#8): each open clarify query runs its OWN clock from when
    it was RAISED (``ResolutionItem.created_at``), not one shared clock from submit — so a query
    raised on day 6 is no longer BORN already-lapsed (notified but reminder-less). Returns
    ``{active, deadline, lapsed, open_count, days_left}``:
      - active     — there are open clarify queries (the clock is meaningfully running)
      - deadline   — the LATEST open query's per-item deadline (the last one to expire); falls back
                     to submit + SLA days when there are no open queries (the assignment-gate floor)
      - lapsed     — every open query has passed its own window (or none are open and submit+SLA has)
      - open_count — open clarify queries
      - days_left  — whole days until ``deadline`` (negative once lapsed; None before submit)."""
    from datetime import timedelta
    now = now or timezone.now()
    start = application.profile_completed_at
    if start is None:
        return {'active': False, 'deadline': None, 'lapsed': False,
                'open_count': 0, 'days_left': None}
    sla_days = query_sla_days(application)
    open_items = list(open_clarify_queries(application))
    open_count = len(open_items)
    # Per-item deadline = when each query was raised + the SLA window (fall back to `start` for a
    # legacy row with no created_at). The app-level deadline is the LATEST to expire, so the app
    # is only 'lapsed' once EVERY open query has had its full window. No open items → the submit
    # clock is the floor (mirrors the old behaviour + keeps the assignment gate from waiting forever).
    submit_deadline = start + timedelta(days=sla_days)
    if open_items:
        deadline = max((it.created_at or start) + timedelta(days=sla_days) for it in open_items)
    else:
        deadline = submit_deadline
    return {
        'active': open_count > 0,
        'deadline': deadline,
        'lapsed': now >= deadline,
        'open_count': open_count,
        'days_left': (timezone.localtime(deadline).date() - timezone.localtime(now).date()).days,
    }


def open_student_tasks(application):
    """Every still-open task the student owes — the items shown in their Action Centre /
    the Check-2 Outstanding box (officer-raised + Check-2 queries/doc-requests). Broader
    than ``open_clarify_queries`` (which is only the clarify-SLA subset)."""
    return application.resolution_items.filter(source__in=('officer', 'check2'), status='open')


def is_ready_for_assignment(application, now=None):
    """The Check-3 assignment gate: an application is ready when ALL student-assigned tasks
    are done OR the SLA window (5 days from submit) has lapsed — whichever comes first
    (proceed-as-is, flagged for the reviewer). Never ready before submission.

    V3 (#8, owner decision 2026-07-03): the FLOOR here is the SUBMIT clock (submit + SLA days),
    DECOUPLED from a late query's own per-item deadline — so a query raised late can't push the
    review start back forever. The per-item clock (``query_sla``) governs the student REMINDER,
    not this floor."""
    from datetime import timedelta
    if application.profile_completed_at is None:
        return False
    if not open_student_tasks(application).exists():
        return True
    now = now or timezone.now()
    return now >= application.profile_completed_at + timedelta(days=query_sla_days(application))
