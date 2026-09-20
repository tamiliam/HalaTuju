"""
The completion-reminder ladder and the auto-close that ends it.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.utils import timezone

from ..models import ScholarshipApplication


# ── Completion reminders + auto-close (the daily reminder job) ────────────────
# Cadence in DAYS from reminder_anchor_at: R1 +2, R2 +9, R3 +23, R4/final +53.
# After the final reminder, a 5-day grace then auto-close (status → 'expired').
REMINDER_THRESHOLDS_DAYS = (2, 9, 23, 53)   # index 0 → R1 … index 3 → R4 (final)
FINAL_REMINDER_GRACE_DAYS = 5               # close this long after R4 was sent


def _elapsed_days_local(now, anchor):
    """Whole CALENDAR days from ``anchor`` to ``now`` in the project timezone
    (Asia/KL). We compare local dates rather than flooring ``(now - anchor)`` so the
    cadence lands on the named day regardless of the anchor's time-of-day vs the fixed
    09:00 daily tick — a 14:30 anchor's R2 (+9) fires on the 9th calendar day at the
    09:00 tick, not the 10th (TD-087)."""
    return (timezone.localtime(now).date() - timezone.localtime(anchor).date()).days


def send_application_reminders(now=None):
    """Send the next due completion reminder to each shortlisted-but-incomplete
    application, and auto-close those that ignored the final reminder. Returns
    ``{'reminded': n, 'closed': n}``.

    Idempotent + burst-proof: a stage is never re-sent (guarded by reminder_stage),
    a completed/expired app drops out of the query, and at most ONE stage advances
    per run — only when its day-threshold is crossed — so even a back-dated anchor
    (the launch backfill) sends one email, not four. The close is gated on
    ``last_reminder_at`` (when the final reminder actually went out), never on raw
    elapsed days, so no application is closed without having received the warning."""
    from ..emails import send_reminder_email, send_application_closed_email
    from .. import usage as _usage
    now = now or timezone.now()
    final_stage = len(REMINDER_THRESHOLDS_DAYS)             # 4
    reminded = closed = 0
    qs = (ScholarshipApplication.objects
          .filter(status='shortlisted', profile_completed_at__isnull=True,
                  reminder_anchor_at__isnull=False)
          .select_related('cohort', 'profile'))
    for app in qs:
        name = getattr(app.profile, 'name', '') if app.profile else ''
        common = dict(to_email=app.notify_email, applicant_name=name,
                      programme_name=app.cohort.name, lang=app.locale)
        # Auto-close: the final reminder has been sent AND its 5-day grace elapsed.
        if (app.reminder_stage >= final_stage and app.last_reminder_at
                and (now - app.last_reminder_at).days >= FINAL_REMINDER_GRACE_DAYS):
            app.status = 'expired'
            app.expired_at = now
            app.save(update_fields=['status', 'expired_at'])
            # Bill the tenant: without this the send meters org-NULL and lands under the
            # billing screen's "Platform (shared base)". See the note on _meter_email.
            with _usage.usage_context(application=app):
                send_application_closed_email(**common)
            closed += 1
            continue
        # Otherwise, send the next stage if its day-threshold is crossed (one per run).
        next_stage = app.reminder_stage + 1                # 1..4
        if next_stage <= final_stage and _elapsed_days_local(now, app.reminder_anchor_at) >= REMINDER_THRESHOLDS_DAYS[next_stage - 1]:
            with _usage.usage_context(application=app):
                send_reminder_email(stage=next_stage, **common)
            app.reminder_stage = next_stage
            app.last_reminder_at = now
            app.save(update_fields=['reminder_stage', 'last_reminder_at'])
            reminded += 1
    return {'reminded': reminded, 'closed': closed}
