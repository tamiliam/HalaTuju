import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestStpmEligibilityAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('load_stpm_data', stdout=StringIO())
        self.client = APIClient()

    def test_endpoint_exists(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {
            'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            'cgpa': 3.8,
            'muet_band': 4,
        }, format='json')
        assert resp.status_code == 200

    def test_returns_eligible_programmes(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {
            'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'},
            'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A+'},
            'cgpa': 3.89,
            'muet_band': 4,
        }, format='json')
        data = resp.json()
        assert 'eligible_programmes' in data
        assert len(data['eligible_programmes']) > 0

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
        assert data['total_eligible'] == len(data['eligible_programmes'])


@pytest.mark.django_db
class TestStpmRankingAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_ranking_returns_200(self):
        """POST /api/v1/stpm/ranking/ returns 200 with valid input."""
        data = {
            'eligible_programmes': [
                {
                    'program_id': 'TEST001', 'program_name': 'Test Programme',
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

    def test_ranking_returns_scored_programmes(self):
        """Response includes fit_score and fit_reasons on each programme."""
        data = {
            'eligible_programmes': [
                {
                    'program_id': 'TEST001', 'program_name': 'Test',
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
        assert 'ranked_programmes' in body
        assert 'total' in body
        assert body['total'] == 1
        prog = body['ranked_programmes'][0]
        assert 'fit_score' in prog
        assert 'fit_reasons' in prog

    def test_ranking_sorted_desc(self):
        """Programmes returned sorted by fit_score descending."""
        data = {
            'eligible_programmes': [
                {'program_id': 'A', 'program_name': 'Low CGPA Margin',
                 'university': 'X', 'stream': 'arts', 'min_cgpa': 3.4,
                 'min_muet_band': 4, 'req_interview': False, 'no_colorblind': False},
                {'program_id': 'B', 'program_name': 'High CGPA Margin',
                 'university': 'Y', 'stream': 'science', 'min_cgpa': 2.0,
                 'min_muet_band': 2, 'req_interview': False, 'no_colorblind': False},
            ],
            'student_cgpa': 3.5,
            'student_signals': {},
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        progs = response.json()['ranked_programmes']
        assert progs[0]['fit_score'] >= progs[1]['fit_score']

    def test_ranking_missing_programmes_400(self):
        """Missing eligible_programmes returns 400."""
        data = {'student_cgpa': 3.5}
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        assert response.status_code == 400

    def test_ranking_empty_programmes(self):
        """Empty list returns empty result."""
        data = {'eligible_programmes': [], 'student_cgpa': 3.5, 'student_signals': {}}
        response = self.client.post('/api/v1/stpm/ranking/', data, format='json')
        body = response.json()
        assert body['ranked_programmes'] == []
        assert body['total'] == 0
