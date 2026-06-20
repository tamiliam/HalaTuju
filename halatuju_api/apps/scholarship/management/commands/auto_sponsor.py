"""R6 — AutoSponsor: allocate standing gifts to matching pool students.

Schedule HOURLY (Cloud Scheduler -> the cron endpoint, mirroring
``halatuju-sponsor-realtime``). Idempotent + self-limiting: a funded student leaves
the fundable set immediately, and insufficient balance is skipped (retried next run).

    python manage.py auto_sponsor
"""
from django.core.management.base import BaseCommand

from apps.scholarship.standing_gift import run_standing_gifts


class Command(BaseCommand):
    help = "Allocate active standing gifts (AutoSponsor) to matching pool students."

    def handle(self, *args, **options):
        result = run_standing_gifts()
        self.stdout.write(
            f"auto-sponsor: {result['funded']} student(s) funded "
            f"from {result['students']} fundable"
        )
