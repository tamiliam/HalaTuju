"""Tests for expanded StudentProfile fields."""
import pytest
from apps.courses.models import StudentProfile, SavedCourse, Course


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
