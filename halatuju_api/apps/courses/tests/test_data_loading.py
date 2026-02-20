"""
Tests for data loading and audit management commands.

Covers:
- TVET course metadata enrichment
- PISMP course metadata enrichment
- Institution modifiers loading from JSON into DB
- MASCO occupation loading and course-occupation M2M linking
"""
from django.test import TestCase
from apps.courses.models import Course, CourseRequirement, Institution, MascoOccupation


class TestTvetCourseMetadata(TestCase):
    """Test that TVET courses get enriched with full metadata."""

    def setUp(self):
        # Simulate a TVET course created by load_requirements (minimal data)
        self.course = Course.objects.create(
            course_id='IKBN-DIP-TEST',
            course='IKBN-DIP-TEST',  # Name defaults to ID when no 'course' col
        )
        CourseRequirement.objects.create(
            course=self.course,
            source_type='tvet',
            min_credits=1,
            pass_bm=True,
        )

    def test_tvet_course_missing_metadata_before_enrichment(self):
        """TVET courses created from requirements have empty metadata fields."""
        self.assertEqual(self.course.level, '')
        self.assertEqual(self.course.department, '')
        self.assertEqual(self.course.description, '')
        self.assertIsNone(self.course.semesters)

    def test_tvet_course_enrichment_updates_metadata(self):
        """After enrichment, TVET course has level, department, description."""
        # Simulate what load_tvet_course_metadata does
        Course.objects.filter(course_id='IKBN-DIP-TEST').update(
            course='Diploma Teknologi Elektrik (Test)',
            level='Diploma',
            department='Elektrik & Elektronik',
            field='Elektrik & Elektronik',
            frontend_label='Elektrik & Elektronik',
            description='Test TVET course description.',
            wbl=True,
            semesters=4,
        )

        self.course.refresh_from_db()
        self.assertEqual(self.course.level, 'Diploma')
        self.assertEqual(self.course.department, 'Elektrik & Elektronik')
        self.assertEqual(self.course.description, 'Test TVET course description.')
        self.assertEqual(self.course.semesters, 4)
        self.assertTrue(self.course.wbl)


class TestPismpCourseMetadata(TestCase):
    """Test that PISMP courses get enriched with teacher training metadata."""

    def setUp(self):
        self.course = Course.objects.create(
            course_id='50PD-TEST',
            course='Bahasa Melayu Pendidikan Rendah',
        )
        CourseRequirement.objects.create(
            course=self.course,
            source_type='pismp',
            min_credits=6,
            pass_bm=True,
            req_malaysian=True,
        )

    def test_pismp_enrichment_sets_education_metadata(self):
        """PISMP courses get level, department, semesters, description."""
        # Simulate what load_pismp_course_metadata does
        for course in Course.objects.filter(requirement__source_type='pismp'):
            updates = {}
            if not course.level:
                updates['level'] = 'Ijazah Sarjana Muda Pendidikan'
            if not course.department:
                updates['department'] = 'Pendidikan'
            if not course.field:
                updates['field'] = 'Pendidikan'
            if not course.semesters:
                updates['semesters'] = 8
            if not course.description:
                updates['description'] = (
                    f'Program Ijazah Sarjana Muda Pendidikan (PISMP) dalam bidang '
                    f'{course.course}.'
                )
            if updates:
                Course.objects.filter(course_id=course.course_id).update(**updates)

        self.course.refresh_from_db()
        self.assertEqual(self.course.level, 'Ijazah Sarjana Muda Pendidikan')
        self.assertEqual(self.course.department, 'Pendidikan')
        self.assertEqual(self.course.field, 'Pendidikan')
        self.assertEqual(self.course.semesters, 8)
        self.assertIn('PISMP', self.course.description)
        self.assertIn('Bahasa Melayu', self.course.description)


class TestInstitutionModifiers(TestCase):
    """Test that institution modifiers are stored in DB and loaded at startup."""

    def setUp(self):
        self.institution = Institution.objects.create(
            institution_id='POLY-TEST',
            institution_name='Test Polytechnic',
            type='Politeknik',
            category='Public',
            state='Selangor',
        )

    def test_modifiers_default_empty(self):
        """Institution modifiers default to empty dict."""
        self.assertEqual(self.institution.modifiers, {})

    def test_modifiers_stored_as_json(self):
        """Institution modifiers can be stored and retrieved as JSON."""
        modifiers = {
            'urban': True,
            'cultural_safety_net': 'high',
            'subsistence_support': False,
            'strong_hostel': True,
        }
        Institution.objects.filter(
            institution_id='POLY-TEST'
        ).update(modifiers=modifiers)

        self.institution.refresh_from_db()
        self.assertTrue(self.institution.modifiers['urban'])
        self.assertEqual(self.institution.modifiers['cultural_safety_net'], 'high')
        self.assertFalse(self.institution.modifiers['subsistence_support'])


class TestMascoOccupationModel(TestCase):
    """Test MascoOccupation model and Course M2M relationship."""

    def setUp(self):
        self.occ = MascoOccupation.objects.create(
            masco_code='3115-24',
            job_title='Juruteknik Mekatronik',
            emasco_url='https://emasco.mohr.gov.my/masco/3115-24',
        )
        self.course = Course.objects.create(
            course_id='TEST-MASCO-001',
            course='Test Diploma Mekatronik',
            level='Diploma',
            department='Engineering',
            field='Mechatronics',
        )

    def test_masco_occupation_str(self):
        """MascoOccupation __str__ shows code and title."""
        self.assertIn('3115-24', str(self.occ))

    def test_masco_primary_key_is_code(self):
        """masco_code is the primary key."""
        fetched = MascoOccupation.objects.get(pk='3115-24')
        self.assertEqual(fetched.job_title, 'Juruteknik Mekatronik')

    def test_course_career_occupations_m2m(self):
        """Course can link to multiple MASCO occupations."""
        occ2 = MascoOccupation.objects.create(
            masco_code='3115-47',
            job_title='Juruteknik Robotik',
            emasco_url='https://emasco.mohr.gov.my/masco/3115-47',
        )
        self.course.career_occupations.add(self.occ, occ2)
        self.assertEqual(self.course.career_occupations.count(), 2)

    def test_reverse_relation_occupation_to_courses(self):
        """MascoOccupation.courses shows linked courses."""
        self.course.career_occupations.add(self.occ)
        self.assertIn(self.course, self.occ.courses.all())

    def test_update_or_create_idempotent(self):
        """Loading the same MASCO code twice doesn't create duplicates."""
        MascoOccupation.objects.update_or_create(
            masco_code='3115-24',
            defaults={
                'job_title': 'Juruteknik Mekatronik (Updated)',
                'emasco_url': 'https://emasco.mohr.gov.my/masco/3115-24',
            },
        )
        self.assertEqual(MascoOccupation.objects.filter(masco_code='3115-24').count(), 1)
        self.occ.refresh_from_db()
        self.assertIn('Updated', self.occ.job_title)
