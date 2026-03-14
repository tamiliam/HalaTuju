"""
Validate MOHE URLs for STPM courses.

Checks each stored mohe_url and reports dead links.

Usage:
    python manage.py validate_stpm_urls
    python manage.py validate_stpm_urls --fix  # clear dead URLs
"""
import httpx
from django.core.management.base import BaseCommand
from apps.courses.models import StpmCourse


class Command(BaseCommand):
    help = 'Validate MOHE URLs for STPM courses'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true', help='Clear dead URLs')
        parser.add_argument('--timeout', type=int, default=10, help='Request timeout in seconds')

    def handle(self, *args, **options):
        fix = options['fix']
        timeout = options['timeout']

        courses = StpmCourse.objects.exclude(mohe_url='').exclude(mohe_url__isnull=True)
        total = courses.count()
        self.stdout.write(f'Checking {total} URLs...')

        dead = []
        alive = 0

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            for i, course in enumerate(courses, 1):
                try:
                    resp = client.head(course.mohe_url)
                    if resp.status_code >= 400:
                        dead.append((course.course_id, course.mohe_url, resp.status_code))
                    else:
                        alive += 1
                except httpx.RequestError as e:
                    dead.append((course.course_id, course.mohe_url, str(e)))

                if i % 50 == 0:
                    self.stdout.write(f'  Checked {i}/{total}...')

        self.stdout.write(f'\nAlive: {alive}')
        self.stdout.write(f'Dead:  {len(dead)}')

        if dead:
            self.stdout.write(self.style.WARNING('\n--- Dead URLs ---'))
            for cid, url, status in dead:
                self.stdout.write(f'  {cid}: {status} — {url}')

            if fix:
                for cid, _, _ in dead:
                    StpmCourse.objects.filter(course_id=cid).update(mohe_url='')
                self.stdout.write(self.style.SUCCESS(f'Cleared {len(dead)} dead URLs'))
