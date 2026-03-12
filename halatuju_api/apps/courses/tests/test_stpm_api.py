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
