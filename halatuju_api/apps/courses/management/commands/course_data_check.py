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
    python manage.py course_data_check --workers 20 --timeout 10
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

# Concurrency for the link check — ~650 URLs finish in well under a minute, so a single
# Cloud Run request (cron or button) completes comfortably inside the timeout.
DEFAULT_WORKERS = 20


class Command(BaseCommand):
    help = 'Read-only course-data health check (audit + link reachability) for the dashboard. No writes.'

    def add_arguments(self, parser):
        parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
                            help='Concurrent link checks (default %d).' % DEFAULT_WORKERS)
        parser.add_argument('--timeout', type=float, default=10.0, help='Per-URL timeout (seconds).')

    def handle(self, *args, **options):
        self.stdout.write('=== Course-data health check (read-only) ===')

        # 1. Audit / counts (DB only, fast) — records the 'audit' dashboard status.
        self.stdout.write('\n[1/2] audit_data...')
        call_command('audit_data')

        # 2. Link reachability (concurrent GETs, NO --fix) — records the 'link_health' status.
        self.stdout.write('\n[2/2] validate_course_urls (read-only)...')
        call_command('validate_course_urls', workers=options['workers'], timeout=options['timeout'])

        self.stdout.write(self.style.SUCCESS('\nHealth check complete (no catalogue writes).'))
