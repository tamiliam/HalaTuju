"""
Check 2 STEP 3 — auto-draft the sponsor profile for applications that are ready for
assignment (all clarify queries answered OR the SLA window lapsed) and have no profile
yet. Gated behind ``CHECK2_AUTO_GENERATE`` (default off): it makes billable Gemini
calls, so it stays a manual admin action until deliberately switched on.

Schedule DAILY (Cloud Scheduler -> the cron endpoint) once enabled.

    python manage.py autogenerate_profiles
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from apps.scholarship.services import autogenerate_ready_profiles


class Command(BaseCommand):
    help = "Auto-draft sponsor profiles for ready applications (Check 2 STEP 3; flag-gated)."

    def handle(self, *args, **options):
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")
        if not getattr(settings, 'CHECK2_AUTO_GENERATE', False):
            self.stdout.write(self.style.WARNING(
                'CHECK2_AUTO_GENERATE is off — nothing generated. Set it to enable.'))
            return
        result = autogenerate_ready_profiles()
        self.stdout.write(self.style.SUCCESS(f"Profiles auto-generated: {result['generated']}"))
