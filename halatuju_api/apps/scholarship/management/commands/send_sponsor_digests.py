"""F3 — send weekly sponsor digests of newly-published anonymised students.

Schedule WEEKLY (Cloud Scheduler -> the cron endpoint). Per-sponsor: only students
published since that sponsor's last digest; nothing new -> skipped.

    python manage.py send_sponsor_digests
"""
from django.core.management.base import BaseCommand

from apps.scholarship.sponsor_notifications import send_sponsor_digests


class Command(BaseCommand):
    help = "Send weekly sponsor digests of newly-published anonymised students."

    def handle(self, *args, **options):
        result = send_sponsor_digests()
        self.stdout.write(
            f"digests: {result['sent']}/{result['sponsors']} weekly sponsor(s) emailed"
        )
