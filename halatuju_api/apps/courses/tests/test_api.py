"""
Tests for course API endpoints.

Covers:
- POST /api/v1/eligibility/check/ — eligibility engine via API
- GET /api/v1/courses/ — course listing
- GET /api/v1/courses/<id>/ — course detail
- GET /api/v1/institutions/ — institution listing

Note: Eligibility tests load CSV data directly into the app config's DataFrame
(bypassing DB) to match the hybrid engine approach used in production.
"""
import os
import unittest
import pandas as pd
from django.test import TestCase, override_settings
from django.apps import apps
from rest_framework.test import APIClient


def _load_and_clean_csv(filepath):
    """Load CSV and enforce strict integer types for flag columns."""
    REQ_FLAG_COLUMNS = [
        'req_malaysian', 'req_male', 'req_female', 'no_colorblind', 'no_disability',
        '3m_only', 'pass_bm', 'credit_bm', 'pass_history',
        'pass_eng', 'credit_english', 'pass_math', 'credit_math', 'pass_math_addmath',
        'pass_math_science', 'pass_science_tech', 'credit_math_sci',
        'credit_math_sci_tech', 'pass_stv', 'credit_sf', 'credit_sfmt',
        'credit_bmbi', 'credit_stv',
        'req_interview', 'single', 'req_group_diversity',
        'credit_bm_b', 'credit_eng_b', 'credit_math_b', 'credit_addmath_b',
        'distinction_bm', 'distinction_eng', 'distinction_math', 'distinction_addmath',
        'distinction_bio', 'distinction_phy', 'distinction_chem', 'distinction_sci',
        'credit_science_group', 'credit_math_or_addmath',
        'pass_islam', 'credit_islam', 'pass_moral', 'credit_moral',
        'pass_sci', 'credit_sci', 'credit_addmath',
    ]
    REQ_COUNT_COLUMNS = ['min_credits', 'min_pass', 'max_aggregate_units']
    ALL_REQ_COLUMNS = REQ_FLAG_COLUMNS + REQ_COUNT_COLUMNS

    df = pd.read_csv(filepath, encoding='utf-8')

    for col in ALL_REQ_COLUMNS:
        if col not in df.columns:
            df[col] = 0

    for col in REQ_FLAG_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    for col in REQ_COUNT_COLUMNS:
        if col == 'max_aggregate_units':
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(100).astype(int)
            df.loc[df[col] == 0, col] = 100
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    return df


def _get_data_dir():
    """Get the path to HalaTuju data directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    halatuju_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    return os.path.join(halatuju_root, 'data')


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestEligibilityEndpoint(TestCase):
    """Test the eligibility check API endpoint."""

    @classmethod
    def setUpClass(cls):
        """Load CSV data into the app config's DataFrame."""
        super().setUpClass()
        data_dir = _get_data_dir()
        if not os.path.exists(data_dir):
            raise unittest.SkipTest(f"Data folder not found: {data_dir}")

        # source_type matches what load_csv_data management command sets
        file_source_map = [
            ('requirements.csv', 'poly'),
            ('tvet_requirements.csv', 'tvet'),
            ('university_requirements.csv', 'ua'),
            ('pismp_requirements.csv', 'pismp'),
        ]
        dfs = []
        for filename, source_type in file_source_map:
            path = os.path.join(data_dir, filename)
            if os.path.exists(path):
                df = _load_and_clean_csv(path)
                df['source_type'] = source_type
                dfs.append(df)

        if not dfs:
            raise unittest.SkipTest("No requirements CSV files found")

        # Inject DataFrame into app config (same as hybrid engine startup)
        courses_config = apps.get_app_config('courses')
        courses_config.requirements_df = pd.concat(dfs, ignore_index=True)

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/eligibility/check/'

    def test_perfect_student_returns_courses(self):
        """A student with all A+ grades should get many eligible courses."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'SN': 'A+', 'PHY': 'A+', 'CHE': 'A+'
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
        """Frontend-format keys (BM, BI, MAT) should work correctly."""
        response = self.client.post(self.url, {
            'grades': {'BM': 'A', 'BI': 'A', 'SEJ': 'A', 'MAT': 'A'},
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
            'grades': {'BM': 'A', 'BI': 'B+', 'SEJ': 'C', 'MAT': 'A'},
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
            'grades': {'BM': 'A', 'MAT': 'A'},
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
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'SN': 'A+', 'PHY': 'A+', 'CHE': 'A+'
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
            'grades': {'BM': 'A', 'MAT': 'A'},
            'gender': 'male',
            'nationality': 'malaysian',
        }, format='json')

        non_citizen_response = self.client.post(self.url, {
            'grades': {'BM': 'A', 'MAT': 'A'},
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
            'grades': {'BM': 'A', 'MAT': 'A', 'SN': 'A'},
            'gender': 'male',
            'colorblind': False,
        }, format='json')

        colorblind_response = self.client.post(self.url, {
            'grades': {'BM': 'A', 'MAT': 'A', 'SN': 'A'},
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
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'SN': 'A+', 'PHY': 'A+', 'CHE': 'A+'
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
            elif course['merit_cutoff']:
                # Poly/UA with cutoff should have a label
                self.assertIn(course['merit_label'], ['High', 'Fair', 'Low'])
                self.assertIsNotNone(course['merit_color'])

    def test_eligibility_merit_high_for_perfect_student(self):
        """Perfect student (all A+) should get 'High' merit for all poly courses with cutoffs."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'SN': 'A+', 'PHY': 'A+', 'CHE': 'A+', 'BIO': 'A+',
                'AMT': 'A+',
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
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'SN': 'A+', 'PHY': 'A+', 'CHE': 'A+', 'BIO': 'A+',
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
                'BM': 'C', 'BI': 'C', 'SEJ': 'C', 'MAT': 'C',
                'SN': 'C',
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
                'BM': 'A-', 'BI': 'A-', 'SEJ': 'A-', 'MAT': 'A-',
                'SN': 'A-', 'PHY': 'C', 'CHE': 'C',
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
                'BM': 'A', 'BI': 'A', 'SEJ': 'A', 'MAT': 'A',
                'SN': 'C', 'PHY': 'C', 'CHE': 'C',
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
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'SN': 'A+', 'PHY': 'A+', 'CHE': 'A+',
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
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'SN': 'A+', 'PHY': 'A+', 'CHE': 'A+', 'BIO': 'A+',
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
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'SN': 'A+', 'PHY': 'A+', 'CHE': 'A+',
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

    def test_pismp_subject_specific_requirement(self):
        """PISMP Matematik requires A in MATH+ADDMATH. Student without ADDMATH should not qualify."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'SN': 'A+', 'PHY': 'A+', 'CHE': 'A+',
                # No AMT (Add Math) — Matematik PISMP requires A in MATH + ADDMATH
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
        self.assertIn('count', data)

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
        self.assertIn('count', data)

    def test_institution_detail_not_found(self):
        """Non-existent institution_id should return 404."""
        response = self.client.get('/api/v1/institutions/FAKE_INST/')
        self.assertEqual(response.status_code, 404)
