"""
Check 2 STEP 2 — send the delayed "we have a few questions" email.

The organisation's query-email delay after a student submits (org_config
``query_email_delay_hours``; platform default ``QUERY_EMAIL_DELAY_HOURS`` = 2h), email them
once that clarify questions are waiting in their Action Centre — only if questions are
actually open. The delay makes it read like a human reviewed the application, not a bot.

Schedule this FREQUENTLY (e.g. hourly via Cloud Scheduler -> the cron endpoint) so the
delay target is honoured.

    python manage.py send_due_query_emails [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import (
    QUERY_SLA_ACTIVE_STATUSES, _query_email_due_window, send_due_query_emails,
)


class Command(BaseCommand):
    help = "Send the delayed Check-2 'a few questions' email (~2h after submission)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List who would be emailed without sending or changing anything.',
        )

    def handle(self, *args, **options):
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        if options['dry_run']:
            # The SAME per-organisation window the real sweep uses — a dry run that re-spells
            # the platform-only cutoff would lie for any organisation with its own delay.
            now = timezone.now()
            qs = (ScholarshipApplication.objects
                  .filter(_query_email_due_window(now),
                          status__in=QUERY_SLA_ACTIVE_STATUSES,
                          profile_completed_at__isnull=False,
                          query_raised_notified_at__isnull=True)
                  .select_related('cohort', 'profile'))
            n = 0
            for app in qs:
                clarify = [r for r in sync_check2_queries(app) if r.kind == 'clarify']
                if not clarify:
                    continue
                self.stdout.write(
                    f"  [dry-run] would email app #{app.pk} ({len(clarify)} questions) -> "
                    f"{app.notify_email or '(no email)'}")
                n += 1
            self.stdout.write(self.style.SUCCESS(f"Query emails: {n} would be sent"))
            return

        result = send_due_query_emails()
        self.stdout.write(self.style.SUCCESS(f"Query emails: {result['sent']} sent"))
