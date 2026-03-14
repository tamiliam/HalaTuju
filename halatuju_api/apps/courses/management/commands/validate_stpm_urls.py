"""
Validate MOHE URLs for STPM courses using Selenium.

Renders each URL in a headless browser and checks whether MOHE actually
lists the programme (looks for "daripada 0 carian" or "Tiada Maklumat
Program" to detect dead links).

HTTP status codes are useless here — MOHE returns 200/302 for every URL
regardless of whether the course exists.

Usage:
    python manage.py validate_stpm_urls
    python manage.py validate_stpm_urls --fix       # clear dead URLs
    python manage.py validate_stpm_urls --limit 50   # check first 50 only

Requires: pip install selenium (+ Chrome/Chromium installed)
"""
from django.core.management.base import BaseCommand
from apps.courses.models import StpmCourse


class Command(BaseCommand):
    help = 'Validate MOHE URLs for STPM courses (Selenium-based)'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true', help='Clear dead URLs')
        parser.add_argument('--limit', type=int, default=0, help='Check only first N courses')
        parser.add_argument('--delay', type=float, default=3.0, help='Seconds to wait for page render')

    def handle(self, *args, **options):
        fix = options['fix']
        limit = options['limit']
        delay = options['delay']

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'selenium is required: pip install selenium'
            ))
            return

        courses = StpmCourse.objects.exclude(mohe_url='').exclude(mohe_url__isnull=True)
        if limit:
            courses = courses[:limit]

        total = len(courses) if limit else courses.count()
        self.stdout.write(f'Checking {total} URLs (Selenium, {delay}s render wait)...')

        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        driver = webdriver.Chrome(options=chrome_options)

        import time
        dead = []
        alive = 0
        errors = []

        try:
            for i, course in enumerate(courses, 1):
                try:
                    driver.get(course.mohe_url)
                    time.sleep(delay)

                    body = driver.find_element(By.TAG_NAME, 'body')
                    text = body.text

                    if 'daripada 0 carian' in text or 'Tiada Maklumat Program' in text:
                        dead.append((course.course_id, course.course_name, course.mohe_url))
                        self.stdout.write(self.style.WARNING(
                            f'  DEAD: {course.course_id} — {course.program_name}'
                        ))
                    else:
                        alive += 1

                except Exception as e:
                    errors.append((course.course_id, course.mohe_url, str(e)))

                if i % 25 == 0:
                    self.stdout.write(f'  Checked {i}/{total}...')
        finally:
            driver.quit()

        self.stdout.write(f'\nAlive: {alive}')
        self.stdout.write(f'Dead:  {len(dead)}')
        if errors:
            self.stdout.write(f'Errors: {len(errors)}')

        if dead:
            self.stdout.write(self.style.WARNING('\n--- Dead URLs ---'))
            for cid, name, url in dead:
                self.stdout.write(f'  {cid}: {name}')
                self.stdout.write(f'         {url}')

            if fix:
                ids = [cid for cid, _, _ in dead]
                StpmCourse.objects.filter(course_id__in=ids).update(mohe_url='')
                self.stdout.write(self.style.SUCCESS(f'Cleared {len(dead)} dead URLs'))

        if errors:
            self.stdout.write(self.style.WARNING('\n--- Errors ---'))
            for cid, url, err in errors:
                self.stdout.write(f'  {cid}: {err}')
