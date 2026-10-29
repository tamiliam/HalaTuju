"""Daily 'results-overdue-flag' (student maintenance S4b): keep every funded student's result terms
up to date (`results_expectations.ensure_all` — idempotent: a term row is made once, when its term
begins) and pair accepted results with them. The "not submitted" standing and the Results overdue
filter read those rows, by date; nothing here judges a student.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import results_expectations


class Command(BaseCommand):
    help = "Make each funded student's result terms (and pair accepted results); daily."

    def handle(self, *args, **options):
        made = results_expectations.ensure_all()
        self.stdout.write(f'results terms made: {made}')
