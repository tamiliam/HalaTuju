import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestStpmSearchAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('load_stpm_data', stdout=StringIO())
        self.client = APIClient()

    def test_search_returns_200(self):
        resp = self.client.get('/api/v1/stpm/search/')
        assert resp.status_code == 200

    def test_search_returns_programmes(self):
        resp = self.client.get('/api/v1/stpm/search/')
        data = resp.json()
        assert 'programmes' in data
        assert 'total_count' in data
        assert 'filters' in data
        assert data['total_count'] > 0

    def test_search_text_filter(self):
        resp = self.client.get('/api/v1/stpm/search/?q=kejuruteraan')
        data = resp.json()
        assert data['total_count'] > 0
        for prog in data['programmes']:
            assert 'kejuruteraan' in prog['program_name'].lower() or 'engineering' in prog['program_name'].lower()

    def test_search_university_filter(self):
        resp_all = self.client.get('/api/v1/stpm/search/')
        resp_um = self.client.get('/api/v1/stpm/search/?university=UM')
        assert resp_um.json()['total_count'] <= resp_all.json()['total_count']
        for prog in resp_um.json()['programmes']:
            assert prog['university'] == 'UM'

    def test_search_stream_filter(self):
        resp = self.client.get('/api/v1/stpm/search/?stream=science')
        data = resp.json()
        for prog in data['programmes']:
            assert prog['stream'] in ('science', 'both')

    def test_search_pagination(self):
        resp1 = self.client.get('/api/v1/stpm/search/?limit=5&offset=0')
        resp2 = self.client.get('/api/v1/stpm/search/?limit=5&offset=5')
        data1 = resp1.json()
        data2 = resp2.json()
        assert len(data1['programmes']) == 5
        assert len(data2['programmes']) == 5
        assert data1['programmes'][0]['program_id'] != data2['programmes'][0]['program_id']

    def test_search_filters_list(self):
        resp = self.client.get('/api/v1/stpm/search/')
        filters = resp.json()['filters']
        assert 'universities' in filters
        assert 'streams' in filters
        assert len(filters['universities']) > 0

    def test_search_programme_shape(self):
        resp = self.client.get('/api/v1/stpm/search/?limit=1')
        prog = resp.json()['programmes'][0]
        assert 'program_id' in prog
        assert 'program_name' in prog
        assert 'university' in prog
        assert 'stream' in prog
        assert 'min_cgpa' in prog
        assert 'min_muet_band' in prog
        assert 'req_interview' in prog
