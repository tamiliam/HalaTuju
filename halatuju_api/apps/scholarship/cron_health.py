"""The body of `CronRunView` (it runs ONE whitelisted job) and what the System health light expects
of each scheduled job (2026-10-28).

`run_job` is the single choke-point every Cloud Scheduler call passes through, so it is where each
run's outcome is recorded (`system_health_store.record_cron`). It lives here rather than in
`views.py` because that file is a ledgered oversize file with no room left to grow.

`EXPECTED_CADENCE` is the LIVE Cloud Scheduler fleet as read on 2026-10-28, keyed by `CronRunView.JOBS`
key (the scheduler's own job names differ — `halatuju-vircle-sheet-sync` calls `sync-vircle-sheet`,
`doc-backup` calls `backup-documents`). A job in JOBS but not here (a one-off door, an unscheduled
report) is never expected to run and is not watched. `release-decisions-15m` is a Cloud Run JOB,
not a call to this endpoint, so it cannot be watched here.
⚠ When a Scheduler entry is added, paused or re-timed, change this dict in the same change —
`test_system_health.py` holds every key to a real JOBS entry.
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
    # hourly
    'sponsor-realtime': HOURLY,
    'query-emails': HOURLY,
    'release-award-offer-emails': HOURLY,
    'auto-sponsor': HOURLY,
    'partner-milestones': HOURLY,
    'read-outage-start': HOURLY,             # at :05
    'reprocess-ic-vision': HOURLY,
    # every 15 minutes
    'notify-contact-submissions': EVERY_15_MIN,
    'interview-reminders': EVERY_15_MIN,
    'application-nudges': EVERY_15_MIN,
    # daily
    'purge-referrals': DAILY,
    'query-reminders': DAILY,
    'application-reminders': DAILY,
    # ⚠ The Scheduler entry is named `backfill-profiles`; JOBS has no such key, and this is the
    # nearest one. Confirm against `gcloud scheduler jobs describe` and correct it if not.
    'backfill-assigned-profiles': DAILY,
    'review-nudges': DAILY,
    'spending-ingest': DAILY,
    'vision-outage': DAILY,
    'sync-vircle-sheet': DAILY,              # Scheduler: halatuju-vircle-sheet-sync, 07:05 MYT
    'expire-temp-passwords': DAILY,
    'lapse-expired-offers': DAILY,
    # weekly
    'backup-documents': WEEKLY,              # Scheduler: doc-backup
    'course-data-check': WEEKLY,
    'sponsor-digests': WEEKLY,
    'partner-digests': WEEKLY,
    # monthly / yearly
    'issue-monthly-invoices': MONTHLY,
    'refresh-reminder': YEARLY,
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
