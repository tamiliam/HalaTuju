"""
One-time command to populate mohe_url for existing STPM courses.

Sources:
1. stpm_science_full.csv — has actual scraped URLs for ~1003 science programmes
2. Pattern generation for remaining courses (arts)

Usage:
    python manage.py populate_stpm_urls --csv-path /path/to/stpm_science_full.csv
    python manage.py populate_stpm_urls --csv-path /path/to/stpm_science_full.csv --dry-run
"""
import csv
from django.core.management.base import BaseCommand
from apps.courses.models import StpmCourse


MOHE_BASE = 'https://online.mohe.gov.my/epanduan/carianNamaProgram'


def build_mohe_url(course_id: str, stream: str) -> str:
    """Generate MOHE ePanduan URL from course_id and stream."""
    prefix = course_id[:2]
    # Science gets S, arts gets A, both defaults to S
    cat = 'A' if stream == 'arts' else 'S'
    return f'{MOHE_BASE}/{prefix}/{course_id}/{cat}/stpm'


class Command(BaseCommand):
    help = 'Populate mohe_url for STPM courses from CSV + pattern generation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-path', type=str, default='',
            help='Path to stpm_science_full.csv with scraped URLs',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would be updated without writing to DB',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        dry_run = options['dry_run']

        # Step 1: Load URLs from CSV if provided
        csv_urls = {}
        if csv_path:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # skip header
                for row in reader:
                    if len(row) >= 4 and row[3].startswith('http'):
                        course_id = row[1].strip()
                        url = row[3].strip()
                        csv_urls[course_id] = url
            self.stdout.write(f'Loaded {len(csv_urls)} URLs from CSV')

        # Step 2: Update courses
        courses = StpmCourse.objects.all()
        updated = 0
        generated = 0

        for course in courses:
            if course.mohe_url:
                continue  # already has URL

            url = csv_urls.get(course.course_id)
            if url:
                source = 'csv'
            else:
                url = build_mohe_url(course.course_id, course.stream)
                source = 'generated'
                generated += 1

            if dry_run:
                self.stdout.write(f'  [{source}] {course.course_id}: {url}')
            else:
                course.mohe_url = url
                course.save(update_fields=['mohe_url'])
            updated += 1

        action = 'Would update' if dry_run else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} {updated} courses ({updated - generated} from CSV, {generated} generated)'
        ))
