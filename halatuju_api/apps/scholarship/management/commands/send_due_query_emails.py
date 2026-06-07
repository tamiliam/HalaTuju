"""
Check 2 STEP 2 — send the delayed "we have a few questions" email.

~2 hours after a student submits (``QUERY_EMAIL_DELAY_HOURS``), email them once that
clarify questions are waiting in their Action Centre — only if questions are actually
open. The delay makes it read like a human reviewed the application, not a bot.

Schedule this FREQUENTLY (e.g. hourly via Cloud Scheduler -> the cron endpoint) so the
~2-hour target is honoured.

    python manage.py send_due_query_emails [--dry-run]
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import (
    QUERY_EMAIL_DELAY_HOURS, QUERY_SLA_ACTIVE_STATUSES, send_due_query_emails,
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
            now = timezone.now()
            cutoff = now - timedelta(hours=QUERY_EMAIL_DELAY_HOURS)
            qs = (ScholarshipApplication.objects
                  .filter(status__in=QUERY_SLA_ACTIVE_STATUSES,
                          profile_completed_at__isnull=False, profile_completed_at__lte=cutoff,
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
