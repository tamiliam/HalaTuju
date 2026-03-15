"""
Tests for course API endpoints.

Covers:
- POST /api/v1/eligibility/check/ — eligibility engine via API
- GET /api/v1/courses/ — course listing
- GET /api/v1/courses/<id>/ — course detail
- GET /api/v1/institutions/ — institution listing
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.courses.tests.conftest import load_requirements_df


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestEligibilityEndpoint(TestCase):
    """Test the eligibility check API endpoint."""
    fixtures = ['courses', 'requirements']

    @classmethod
    def setUpClass(cls):
        """Load DB fixtures into the app config's DataFrame."""
        super().setUpClass()
        load_requirements_df()

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/eligibility/check/'

    def test_perfect_student_returns_courses(self):
        """A student with all A+ grades should get many eligible courses."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+'
            },
            'gender': 'male',
            'nationality': 'malaysian',
            'colorblind': False,
            'disability': False,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('eligible_courses', data)
        self.assertIn('total_count', data)
        self.assertIn('stats', data)
        # Perfect student should get many courses
        self.assertGreater(data['total_count'], 100)

    def test_empty_grades_returns_few_courses(self):
        """A student with no grades (The Ghost) should get very few courses."""
        response = self.client.post(self.url, {
            'grades': {},
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Ghost student gets some 3m_only courses
        self.assertLess(data['total_count'], 50)

    def test_frontend_grade_keys_accepted(self):
        """Frontend sends engine keys (bm, eng, math) now."""
        response = self.client.post(self.url, {
            'grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()['total_count'], 0)

    def test_engine_grade_keys_accepted(self):
        """Engine-format keys (bm, eng, math) should also work."""
        response = self.client.post(self.url, {
            'grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            'gender': 'Lelaki',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()['total_count'], 0)

    def test_frontend_and_engine_keys_return_same_count(self):
        """Same grades via frontend or engine keys should return identical results."""
        frontend_response = self.client.post(self.url, {
            'grades': {'bm': 'A', 'eng': 'B+', 'hist': 'C', 'math': 'A'},
            'gender': 'male',
        }, format='json')

        engine_response = self.client.post(self.url, {
            'grades': {'bm': 'A', 'eng': 'B+', 'hist': 'C', 'math': 'A'},
            'gender': 'Lelaki',
        }, format='json')

        self.assertEqual(frontend_response.status_code, 200)
        self.assertEqual(engine_response.status_code, 200)
        self.assertEqual(
            frontend_response.json()['total_count'],
            engine_response.json()['total_count']
        )

    def test_response_has_course_details(self):
        """Each eligible course should have expected fields."""
        response = self.client.post(self.url, {
            'grades': {'bm': 'A', 'math': 'A'},
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        self.assertGreater(len(courses), 0)
        course = courses[0]
        self.assertIn('course_id', course)
        self.assertIn('course_name', course)
        self.assertIn('source_type', course)

    def test_stats_breakdown(self):
        """Stats should break down by source_type (poly, tvet, ua)."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+'
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        stats = response.json()['stats']
        # Perfect student should qualify for all source types
        self.assertIn('poly', stats)
        self.assertIn('tvet', stats)

    def test_missing_grades_returns_400(self):
        """Request without grades field should return 400."""
        response = self.client.post(self.url, {
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_non_citizen_gets_fewer_courses(self):
        """Non-Malaysian should be excluded from Malaysian-only courses."""
        citizen_response = self.client.post(self.url, {
            'grades': {'bm': 'A', 'math': 'A'},
            'gender': 'male',
            'nationality': 'malaysian',
        }, format='json')

        non_citizen_response = self.client.post(self.url, {
            'grades': {'bm': 'A', 'math': 'A'},
            'gender': 'male',
            'nationality': 'non_malaysian',
        }, format='json')

        self.assertEqual(citizen_response.status_code, 200)
        self.assertEqual(non_citizen_response.status_code, 200)
        self.assertGreaterEqual(
            citizen_response.json()['total_count'],
            non_citizen_response.json()['total_count']
        )

    def test_colorblind_gets_fewer_courses(self):
        """Colorblind student excluded from no_colorblind courses."""
        normal_response = self.client.post(self.url, {
            'grades': {'bm': 'A', 'math': 'A', 'sci': 'A'},
            'gender': 'male',
            'colorblind': False,
        }, format='json')

        colorblind_response = self.client.post(self.url, {
            'grades': {'bm': 'A', 'math': 'A', 'sci': 'A'},
            'gender': 'male',
            'colorblind': True,
        }, format='json')

        self.assertEqual(normal_response.status_code, 200)
        self.assertEqual(colorblind_response.status_code, 200)
        self.assertGreaterEqual(
            normal_response.json()['total_count'],
            colorblind_response.json()['total_count']
        )

    def test_eligibility_merit_labels_present(self):
        """Each eligible course should include merit traffic light fields."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+'
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        self.assertGreater(len(courses), 0)

        for course in courses:
            # All courses must have the merit fields
            self.assertIn('student_merit', course)
            self.assertIn('merit_label', course)
            self.assertIn('merit_color', course)
            self.assertIsInstance(course['student_merit'], (int, float))

            if course['source_type'] == 'tvet':
                # TVET has no merit data
                self.assertIsNone(course['merit_label'])
                self.assertIsNone(course['merit_color'])
            elif course['source_type'] in ('matric', 'stpm'):
                # Matric/STPM use their own merit system (no merit_color)
                if course['merit_cutoff']:
                    self.assertIn(course['merit_label'], ['High', 'Fair', 'Low'])
            elif course['merit_cutoff']:
                # Poly/UA with cutoff should have a label
                self.assertIn(course['merit_label'], ['High', 'Fair', 'Low'])
                self.assertIsNotNone(course['merit_color'])

    def test_eligibility_merit_high_for_perfect_student(self):
        """Perfect student (all A+) should get 'High' merit for all poly courses with cutoffs."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+', 'bio': 'A+',
                'addmath': 'A+',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']

        poly_with_cutoff = [
            c for c in courses
            if c['source_type'] == 'poly' and c['merit_cutoff']
        ]
        # Perfect student should have poly courses with cutoffs
        self.assertGreater(len(poly_with_cutoff), 0)

        for course in poly_with_cutoff:
            self.assertEqual(
                course['merit_label'], 'High',
                f"Perfect student should get 'High' for {course['course_id']} "
                f"(cutoff={course['merit_cutoff']}, merit={course['student_merit']})"
            )

    # --- PISMP Integration Tests ---

    def test_pismp_perfect_student_eligible(self):
        """Perfect student (all A+) should qualify for PISMP courses."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+', 'bio': 'A+',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        pismp = [c for c in courses if c['source_type'] == 'pismp']
        self.assertGreater(len(pismp), 0, "Perfect student should qualify for PISMP courses")

    def test_pismp_weak_student_excluded(self):
        """Student with no A grades should NOT qualify for any PISMP courses."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C',
                'sci': 'C',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        pismp = [c for c in courses if c['source_type'] == 'pismp']
        self.assertEqual(len(pismp), 0, "Student with only C grades should not qualify for PISMP")

    def test_pismp_borderline_student(self):
        """Student with exactly 5 A- grades should qualify for generic PISMP (5 Cemerlang)."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A-', 'eng': 'A-', 'hist': 'A-', 'math': 'A-',
                'sci': 'A-', 'phy': 'C', 'chem': 'C',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        pismp = [c for c in courses if c['source_type'] == 'pismp']
        self.assertGreater(len(pismp), 0, "Student with 5 A- should qualify for generic PISMP")

    def test_pismp_four_a_excluded(self):
        """Student with only 4 A grades should NOT qualify for PISMP (need 5 Cemerlang)."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A',
                'sci': 'C', 'phy': 'C', 'chem': 'C',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        pismp = [c for c in courses if c['source_type'] == 'pismp']
        self.assertEqual(len(pismp), 0, "Student with only 4 A grades should not qualify for PISMP")

    def test_pismp_malaysian_only(self):
        """Non-Malaysian should NOT qualify for PISMP (req_malaysian=1)."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+',
            },
            'gender': 'male',
            'nationality': 'Bukan Warganegara',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        pismp = [c for c in courses if c['source_type'] == 'pismp']
        self.assertEqual(len(pismp), 0, "Non-Malaysian should not qualify for PISMP")

    def test_pismp_in_stats(self):
        """Stats should include 'pismp' count for eligible perfect student."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+', 'bio': 'A+',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        stats = response.json()['stats']
        self.assertIn('pismp', stats)
        self.assertGreater(stats['pismp'], 0)

    def test_pismp_no_merit_label(self):
        """PISMP courses should have no merit_label (no cutoff data, like TVET)."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        pismp = [c for c in courses if c['source_type'] == 'pismp']
        self.assertGreater(len(pismp), 0)
        for course in pismp:
            self.assertIsNone(course['merit_label'], f"PISMP {course['course_id']} should have no merit label")
            self.assertIsNone(course['merit_color'])

    # --- Matric/STPM Pathway Integration Tests ---

    def test_eligibility_includes_matric_tracks(self):
        """Eligible matric tracks appear in eligible_courses."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+', 'bio': 'A+',
                'addmath': 'A+',
            },
            'gender': 'male',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        courses = response.data['eligible_courses']
        matric_courses = [c for c in courses if c['source_type'] == 'matric']
        self.assertGreater(len(matric_courses), 0)
        mc = matric_courses[0]
        self.assertIn('merit_label', mc)
        self.assertIn('student_merit', mc)
        self.assertEqual(mc['level'], 'Pra-U')
        self.assertEqual(mc['pathway_type'], 'matric')

    def test_eligibility_includes_stpm_bidangs(self):
        """Eligible STPM bidangs appear in eligible_courses."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+', 'bio': 'A+',
                'addmath': 'A+',
            },
            'gender': 'male',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        courses = response.data['eligible_courses']
        stpm_courses = [c for c in courses if c['source_type'] == 'stpm']
        self.assertGreater(len(stpm_courses), 0)
        sc = stpm_courses[0]
        self.assertEqual(sc['pathway_type'], 'stpm')
        self.assertEqual(sc['level'], 'Pra-U')

    def test_pathway_stats_include_matric_stpm(self):
        """pathway_stats should count matric and stpm entries."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+', 'bio': 'A+',
                'addmath': 'A+',
            },
            'gender': 'male',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        stats = response.data['pathway_stats']
        self.assertIn('matric', stats)
        self.assertIn('stpm', stats)

    def test_pismp_subject_specific_requirement(self):
        """PISMP Matematik requires A in MATH+ADDMATH. Student without ADDMATH should not qualify."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+',
                # No addmath — Matematik PISMP requires A in math + addmath
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        # Check Matematik Pendidikan Rendah courses (require A in MATH + ADDMATH)
        math_pismp = [c for c in courses if c['source_type'] == 'pismp' and 'Matematik' in c.get('course_name', '')]
        for course in math_pismp:
            # This student doesn't have ADDMATH, so shouldn't qualify for Matematik PISMP
            # that requires A in 2 of [MATH, ADDMATH]
            self.fail(f"Student without ADDMATH should not qualify for {course['course_name']}")


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestCourseEndpoints(TestCase):
    """Test course catalog endpoints."""

    def setUp(self):
        self.client = APIClient()

    def test_course_list(self):
        """GET /api/v1/courses/ should return course list."""
        response = self.client.get('/api/v1/courses/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('courses', data)
        self.assertIn('total_count', data)

    def test_course_detail_not_found(self):
        """Non-existent course_id should return 404."""
        response = self.client.get('/api/v1/courses/FAKE_COURSE_ID/')
        self.assertEqual(response.status_code, 404)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestCourseDetailOfferings(TestCase):
    """Test course detail endpoint returns offering details (fees, hyperlinks, badges)."""

    def setUp(self):
        self.client = APIClient()
        from apps.courses.models import Course, Institution, CourseInstitution
        # Create test course
        self.course = Course.objects.create(
            course_id='TEST-DIP-001',
            course='Test Diploma in Engineering',
            level='Diploma',
            department='Engineering',
            field='Mechanical Engineering',
            semesters=6,
        )
        # Create test institution
        self.inst = Institution.objects.create(
            institution_id='TEST-INST-001',
            institution_name='Test Polytechnic',
            acronym='TPoly',
            type='Politeknik',
            category='Public',
            state='Selangor',
        )
        # Create offering with full details
        self.offering = CourseInstitution.objects.create(
            course=self.course,
            institution=self.inst,
            hyperlink='https://example.com/apply',
            tuition_fee_semester='RM 200 / semester',
            hostel_fee_semester='RM 60 / semester',
            registration_fee='RM 50',
            monthly_allowance=100.00,
            practical_allowance=300.00,
            free_hostel=True,
            free_meals=True,
        )

    def test_course_detail_returns_offering_fees(self):
        """Course detail should include tuition, hostel, and registration fees."""
        response = self.client.get(f'/api/v1/courses/{self.course.course_id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        inst = data['institutions'][0]
        self.assertEqual(inst['tuition_fee_semester'], 'RM 200 / semester')
        self.assertEqual(inst['hostel_fee_semester'], 'RM 60 / semester')
        self.assertEqual(inst['registration_fee'], 'RM 50')

    def test_course_detail_returns_hyperlink(self):
        """Course detail should include the application hyperlink."""
        response = self.client.get(f'/api/v1/courses/{self.course.course_id}/')
        data = response.json()
        inst = data['institutions'][0]
        self.assertEqual(inst['hyperlink'], 'https://example.com/apply')

    def test_course_detail_returns_allowances(self):
        """Course detail should include monthly and practical allowances."""
        response = self.client.get(f'/api/v1/courses/{self.course.course_id}/')
        data = response.json()
        inst = data['institutions'][0]
        self.assertEqual(inst['monthly_allowance'], 100.0)
        self.assertEqual(inst['practical_allowance'], 300.0)

    def test_course_detail_returns_free_badges(self):
        """Course detail should include free_hostel and free_meals flags."""
        response = self.client.get(f'/api/v1/courses/{self.course.course_id}/')
        data = response.json()
        inst = data['institutions'][0]
        self.assertTrue(inst['free_hostel'])
        self.assertTrue(inst['free_meals'])

    def test_course_detail_handles_empty_offering_fields(self):
        """Offering with no fee data should return empty strings and nulls."""
        from apps.courses.models import Course, Institution, CourseInstitution
        course2 = Course.objects.create(
            course_id='TEST-DIP-002', course='Test Diploma 2',
            level='Diploma', department='IT', field='IT',
        )
        inst2 = Institution.objects.create(
            institution_id='TEST-INST-002',
            institution_name='Test College',
            type='College', category='Private', state='Johor',
        )
        CourseInstitution.objects.create(course=course2, institution=inst2)

        response = self.client.get(f'/api/v1/courses/{course2.course_id}/')
        data = response.json()
        inst = data['institutions'][0]
        self.assertEqual(inst['hyperlink'], '')
        self.assertEqual(inst['tuition_fee_semester'], '')
        self.assertIsNone(inst['monthly_allowance'])
        self.assertFalse(inst['free_hostel'])
        self.assertFalse(inst['free_meals'])


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestCourseDetailCareerOccupations(TestCase):
    """Test course detail endpoint returns career occupation data."""

    def setUp(self):
        self.client = APIClient()
        from apps.courses.models import Course, MascoOccupation
        self.course = Course.objects.create(
            course_id='TEST-DIP-CAREER',
            course='Test Diploma in IT',
            level='Diploma',
            department='IT',
            field='Software Engineering',
        )
        self.occ1 = MascoOccupation.objects.create(
            masco_code='2512-03',
            job_title='Pembangun Perisian',
            emasco_url='https://emasco.mohr.gov.my/masco/2512-03',
        )
        self.occ2 = MascoOccupation.objects.create(
            masco_code='3512-06',
            job_title='Penolong Pembangun Perisian',
            emasco_url='https://emasco.mohr.gov.my/masco/3512-06',
        )
        self.course.career_occupations.add(self.occ1, self.occ2)

    def test_course_detail_includes_career_occupations(self):
        """Course detail should include career_occupations list."""
        response = self.client.get(f'/api/v1/courses/{self.course.course_id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('career_occupations', data)
        self.assertEqual(len(data['career_occupations']), 2)

    def test_career_occupation_fields(self):
        """Each career occupation should have masco_code, job_title, emasco_url."""
        response = self.client.get(f'/api/v1/courses/{self.course.course_id}/')
        data = response.json()
        occ = data['career_occupations'][0]
        self.assertIn('masco_code', occ)
        self.assertIn('job_title', occ)
        self.assertIn('emasco_url', occ)

    def test_course_without_career_occupations(self):
        """Course with no linked occupations should return empty list."""
        from apps.courses.models import Course
        course2 = Course.objects.create(
            course_id='TEST-DIP-NOCAREER',
            course='Test Diploma No Career',
            level='Diploma', department='Art', field='Art',
        )
        response = self.client.get(f'/api/v1/courses/{course2.course_id}/')
        data = response.json()
        self.assertEqual(data['career_occupations'], [])


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestCourseDetailBilingualDescriptions(TestCase):
    """Test course detail endpoint returns bilingual description fields."""

    def setUp(self):
        self.client = APIClient()
        from apps.courses.models import Course
        self.course = Course.objects.create(
            course_id='TEST-BILINGUAL-001',
            course='Diploma Kejuruteraan Mekanikal',
            level='Diploma',
            department='Kejuruteraan',
            field='Mekanikal',
            headline='Bina mesin, bina masa depan!',
            headline_en='Build machines, build your future!',
            description='Program ini melatih jurutera mekanikal yang mahir.',
            description_en='This programme trains skilled mechanical engineers.',
        )

    def test_course_detail_returns_bilingual_headline(self):
        """Course detail should include both headline and headline_en."""
        response = self.client.get(f'/api/v1/courses/{self.course.course_id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['course']['headline'], 'Bina mesin, bina masa depan!')
        self.assertEqual(data['course']['headline_en'], 'Build machines, build your future!')

    def test_course_detail_returns_bilingual_description(self):
        """Course detail should include both description and description_en."""
        response = self.client.get(f'/api/v1/courses/{self.course.course_id}/')
        data = response.json()
        self.assertIn('melatih jurutera', data['course']['description'])
        self.assertIn('skilled mechanical', data['course']['description_en'])

    def test_course_detail_empty_bilingual_defaults(self):
        """Course without descriptions should return empty strings for bilingual fields."""
        from apps.courses.models import Course
        bare_course = Course.objects.create(
            course_id='TEST-BARE-001',
            course='Bare Course',
            level='Sijil',
            department='Test',
            field='Test',
        )
        response = self.client.get(f'/api/v1/courses/{bare_course.course_id}/')
        data = response.json()
        self.assertEqual(data['course']['headline_en'], '')
        self.assertEqual(data['course']['description_en'], '')

    def test_course_list_includes_bilingual_fields(self):
        """Course list serializer should include bilingual fields."""
        response = self.client.get('/api/v1/courses/')
        data = response.json()
        if data['total_count'] > 0:
            course = data['courses'][0]
            self.assertIn('headline_en', course)
            self.assertIn('description_en', course)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestInstitutionEndpoints(TestCase):
    """Test institution endpoints."""

    def setUp(self):
        self.client = APIClient()

    def test_institution_list(self):
        """GET /api/v1/institutions/ should return institution list."""
        response = self.client.get('/api/v1/institutions/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('institutions', data)
        self.assertIn('total_count', data)

    def test_institution_detail_not_found(self):
        """Non-existent institution_id should return 404."""
        response = self.client.get('/api/v1/institutions/FAKE_INST/')
        self.assertEqual(response.status_code, 404)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestCourseSearchEndpoint(TestCase):
    """Test the course search/browse API endpoint."""

    @classmethod
    def setUpTestData(cls):
        from apps.courses.models import Course, CourseRequirement, Institution, CourseInstitution
        # Create test courses
        cls.course1 = Course.objects.create(
            course_id='SRCH-DIP-001',
            course='Diploma Kejuruteraan Mekanikal',
            level='Diploma',
            department='Engineering',
            field='Mechanical',
            frontend_label='Mekanikal & Pembuatan',
        )
        CourseRequirement.objects.create(
            course=cls.course1,
            source_type='poly',
            merit_cutoff=45.0,
        )

        cls.course2 = Course.objects.create(
            course_id='SRCH-SIJ-001',
            course='Sijil Teknologi Maklumat',
            level='Sijil',
            department='IT',
            field='IT',
            frontend_label='Teknologi Maklumat',
        )
        CourseRequirement.objects.create(
            course=cls.course2,
            source_type='kkom',
        )

        cls.course3 = Course.objects.create(
            course_id='SRCH-ASI-001',
            course='Asasi Sains',
            level='Asasi',
            department='Science',
            field='Science',
            frontend_label='Sains',
        )
        CourseRequirement.objects.create(
            course=cls.course3,
            source_type='ua',
            merit_cutoff=70.0,
        )

        # Institutions in different states
        cls.inst_sel = Institution.objects.create(
            institution_id='SRCH-INST-SEL',
            institution_name='Politeknik Selangor',
            type='Politeknik',
            state='Selangor',
        )
        cls.inst_joh = Institution.objects.create(
            institution_id='SRCH-INST-JOH',
            institution_name='Kolej Komuniti Johor',
            type='Kolej Komuniti',
            state='Johor',
        )

        # Link courses to institutions
        CourseInstitution.objects.create(course=cls.course1, institution=cls.inst_sel)
        CourseInstitution.objects.create(course=cls.course1, institution=cls.inst_joh)
        CourseInstitution.objects.create(course=cls.course2, institution=cls.inst_joh)

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/courses/search/'

    def test_search_returns_all_courses(self):
        """GET /api/v1/courses/search/ returns courses and filters."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('courses', data)
        self.assertIn('total_count', data)
        self.assertIn('filters', data)
        self.assertGreaterEqual(data['total_count'], 3)

    def test_search_text_filter(self):
        """?q=Mekanikal should filter to matching courses."""
        response = self.client.get(self.url, {'q': 'Mekanikal'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        self.assertTrue(all('Mekanikal' in c['course_name'] for c in courses))

    def test_search_level_filter(self):
        """?level=Diploma should return only Diploma courses."""
        response = self.client.get(self.url, {'level': 'Diploma'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        self.assertTrue(all(c['level'] == 'Diploma' for c in courses))

    def test_search_source_type_filter(self):
        """?source_type=poly should return only poly courses."""
        response = self.client.get(self.url, {'source_type': 'poly'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        self.assertTrue(all(c['source_type'] == 'poly' for c in courses))

    def test_search_state_filter(self):
        """?state=Johor should return courses offered in Johor."""
        response = self.client.get(self.url, {'state': 'Johor'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        course_ids = [c['course_id'] for c in data['courses']]
        # course1 and course2 are in Johor
        self.assertIn('SRCH-DIP-001', course_ids)
        self.assertIn('SRCH-SIJ-001', course_ids)
        # course3 has no institution link
        self.assertNotIn('SRCH-ASI-001', course_ids)

    def test_search_field_filter(self):
        """?field=Teknologi Maklumat should return only IT courses."""
        response = self.client.get(self.url, {'field': 'Teknologi Maklumat'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        self.assertTrue(all(c['field'] == 'Teknologi Maklumat' for c in courses))

    def test_search_pagination(self):
        """?limit=1&offset=0 should return 1 course."""
        response = self.client.get(self.url, {'limit': 1, 'offset': 0})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['courses']), 1)
        self.assertGreaterEqual(data['total_count'], 3)

    def test_search_filters_populated(self):
        """Filters object should contain dynamic options."""
        response = self.client.get(self.url)
        data = response.json()
        filters = data['filters']
        self.assertIn('levels', filters)
        self.assertIn('fields', filters)
        self.assertIn('source_types', filters)
        self.assertIn('states', filters)
        self.assertGreater(len(filters['levels']), 0)

    def test_search_institution_count(self):
        """Courses should include institution_count."""
        response = self.client.get(self.url, {'q': 'Mekanikal'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        mech = next(c for c in courses if c['course_id'] == 'SRCH-DIP-001')
        self.assertEqual(mech['institution_count'], 2)

    def test_search_combined_filters(self):
        """Multiple filters should be combined (AND logic)."""
        response = self.client.get(self.url, {
            'level': 'Diploma',
            'state': 'Selangor',
        })
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        # Only course1 is Diploma AND in Selangor
        self.assertTrue(all(c['level'] == 'Diploma' for c in courses))
        course_ids = [c['course_id'] for c in courses]
        self.assertIn('SRCH-DIP-001', course_ids)

    def test_search_returns_institution_name(self):
        """Search results include primary institution name (alphabetically first)."""
        response = self.client.get(self.url, {'q': 'Mekanikal'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        mech = next(c for c in courses if c['course_id'] == 'SRCH-DIP-001')
        self.assertIn('institution_name', mech)
        # Alphabetically: Kolej Komuniti Johor < Politeknik Selangor
        self.assertEqual(mech['institution_name'], 'Kolej Komuniti Johor')

    def test_search_returns_institution_state(self):
        """Search results include primary institution state."""
        response = self.client.get(self.url, {'q': 'Mekanikal'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        mech = next(c for c in courses if c['course_id'] == 'SRCH-DIP-001')
        self.assertIn('institution_state', mech)
        self.assertEqual(mech['institution_state'], 'Johor')

    def test_search_no_offering_returns_empty_institution(self):
        """Courses with no offerings return empty institution fields."""
        response = self.client.get(self.url, {'q': 'Asasi'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        asasi = next(c for c in courses if c['course_id'] == 'SRCH-ASI-001')
        self.assertEqual(asasi['institution_name'], '')
        self.assertEqual(asasi['institution_state'], '')


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestUnifiedSearchEndpoint(TestCase):
    """Test the unified search endpoint returning both SPM and STPM courses."""

    @classmethod
    def setUpTestData(cls):
        from apps.courses.models import Course, CourseRequirement, Institution, CourseInstitution, StpmCourse, StpmRequirement

        # SPM test course
        cls.spm_course = Course.objects.create(
            course_id='UNI-SPM-001',
            course='Diploma Kejuruteraan Mekanikal',
            level='Diploma',
            department='Engineering',
            field='Mechanical',
            frontend_label='Mekanikal & Pembuatan',
        )
        CourseRequirement.objects.create(
            course=cls.spm_course,
            source_type='poly',
            merit_cutoff=45.0,
        )
        inst = Institution.objects.create(
            institution_id='UNI-INST-001',
            institution_name='Politeknik Test',
            type='Politeknik',
            state='Selangor',
        )
        CourseInstitution.objects.create(course=cls.spm_course, institution=inst)

        # STPM test course
        cls.stpm_course = StpmCourse.objects.create(
            course_id='UNI-STPM-001',
            course_name='Ijazah Sarjana Muda Kejuruteraan Mekanikal',
            university='Universiti Malaya',
            stream='science',
            merit_score=85.0,
            field='Mekanikal & Pembuatan',
        )
        StpmRequirement.objects.create(
            course=cls.stpm_course,
            min_cgpa=3.0,
        )

        # STPM bumiputera-only course (should be excluded)
        cls.stpm_bumi = StpmCourse.objects.create(
            course_id='UNI-STPM-BUMI',
            course_name='Ijazah Sarjana Muda Seni Bina',
            university='UiTM',
            stream='arts',
            field='Seni Bina',
        )
        StpmRequirement.objects.create(
            course=cls.stpm_bumi,
            req_bumiputera=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/courses/search/'

    def test_search_returns_both_spm_and_stpm(self):
        """Search with no qualification filter returns both SPM and STPM courses."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        qualifications = {c['qualification'] for c in response.data['courses']}
        self.assertIn('SPM', qualifications)
        self.assertIn('STPM', qualifications)

    def test_search_qualification_filter_spm(self):
        """qualification=SPM returns only SPM courses."""
        response = self.client.get(self.url, {'qualification': 'SPM'})
        self.assertEqual(response.status_code, 200)
        for course in response.data['courses']:
            self.assertEqual(course['qualification'], 'SPM')

    def test_search_qualification_filter_stpm(self):
        """qualification=STPM returns only STPM courses."""
        response = self.client.get(self.url, {'qualification': 'STPM'})
        self.assertEqual(response.status_code, 200)
        for course in response.data['courses']:
            self.assertEqual(course['qualification'], 'STPM')

    def test_search_stpm_has_course_card_fields(self):
        """STPM courses in unified search have all CourseCard fields."""
        response = self.client.get(self.url, {'qualification': 'STPM'})
        self.assertEqual(response.status_code, 200)
        if response.data['courses']:
            course = response.data['courses'][0]
            for key in ('course_id', 'course_name', 'level', 'field',
                        'source_type', 'merit_cutoff', 'institution_count',
                        'institution_name', 'qualification'):
                self.assertIn(key, course)
            self.assertEqual(course['level'], 'Ijazah Sarjana Muda')
            self.assertEqual(course['source_type'], 'ua')
            self.assertEqual(course['institution_count'], 1)

    def test_search_stpm_maps_fields_correctly(self):
        """STPM course fields are mapped to CourseCard format."""
        response = self.client.get(self.url, {'qualification': 'STPM', 'q': 'Mekanikal'})
        self.assertEqual(response.status_code, 200)
        courses = response.data['courses']
        stpm = next((c for c in courses if c['course_id'] == 'UNI-STPM-001'), None)
        self.assertIsNotNone(stpm)
        self.assertEqual(stpm['course_name'], 'Ijazah Sarjana Muda Kejuruteraan Mekanikal')
        self.assertEqual(stpm['institution_name'], 'Universiti Malaya')
        self.assertEqual(stpm['merit_cutoff'], 85.0)
        self.assertEqual(stpm['field'], 'Mekanikal & Pembuatan')

    def test_search_excludes_bumiputera_only(self):
        """Bumiputera-only STPM courses are excluded from results."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        course_ids = [c['course_id'] for c in response.data['courses']]
        self.assertNotIn('UNI-STPM-BUMI', course_ids)

    def test_search_filters_include_qualification(self):
        """Filter metadata includes qualification options."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('qualifications', response.data['filters'])
        self.assertIn('SPM', response.data['filters']['qualifications'])
        self.assertIn('STPM', response.data['filters']['qualifications'])

    def test_search_text_filter_across_qualifications(self):
        """Text search finds matches in both SPM and STPM."""
        response = self.client.get(self.url, {'q': 'Mekanikal'})
        self.assertEqual(response.status_code, 200)
        qualifications = {c['qualification'] for c in response.data['courses']}
        self.assertEqual(qualifications, {'SPM', 'STPM'})

    def test_search_field_filter_works_for_stpm(self):
        """Field filter works for STPM courses."""
        response = self.client.get(self.url, {'field': 'Mekanikal & Pembuatan'})
        self.assertEqual(response.status_code, 200)
        course_ids = [c['course_id'] for c in response.data['courses']]
        self.assertIn('UNI-STPM-001', course_ids)
        self.assertIn('UNI-SPM-001', course_ids)

    def test_search_level_filter_ijazah(self):
        """Level filter 'Ijazah Sarjana Muda' returns only STPM courses."""
        response = self.client.get(self.url, {'level': 'Ijazah Sarjana Muda'})
        self.assertEqual(response.status_code, 200)
        for course in response.data['courses']:
            self.assertEqual(course['qualification'], 'STPM')

    def test_search_source_type_university(self):
        """Source type filter 'ua' returns only STPM courses."""
        response = self.client.get(self.url, {'source_type': 'ua'})
        self.assertEqual(response.status_code, 200)
        for course in response.data['courses']:
            self.assertEqual(course['qualification'], 'STPM')

    def test_search_stpm_all_have_qualification_field(self):
        """Every course in response has a qualification field."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for course in response.data['courses']:
            self.assertIn('qualification', course)
            self.assertIn(course['qualification'], ('SPM', 'STPM'))


class TestCalculateEndpoints(TestCase):
    """Tests for /calculate/merit/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/calculate/merit/'

    def test_merit_calculation(self):
        """POST all-A grades + coq_score=8 returns expected merit values."""
        payload = {
            'grades': {
                'bm': 'A',
                'eng': 'A',
                'hist': 'A',
                'math': 'A',
                'phy': 'A',
                'chem': 'A',
                'bio': 'A',
                'addmath': 'A',
                'moral': 'A',
            },
            'coq_score': 8.0,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('academic_merit', response.data)
        self.assertIn('final_merit', response.data)
        self.assertAlmostEqual(response.data['academic_merit'], 90.0, places=1)
        self.assertAlmostEqual(response.data['final_merit'], 98.0, places=1)

    def test_merit_missing_grades(self):
        """POST empty body returns 400."""
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 400)

    # --- CGPA endpoint tests ---

    def test_cgpa_calculation(self):
        """POST STPM grades A, B+, B with koko_score=8 returns expected CGPA values."""
        url = '/api/v1/calculate/cgpa/'
        payload = {
            'stpm_grades': {'PA': 'A', 'MATH_T': 'B+', 'PHYSICS': 'B'},
            'koko_score': 8,
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.data['academic_cgpa'], 3.44, places=2)
        self.assertAlmostEqual(response.data['cgpa'], 3.42, places=2)
        self.assertAlmostEqual(response.data['merit_percent'], 85.5, places=1)

    def test_cgpa_missing_grades(self):
        """POST empty body returns 400."""
        url = '/api/v1/calculate/cgpa/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 400)

    # --- Pathways endpoint tests ---

    def test_pathways_calculation(self):
        """POST /calculate/pathways/ returns all 6 pathway results with fit scores."""
        response = self.client.post(
            '/api/v1/calculate/pathways/',
            data={
                'grades': {
                    'bm': 'A', 'eng': 'A', 'math': 'A', 'hist': 'A',
                    'phy': 'A', 'chem': 'A', 'addmath': 'A', 'bio': 'A',
                },
                'coq_score': 8.0,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('pathways', data)
        self.assertEqual(len(data['pathways']), 6)  # 4 matric + 2 stpm
        # First result should be matric sains
        sains = data['pathways'][0]
        self.assertEqual(sains['track_id'], 'sains')
        self.assertTrue(sains['eligible'])
        self.assertIn('merit', sains)
        self.assertIn('fit_score', sains)

    def test_pathways_with_signals(self):
        """POST /calculate/pathways/ accepts optional signals for fit scoring."""
        response = self.client.post(
            '/api/v1/calculate/pathways/',
            data={
                'grades': {
                    'bm': 'A', 'eng': 'A', 'math': 'A', 'hist': 'A',
                    'phy': 'A', 'chem': 'A', 'addmath': 'A', 'bio': 'A',
                },
                'coq_score': 8.0,
                'signals': {
                    'work_preference_signals': {'problem_solving': 1},
                },
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        sains = data['pathways'][0]
        # With problem_solving signal, fit_score should be higher than base
        self.assertGreater(sains['fit_score'], 108)

    def test_pathways_missing_grades(self):
        """POST /calculate/pathways/ with no grades returns 400."""
        response = self.client.post(
            '/api/v1/calculate/pathways/',
            data={},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
