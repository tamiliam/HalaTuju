"""
Create the live BrightPath Bursary Programme cohort for 2026 (idempotent).

The shortlisting thresholds are the model defaults (settled 2026-05-24): SPM
4 A- + 5 B+, STPM PNGK 2.9, per-capita ceiling RM1,584, reveal delays 2h/48h —
so this only sets code / name / year / income_ceiling reference. Re-running is a
no-op (get_or_create on the unique code). Pass --open / --closed to control
whether it accepts applications immediately (default: open).

    python manage.py seed_b40_2026_cohort [--closed]
"""
from django.core.management.base import BaseCommand
from django.db import connection

from apps.scholarship.models import ScholarshipCohort

CODE = 'b40-2026'   # internal slug — unchanged by the BrightPath rename (never shown to users)
DISPLAY_NAME = 'BrightPath Bursary Programme 2026'   # the {programme} value in emails/UI


class Command(BaseCommand):
    help = "Create the b40-2026 cohort (idempotent). Thresholds come from model defaults."

    def add_arguments(self, parser):
        parser.add_argument(
            '--closed', action='store_true',
            help='Create the cohort NOT accepting applications yet (is_open=False); flip it open later.',
        )

    def handle(self, *args, **options):
        db = connection.settings_dict
        # Transparency: which database are we acting on? (management-command lesson)
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        is_open = not options['closed']
        cohort, created = ScholarshipCohort.objects.get_or_create(
            code=CODE,
            defaults={
                'name': DISPLAY_NAME,
                'year': 2026,
                'is_active': True,
                'is_open': is_open,
                # income_ceiling is the B40 reference figure; the income gate itself
                # uses per_capita_ceiling (a model default). All thresholds default.
                'income_ceiling': 5860,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created cohort '{CODE}' (is_open={cohort.is_open})"))
        elif cohort.name != DISPLAY_NAME:
            old = cohort.name
            cohort.name = DISPLAY_NAME       # idempotent name sync (the BrightPath rename)
            cohort.save(update_fields=['name'])
            self.stdout.write(self.style.SUCCESS(f"Renamed cohort '{CODE}': '{old}' → '{DISPLAY_NAME}'"))
        else:
            self.stdout.write(self.style.WARNING(
                f"Cohort '{CODE}' already exists (is_open={cohort.is_open}) — name already current"
            ))

        # Echo the thresholds the engine will use, for verification.
        self.stdout.write(
            "Thresholds: "
            f"min_spm_a_count={cohort.min_spm_a_count}, min_spm_bplus_count={cohort.min_spm_bplus_count}, "
            f"min_stpm_pngk={cohort.min_stpm_pngk}, per_capita_ceiling=RM{cohort.per_capita_ceiling}, "
            f"income_ceiling=RM{cohort.income_ceiling}, "
            f"success_delay_hours={cohort.success_delay_hours}, decline_delay_hours={cohort.decline_delay_hours}"
        )
