"""One-off backfill: normalise each application's offer-letter reporting date into the new
sortable ``reporting_date`` column (reviewer-query S3). Idempotent — re-runnable; only writes
when the parsed date differs from what's stored. Going forward the column is kept current by
``autofill_pathway_from_offer`` on every offer (re)extraction; this seeds the existing rows.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.pathway_engine import offer_reporting_date


class Command(BaseCommand):
    help = "Backfill ScholarshipApplication.reporting_date from offer letters."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report only; no writes.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        # Only applications that actually have an offer letter.
        qs = (ScholarshipApplication.objects
              .filter(documents__doc_type='offer_letter').distinct()
              .select_related('profile'))
        updated = skipped = 0
        for app in qs:
            rd = offer_reporting_date(app)
            if rd is None or app.reporting_date == rd:
                skipped += 1
                continue
            self.stdout.write(f'  app {app.id}: {app.reporting_date} -> {rd}')
            if not dry:
                app.reporting_date = rd
                app.save(update_fields=['reporting_date'])
            updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry else ""}reporting_date backfill: {updated} updated, {skipped} unchanged/none.'))
