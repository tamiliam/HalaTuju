import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestStpmSearchAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('loaddata', 'stpm_courses', 'stpm_requirements', stdout=StringIO(), verbosity=0)
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
        call_command('loaddata', 'stpm_courses', 'stpm_requirements', stdout=StringIO(), verbosity=0)
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

    def test_stpm_detail_includes_mohe_url(self):
        """STPM detail endpoint returns mohe_url when set."""
        from apps.courses.models import StpmCourse
        course = StpmCourse.objects.first()
        course.mohe_url = 'https://online.mohe.gov.my/epanduan/test'
        course.save(update_fields=['mohe_url'])

        resp = self.client.get(f'/api/v1/stpm/courses/{course.course_id}/')
        assert resp.status_code == 200
        assert resp.json()['mohe_url'] == 'https://online.mohe.gov.my/epanduan/test'

    def test_stpm_detail_mohe_url_empty_when_not_set(self):
        """STPM detail endpoint returns empty string when mohe_url not set."""
        from apps.courses.models import StpmCourse
        course = StpmCourse.objects.first()
        course.mohe_url = ''
        course.save(update_fields=['mohe_url'])

        resp = self.client.get(f'/api/v1/stpm/courses/{course.course_id}/')
        assert resp.status_code == 200
        assert resp.json()['mohe_url'] == ''


@pytest.mark.django_db
class TestStpmDetailSubjectGroups:
    """Tests for human-readable subject group rendering in STPM detail."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from apps.courses.models import FieldTaxonomy, StpmCourse, StpmRequirement
        self.client = APIClient()
        field_key, _ = FieldTaxonomy.objects.get_or_create(
            key='engineering',
            defaults={'name_en': 'Engineering', 'name_ms': 'Kejuruteraan', 'name_ta': 'பொறியியல்', 'image_slug': 'engineering'},
        )
        self.course = StpmCourse.objects.create(
            course_id='TEST001',
            course_name='Test Engineering',
            university='Test University',
            stream='science',
            field_key=field_key,
        )
        self.req = StpmRequirement.objects.create(
            course=self.course,
            stpm_req_physics=True,
            stpm_subject_group=[
                {'min_count': 2, 'min_grade': 'A', 'subjects': ['PHYSICS', 'CHEMISTRY', 'MATH_T']},
                {'min_count': 1, 'min_grade': 'C', 'subjects': None},
            ],
            spm_subject_group=[
                {'min_count': 3, 'min_grade': 'B', 'subjects': ['PHYSICS_SPM', 'CHEMISTRY_SPM', 'MATH']},
                {'min_count': 1, 'min_grade': 'C', 'subjects': None, 'exclude': ['EKONOMI_SPM', 'PERNIAGAAN_SPM']},
            ],
            no_disability=True,
        )

    def test_detail_has_stpm_subject_groups_display(self):
        resp = self.client.get('/api/v1/stpm/courses/TEST001/')
        req = resp.json()['requirements']
        groups = req['stpm_subject_groups_display']
        assert len(groups) == 2
        assert groups[0]['min_count'] == 2
        assert groups[0]['min_grade'] == 'A'
        assert 'Physics' in groups[0]['subjects']
        assert 'Chemistry' in groups[0]['subjects']
        assert 'Mathematics (T)' in groups[0]['subjects']
        assert groups[0]['any_subject'] is False
        assert groups[1]['min_count'] == 1
        assert groups[1]['any_subject'] is True
        assert groups[1]['subjects'] == []

    def test_detail_has_spm_subject_groups_display(self):
        resp = self.client.get('/api/v1/stpm/courses/TEST001/')
        req = resp.json()['requirements']
        groups = req['spm_subject_groups_display']
        assert len(groups) == 2
        assert groups[0]['min_count'] == 3
        assert groups[0]['min_grade'] == 'B'
        assert 'Fizik' in groups[0]['subjects']
        assert 'Kimia' in groups[0]['subjects']
        assert 'Matematik' in groups[0]['subjects']
        assert groups[1]['any_subject'] is True
        assert len(groups[1]['exclude']) == 2
        assert 'Ekonomi' in groups[1]['exclude']

    def test_detail_empty_groups_when_no_subject_group(self):
        self.req.stpm_subject_group = None
        self.req.spm_subject_group = None
        self.req.save()
        resp = self.client.get('/api/v1/stpm/courses/TEST001/')
        req = resp.json()['requirements']
        assert req['stpm_subject_groups_display'] == []
        assert req['spm_subject_groups_display'] == []

    def test_detail_includes_no_disability(self):
        resp = self.client.get('/api/v1/stpm/courses/TEST001/')
        req = resp.json()['requirements']
        assert req['no_disability'] is True
