"""
Management command to audit data completeness.

Usage:
    python manage.py audit_data

Reports gaps across courses, institutions, requirements, and offerings.
"""
from django.core.management.base import BaseCommand
from apps.courses.models import (
    Course, CourseRequirement, CourseTag, Institution, CourseInstitution
)


class Command(BaseCommand):
    help = 'Audit data completeness and report gaps'

    def handle(self, *args, **options):
        self.stdout.write('\n=== HalaTuju Data Audit ===\n')
        self.audit_courses()
        self.audit_requirements()
        self.audit_institutions()
        self.audit_offerings()
        self.audit_tags()
        self.stdout.write(self.style.SUCCESS('\nAudit complete.'))

    def audit_courses(self):
        total = Course.objects.count()
        no_desc = Course.objects.filter(description='').count()
        no_level = Course.objects.filter(level='').count()
        no_dept = Course.objects.filter(department='').count()
        no_field = Course.objects.filter(field='').count()
        no_label = Course.objects.filter(frontend_label='').count()
        no_sem = Course.objects.filter(semesters__isnull=True).count()

        self.stdout.write(f'COURSES: {total} total')
        self.stdout.write(f'  Missing description:    {no_desc}')
        self.stdout.write(f'  Missing level:          {no_level}')
        self.stdout.write(f'  Missing department:     {no_dept}')
        self.stdout.write(f'  Missing field:          {no_field}')
        self.stdout.write(f'  Missing frontend_label: {no_label}')
        self.stdout.write(f'  Missing semesters:      {no_sem}')

        if no_level > 0:
            ids = list(Course.objects.filter(level='').values_list(
                'course_id', flat=True
            )[:5])
            self.stdout.write(f'  Sample missing level: {ids}')

    def audit_requirements(self):
        total_courses = Course.objects.count()
        total_reqs = CourseRequirement.objects.count()
        orphaned = total_courses - total_reqs

        by_source = {}
        for req in CourseRequirement.objects.values('source_type'):
            st = req['source_type']
            by_source[st] = by_source.get(st, 0) + 1

        self.stdout.write(f'\nREQUIREMENTS: {total_reqs} / {total_courses} courses covered')
        self.stdout.write(f'  Courses without requirements: {orphaned}')
        for st, count in sorted(by_source.items()):
            self.stdout.write(f'  {st}: {count}')

    def audit_institutions(self):
        total = Institution.objects.count()
        no_url = Institution.objects.filter(url='').count()
        no_addr = Institution.objects.filter(address='').count()
        no_phone = Institution.objects.filter(phone='').count()
        no_mods = Institution.objects.filter(modifiers={}).count()

        self.stdout.write(f'\nINSTITUTIONS: {total} total')
        self.stdout.write(f'  Missing URL:       {no_url}')
        self.stdout.write(f'  Missing address:   {no_addr}')
        self.stdout.write(f'  Missing phone:     {no_phone}')
        self.stdout.write(f'  Missing modifiers: {no_mods}')

    def audit_offerings(self):
        total = CourseInstitution.objects.count()
        no_link = CourseInstitution.objects.filter(hyperlink='').count()
        no_tuition = CourseInstitution.objects.filter(tuition_fee_semester='').count()
        no_allowance = CourseInstitution.objects.filter(
            monthly_allowance__isnull=True
        ).count()

        self.stdout.write(f'\nOFFERINGS: {total} total (course-institution links)')
        self.stdout.write(f'  Missing hyperlink:  {no_link}')
        self.stdout.write(f'  Missing tuition:    {no_tuition}')
        self.stdout.write(f'  Missing allowance:  {no_allowance}')

    def audit_tags(self):
        total_courses = Course.objects.count()
        total_tags = CourseTag.objects.count()
        missing = total_courses - total_tags

        self.stdout.write(f'\nTAGS: {total_tags} / {total_courses} courses tagged')
        self.stdout.write(f'  Courses without tags: {missing}')

        if missing > 0:
            tagged_ids = set(CourseTag.objects.values_list(
                'course_id', flat=True
            ))
            all_ids = set(Course.objects.values_list(
                'course_id', flat=True
            ))
            untagged = list(all_ids - tagged_ids)[:5]
            self.stdout.write(f'  Sample untagged: {untagged}')
