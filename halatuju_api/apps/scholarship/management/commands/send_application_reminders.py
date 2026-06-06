"""
Send completion reminders + auto-close for shortlisted-but-incomplete B40 applications.

Cadence (days from ``reminder_anchor_at`` = the shortlist invitation): R1 +2, R2 +9,
R3 +23, R4/final +53; then a 5-day grace and auto-close (status -> 'expired'). One email
per application per run, advancing one stage at a time — idempotent (a stage is never
re-sent) and burst-proof. The close is gated on the final reminder actually having gone
out >= 5 days earlier, so no application is closed without the warning.

Schedule this DAILY (e.g. Cloud Scheduler -> the cron endpoint, ~9am Asia/KL).

    python manage.py send_application_reminders [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import (
    FINAL_REMINDER_GRACE_DAYS, REMINDER_THRESHOLDS_DAYS, send_application_reminders,
)


class Command(BaseCommand):
    help = "Send due completion reminders + auto-close shortlisted apps that never completed."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List who would be reminded/closed without sending or changing anything.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        if dry:
            now = timezone.now()
            final_stage = len(REMINDER_THRESHOLDS_DAYS)
            qs = (ScholarshipApplication.objects
                  .filter(status='shortlisted', profile_completed_at__isnull=True,
                          reminder_anchor_at__isnull=False)
                  .select_related('cohort', 'profile'))
            remind = close = 0
            for app in qs:
                days = (now - app.reminder_anchor_at).days
                if (app.reminder_stage >= final_stage and app.last_reminder_at
                        and (now - app.last_reminder_at).days >= FINAL_REMINDER_GRACE_DAYS):
                    self.stdout.write(f"  [dry-run] would CLOSE app #{app.pk} -> {app.notify_email or '(no email)'}")
                    close += 1
                    continue
                nxt = app.reminder_stage + 1
                if nxt <= final_stage and days >= REMINDER_THRESHOLDS_DAYS[nxt - 1]:
                    self.stdout.write(f"  [dry-run] would send R{nxt} (day {days}) to app #{app.pk} -> {app.notify_email or '(no email)'}")
                    remind += 1
            self.stdout.write(self.style.SUCCESS(f"Reminders: {remind} would be sent, {close} would be closed"))
            return

        result = send_application_reminders()
        self.stdout.write(self.style.SUCCESS(
            f"Reminders: {result['reminded']} sent, {result['closed']} closed"
        ))
