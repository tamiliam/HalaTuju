"""
Read-only course-data health check for the Course Data dashboard.

Runs the two server-runnable, NON-MUTATING reporters back to back and lets each record its
dashboard status:
    audit_data            → 'audit' card (counts / completeness)
    validate_course_urls  → 'link_health' card (reachability)  — concurrent, NO --fix

This is what the weekly Cloud Scheduler job (CronRunView 'course-data-check') and the dashboard's
"Run health check now" button both call. It NEVER writes to the catalogue — no --fix, no --apply,
no scrape. The browser-based catalogue scrapes (refresh_stpm / scrape_uptvet) stay manual/local.

Usage:
    python manage.py course_data_check
    python manage.py course_data_check --workers 20 --timeout 20
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

# Concurrency for the link check. ~650 URLs with a 20s timeout means the slow MY-gov tail
# dominates wall-clock, so we run 40 in parallel (read-only GETs) AND skip the per-URL retry
# (retries=0) for this bulk run — the 20s timeout already catches slow-but-alive sites, and a
# retry would double the slow tail and push the single Cloud Run request past its limit.
DEFAULT_WORKERS = 40
# MY gov/edu portals (IPG, matriculation, polytechnics) routinely take 10-15s to first byte from
# Cloud Run. A 10s budget false-flagged many as "connection failed"; 20s + the one retry in
# check_url clears almost all of those while still bounding the run well under the request timeout.
DEFAULT_TIMEOUT = 20.0


class Command(BaseCommand):
    help = 'Read-only course-data health check (audit + link reachability) for the dashboard. No writes.'

    def add_arguments(self, parser):
        parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
                            help='Concurrent link checks (default %d).' % DEFAULT_WORKERS)
        parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT,
                            help='Per-URL timeout in seconds (default %g).' % DEFAULT_TIMEOUT)

    def handle(self, *args, **options):
        self.stdout.write('=== Course-data health check (read-only) ===')

        # 1. Audit / counts (DB only, fast) — records the 'audit' dashboard status.
        self.stdout.write('\n[1/2] audit_data...')
        call_command('audit_data')

        # 2. Link reachability (concurrent GETs, NO --fix, retries=0) — records 'link_health'.
        self.stdout.write('\n[2/2] validate_course_urls (read-only)...')
        call_command('validate_course_urls', workers=options['workers'],
                     timeout=options['timeout'], retries=0)

        self.stdout.write(self.style.SUCCESS('\nHealth check complete (no catalogue writes).'))
