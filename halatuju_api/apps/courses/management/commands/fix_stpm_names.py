"""
One-shot management command to reformat existing StpmCourse.program_name
values to proper title case.

Usage:
    python manage.py fix_stpm_names
    python manage.py fix_stpm_names --dry-run
"""
from django.core.management.base import BaseCommand

from apps.courses.models import StpmCourse
from apps.courses.management.commands.load_stpm_data import proper_case_name


class Command(BaseCommand):
    help = 'Reformat existing StpmCourse programme names to proper title case'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print changes without saving to the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run mode — no changes will be saved.'))

        courses = StpmCourse.objects.all()
        total = courses.count()
        self.stdout.write(f'Processing {total} courses...')

        to_update = []
        changed = 0

        for course in courses.iterator():
            new_name = proper_case_name(course.program_name)
            if new_name != course.program_name:
                if dry_run:
                    self.stdout.write(f'  {course.program_name!r}')
                    self.stdout.write(f'    -> {new_name!r}')
                else:
                    course.program_name = new_name
                    to_update.append(course)
                changed += 1

        if not dry_run and to_update:
            StpmCourse.objects.bulk_update(to_update, ['program_name'])
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done: updated {changed} of {total} programme names.'
                )
            )
        elif dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Dry-run complete: {changed} of {total} would be updated.'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('All names already properly cased.'))
