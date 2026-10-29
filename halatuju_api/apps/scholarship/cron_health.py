"""The body of `CronRunView` (it runs ONE whitelisted job) and what the System health light expects
of each scheduled job (2026-10-28).

`run_job` is the single choke-point every Cloud Scheduler call passes through, so it is where each
run's outcome is recorded (`system_health_store.record_cron`). It lives here rather than in
`views.py` because that file is a ledgered oversize file with no room left to grow.

`EXPECTED_CADENCE` is EXACTLY the live Cloud Scheduler fleet that calls this endpoint, as the lead read
it on 2026-10-28, keyed by `CronRunView.JOBS` key (the Scheduler's own job names differ —
`release-decisions-15m` calls `decision-emails`, `halatuju-vircle-sheet-sync` calls `sync-vircle-sheet`).
Times are MYT. A job in JOBS but not here (a one-off door, an unscheduled report) is never expected to
run and is not watched.
⚠ When a Scheduler entry is added, paused or re-timed, change this dict in the same change —
`test_system_health.py` pins the set and holds every key to a real JOBS entry.
"""
import io
import logging
from datetime import timedelta

from django.core.management import call_command

from . import system_health_store as store

log = logging.getLogger(__name__)

EVERY_15_MIN = timedelta(minutes=15)
HOURLY = timedelta(hours=1)
DAILY = timedelta(days=1)
WEEKLY = timedelta(days=7)
MONTHLY = timedelta(days=31)     # the 15th of each month; 31 days so no month reads "late"
YEARLY = timedelta(days=366)

EXPECTED_CADENCE = {
    # every 15 minutes
    'application-nudges': EVERY_15_MIN,
    'decision-emails': EVERY_15_MIN,         # Scheduler: release-decisions-15m
    'interview-reminders': EVERY_15_MIN,
    'notify-contact-submissions': EVERY_15_MIN,
    # hourly
    'auto-sponsor': HOURLY,
    'partner-milestones': HOURLY,
    'query-emails': HOURLY,
    'read-outage-start': HOURLY,             # at :05
    'release-award-offer-emails': HOURLY,
    'reprocess-ic-vision': HOURLY,
    'sponsor-realtime': HOURLY,
    # daily
    'application-reminders': DAILY,          # 09:00
    'backfill-assigned-profiles': DAILY,     # 04:00
    'expire-temp-passwords': DAILY,          # 09:30
    'lapse-expired-offers': DAILY,           # 09:00
    'purge-referrals': DAILY,                # 03:00
    'query-reminders': DAILY,                # 09:00
    'results-overdue-flag': DAILY,           # 08:00 — ⚠ NEW in maintenance S4b: create the Scheduler job
    'review-nudges': DAILY,                  # 09:00
    'spending-ingest': DAILY,                # 07:00
    'sync-vircle-sheet': DAILY,              # 07:05
    'vision-outage': DAILY,                  # 02:00
    # weekly (Mondays)
    'backup-documents': WEEKLY,              # 03:00
    'course-data-check': WEEKLY,             # 03:00
    'partner-digests': WEEKLY,               # 08:00
    'sponsor-digests': WEEKLY,               # 09:00
    # monthly / yearly
    'issue-monthly-invoices': MONTHLY,       # the 15th, 09:00
    'refresh-reminder': YEARLY,              # 1 December, 09:00
}


def run_job(job, command, args):
    """Run one whitelisted management command and return the response body. Never raises: a 500
    only makes Cloud Scheduler retry. The run's outcome is recorded, best-effort."""
    out = io.StringIO()
    try:
        call_command(command, *args, stdout=out)
    except Exception as e:  # report, never 500 into scheduler retries
        log.warning('Cron job %s failed: %s', job, e, exc_info=True)
        store.record_cron(job, False, store.error_name(e))
        return {'job': job, 'error': str(e)[:300]}
    store.record_cron(job, True)
    return {'job': job, 'output': out.getvalue()[:12000]}
