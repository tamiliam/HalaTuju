"""F3 — alert real-time sponsors about newly-published anonymised students.

Schedule HOURLY (Cloud Scheduler -> the cron endpoint, mirroring
``halatuju-application-reminders``). Idempotent + batched: a student is alerted once.

    python manage.py send_sponsor_realtime
"""
from django.core.management.base import BaseCommand

from apps.scholarship.sponsor_notifications import send_sponsor_realtime


class Command(BaseCommand):
    help = "Send real-time sponsor alerts for newly-published anonymised students."

    def handle(self, *args, **options):
        result = send_sponsor_realtime()
        self.stdout.write(
            f"realtime: {result['students']} new student(s) -> "
            f"{result['sent']}/{result['sponsors']} sponsor(s) emailed"
        )
