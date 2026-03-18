"""
Management command to audit data completeness.

Usage:
    python manage.py audit_data

Reports gaps across courses, institutions, requirements, and offerings.
"""
from django.core.management.base import BaseCommand
from apps.courses.models import (
    Course, CourseRequirement, CourseTag, Institution, CourseInstitution,
    StpmCourse, StpmRequirement,
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
        self.audit_stpm_courses()
        self.audit_stpm_requirements()
        self.audit_stpm_careers()
        self.stdout.write(self.style.SUCCESS('\nAudit complete.'))

    def audit_courses(self):
        total = Course.objects.count()
        no_desc = Course.objects.filter(description='').count()
        no_level = Course.objects.filter(level='').count()
        no_dept = Course.objects.filter(department='').count()
        no_field = Course.objects.filter(field='').count()
        no_sem = Course.objects.filter(semesters__isnull=True).count()

        self.stdout.write(f'COURSES: {total} total')
        self.stdout.write(f'  Missing description:    {no_desc}')
        self.stdout.write(f'  Missing level:          {no_level}')
        self.stdout.write(f'  Missing department:     {no_dept}')
        self.stdout.write(f'  Missing field:          {no_field}')
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

    def audit_stpm_courses(self):
        total = StpmCourse.objects.count()
        active = StpmCourse.objects.filter(is_active=True).count()
        inactive = total - active
        no_desc = StpmCourse.objects.filter(description='').count()
        no_headline = StpmCourse.objects.filter(headline='').count()
        no_mohe = StpmCourse.objects.filter(mohe_url='').count()
        no_merit = StpmCourse.objects.filter(merit_score__isnull=True).count()
        no_institution = StpmCourse.objects.filter(institution__isnull=True).count()
        no_careers = StpmCourse.objects.filter(career_occupations__isnull=True).distinct().count()

        self.stdout.write(f'\nSTPM COURSES: {total} total ({active} active, {inactive} inactive)')
        self.stdout.write(f'  Missing description:    {no_desc}')
        self.stdout.write(f'  Missing headline:       {no_headline}')
        self.stdout.write(f'  Missing MOHE URL:       {no_mohe}')
        self.stdout.write(f'  Missing merit score:    {no_merit}')
        self.stdout.write(f'  Missing institution FK: {no_institution}')
        self.stdout.write(f'  Missing career links:   {no_careers}')

    def audit_stpm_requirements(self):
        total_courses = StpmCourse.objects.count()
        total_reqs = StpmRequirement.objects.count()
        orphaned = total_courses - total_reqs

        self.stdout.write(f'\nSTPM REQUIREMENTS: {total_reqs} / {total_courses} courses covered')
        self.stdout.write(f'  Courses without requirements: {orphaned}')

        if orphaned > 0:
            req_ids = set(StpmRequirement.objects.values_list('course_id', flat=True))
            all_ids = set(StpmCourse.objects.values_list('course_id', flat=True))
            missing = list(all_ids - req_ids)[:5]
            self.stdout.write(f'  Sample missing: {missing}')

        # Subject group coverage
        has_stpm_group = StpmRequirement.objects.exclude(
            stpm_subject_group__isnull=True
        ).count()
        has_spm_group = StpmRequirement.objects.exclude(
            spm_subject_group__isnull=True
        ).count()
        self.stdout.write(f'  With STPM subject groups: {has_stpm_group}')
        self.stdout.write(f'  With SPM subject groups:  {has_spm_group}')

    def audit_stpm_careers(self):
        total_stpm = StpmCourse.objects.count()
        with_careers = StpmCourse.objects.filter(
            career_occupations__isnull=False
        ).distinct().count()
        without = total_stpm - with_careers

        total_links = StpmCourse.career_occupations.through.objects.count()

        self.stdout.write(f'\nSTPM CAREER MAPPINGS: {with_careers} / {total_stpm} courses mapped')
        self.stdout.write(f'  Courses without career links: {without}')
        self.stdout.write(f'  Total M2M links: {total_links}')
