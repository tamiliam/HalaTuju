"""
Compare scraped MOHE data with DB and sync changes.

Reads the CSV output from scrape_mohe_stpm and:
1. Reports new programmes (in MOHE but not in DB)
2. Reports removed programmes (in DB but not in MOHE)
3. Reports changed merit scores
4. Updates mohe_url for all matched courses
5. Optionally applies merit score updates

Usage:
    python manage.py sync_stpm_mohe --csv data/stpm/mohe_latest.csv
    python manage.py sync_stpm_mohe --csv data/stpm/mohe_latest.csv --apply
"""
import csv
from django.core.management.base import BaseCommand
from apps.courses.models import StpmCourse


class Command(BaseCommand):
    help = 'Sync STPM course data from scraped MOHE CSV'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, required=True, help='Path to scraped CSV')
        parser.add_argument('--apply', action='store_true', help='Apply changes (default: report only)')

    def handle(self, *args, **options):
        csv_path = options['csv']
        apply = options['apply']

        # Load scraped data
        scraped = {}
        with open(csv_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                cid = row['course_id'].strip()
                if cid:
                    scraped[cid] = row

        # Load DB data
        db_courses = {c.course_id: c for c in StpmCourse.objects.all()}

        db_ids = set(db_courses.keys())
        mohe_ids = set(scraped.keys())

        # --- Report ---
        new_ids = mohe_ids - db_ids
        removed_ids = db_ids - mohe_ids
        common_ids = db_ids & mohe_ids

        self.stdout.write(f'\n=== STPM MOHE Sync Report ===')
        self.stdout.write(f'MOHE programmes: {len(mohe_ids)}')
        self.stdout.write(f'DB courses:      {len(db_ids)}')
        self.stdout.write(f'Matched:         {len(common_ids)}')

        # New programmes
        if new_ids:
            self.stdout.write(self.style.WARNING(f'\n--- NEW ({len(new_ids)}) ---'))
            for cid in sorted(new_ids):
                row = scraped[cid]
                self.stdout.write(f'  + {cid}: {row["course_name"]} ({row["university"]})')

        # Removed programmes
        if removed_ids:
            self.stdout.write(self.style.ERROR(f'\n--- REMOVED ({len(removed_ids)}) ---'))
            for cid in sorted(removed_ids):
                course = db_courses[cid]
                self.stdout.write(f'  - {cid}: {course.course_name} ({course.university})')

        # Merit changes
        merit_changes = []
        url_updates = 0
        for cid in common_ids:
            row = scraped[cid]
            course = db_courses[cid]

            # Check merit change
            new_merit = None
            if row.get('merit'):
                try:
                    new_merit = float(row['merit'])
                except ValueError:
                    pass

            if new_merit is not None and course.merit_score is not None:
                if abs(new_merit - course.merit_score) > 0.01:
                    merit_changes.append((cid, course.merit_score, new_merit))

            # Check URL update needed
            if row.get('mohe_url') and row['mohe_url'] != course.mohe_url:
                url_updates += 1

        if merit_changes:
            self.stdout.write(self.style.WARNING(f'\n--- MERIT CHANGES ({len(merit_changes)}) ---'))
            for cid, old, new in sorted(merit_changes):
                self.stdout.write(f'  ~ {cid}: {old:.2f}% -> {new:.2f}%')

        self.stdout.write(f'\nURL updates needed: {url_updates}')

        # --- Apply ---
        if not apply:
            self.stdout.write(self.style.NOTICE(
                '\nDry run. Use --apply to write changes to DB.'
            ))
            return

        # Apply URL updates
        updated = 0
        for cid in common_ids:
            row = scraped[cid]
            course = db_courses[cid]
            changed = False

            if row.get('mohe_url') and row['mohe_url'] != course.mohe_url:
                course.mohe_url = row['mohe_url']
                changed = True

            if changed:
                course.save(update_fields=['mohe_url'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'\nApplied: {updated} URL updates'))

        if merit_changes:
            self.stdout.write(self.style.WARNING(
                f'{len(merit_changes)} merit changes detected but NOT auto-applied. '
                'Review the report above and update manually or extend this command.'
            ))

        if new_ids:
            self.stdout.write(self.style.WARNING(
                f'{len(new_ids)} new programmes detected. '
                'These need manual review — requirements must be parsed before adding to DB.'
            ))

        if removed_ids:
            self.stdout.write(self.style.WARNING(
                f'{len(removed_ids)} programmes no longer on MOHE. '
                'Consider marking as inactive rather than deleting.'
            ))
