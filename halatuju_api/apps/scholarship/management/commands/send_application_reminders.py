"""
Send completion reminders + auto-close for shortlisted-but-incomplete B40 applications.

Cadence (days from ``reminder_anchor_at`` = the shortlist invitation) is the ORGANISATION's
(org_config ``reminder_1_days`` … ``reminder_4_days``; platform R1 +2, R2 +9, R3 +23, R4/final
+53), then its ``auto_close_after_final_reminder_days`` grace (platform 5) and auto-close
(status -> 'expired'). One email per application per run, advancing one stage at a time —
idempotent (a stage is never re-sent) and burst-proof. The close is gated on the final
reminder actually having gone out that grace earlier, so no application is closed without the
warning. ``--dry-run`` asks the same ``reminder_due`` the live sweep does.

Schedule this DAILY (e.g. Cloud Scheduler -> the cron endpoint, ~9am Asia/KL).

    python manage.py send_application_reminders [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import _elapsed_days_local, send_application_reminders
from apps.scholarship.services.reminders import reminder_due


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
            cache = {}
            qs = (ScholarshipApplication.objects
                  .filter(status='shortlisted', profile_completed_at__isnull=True,
                          reminder_anchor_at__isnull=False)
                  .select_related('cohort', 'profile', 'owning_organisation__configuration'))
            remind = close = 0
            for app in qs:
                # The SAME decision the live sweep makes (`reminder_due`, the organisation's
                # ladder) — a dry run that kept its own copy would report a schedule the live
                # run does not follow.
                action, nxt = reminder_due(app, now, cache)
                if action == 'close':
                    self.stdout.write(f"  [dry-run] would CLOSE app #{app.pk} -> {app.notify_email or '(no email)'}")
                    close += 1
                    continue
                if action == 'remind':
                    days = _elapsed_days_local(now, app.reminder_anchor_at)
                    self.stdout.write(f"  [dry-run] would send R{nxt} (day {days}) to app #{app.pk} -> {app.notify_email or '(no email)'}")
                    remind += 1
            self.stdout.write(self.style.SUCCESS(f"Reminders: {remind} would be sent, {close} would be closed"))
            return

        result = send_application_reminders()
        self.stdout.write(self.style.SUCCESS(
            f"Reminders: {result['reminded']} sent, {result['closed']} closed"
        ))
