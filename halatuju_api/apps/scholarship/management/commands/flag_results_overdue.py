"""Daily 'results-overdue-flag' (student maintenance S4b).

1. Keep every funded student's result terms up to date (`results_expectations.ensure_all` —
   idempotent: a term row is made once, when its term begins) and pair accepted results with them.
   The "not submitted" standing and the Results overdue filter read those rows, by date.
2. With `MAINTENANCE_REMINDERS_ENABLED` on: flag each term newly past its due date AND the grace —
   one `results_overdue` line on her file and one email (`flag_overdue`, stamped, so once per term).
"""
from django.core.management.base import BaseCommand

from apps.scholarship import results_expectations


class Command(BaseCommand):
    help = "Make each funded student's result terms; flag (and tell) a student whose result is overdue."

    def handle(self, *args, **options):
        made = results_expectations.ensure_all()
        flagged = results_expectations.flag_overdue()
        self.stdout.write(f'results terms made: {made}; overdue flagged: {flagged}')
