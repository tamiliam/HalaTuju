"""Tests for expanded StudentProfile fields."""
import pytest
from django.test import RequestFactory
from apps.courses.models import StudentProfile, SavedCourse, Course
from apps.courses.views import ProfileView, SavedCoursesView, SavedCourseDetailView


@pytest.mark.django_db
class TestProfileNewFields:

    def test_profile_has_nric_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-nric',
            nric='010203-14-1234',
        )
        p.refresh_from_db()
        assert p.nric == '010203-14-1234'

    def test_profile_has_address_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-addr',
            address='123 Jalan Merdeka, Petaling Jaya',
        )
        p.refresh_from_db()
        assert p.address == '123 Jalan Merdeka, Petaling Jaya'

    def test_profile_has_phone_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-phone',
            phone='+60123456789',
        )
        p.refresh_from_db()
        assert p.phone == '+60123456789'

    def test_profile_has_family_income_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-income',
            family_income='RM1,001-3,000',
        )
        p.refresh_from_db()
        assert p.family_income == 'RM1,001-3,000'

    def test_profile_has_siblings_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-siblings',
            siblings=3,
        )
        p.refresh_from_db()
        assert p.siblings == 3

    def test_new_fields_default_blank(self):
        p = StudentProfile.objects.create(supabase_user_id='test-defaults')
        p.refresh_from_db()
        assert p.nric == ''
        assert p.address == ''
        assert p.phone == ''
        assert p.family_income == ''
        assert p.siblings is None


@pytest.mark.django_db
class TestSavedCourseInterestStatus:

    def _make_course(self):
        return Course.objects.create(
            course_id='TEST-001',
            course='Test Course',
            level='Diploma',
        )

    def test_default_status_is_interested(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-status')
        course = self._make_course()
        sc = SavedCourse.objects.create(student=profile, course=course)
        sc.refresh_from_db()
        assert sc.interest_status == 'interested'

    def test_can_set_planning_status(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-planning')
        course = Course.objects.create(course_id='TEST-002', course='Test 2', level='Diploma')
        sc = SavedCourse.objects.create(
            student=profile, course=course, interest_status='planning'
        )
        sc.refresh_from_db()
        assert sc.interest_status == 'planning'

    def test_can_set_got_offer_status(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-offer')
        course = Course.objects.create(course_id='TEST-003', course='Test 3', level='Diploma')
        sc = SavedCourse.objects.create(
            student=profile, course=course, interest_status='got_offer'
        )
        sc.refresh_from_db()
        assert sc.interest_status == 'got_offer'


def _auth_request(method, data=None, user_id='api-test-user'):
    """Create a fake authenticated request."""
    factory = RequestFactory()
    if method == 'GET':
        request = factory.get('/api/v1/profile/')
    elif method == 'PUT':
        request = factory.put(
            '/api/v1/profile/',
            data=data,
            content_type='application/json',
        )
    request.user_id = user_id
    request.data = data or {}
    return request


@pytest.mark.django_db
class TestProfileAPINewFields:

    def test_get_profile_returns_new_fields(self):
        StudentProfile.objects.create(
            supabase_user_id='api-test-user',
            nric='010203-14-1234',
            address='Jalan Test',
            phone='+60123456789',
            family_income='RM1,001-3,000',
            siblings=3,
        )
        request = _auth_request('GET')
        response = ProfileView().get(request)
        assert response.status_code == 200
        assert response.data['nric'] == '010203-14-1234'
        assert response.data['address'] == 'Jalan Test'
        assert response.data['phone'] == '+60123456789'
        assert response.data['family_income'] == 'RM1,001-3,000'
        assert response.data['siblings'] == 3

    def test_put_profile_updates_new_fields(self):
        StudentProfile.objects.create(supabase_user_id='api-test-user')
        request = _auth_request('PUT', data={
            'nric': '010203-14-1234',
            'address': 'New Address',
            'phone': '+60199999999',
            'family_income': 'RM3,001-5,000',
            'siblings': 5,
        })
        response = ProfileView().put(request)
        assert response.status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='api-test-user')
        assert p.nric == '010203-14-1234'
        assert p.siblings == 5


@pytest.mark.django_db
class TestSavedCoursesAPIInterestStatus:

    def _setup(self, user_id='saved-api-user'):
        profile = StudentProfile.objects.create(supabase_user_id=user_id)
        course = Course.objects.create(
            course_id='TEST-API-001', course='Test Course', level='Diploma'
        )
        SavedCourse.objects.create(student=profile, course=course)
        return profile, course

    def test_get_saved_courses_includes_interest_status(self):
        self._setup()
        factory = RequestFactory()
        request = factory.get('/api/v1/saved-courses/')
        request.user_id = 'saved-api-user'
        response = SavedCoursesView().get(request)
        assert response.status_code == 200
        assert 'interest_status' in response.data['saved_courses'][0]
        assert response.data['saved_courses'][0]['interest_status'] == 'interested'

    def test_patch_saved_course_updates_status(self):
        self._setup(user_id='patch-user')
        factory = RequestFactory()
        request = factory.patch(
            '/api/v1/saved-courses/TEST-API-001/',
            data={'interest_status': 'planning'},
            content_type='application/json',
        )
        request.user_id = 'patch-user'
        request.data = {'interest_status': 'planning'}
        response = SavedCourseDetailView().patch(request, course_id='TEST-API-001')
        assert response.status_code == 200
        sc = SavedCourse.objects.get(student_id='patch-user', course_id='TEST-API-001')
        assert sc.interest_status == 'planning'
