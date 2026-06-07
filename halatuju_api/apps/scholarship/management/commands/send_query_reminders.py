"""
Check 2 STEP 2 — nudge submitted B40 students who still have open AI clarify queries.

One reminder per application, sent from ~2 days before the cohort's query SLA deadline
(``ScholarshipCohort.query_response_sla_days``, default 5) and only while queries are
still open and the window hasn't lapsed. Idempotent via ``query_reminder_at``. Lapsed
applications are NOT emailed — they already proceed-as-is (flagged for the reviewer).

Schedule this DAILY (Cloud Scheduler -> the cron endpoint, ~9am Asia/KL), alongside
the completion-reminder job.

    python manage.py send_query_reminders [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import (
    QUERY_SLA_ACTIVE_STATUSES, query_sla, query_sla_days, send_query_reminders,
    _elapsed_days_local,
)


class Command(BaseCommand):
    help = "Send a one-off 'answer your queries' reminder to submitted students with open clarify queries."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List who would be reminded without sending or changing anything.',
        )

    def handle(self, *args, **options):
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        if options['dry_run']:
            now = timezone.now()
            qs = (ScholarshipApplication.objects
                  .filter(status__in=QUERY_SLA_ACTIVE_STATUSES,
                          profile_completed_at__isnull=False, query_reminder_at__isnull=True)
                  .select_related('cohort', 'profile'))
            n = 0
            for app in qs:
                sla = query_sla(app, now)
                if not sla['active'] or sla['lapsed']:
                    continue
                if _elapsed_days_local(now, app.profile_completed_at) < max(query_sla_days(app) - 2, 0):
                    continue
                self.stdout.write(
                    f"  [dry-run] would remind app #{app.pk} "
                    f"({sla['open_count']} open, {sla['days_left']}d left) -> "
                    f"{app.notify_email or '(no email)'}")
                n += 1
            self.stdout.write(self.style.SUCCESS(f"Query reminders: {n} would be sent"))
            return

        result = send_query_reminders()
        self.stdout.write(self.style.SUCCESS(f"Query reminders: {result['reminded']} sent"))
