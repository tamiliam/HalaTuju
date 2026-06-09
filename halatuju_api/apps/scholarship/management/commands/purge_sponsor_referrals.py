"""F4 — PDPA purge of unconverted sponsor-referral invitee PII.

Schedule DAILY (Cloud Scheduler → the cron endpoint, mirroring the F3 jobs). Scrubs
``invitee_email``/``invitee_name`` from still-``invited`` referrals older than 60 days
and marks them ``expired``. Idempotent.

    python manage.py purge_sponsor_referrals
"""
from django.core.management.base import BaseCommand

from apps.scholarship.referrals import purge_expired_referrals


class Command(BaseCommand):
    help = "Scrub invitee PII from unconverted sponsor referrals older than the retention window."

    def handle(self, *args, **options):
        purged = purge_expired_referrals()
        self.stdout.write(f"purge_sponsor_referrals: {purged} referral(s) expired + scrubbed")
