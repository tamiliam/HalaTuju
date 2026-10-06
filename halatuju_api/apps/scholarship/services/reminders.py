"""
The completion-reminder ladder and the auto-close that ends it.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.utils import timezone

from ..models import ScholarshipApplication


# ── Completion reminders + auto-close (the daily reminder job) ────────────────
# Cadence in DAYS from reminder_anchor_at — PER ORGANISATION since org-timing Sprint 1
# (org_config `reminder_1_days` … `reminder_4_days`, `auto_close_after_final_reminder_days`).
# The two names below are the PLATFORM defaults behind those keys (R1 +2, R2 +9, R3 +23,
# R4/final +53, then a 5-day grace and auto-close). They MOVED to the leaf
# `apps/scholarship/constants.py` so the registry can read them without crossing into this
# package, and are re-exported here (and from `services`) unchanged.
from ..constants import FINAL_REMINDER_GRACE_DAYS, REMINDER_THRESHOLDS_DAYS

_LADDER_KEYS = ('reminder_1_days', 'reminder_2_days', 'reminder_3_days', 'reminder_4_days')


def reminder_ladder(organisation, cache=None):
    """The organisation's four reminder days, R1..R4, as a tuple. ⚠ THE ONE READER for the live
    sweep AND its dry run (`send_application_reminders --dry-run`), so the dry run can never
    report a schedule the live run does not follow. `cache` (a dict) holds one answer per
    organisation for the length of a sweep."""
    return _per_org(cache, ('ladder', getattr(organisation, 'pk', None)), lambda: tuple(
        _org_value(organisation, key) for key in _LADDER_KEYS))


def close_grace_days(organisation, cache=None):
    """Days after R4 before the application auto-closes — the organisation's
    `auto_close_after_final_reminder_days`. R4's email states this same number."""
    return _per_org(cache, ('close', getattr(organisation, 'pk', None)), lambda: (
        _org_value(organisation, 'auto_close_after_final_reminder_days')))


def _per_org(cache, slot, compute):
    """`compute()` once per `slot` while `cache` lives; uncached when `cache` is None."""
    if cache is None:
        return compute()
    if slot not in cache:
        cache[slot] = compute()
    return cache[slot]


def _org_value(organisation, key):
    from apps.courses import org_config
    return org_config.value(organisation, key)


def promised_close_days(app, cache=None):
    """How long after the final reminder `app` may be closed: the LONGER of what that reminder
    STATED and the organisation's current setting.

    ⚠ THE PROMISE IS KEPT (adversarial review F1, owner option 1, 2026-10-07). R4 tells the
    student "within N days"; an organisation that lowers the close afterwards must not close
    her sooner than N, and one that raises it gives her the longer wait. The stated N is stamped
    on `final_reminder_close_days` when R4 goes out; a NULL stamp is a final reminder sent before
    that column existed, whose wording was the literal platform 5."""
    stated = app.final_reminder_close_days
    if stated is None:
        stated = FINAL_REMINDER_GRACE_DAYS
    return max(stated, close_grace_days(app.owning_organisation, cache))


def reminder_due(app, now, cache=None):
    """What the sweep owes `app` today: ('close', None), ('remind', stage) or (None, None).

    The close is gated on `last_reminder_at` (when the final reminder actually went out), never
    on raw elapsed days, so no application is closed without having received the warning — and
    never sooner than that warning said (`promised_close_days`)."""
    org = app.owning_organisation
    ladder = reminder_ladder(org, cache)
    final_stage = len(ladder)                                     # 4
    if (app.reminder_stage >= final_stage and app.last_reminder_at
            and (now - app.last_reminder_at).days >= promised_close_days(app, cache)):
        return 'close', None
    next_stage = app.reminder_stage + 1                           # 1..4
    if (next_stage <= final_stage
            and _elapsed_days_local(now, app.reminder_anchor_at) >= ladder[next_stage - 1]):
        return 'remind', next_stage
    return None, None


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
    reminded = closed = 0
    cache = {}                                             # one ladder per organisation
    qs = (ScholarshipApplication.objects
          .filter(status='shortlisted', profile_completed_at__isnull=True,
                  reminder_anchor_at__isnull=False)
          .select_related('cohort', 'profile', 'owning_organisation__configuration'))
    for app in qs:
        name = getattr(app.profile, 'name', '') if app.profile else ''
        common = dict(to_email=app.notify_email, applicant_name=name,
                      programme_name=app.cohort.name, lang=app.locale)
        action, next_stage = reminder_due(app, now, cache)
        # Auto-close: the final reminder has been sent AND the organisation's grace elapsed.
        if action == 'close':
            app.status = 'expired'
            app.expired_at = now
            app.save(update_fields=['status', 'expired_at'])
            # Bill the tenant: without this the send meters org-NULL and lands under the
            # billing screen's "Platform (shared base)". See the note on _meter_email.
            with _usage.usage_context(application=app):
                send_application_closed_email(**common)
            closed += 1
            continue
        # Otherwise, send the next stage if its day-threshold is crossed (one per run). R4 states
        # the close in days, so it is handed the SAME number the close above waits for.
        if action == 'remind':
            close_days = close_grace_days(app.owning_organisation, cache)
            with _usage.usage_context(application=app):
                send_reminder_email(stage=next_stage, close_days=close_days, **common)
            app.reminder_stage = next_stage
            app.last_reminder_at = now
            fields = ['reminder_stage', 'last_reminder_at']
            if next_stage == len(_LADDER_KEYS):
                # The FINAL reminder states the close; record exactly what it said, in the same
                # save, so the close can never come sooner (`promised_close_days`).
                app.final_reminder_close_days = close_days
                fields.append('final_reminder_close_days')
            app.save(update_fields=fields)
            reminded += 1
    return {'reminded': reminded, 'closed': closed}
