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
