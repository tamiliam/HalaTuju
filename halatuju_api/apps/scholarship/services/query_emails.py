"""
The delayed "a query was raised" email and its reminders.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.utils import timezone

from ..models import ScholarshipApplication
from .queries_sla import QUERY_SLA_ACTIVE_STATUSES, query_sla


# How long after submission to hold the "we have a few questions" email, so it reads as
# a human review rather than an instant bot reply (the owner's call). PLATFORM default —
# an organisation can tune its own delay via org_config `query_email_delay_hours`
# (Organisation → Settings → Configuration; Org Config Sprint B), whose registry default
# reads THIS constant.
# ⚠ It MOVED to `apps/scholarship/constants.py` at code health H16 and is RE-EXPORTED here, so
# `services.QUERY_EMAIL_DELAY_HOURS` still answers exactly as it did. `apps.courses` reads it
# from `constants`, which imports nothing — so the back-edge no longer pulls the whole
# eighteen-module `services` package in to read one integer.
from ..constants import QUERY_EMAIL_DELAY_HOURS


def _query_email_due_window(now):
    """The submitted-long-enough Q for `send_due_query_emails`, PER ORGANISATION.

    ⚠ THE DEFAULT ARM MUST BE SPELLED `~Q(id__in=…) | Q(isnull)` — SQL's `NOT (col IN …)` is
    NULL-false, so a bare negation silently drops every NULL-org application the moment ANY
    organisation configures a delay (the `pool._funded_grace_window` spelling, copied on
    purpose). The filter must stay in SQL: the sweep's loop calls `sync_check2_queries`, which
    CREATES items, so a too-early application let through the queryset would be asked early
    even if the send itself were skipped.
    """
    from datetime import timedelta
    from django.db.models import Q
    from apps.courses import org_config

    custom = org_config.custom_values('query_email_delay_hours')
    default_cutoff = now - timedelta(hours=org_config.default('query_email_delay_hours'))
    if not custom:
        return Q(profile_completed_at__lte=default_cutoff)
    window = (Q(profile_completed_at__lte=default_cutoff)
              & (~Q(owning_organisation_id__in=list(custom))
                 | Q(owning_organisation_id__isnull=True)))
    for org_id, hours in custom.items():
        window |= Q(owning_organisation_id=org_id,
                    profile_completed_at__lte=now - timedelta(hours=hours))
    return window


def bump_query_notify_on_new_item(application):
    """A NEW student-visible query / doc-request was just raised on an ALREADY-notified
    application → clear the one-time notify stamp so the batched hourly `send_due_query_emails`
    sweep announces it ONCE on its next run. Without this, a request raised AFTER the initial
    email (by a Check-2 re-sync or a verdict recompute) never reaches the student — they sit on
    it for days. Mirrors the officer-raise re-notify (views_admin.AdminRaiseItemView).

    Guarded by CHECK2_STUDENT_QUERIES_ENABLED (the student-query channel). No-op if the student
    hasn't been notified yet (the initial sweep will cover the new item anyway). Safe to call
    whenever a genuinely new item is created — creation is once-per-code, so this can't spam."""
    from django.conf import settings as _settings
    if not getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False):
        return
    if application.query_raised_notified_at is None:
        return
    application.query_raised_notified_at = None
    application.save(update_fields=['query_raised_notified_at'])


def send_due_query_emails(now=None):
    """Frequent sweep (hourly): the organisation's query-email delay after a student submits
    (org_config ``query_email_delay_hours``; platform default ``QUERY_EMAIL_DELAY_HOURS``),
    email them ONCE that a few clarify questions are waiting in their Action Centre — but
    only if questions are actually open (if they answered everything in the form, none).
    The delay is deliberate so it feels like someone reviewed the application. Idempotent
    via ``query_raised_notified_at``. Returns ``{'sent': n}``."""
    from django.conf import settings as _settings
    from ..check2_queries import sync_check2_queries
    from ..emails import send_query_raised_email
    if not getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False):
        return {'sent': 0}   # student queries held until the questions are reviewed
    now = now or timezone.now()
    sent = 0
    qs = (ScholarshipApplication.objects
          .filter(_query_email_due_window(now),
                  status__in=QUERY_SLA_ACTIVE_STATUSES,
                  profile_completed_at__isnull=False,
                  query_raised_notified_at__isnull=True)
          .select_related('cohort', 'profile'))
    from ..resolution import STUDENT_DOC_REQUEST_CODES
    for app in qs:
        # Every open thing the student must act on counts — the Check-2 clarify questions +
        # the one-tap pathway confirm (sync_check2_queries) AND the "review assistant"
        # missing-compulsory-document requests (a `doc` system gap, created at submit by
        # confirm_profile). So a student whose only open item is "upload your birth
        # certificate" is still told to check their Action Centre.
        queries = list(sync_check2_queries(app))
        doc_requests = app.resolution_items.filter(
            source='system', status='open', code__in=STUDENT_DOC_REQUEST_CODES).count()
        # Reviewer-raised items (doc-request / clarify / explanation) also need the
        # student to act — they always show in the Action Centre but were never counted
        # toward this notification, so a reviewer doc-request/re-request went unnotified.
        officer_open = (app.resolution_items
                        .filter(source='officer', status='open').exclude(kind='human').count())
        n_open = len(queries) + doc_requests + officer_open
        if n_open == 0:
            continue
        name = getattr(app.profile, 'name', '') if app.profile else ''
        send_query_raised_email(
            to_email=app.notify_email, applicant_name=name,
            programme_name=app.cohort.name, n_queries=n_open, lang=app.locale)
        app.query_raised_notified_at = now
        app.save(update_fields=['query_raised_notified_at'])
        sent += 1
    return {'sent': sent}


def send_query_reminders(now=None):
    """Daily sweep: nudge submitted students who still have open Check-2 clarify
    queries, once, ~2 days before the SLA deadline. Reuses the trilingual email
    infra. Idempotent via ``query_reminder_at`` (one reminder per application).
    Lapsed apps are NOT emailed (they already proceed-as-is). Returns ``{'reminded': n}``."""
    from django.conf import settings as _settings
    from ..emails import send_query_reminder_email
    if not getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False):
        return {'reminded': 0}   # student queries held until the questions are reviewed
    now = now or timezone.now()
    sent = 0
    qs = (ScholarshipApplication.objects
          .filter(status__in=QUERY_SLA_ACTIVE_STATUSES,
                  profile_completed_at__isnull=False, query_reminder_at__isnull=True)
          .select_related('cohort', 'profile'))
    for app in qs:
        sla = query_sla(app, now)
        if not sla['active'] or sla['lapsed']:
            continue
        # V3 (#8): fire ~2 days before the PER-ITEM deadline (the latest open query's own clock,
        # from query_sla), not the submit clock — so a query raised late still gets its reminder
        # instead of being born past a submit-anchored window (the "notified but reminder-less" bug).
        if sla['days_left'] is None or sla['days_left'] > 2:
            continue
        name = getattr(app.profile, 'name', '') if app.profile else ''
        send_query_reminder_email(
            to_email=app.notify_email, applicant_name=name,
            programme_name=app.cohort.name, n_queries=sla['open_count'],
            days_left=max(sla['days_left'], 0), lang=app.locale)
        app.query_reminder_at = now
        app.save(update_fields=['query_reminder_at'])
        sent += 1
    return {'reminded': sent}
