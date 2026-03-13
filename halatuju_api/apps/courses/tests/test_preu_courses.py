"""
Tests for pre-university course eligibility and merit calculation via the API.

Covers:
- POST /api/v1/eligibility/check/ — matric and STPM eligibility + merit
- GET /api/v1/courses/search/ — search/filter for pre-U courses

Note: Eligibility tests load CSV data directly into the app config's DataFrame
(bypassing DB) to match the hybrid engine approach used in production.
Pre-U courses are appended to the DataFrame AND created as Django model instances.
"""
import os
import unittest
import pandas as pd
from django.test import TestCase, override_settings
from django.apps import apps
from rest_framework.test import APIClient

from apps.courses.models import Course, CourseRequirement


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


def _build_preu_df_rows():
    """Build DataFrame rows for 6 pre-U courses, matching the CSV column schema."""
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

    rows = []
    for req in PREU_REQUIREMENTS:
        row = {col: 0 for col in REQ_FLAG_COLUMNS}
        row['min_credits'] = 0
        row['min_pass'] = 0
        row['max_aggregate_units'] = 100
        row['merit_cutoff'] = None
        row['merit_type'] = 'standard'
        row['complex_requirements'] = ''
        row['subject_group_req'] = ''
        row['remarks'] = ''

        # Apply requirement overrides
        row['course_id'] = req['course_id']
        row['source_type'] = req['source_type']
        row['merit_type'] = req.get('merit_type', 'standard')
        row['merit_cutoff'] = req.get('merit_cutoff')
        row['min_credits'] = req.get('min_credits', 0)

        # Apply flag overrides
        for flag in REQ_FLAG_COLUMNS:
            if flag in req:
                row[flag] = req[flag]

        # Complex requirements as JSON (engine expects string or dict)
        if 'complex_requirements' in req:
            row['complex_requirements'] = req['complex_requirements']

        rows.append(row)
    return rows


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestPreUEligibility(TestCase):
    """Test pre-university eligibility via the API endpoint."""

    @classmethod
    def setUpClass(cls):
        """Load CSV data + pre-U courses into the app config's DataFrame."""
        super().setUpClass()
        data_dir = _get_data_dir()
        if not os.path.exists(data_dir):
            raise unittest.SkipTest(f"Data folder not found: {data_dir}")

        # Load base CSV data (same pattern as test_api.py)
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

        combined_df = pd.concat(dfs, ignore_index=True)

        # Ensure merit_type column exists (older CSVs may not have it)
        if 'merit_type' not in combined_df.columns:
            combined_df['merit_type'] = 'standard'

        # Append 6 pre-U requirement rows
        preu_rows = _build_preu_df_rows()
        preu_df = pd.DataFrame(preu_rows)
        combined_df = pd.concat([combined_df, preu_df], ignore_index=True)

        # Inject into app config
        courses_config = apps.get_app_config('courses')
        courses_config.requirements_df = combined_df

        # Create Course model instances for the 6 pre-U courses (for detail lookups)
        for cd in PREU_COURSES:
            Course.objects.get_or_create(
                course_id=cd['course_id'],
                defaults=cd,
            )

        # Set up course_pathway_map for pre-U courses
        courses_config.course_pathway_map = getattr(courses_config, 'course_pathway_map', {})
        courses_config.course_pathway_map.update({
            'matric-sains': 'matric',
            'matric-kejuruteraan': 'matric',
            'matric-sains-komputer': 'matric',
            'matric-perakaunan': 'matric',
            'stpm-sains': 'stpm',
            'stpm-sains-sosial': 'stpm',
        })

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/eligibility/check/'

    # ── Matric eligibility tests ─────────────────────────────────────

    def test_matric_sains_eligible(self):
        """Science student with good grades qualifies for matric sains, gets merit_label."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A', 'BI': 'A', 'SEJ': 'A', 'MAT': 'A',
                'AMT': 'A', 'CHE': 'A', 'PHY': 'A', 'BIO': 'A',
                'SN': 'A',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        matric_sains = [c for c in courses if c['course_id'] == 'matric-sains']
        self.assertEqual(len(matric_sains), 1, "Should qualify for Matrikulasi Sains")
        mc = matric_sains[0]
        self.assertEqual(mc['source_type'], 'matric')
        self.assertIn(mc['merit_label'], ['High', 'Fair', 'Low'])
        self.assertIsNotNone(mc['student_merit'])
        self.assertEqual(mc['level'], 'Pra-U')

    def test_matric_merit_values(self):
        """Perfect grades + coq_score=10 should yield merit=100, label=High."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'AMT': 'A+', 'CHE': 'A+', 'PHY': 'A+', 'BIO': 'A+',
                'SN': 'A+',
            },
            'gender': 'male',
            'coq_score': 10,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        matric_sains = [c for c in courses if c['course_id'] == 'matric-sains']
        self.assertEqual(len(matric_sains), 1)
        mc = matric_sains[0]
        # 4 best subjects @ A+(25) = 100 points → academic = (100/100)*90 = 90
        # + coq 10 → merit = 100
        self.assertEqual(mc['student_merit'], 100)
        self.assertEqual(mc['merit_label'], 'High')

    def test_matric_not_eligible_bad_grades(self):
        """Weak student (BM: D) should not get matric courses — credit_bm fails."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'D', 'BI': 'D', 'SEJ': 'D', 'MAT': 'D',
                'SN': 'D',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        matric_courses = [c for c in courses if c['source_type'] == 'matric']
        self.assertEqual(len(matric_courses), 0, "Weak student should not qualify for any matric track")

    # ── STPM eligibility tests ───────────────────────────────────────

    def test_stpm_sains_eligible(self):
        """BM credit + 3 science credits qualifies for STPM sains, gets merit display."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A', 'BI': 'A', 'SEJ': 'A', 'MAT': 'A',
                'AMT': 'A', 'CHE': 'A', 'PHY': 'A',
                'SN': 'A',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        stpm_sains = [c for c in courses if c['course_id'] == 'stpm-sains']
        self.assertEqual(len(stpm_sains), 1, "Should qualify for Tingkatan 6 Sains")
        sc = stpm_sains[0]
        self.assertEqual(sc['source_type'], 'stpm')
        self.assertIn(sc['merit_label'], ['High', 'Fair', 'Low'])
        # STPM has mata_gred display values
        self.assertIsNotNone(sc['merit_display_student'])
        self.assertIsNotNone(sc['merit_display_cutoff'])

    def test_stpm_mata_gred_values(self):
        """Perfect grades → mata_gred=3 (3 subjects × A+=1), display '3'/'18', label High."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'AMT': 'A+', 'CHE': 'A+', 'PHY': 'A+', 'BIO': 'A+',
                'SN': 'A+',
            },
            'gender': 'male',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        courses = response.json()['eligible_courses']
        stpm_sains = [c for c in courses if c['course_id'] == 'stpm-sains']
        self.assertEqual(len(stpm_sains), 1)
        sc = stpm_sains[0]
        # Best 3 subjects from different groups, all A+ (mata_gred=1 each) → total 3
        self.assertEqual(sc['merit_display_student'], '3')
        self.assertEqual(sc['merit_display_cutoff'], '18')
        self.assertEqual(sc['merit_label'], 'High')

    # ── Stats tests ──────────────────────────────────────────────────

    def test_preu_courses_appear_in_stats(self):
        """Strong student should have 'matric' and 'stpm' in pathway stats."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A+', 'BI': 'A+', 'SEJ': 'A+', 'MAT': 'A+',
                'AMT': 'A+', 'CHE': 'A+', 'PHY': 'A+', 'BIO': 'A+',
                'SN': 'A+',
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
