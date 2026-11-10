"""
Compare scraped MOHE data with DB and sync changes.

Reads the CSV output from scrape_mohe_stpm and:
1. Reports new programmes (in MOHE but not in DB)
2. Reports removed programmes (in DB but not in MOHE)
3. Reports changed merit scores
4. Updates mohe_url for all matched courses
5. Deactivates removed courses / reactivates returned courses

Usage:
    python manage.py sync_stpm_mohe --csv data/stpm/mohe_latest.csv
    python manage.py sync_stpm_mohe --csv data/stpm/mohe_latest.csv --apply
"""
import csv
from django.core.management.base import BaseCommand, CommandError
from apps.courses.models import StpmCourse

# Safety guard for --apply: a partial/failed scrape (e.g. MOHE redesigns their DOM
# and few/zero cards parse) makes most of the catalogue look "removed", which would
# deactivate it and empty the student-facing site. Refuse a mass deactivation on a
# non-trivial catalogue unless --force.
GUARD_MIN_ACTIVE = 50           # below this the catalogue is too small to guard (tests / fresh DB)
MAX_DEACTIVATE_FRACTION = 0.10  # abort --apply if it would deactivate more than this share of active courses


class Command(BaseCommand):
    help = 'Sync STPM course data from scraped MOHE CSV'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, required=True, help='Path to scraped CSV')
        parser.add_argument('--apply', action='store_true', help='Apply changes (default: report only)')
        parser.add_argument(
            '--force', action='store_true',
            help='Override the mass-deactivation safety guard (only after verifying a large removal is real).')

    def handle(self, *args, **options):
        scraped = self._load_scraped(options['csv'])

        # Load DB data (all courses, including inactive)
        db_courses = {c.course_id: c for c in StpmCourse.objects.all()}
        db_ids = set(db_courses.keys())
        mohe_ids = set(scraped.keys())

        new_ids = mohe_ids - db_ids
        removed_ids = db_ids - mohe_ids
        common_ids = db_ids & mohe_ids

        # Courses currently active that the scrape no longer lists — the deactivation set.
        active_removed = [cid for cid in removed_ids if db_courses[cid].is_active]
        active_before = sum(1 for c in db_courses.values() if c.is_active)
        reactivate_ids = [cid for cid in common_ids if not db_courses[cid].is_active]

        self._report_counts(mohe_ids, db_ids, common_ids)
        self._report_new(new_ids, scraped)
        self._report_removed(removed_ids, active_removed, db_courses)
        self._report_reactivate(reactivate_ids, db_courses)
        merit_changes, url_updates = self._compare_common(common_ids, scraped, db_courses)
        self._report_merit_and_urls(merit_changes, url_updates)

        if not options['apply']:
            self.stdout.write(self.style.NOTICE(
                '\nDry run. Use --apply to write changes to DB.'
            ))
            return

        self._check_deactivation_guard(
            options['force'], active_before, active_removed, len(mohe_ids))
        self._apply_url_updates(common_ids, scraped, db_courses)
        self._apply_activation_changes(active_removed, reactivate_ids)
        self._report_unapplied(merit_changes, new_ids)

    # --- load -------------------------------------------------------------

    @staticmethod
    def _load_scraped(csv_path):
        scraped = {}
        with open(csv_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                cid = row['course_id'].strip()
                if cid:
                    scraped[cid] = row
        return scraped

    # --- report -----------------------------------------------------------

    def _report_counts(self, mohe_ids, db_ids, common_ids):
        inactive_count = StpmCourse.objects.filter(is_active=False).count()
        self.stdout.write('\n=== STPM MOHE Sync Report ===')
        self.stdout.write(f'MOHE programmes: {len(mohe_ids)}')
        self.stdout.write(f'DB courses:      {len(db_ids)}')
        self.stdout.write(f'Matched:         {len(common_ids)}')
        self.stdout.write(f'Currently inactive: {inactive_count}')

    def _report_new(self, new_ids, scraped):
        if not new_ids:
            return
        self.stdout.write(self.style.WARNING(f'\n--- NEW ({len(new_ids)}) ---'))
        for cid in sorted(new_ids):
            row = scraped[cid]
            self.stdout.write(f'  + {cid}: {row["course_name"]} ({row["university"]})')

    def _report_removed(self, removed_ids, active_removed, db_courses):
        """Removed programmes (in DB but not in MOHE)."""
        if not removed_ids:
            return
        already_inactive = [cid for cid in removed_ids if not db_courses[cid].is_active]

        if active_removed:
            self.stdout.write(self.style.ERROR(
                f'\n--- REMOVED — will deactivate ({len(active_removed)}) ---'
            ))
            for cid in sorted(active_removed):
                course = db_courses[cid]
                self.stdout.write(f'  - {cid}: {course.course_name} ({course.university})')

        if already_inactive:
            self.stdout.write(
                f'\n  ({len(already_inactive)} already inactive, unchanged)'
            )

    def _report_reactivate(self, reactivate_ids, db_courses):
        """Reactivation candidates (in MOHE and in DB but currently inactive)."""
        if not reactivate_ids:
            return
        self.stdout.write(self.style.SUCCESS(
            f'\n--- REACTIVATE ({len(reactivate_ids)}) ---'
        ))
        for cid in sorted(reactivate_ids):
            course = db_courses[cid]
            self.stdout.write(f'  ↑ {cid}: {course.course_name} ({course.university})')

    @staticmethod
    def _compare_common(common_ids, scraped, db_courses):
        """Merit changes and the count of mohe_url updates over the matched courses."""
        merit_changes = []
        url_updates = 0
        for cid in common_ids:
            row = scraped[cid]
            course = db_courses[cid]

            new_merit = None
            if row.get('merit'):
                try:
                    new_merit = float(row['merit'])
                except ValueError:
                    pass

            if new_merit is not None and course.merit_score is not None:
                if abs(new_merit - course.merit_score) > 0.01:
                    merit_changes.append((cid, course.merit_score, new_merit))

            if row.get('mohe_url') and row['mohe_url'] != course.mohe_url:
                url_updates += 1
        return merit_changes, url_updates

    def _report_merit_and_urls(self, merit_changes, url_updates):
        if merit_changes:
            self.stdout.write(self.style.WARNING(f'\n--- MERIT CHANGES ({len(merit_changes)}) ---'))
            for cid, old, new in sorted(merit_changes):
                self.stdout.write(f'  ~ {cid}: {old:.2f}% -> {new:.2f}%')

        self.stdout.write(f'\nURL updates needed: {url_updates}')

    # --- apply ------------------------------------------------------------

    @staticmethod
    def _check_deactivation_guard(force, active_before, active_removed, mohe_count):
        """SAFETY GUARD — block a catalogue-wiping apply from a partial/failed scrape.

        If applying would deactivate more than MAX_DEACTIVATE_FRACTION of a non-trivial
        live catalogue, abort: this is almost always a bad scrape, not that many real
        removals. --force overrides once the operator has verified the removals are real.
        """
        if not force and active_before >= GUARD_MIN_ACTIVE and active_removed:
            frac = len(active_removed) / active_before
            if frac > MAX_DEACTIVATE_FRACTION:
                raise CommandError(
                    f'Refusing to apply: this would deactivate {len(active_removed)} of '
                    f'{active_before} active courses ({frac:.0%}), from a CSV of only '
                    f'{mohe_count} programmes. That looks like a partial or failed scrape '
                    f'(e.g. a MOHE site change), not real removals. Re-scrape and verify the '
                    f'count, or pass --force if the removals are genuinely correct.'
                )

    def _apply_url_updates(self, common_ids, scraped, db_courses):
        updated = 0
        for cid in common_ids:
            row = scraped[cid]
            course = db_courses[cid]
            if row.get('mohe_url') and row['mohe_url'] != course.mohe_url:
                course.mohe_url = row['mohe_url']
                course.save(update_fields=['mohe_url'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'\nApplied: {updated} URL updates'))

    def _apply_activation_changes(self, active_removed, reactivate_ids):
        if active_removed:
            deactivated = StpmCourse.objects.filter(
                course_id__in=active_removed
            ).update(is_active=False)
            self.stdout.write(self.style.WARNING(
                f'Deactivated {deactivated} removed courses'
            ))

        if reactivate_ids:
            reactivated = StpmCourse.objects.filter(
                course_id__in=reactivate_ids
            ).update(is_active=True)
            self.stdout.write(self.style.SUCCESS(
                f'Reactivated {reactivated} returned courses'
            ))

    def _report_unapplied(self, merit_changes, new_ids):
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
