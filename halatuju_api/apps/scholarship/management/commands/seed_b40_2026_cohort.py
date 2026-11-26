"""
Create the live BrightPath Bursary Programme cohort for 2026 (idempotent).

The shortlisting thresholds were settled 2026-05-24: SPM 4 A- + 5 B+, STPM PNGK 2.9,
household line RM5,860, per-capita line RM1,584; reveal delays 2h/48h (model defaults).
⚠ Criteria Sprint 3b: the model no longer has default bars (a blank is no rule), so this
command states every bar itself and stores the criteria tree at create time
(`criteria_new.stamp_new`). The thresholds echoed below are read from that tree. Re-running is a
no-op (get_or_create on the unique code). Pass --open / --closed to control
whether it accepts applications immediately (default: open).

    python manage.py seed_b40_2026_cohort [--closed]
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.scholarship import criteria_new
from apps.scholarship.criteria_read import column_values
from apps.scholarship.models import ScholarshipCohort

CODE = 'b40-2026'   # internal slug — unchanged by the BrightPath rename (never shown to users)
DISPLAY_NAME = 'BrightPath Bursary Programme 2026'   # the {programme} value in emails/UI
#: The bars this command has always created the intake with (the model defaults until Sprint 3b).
SETTLED_BARS = {'min_spm_a_count': 4, 'min_spm_bplus_count': 5, 'min_stpm_pngk': 2.9,
                'income_ceiling': 5860, 'per_capita_ceiling': 1584}


class Command(BaseCommand):
    help = "Create the b40-2026 cohort (idempotent). States its own thresholds and stores its criteria tree."

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
        cohort = ScholarshipCohort.objects.filter(code=CODE).first()
        created = cohort is None
        if created:
            cohort = ScholarshipCohort(
                code=CODE, name=DISPLAY_NAME, year=2026, is_active=True, is_open=is_open,
                # The 2026-05-24 bars, stated (they were model defaults until criteria Sprint 3b).
                **SETTLED_BARS)
            problems = criteria_new.stamp_new(cohort)
            if problems:
                raise CommandError('criteria tree refused: ' + '; '.join(problems))
            cohort.save(force_insert=True)

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

        # Echo the thresholds the engine will use, for verification - read from the criteria
        # tree the gate reads (`criteria_read.column_values`), not the old columns (TD-772).
        bars = column_values(cohort)
        self.stdout.write(
            "Thresholds: "
            f"min_spm_a_count={bars['min_spm_a_count']}, min_spm_bplus_count={bars['min_spm_bplus_count']}, "
            f"min_spm_credit_count={bars['min_spm_credit_count']}, "
            f"min_stpm_pngk={bars['min_stpm_pngk']}, per_capita_ceiling=RM{bars['per_capita_ceiling']}, "
            f"income_ceiling=RM{bars['income_ceiling']}, "
            f"success_delay_hours={cohort.success_delay_hours}, decline_delay_hours={cohort.decline_delay_hours}"
        )
