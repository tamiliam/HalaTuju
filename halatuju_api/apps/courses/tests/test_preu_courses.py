"""
Tests for pre-university course eligibility and search via the API.

Covers:
- POST /api/v1/eligibility/check/ — pre-U courses in stats/pathway_stats
- GET /api/v1/courses/search/ — search/filter for pre-U courses

Note: Matric/STPM eligibility logic is tested in test_pathways.py.
This file tests API-level integration (stats, search).
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.courses.models import Course, CourseRequirement
from apps.courses.tests.conftest import load_requirements_df


# Pre-U course definitions (mirrors migration 0017)
PREU_COURSES = [
    {
        'course_id': 'matric-sains',
        'course': 'Matrikulasi — Sains',
        'level': 'Pra-U',
        'department': 'KPM',
        'field': 'Sains & Teknologi',
        'frontend_label': 'Sains & Teknologi',
    },
    {
        'course_id': 'matric-kejuruteraan',
        'course': 'Matrikulasi — Kejuruteraan',
        'level': 'Pra-U',
        'department': 'KPM',
        'field': 'Kejuruteraan',
        'frontend_label': 'Kejuruteraan',
    },
    {
        'course_id': 'matric-sains-komputer',
        'course': 'Matrikulasi — Sains Komputer',
        'level': 'Pra-U',
        'department': 'KPM',
        'field': 'Teknologi Maklumat',
        'frontend_label': 'Teknologi Maklumat',
    },
    {
        'course_id': 'matric-perakaunan',
        'course': 'Matrikulasi — Perakaunan',
        'level': 'Pra-U',
        'department': 'KPM',
        'field': 'Perakaunan & Kewangan',
        'frontend_label': 'Perakaunan & Kewangan',
    },
    {
        'course_id': 'stpm-sains',
        'course': 'Tingkatan 6 — Sains',
        'level': 'Pra-U',
        'department': 'KPM',
        'field': 'Sains & Teknologi',
        'frontend_label': 'Sains & Teknologi',
    },
    {
        'course_id': 'stpm-sains-sosial',
        'course': 'Tingkatan 6 — Sains Sosial',
        'level': 'Pra-U',
        'department': 'KPM',
        'field': 'Sains Sosial',
        'frontend_label': 'Sains Sosial',
    },
]

PREU_REQUIREMENTS = [
    {
        'course_id': 'matric-sains',
        'source_type': 'matric',
        'merit_type': 'matric',
        'merit_cutoff': 94,
        'credit_bm': 1,
        'pass_history': 1,
        'complex_requirements': {
            'or_groups': [
                {'count': 1, 'grade': 'B', 'subjects': ['math']},
                {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                {'count': 1, 'grade': 'C', 'subjects': ['chem']},
                {'count': 1, 'grade': 'C', 'subjects': ['phy', 'bio']},
            ],
        },
        'min_credits': 5,
    },
    {
        'course_id': 'matric-kejuruteraan',
        'source_type': 'matric',
        'merit_type': 'matric',
        'merit_cutoff': 94,
        'credit_bm': 1,
        'pass_history': 1,
        'complex_requirements': {
            'or_groups': [
                {'count': 1, 'grade': 'B', 'subjects': ['math']},
                {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                {'count': 1, 'grade': 'C', 'subjects': ['phy']},
            ],
        },
        'min_credits': 5,
    },
    {
        'course_id': 'matric-sains-komputer',
        'source_type': 'matric',
        'merit_type': 'matric',
        'merit_cutoff': 94,
        'credit_bm': 1,
        'pass_history': 1,
        'complex_requirements': {
            'or_groups': [
                {'count': 1, 'grade': 'C', 'subjects': ['math']},
                {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                {'count': 1, 'grade': 'C', 'subjects': ['comp_sci']},
            ],
        },
        'min_credits': 5,
    },
    {
        'course_id': 'matric-perakaunan',
        'source_type': 'matric',
        'merit_type': 'matric',
        'merit_cutoff': 94,
        'credit_bm': 1,
        'pass_history': 1,
        'complex_requirements': {
            'or_groups': [
                {'count': 1, 'grade': 'C', 'subjects': ['math']},
            ],
        },
        'min_credits': 5,
    },
    {
        'course_id': 'stpm-sains',
        'source_type': 'stpm',
        'merit_type': 'stpm_mata_gred',
        'merit_cutoff': 18,
        'credit_bm': 1,
        'pass_history': 1,
        'min_credits': 3,
    },
    {
        'course_id': 'stpm-sains-sosial',
        'source_type': 'stpm',
        'merit_type': 'stpm_mata_gred',
        'merit_cutoff': 18,
        'credit_bm': 1,
        'pass_history': 1,
        'min_credits': 3,
    },
]


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestPreUEligibility(TestCase):
    """Test pre-U courses appear in eligibility stats via the API."""
    fixtures = ['courses', 'requirements']

    @classmethod
    def setUpClass(cls):
        """Load DB fixtures into the app config's DataFrame."""
        super().setUpClass()
        load_requirements_df()

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/eligibility/check/'

    def test_preu_courses_appear_in_stats(self):
        """Strong student should have 'matric' and 'stpm' in pathway stats."""
        response = self.client.post(self.url, {
            'grades': {
                'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                'addmath': 'A+', 'chem': 'A+', 'phy': 'A+', 'bio': 'A+',
                'sci': 'A+',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Stats should include matric and stpm source types
        stats = data['stats']
        self.assertIn('matric', stats)
        self.assertIn('stpm', stats)

        # Pathway stats should also include them
        pathway_stats = data['pathway_stats']
        self.assertIn('matric', pathway_stats)
        self.assertIn('stpm', pathway_stats)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestPreUSearch(TestCase):
    """Test search endpoint for pre-university courses."""

    @classmethod
    def setUpTestData(cls):
        """Create Course + CourseRequirement model instances (no DataFrame needed)."""
        for cd in PREU_COURSES:
            Course.objects.get_or_create(
                course_id=cd['course_id'],
                defaults=cd,
            )

        # Create CourseRequirement instances for search filtering
        req_map = {r['course_id']: r for r in PREU_REQUIREMENTS}
        for cd in PREU_COURSES:
            cid = cd['course_id']
            req = req_map[cid]
            CourseRequirement.objects.get_or_create(
                course_id=cid,
                defaults={
                    'source_type': req['source_type'],
                    'merit_type': req.get('merit_type', 'standard'),
                    'merit_cutoff': req.get('merit_cutoff'),
                    'min_credits': req.get('min_credits', 0),
                    'credit_bm': bool(req.get('credit_bm', 0)),
                    'pass_history': bool(req.get('pass_history', 0)),
                    'complex_requirements': req.get('complex_requirements'),
                },
            )

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/courses/search/'

    def test_search_by_level_preu(self):
        """?level=Pra-U should return pre-university courses."""
        response = self.client.get(self.url, {'level': 'Pra-U'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        self.assertGreaterEqual(len(courses), 6)
        for c in courses:
            self.assertEqual(c['level'], 'Pra-U')

    def test_search_by_text_matrikulasi(self):
        """?q=Matrikulasi should return matric courses."""
        response = self.client.get(self.url, {'q': 'Matrikulasi'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        self.assertGreaterEqual(len(courses), 4)
        for c in courses:
            self.assertIn('Matrikulasi', c['course_name'])

    def test_search_by_source_type_matric(self):
        """?source_type=matric should return only matric courses."""
        response = self.client.get(self.url, {'source_type': 'matric'})
        self.assertEqual(response.status_code, 200)
        courses = response.json()['courses']
        self.assertGreaterEqual(len(courses), 4)
        for c in courses:
            self.assertEqual(c['source_type'], 'matric')
