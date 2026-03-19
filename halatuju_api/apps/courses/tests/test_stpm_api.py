import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from apps.courses.models import FieldTaxonomy, MascoOccupation, StpmCourse, StpmRequirement


@pytest.mark.django_db
class TestStpmEligibilityAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('loaddata', 'stpm_courses', 'stpm_requirements', stdout=StringIO(), verbosity=0)
        self.client = APIClient()

    def test_endpoint_exists(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {
            'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            'cgpa': 3.8,
            'muet_band': 4,
        }, format='json')
        assert resp.status_code == 200

    def test_returns_eligible_courses(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {
            'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'},
            'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A+'},
            'cgpa': 3.89,
            'muet_band': 4,
        }, format='json')
        data = resp.json()
        assert 'eligible_courses' in data
        assert len(data['eligible_courses']) > 0

    def test_missing_required_fields(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {}, format='json')
        assert resp.status_code == 400

    def test_returns_count(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {
            'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            'cgpa': 3.8,
            'muet_band': 4,
        }, format='json')
        data = resp.json()
        assert 'total_eligible' in data
        assert data['total_eligible'] == len(data['eligible_courses'])


@pytest.mark.django_db
class TestStpmRankingAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_ranking_returns_200(self):
        """POST /api/v1/stpm/ranking/ returns 200 with valid input."""
        data = {
            'eligible_courses': [
                {
                    'course_id': 'TEST001', 'course_name': 'Test Course',
                    'university': 'UM', 'stream': 'science',
                    'min_cgpa': 2.5, 'min_muet_band': 3,
                    'req_interview': False, 'no_colorblind': False,
                }
            ],
            'student_cgpa': 3.5,
            'student_signals': {},
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        assert response.status_code == 200

    def test_ranking_returns_scored_courses(self):
        """Response includes fit_score and fit_reasons on each course."""
        data = {
            'eligible_courses': [
                {
                    'course_id': 'TEST001', 'course_name': 'Test',
                    'university': 'UM', 'stream': 'science',
                    'min_cgpa': 2.5, 'min_muet_band': 3,
                    'req_interview': False, 'no_colorblind': False,
                }
            ],
            'student_cgpa': 3.5,
            'student_signals': {},
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        body = response.json()
        assert 'ranked_courses' in body
        assert 'total' in body
        assert body['total'] == 1
        prog = body['ranked_courses'][0]
        assert 'fit_score' in prog
        assert 'fit_reasons' in prog

    def test_ranking_sorted_desc(self):
        """Courses returned sorted by fit_score descending."""
        data = {
            'eligible_courses': [
                {'course_id': 'A', 'course_name': 'Low CGPA Margin',
                 'university': 'X', 'stream': 'arts', 'min_cgpa': 3.4,
                 'min_muet_band': 4, 'req_interview': False, 'no_colorblind': False},
                {'course_id': 'B', 'course_name': 'High CGPA Margin',
                 'university': 'Y', 'stream': 'science', 'min_cgpa': 2.0,
                 'min_muet_band': 2, 'req_interview': False, 'no_colorblind': False},
            ],
            'student_cgpa': 3.5,
            'student_signals': {},
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        progs = response.json()['ranked_courses']
        assert progs[0]['fit_score'] >= progs[1]['fit_score']

    def test_ranking_missing_courses_400(self):
        """Missing eligible_courses returns 400."""
        data = {'student_cgpa': 3.5}
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        assert response.status_code == 400

    def test_ranking_empty_courses(self):
        """Empty list returns empty result."""
        data = {'eligible_courses': [], 'student_cgpa': 3.5, 'student_signals': {}}
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        body = response.json()
        assert body['ranked_courses'] == []
        assert body['total'] == 0


@pytest.mark.django_db
class TestStpmRankingW11PreQuizRiasec:
    """W11: STPM subjects as free pre-quiz RIASEC signal."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        # Two courses: one I-type (science), one A-type (arts)
        self.science_course = {
            'course_id': 'SCI001', 'course_name': 'BSc Physics',
            'university': 'UM', 'stream': 'science',
            'min_cgpa': 2.5, 'min_muet_band': 3,
            'req_interview': False, 'no_colorblind': False,
            'riasec_type': 'I',
        }
        self.arts_course = {
            'course_id': 'ART001', 'course_name': 'BA Literature',
            'university': 'UM', 'stream': 'arts',
            'min_cgpa': 2.5, 'min_muet_band': 3,
            'req_interview': False, 'no_colorblind': False,
            'riasec_type': 'A',
        }

    def test_science_subjects_boost_investigative_courses(self):
        """Science subjects should boost I-type courses via RIASEC seed."""
        data = {
            'eligible_courses': [self.science_course, self.arts_course],
            'student_cgpa': 3.0,
            'student_signals': {},
            'stpm_subjects': ['physics', 'chemistry', 'biology'],
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        assert response.status_code == 200
        progs = response.json()['ranked_courses']
        # Science student → I-type should rank higher than A-type
        sci = next(p for p in progs if p['course_id'] == 'SCI001')
        art = next(p for p in progs if p['course_id'] == 'ART001')
        assert sci['fit_score'] > art['fit_score']

    def test_arts_subjects_boost_artistic_courses(self):
        """Arts subjects should boost A-type courses."""
        data = {
            'eligible_courses': [self.science_course, self.arts_course],
            'student_cgpa': 3.0,
            'student_signals': {},
            'stpm_subjects': ['literature_english', 'visual_arts', 'history'],
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        progs = response.json()['ranked_courses']
        art = next(p for p in progs if p['course_id'] == 'ART001')
        sci = next(p for p in progs if p['course_id'] == 'SCI001')
        assert art['fit_score'] > sci['fit_score']

    def test_existing_riasec_seed_not_overwritten(self):
        """Post-quiz signals with riasec_seed should NOT be replaced by stpm_subjects."""
        # Student has quiz-derived A-type seed but science subjects
        data = {
            'eligible_courses': [self.science_course, self.arts_course],
            'student_cgpa': 3.0,
            'student_signals': {
                'riasec_seed': {'riasec_A': 5, 'riasec_S': 3},
            },
            'stpm_subjects': ['physics', 'chemistry', 'biology'],
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        progs = response.json()['ranked_courses']
        # Quiz says A-type → arts should still rank higher despite science subjects
        art = next(p for p in progs if p['course_id'] == 'ART001')
        sci = next(p for p in progs if p['course_id'] == 'SCI001')
        assert art['fit_score'] > sci['fit_score']

    def test_no_stpm_subjects_no_effect(self):
        """Without stpm_subjects, pre-quiz ranking is CGPA-only (same as before)."""
        data = {
            'eligible_courses': [self.science_course, self.arts_course],
            'student_cgpa': 3.0,
            'student_signals': {},
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        progs = response.json()['ranked_courses']
        # Both courses have same min_cgpa, so scores should be equal
        assert progs[0]['fit_score'] == progs[1]['fit_score']

    def test_empty_stpm_subjects_no_effect(self):
        """Empty stpm_subjects list has no effect."""
        data = {
            'eligible_courses': [self.science_course, self.arts_course],
            'student_cgpa': 3.0,
            'student_signals': {},
            'stpm_subjects': [],
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        progs = response.json()['ranked_courses']
        assert progs[0]['fit_score'] == progs[1]['fit_score']

    def test_pa_excluded_from_seed(self):
        """pengajian_am (PA) should not contribute to RIASEC seed."""
        data = {
            'eligible_courses': [self.science_course, self.arts_course],
            'student_cgpa': 3.0,
            'student_signals': {},
            'stpm_subjects': ['pengajian_am'],
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        progs = response.json()['ranked_courses']
        # PA alone produces no seed → same as no subjects
        assert progs[0]['fit_score'] == progs[1]['fit_score']

    def test_framing_still_returned(self):
        """Response still includes framing metadata with W11 active."""
        data = {
            'eligible_courses': [self.science_course],
            'student_cgpa': 3.0,
            'student_signals': {},
            'stpm_subjects': ['physics', 'chemistry'],
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        body = response.json()
        assert 'framing' in body


@pytest.mark.django_db
class TestStpmCourseDetailCareerOccupations(TestCase):
    """Test career_occupations in STPM course detail endpoint."""

    def setUp(self):
        self.field, _ = FieldTaxonomy.objects.get_or_create(
            key='it', defaults={
                'name_en': 'IT & Digital', 'name_ms': 'IT & Digital',
                'name_ta': 'IT & Digital', 'image_slug': 'it', 'sort_order': 1,
            })
        self.course = StpmCourse.objects.create(
            course_id='stpm-test-career',
            course_name='Ijazah Sarjana Muda Sains Komputer',
            university='Universiti Malaya',
            field_key=self.field,
        )
        StpmRequirement.objects.create(course=self.course)
        self.occ = MascoOccupation.objects.create(
            masco_code='2512-03',
            job_title='Jurutera Perisian',
            emasco_url='https://emasco.mohr.gov.my/masco/2512-03',
        )
        self.course.career_occupations.add(self.occ)

    def test_career_occupations_included(self):
        resp = self.client.get(f'/api/v1/stpm/courses/{self.course.course_id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('career_occupations', data)
        self.assertEqual(len(data['career_occupations']), 1)

    def test_career_occupation_fields(self):
        resp = self.client.get(f'/api/v1/stpm/courses/{self.course.course_id}/')
        occ = resp.json()['career_occupations'][0]
        self.assertEqual(occ['masco_code'], '2512-03')
        self.assertEqual(occ['job_title'], 'Jurutera Perisian')
        self.assertIn('emasco_url', occ)

    def test_empty_career_occupations(self):
        course2 = StpmCourse.objects.create(
            course_id='stpm-test-empty',
            course_name='Test Empty',
            university='UM',
            field_key=self.field,
        )
        StpmRequirement.objects.create(course=course2)
        resp = self.client.get(f'/api/v1/stpm/courses/{course2.course_id}/')
        self.assertEqual(resp.json()['career_occupations'], [])
