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

    def test_search_returns_courses(self):
        resp = self.client.get('/api/v1/stpm/search/')
        data = resp.json()
        assert 'courses' in data
        assert 'total_count' in data
        assert 'filters' in data
        assert data['total_count'] > 0

    def test_search_text_filter(self):
        resp = self.client.get('/api/v1/stpm/search/?q=kejuruteraan')
        data = resp.json()
        assert data['total_count'] > 0
        for prog in data['courses']:
            assert 'kejuruteraan' in prog['course_name'].lower() or 'engineering' in prog['course_name'].lower()

    def test_search_university_filter(self):
        resp_all = self.client.get('/api/v1/stpm/search/')
        resp_um = self.client.get('/api/v1/stpm/search/?university=UM')
        assert resp_um.json()['total_count'] <= resp_all.json()['total_count']
        for prog in resp_um.json()['courses']:
            assert prog['university'] == 'UM'

    def test_search_stream_filter(self):
        resp = self.client.get('/api/v1/stpm/search/?stream=science')
        data = resp.json()
        for prog in data['courses']:
            assert prog['stream'] in ('science', 'both')

    def test_search_pagination(self):
        resp1 = self.client.get('/api/v1/stpm/search/?limit=5&offset=0')
        resp2 = self.client.get('/api/v1/stpm/search/?limit=5&offset=5')
        data1 = resp1.json()
        data2 = resp2.json()
        assert len(data1['courses']) == 5
        assert len(data2['courses']) == 5
        assert data1['courses'][0]['course_id'] != data2['courses'][0]['course_id']

    def test_search_filters_list(self):
        resp = self.client.get('/api/v1/stpm/search/')
        filters = resp.json()['filters']
        assert 'universities' in filters
        assert 'streams' in filters
        assert len(filters['universities']) > 0

    def test_search_course_shape(self):
        resp = self.client.get('/api/v1/stpm/search/?limit=1')
        prog = resp.json()['courses'][0]
        assert 'course_id' in prog
        assert 'course_name' in prog
        assert 'university' in prog
        assert 'stream' in prog
        assert 'min_cgpa' in prog
        assert 'min_muet_band' in prog
        assert 'req_interview' in prog


@pytest.mark.django_db
class TestStpmCourseDetailAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('load_stpm_data', stdout=StringIO())
        self.client = APIClient()

    def test_detail_returns_200(self):
        resp = self.client.get('/api/v1/stpm/search/?limit=1')
        prog_id = resp.json()['courses'][0]['course_id']
        resp = self.client.get(f'/api/v1/stpm/courses/{prog_id}/')
        assert resp.status_code == 200

    def test_detail_returns_course_data(self):
        resp = self.client.get('/api/v1/stpm/search/?limit=1')
        prog_id = resp.json()['courses'][0]['course_id']
        resp = self.client.get(f'/api/v1/stpm/courses/{prog_id}/')
        data = resp.json()
        assert data['course_id'] == prog_id
        assert 'course_name' in data
        assert 'university' in data
        assert 'stream' in data
        assert 'requirements' in data
        req = data['requirements']
        assert 'min_cgpa' in req
        assert 'min_muet_band' in req
        assert 'stpm_subjects' in req
        assert 'spm_prerequisites' in req

    def test_detail_404_for_missing(self):
        resp = self.client.get('/api/v1/stpm/courses/NONEXISTENT/')
        assert resp.status_code == 404

    def test_detail_stpm_subjects_list(self):
        resp = self.client.get('/api/v1/stpm/search/?limit=1')
        prog_id = resp.json()['courses'][0]['course_id']
        resp = self.client.get(f'/api/v1/stpm/courses/{prog_id}/')
        subjects = resp.json()['requirements']['stpm_subjects']
        assert isinstance(subjects, list)
