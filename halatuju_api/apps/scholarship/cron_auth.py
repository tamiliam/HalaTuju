"""Who may run an internal cron job (`CronRunView`) — SEC-05, A1.9.

Before A1.9 ONE shared `CRON_SECRET` opened all ~60 jobs: the key Cloud Scheduler uses for a
reminder email also opened the batch award, the invoice run and the billable re-reads. Now each
job belongs to a FAMILY, and each family has its own key:

* ``money``       — moves money or a funding decision: awards, AutoSponsor, invoices, lapses,
                    rescoring, the spending ledger and the Vircle payment sheet.
* ``paid``        — calls a billable model / OCR in bulk: re-reads, profile drafts, blurbs.
* ``email``       — sends mail (reminders, digests, alerts), nothing else.
* ``maintenance`` — housekeeping, back-fills, seeds and read-only audits.

The family key lives in ``settings.CRON_FAMILY_SECRETS`` (env ``CRON_SECRET_MONEY``,
``CRON_SECRET_PAID``, ``CRON_SECRET_EMAIL``, ``CRON_SECRET_MAINTENANCE``).

⚠ SAFE TO DEPLOY BEFORE THE ENV VARS EXIST. The shared ``CRON_SECRET`` still opens every job
while it is set, so nothing changes on deploy. The owner then gives each Scheduler job its
family key, and finally removes ``CRON_SECRET`` from the service — from that moment only the
family key opens a job. An unset key opens nothing (an empty header never matches).

Every job in ``CronRunView.JOBS`` must have a family here (pinned by test_cron_auth.py), so a
new job cannot slip in unclassified.
"""
import hmac
import logging

from django.conf import settings

log = logging.getLogger(__name__)

FAMILIES = ('money', 'paid', 'email', 'maintenance')

_BY_FAMILY = {
    'money': (
        'award-students-batch', 'auto-sponsor', 'issue-monthly-invoices', 'lapse-expired-offers',
        'rescore-pending', 'sync-vircle-sheet', 'spending-ingest', 'spending-sort',
        'spending-import-only', 'spending-reread',
    ),
    'paid': (
        'autogenerate-profiles', 'backfill-assigned-profiles', 'refresh-profiles',
        'reextract-documents', 'reextract-offers', 'reprocess-ic-vision', 'backfill-anon-blurbs',
        'spending-ingest-report', 'spending-sort-report',
        'finalise-profiles',  # A2.1: the verdict's final profile + blurb (Gemini)
    ),
    'email': (
        'vision-outage', 'read-outage-start', 'decision-emails', 'application-reminders',
        'application-nudges', 'query-emails', 'query-reminders', 'send-award-offer-emails',
        'send-sign-invitation-emails', 'send-vircle-install-emails', 'bursary-signing-reminders',
        'release-award-offer-emails', 'sponsor-realtime', 'sponsor-digests', 'refresh-reminder',
        'interview-reminders', 'results-due-reminders', 'announcement-emails', 'survey-emails',
        'module-emails', 'review-nudges', 'notify-contact-submissions', 'partner-digests',
        'partner-milestones',
    ),
    'maintenance': (
        'backfill-verdict-engine-version', 'purge-referrals', 'backup-documents',
        'course-data-check', 'results-overdue-flag', 'expire-temp-passwords',
        'backfill-reporting-dates', 'backfill-confirmed-profiles', 'seed-partner-emails',
        'seed-sponsor-emails', 'repair-confirmed-pathway', 'audit-pathway-ticks',
        'backfill-requirements-snapshots', 'backfill-untagged-income-docs',
    ),
}

JOB_FAMILY = {job: family for family, jobs in _BY_FAMILY.items() for job in jobs}


def _matches(secret, provided):
    """Constant-time compare; an empty secret never matches (an unset key opens nothing)."""
    return bool(secret) and hmac.compare_digest(secret.encode(), provided.encode())


def opened_by(job, provided):
    """Which key opens ``job`` for the header value ``provided``: the family name, 'shared'
    (the legacy ``CRON_SECRET``), or None (refuse)."""
    provided = provided or ''
    family = JOB_FAMILY.get(job)
    family_secret = (getattr(settings, 'CRON_FAMILY_SECRETS', None) or {}).get(family) or ''
    if family and _matches(family_secret, provided):
        return family
    if _matches(getattr(settings, 'CRON_SECRET', '') or '', provided):
        return 'shared'
    return None


def allowed(job, provided):
    """True when the header opens this job. Logs which key did (never the key itself), so the
    owner can see when no Scheduler job still uses the shared one."""
    key = opened_by(job, provided)
    if key == 'shared':
        log.info('cron %s opened by the shared CRON_SECRET (SEC-05: move it to its family key)', job)
    return key is not None
