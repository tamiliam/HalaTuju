"""Tests for expanded StudentProfile fields."""
import pytest
from django.test import RequestFactory
from apps.courses.models import StudentProfile, SavedCourse, Course
from apps.courses.views import ProfileView, ProfileSyncView, SavedCoursesView, SavedCourseDetailView, NricClaimView


@pytest.mark.django_db
class TestProfileNewFields:

    def test_profile_has_nric_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-nric',
            nric='010203-14-1234',
        )
        p.refresh_from_db()
        assert p.nric == '010203-14-1234'

    def test_name_stored_uppercase(self):
        # Owner 2026-07-16: names are normalised to CAPS at the write boundary so every
        # reader shows them consistently.
        p = StudentProfile.objects.create(supabase_user_id='test-name-caps',
                                          name='Shaarveshwaar A/L Sarawanan')
        p.refresh_from_db()
        assert p.name == 'SHAARVESHWAAR A/L SARAWANAN'
        # a later edit is also normalised
        p.name = 'navitha a/p nadaraj'
        p.save()
        p.refresh_from_db()
        assert p.name == 'NAVITHA A/P NADARAJ'
        # blank stays blank (no crash)
        p.name = ''
        p.save(); p.refresh_from_db()
        assert p.name == ''

    def test_profile_has_address_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-addr',
            address='123 Jalan Merdeka, Petaling Jaya',
        )
        p.refresh_from_db()
        assert p.address == '123 Jalan Merdeka, Petaling Jaya'

    def test_profile_has_contact_phone_field(self):
        # TD-061: contact_phone is the canonical phone (legacy `phone` dropped).
        p = StudentProfile.objects.create(
            supabase_user_id='test-phone',
            contact_phone='+60123456789',
        )
        p.refresh_from_db()
        assert p.contact_phone == '+60123456789'

    def test_profile_has_household_income_field(self):
        # TD-061: household_income replaces the legacy free-text family_income.
        p = StudentProfile.objects.create(
            supabase_user_id='test-income',
            household_income=2500,
        )
        p.refresh_from_db()
        assert p.household_income == 2500

    def test_profile_has_household_size_field(self):
        # TD-061: household_size replaces the legacy siblings count.
        p = StudentProfile.objects.create(
            supabase_user_id='test-siblings',
            household_size=5,
        )
        p.refresh_from_db()
        assert p.household_size == 5

    def test_new_fields_default_blank(self):
        p = StudentProfile.objects.create(supabase_user_id='test-defaults')
        p.refresh_from_db()
        assert p.nric == ''
        assert p.address == ''
        assert p.contact_phone == ''
        assert p.household_income is None
        assert p.household_size is None


@pytest.mark.django_db
class TestSavedCourseInterestStatus:

    def _make_course(self):
        return Course.objects.create(
            course_id='TEST-001',
            course='Test Course',
            level='Diploma',
            field_key_id='umum',
        )

    def test_default_status_is_interested(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-status')
        course = self._make_course()
        sc = SavedCourse.objects.create(student=profile, course=course)
        sc.refresh_from_db()
        assert sc.interest_status == 'interested'

    def test_can_set_planning_status(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-planning')
        course = Course.objects.create(course_id='TEST-002', course='Test 2', level='Diploma', field_key_id='umum')
        sc = SavedCourse.objects.create(
            student=profile, course=course, interest_status='planning'
        )
        sc.refresh_from_db()
        assert sc.interest_status == 'planning'

    def test_can_set_got_offer_status(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-offer')
        course = Course.objects.create(course_id='TEST-003', course='Test 3', level='Diploma', field_key_id='umum')
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
            contact_phone='+60123456789',
            household_income=2500,
            household_size=5,
        )
        request = _auth_request('GET')
        response = ProfileView().get(request)
        assert response.status_code == 200
        assert response.data['nric'] == '010203-14-1234'
        assert response.data['address'] == 'Jalan Test'
        assert response.data['contact_phone'] == '+60123456789'
        # TD-061: canonical financial fields replace family_income/siblings.
        assert response.data['household_income'] == 2500
        assert response.data['household_size'] == 5

    def test_put_profile_updates_new_fields(self):
        StudentProfile.objects.create(supabase_user_id='api-test-user')
        request = _auth_request('PUT', data={
            'nric': '010203-14-1234',   # ignored — read-only via PUT (S7 soft-NRIC gap fix)
            'address': 'New Address',
            'contact_phone': '+60199999999',
            'household_income': 3500,
            'household_size': 6,
        })
        response = ProfileView().put(request)
        assert response.status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='api-test-user')
        assert p.address == 'New Address'
        assert p.household_income == 3500
        assert p.household_size == 6
        # NRIC is NOT settable via PUT — it changes only through the validated claim
        # endpoint (/profile/claim-nric/). Closes the soft-NRIC write gap.
        assert p.nric == ''


@pytest.mark.django_db
class TestSavedCoursesAPIInterestStatus:

    def _setup(self, user_id='saved-api-user'):
        profile = StudentProfile.objects.create(supabase_user_id=user_id)
        course = Course.objects.create(
            course_id='TEST-API-001', course='Test Course', level='Diploma',
            field_key_id='umum',
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


@pytest.mark.django_db
class TestStpmProfileFields:
    """Tests for STPM-related fields on StudentProfile."""

    def test_exam_type_default(self):
        """StudentProfile defaults to exam_type='spm'."""
        profile = StudentProfile.objects.create(
            supabase_user_id='test-stpm-default',
            gender='Lelaki',
            nationality='Warganegara',
        )
        assert profile.exam_type == 'spm'

    def test_stpm_fields_stored(self):
        """STPM-specific fields should be stored on profile."""
        profile = StudentProfile.objects.create(
            supabase_user_id='test-stpm-fields',
            gender='Lelaki',
            nationality='Warganegara',
            exam_type='stpm',
            stpm_grades={'PA': 'A', 'MATH_T': 'B+'},
            stpm_cgpa=3.67,
            muet_band=4,
            spm_prereq_grades={'bm': 'A', 'eng': 'B+'},
        )
        assert profile.exam_type == 'stpm'
        assert profile.stpm_grades == {'PA': 'A', 'MATH_T': 'B+'}
        assert profile.stpm_cgpa == 3.67
        assert profile.muet_band == 4
        assert profile.spm_prereq_grades == {'bm': 'A', 'eng': 'B+'}

    def test_stpm_fields_default_empty(self):
        """STPM fields default to empty/null when not set."""
        profile = StudentProfile.objects.create(
            supabase_user_id='test-stpm-empty',
        )
        profile.refresh_from_db()
        assert profile.exam_type == 'spm'
        assert profile.stpm_grades == {}
        assert profile.stpm_cgpa is None
        assert profile.muet_band is None
        assert profile.spm_prereq_grades == {}


@pytest.mark.django_db
class TestProfileSyncStpmFields:
    """Tests for STPM fields via ProfileSyncView."""

    def _sync_request(self, data, user_id='sync-stpm-user'):
        factory = RequestFactory()
        request = factory.post(
            '/api/v1/profile/sync/',
            data=data,
            content_type='application/json',
        )
        request.user_id = user_id
        request.data = data
        return request

    def test_sync_creates_profile_with_stpm_fields(self):
        request = self._sync_request({
            'exam_type': 'stpm',
            'stpm_grades': {'PA': 'A', 'MATH_T': 'B+'},
            'stpm_cgpa': 3.67,
            'muet_band': 4,
            'spm_prereq_grades': {'bm': 'A'},
        })
        response = ProfileSyncView().post(request)
        assert response.status_code == 200
        assert response.data['created'] is True

        profile = StudentProfile.objects.get(supabase_user_id='sync-stpm-user')
        assert profile.exam_type == 'stpm'
        assert profile.stpm_grades == {'PA': 'A', 'MATH_T': 'B+'}
        assert profile.stpm_cgpa == 3.67
        assert profile.muet_band == 4
        assert profile.spm_prereq_grades == {'bm': 'A'}

    def test_sync_persists_coq_score(self):
        """CoQ (co-curricular) score is entered in onboarding and must persist to the
        DB like any other result — the apply form reads it from the profile. Regression
        for the 2.2.0 gap where coq_score was collected client-side but never synced."""
        request = self._sync_request({
            'grades': {'bm': 'A', 'eng': 'B', 'math': 'A'},
            'coq_score': 7.5,
        }, user_id='sync-coq-user')
        response = ProfileSyncView().post(request)
        assert response.status_code == 200
        profile = StudentProfile.objects.get(supabase_user_id='sync-coq-user')
        assert profile.coq_score == 7.5

    def test_sync_updates_existing_profile_stpm_fields(self):
        StudentProfile.objects.create(
            supabase_user_id='sync-stpm-update',
            exam_type='spm',
        )
        request = self._sync_request({
            'exam_type': 'stpm',
            'stpm_cgpa': 3.50,
            'muet_band': 3,
        }, user_id='sync-stpm-update')
        response = ProfileSyncView().post(request)
        assert response.status_code == 200
        assert response.data['created'] is False

        profile = StudentProfile.objects.get(supabase_user_id='sync-stpm-update')
        assert profile.exam_type == 'stpm'
        assert profile.stpm_cgpa == 3.50
        assert profile.muet_band == 3

    def test_get_profile_returns_stpm_fields(self):
        StudentProfile.objects.create(
            supabase_user_id='get-stpm-user',
            exam_type='stpm',
            stpm_grades={'PA': 'A-'},
            stpm_cgpa=3.33,
            muet_band=5,
            spm_prereq_grades={'bm': 'B+'},
        )
        factory = RequestFactory()
        request = factory.get('/api/v1/profile/')
        request.user_id = 'get-stpm-user'
        response = ProfileView().get(request)
        assert response.status_code == 200
        assert response.data['exam_type'] == 'stpm'
        assert response.data['stpm_grades'] == {'PA': 'A-'}
        assert response.data['stpm_cgpa'] == 3.33
        assert response.data['muet_band'] == 5
        assert response.data['spm_prereq_grades'] == {'bm': 'B+'}


@pytest.mark.django_db
class TestContactFields:
    """Contact email/phone fields with verification status."""

    def test_contact_email_default_blank(self):
        profile = StudentProfile.objects.create(supabase_user_id='contact-test-1')
        assert profile.contact_email == ''
        assert profile.contact_email_verified is False

    def test_contact_phone_default_blank(self):
        profile = StudentProfile.objects.create(supabase_user_id='contact-test-2')
        assert profile.contact_phone == ''
        assert profile.contact_phone_verified is False

    def test_contact_email_can_be_set(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='contact-test-3',
            contact_email='test@example.com',
            contact_email_verified=True,
        )
        profile.refresh_from_db()
        assert profile.contact_email == 'test@example.com'
        assert profile.contact_email_verified is True

    def test_contact_phone_can_be_set(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='contact-test-4',
            contact_phone='+60123456789',
            contact_phone_verified=False,
        )
        profile.refresh_from_db()
        assert profile.contact_phone == '+60123456789'
        assert profile.contact_phone_verified is False


@pytest.mark.django_db
class TestNricUniqueness:
    """NRIC is unique only once VERIFIED (soft-NRIC, S7) — editable & duplicable until then."""

    def test_nric_unique_constraint(self):
        from django.db import IntegrityError, transaction
        # Two UNVERIFIED profiles may share an NRIC (still editable, not yet enforced).
        StudentProfile.objects.create(supabase_user_id='nric-uniq-1', nric='040815-01-2022')
        StudentProfile.objects.create(supabase_user_id='nric-uniq-2', nric='040815-01-2022')
        assert StudentProfile.objects.filter(nric='040815-01-2022').count() == 2

        # One can be verified...
        p1 = StudentProfile.objects.get(supabase_user_id='nric-uniq-1')
        p1.nric_verified = True
        p1.save()
        # ...but a SECOND verified profile with the same NRIC is rejected.
        p2 = StudentProfile.objects.get(supabase_user_id='nric-uniq-2')
        p2.nric_verified = True
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                p2.save()

    def test_blank_nric_not_unique(self):
        """Multiple profiles can have blank NRIC (pre-onboarding)."""
        StudentProfile.objects.create(supabase_user_id='blank-nric-1', nric='')
        StudentProfile.objects.create(supabase_user_id='blank-nric-2', nric='')
        assert StudentProfile.objects.filter(nric='').count() == 2


@pytest.mark.django_db
class TestSoftNric:
    """Soft-NRIC (S7): editable until an admin verifies it, then locked. coq + call language persist."""

    def _claim(self, nric, user_id, confirm=False):
        factory = RequestFactory()
        req = factory.post('/api/v1/profile/claim-nric/')
        req.user_id = user_id
        req.data = {'nric': nric, 'confirm': confirm}
        return NricClaimView().post(req)

    def test_get_returns_nric_verified_false_by_default(self):
        StudentProfile.objects.create(supabase_user_id='snric-1')
        request = _auth_request('GET', user_id='snric-1')
        request.supabase_user = {'id': 'snric-1', 'email': 'x@gmail.com'}
        resp = ProfileView().get(request)
        assert resp.data['nric_verified'] is False

    def test_coq_and_call_language_round_trip(self):
        StudentProfile.objects.create(supabase_user_id='snric-coq')
        put = _auth_request('PUT', data={'coq_score': 8.5, 'preferred_call_language': 'ta'},
                            user_id='snric-coq')
        assert ProfileView().put(put).status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='snric-coq')
        assert p.coq_score == 8.5
        assert p.preferred_call_language == 'ta'

    def test_claim_overwrites_while_unverified(self):
        assert self._claim('040815-01-2022', 'snric-edit').data['status'] == 'created'
        # A different NRIC overwrites it while still unverified.
        assert self._claim('050620-10-3344', 'snric-edit').data['status'] == 'created'
        p = StudentProfile.objects.get(supabase_user_id='snric-edit')
        assert p.nric == '050620-10-3344'

    def test_claim_blocked_once_verified(self):
        self._claim('040815-01-2022', 'snric-lock')
        p = StudentProfile.objects.get(supabase_user_id='snric-lock')
        p.nric_verified = True
        p.save()
        resp = self._claim('050620-10-3344', 'snric-lock')
        assert resp.status_code == 403
        assert resp.data.get('code') == 'nric_locked'
        p.refresh_from_db()
        assert p.nric == '040815-01-2022'   # unchanged — locked


@pytest.mark.django_db
class TestProfileContactAPI:
    """Profile API returns and accepts contact fields."""

    def test_get_profile_returns_contact_fields(self):
        StudentProfile.objects.create(
            supabase_user_id='contact-api-1',
            contact_email='test@example.com',
            contact_email_verified=True,
            contact_phone='+60123456789',
            contact_phone_verified=False,
        )
        factory = RequestFactory()
        request = factory.get('/api/v1/profile/')
        request.user_id = 'contact-api-1'
        request.supabase_user = {'id': 'contact-api-1', 'email': 'login@gmail.com'}
        resp = ProfileView.as_view()(request)
        assert resp.data['contact_email'] == 'test@example.com'
        assert resp.data['contact_email_verified'] is True
        assert resp.data['contact_phone'] == '+60123456789'
        assert resp.data['contact_phone_verified'] is False
        assert resp.data['email'] == 'login@gmail.com'

    def test_put_contact_email_resets_verified(self):
        """Editing contact_email resets verification status."""
        StudentProfile.objects.create(
            supabase_user_id='contact-api-2',
            contact_email='old@example.com',
            contact_email_verified=True,
        )
        factory = RequestFactory()
        request = factory.put(
            '/api/v1/profile/',
            data={'contact_email': 'new@example.com'},
            content_type='application/json',
        )
        request.user_id = 'contact-api-2'
        request.supabase_user = {'id': 'contact-api-2', 'email': 'login@gmail.com'}
        resp = ProfileView.as_view()(request)
        assert resp.status_code == 200
        profile = StudentProfile.objects.get(supabase_user_id='contact-api-2')
        assert profile.contact_email == 'new@example.com'
        assert profile.contact_email_verified is False

    def test_put_contact_phone_resets_verified(self):
        """Editing contact_phone resets verification status."""
        StudentProfile.objects.create(
            supabase_user_id='contact-api-3',
            contact_phone='+60111111111',
            contact_phone_verified=True,
        )
        factory = RequestFactory()
        request = factory.put(
            '/api/v1/profile/',
            data={'contact_phone': '+60222222222'},
            content_type='application/json',
        )
        request.user_id = 'contact-api-3'
        request.supabase_user = {'id': 'contact-api-3', 'email': 'login@gmail.com'}
        resp = ProfileView.as_view()(request)
        assert resp.status_code == 200
        profile = StudentProfile.objects.get(supabase_user_id='contact-api-3')
        assert profile.contact_phone == '+60222222222'
        assert profile.contact_phone_verified is False

    def test_put_same_contact_email_keeps_verified(self):
        """Saving the same email value should NOT reset verified status."""
        StudentProfile.objects.create(
            supabase_user_id='contact-api-4',
            contact_email='same@example.com',
            contact_email_verified=True,
        )
        factory = RequestFactory()
        request = factory.put(
            '/api/v1/profile/',
            data={'contact_email': 'same@example.com'},
            content_type='application/json',
        )
        request.user_id = 'contact-api-4'
        request.supabase_user = {'id': 'contact-api-4', 'email': 'login@gmail.com'}
        ProfileView.as_view()(request)
        profile = StudentProfile.objects.get(supabase_user_id='contact-api-4')
        assert profile.contact_email_verified is True  # Should stay True

    def test_get_profile_auto_defaults_contact_email_from_auth(self):
        """When contact_email is blank, the GET response falls back to the auth email
        and reports it as verified (the auth email is already verified by Supabase/Google).
        The DB row is untouched — fallback is read-only and resolves at request time."""
        StudentProfile.objects.create(supabase_user_id='cmail-fallback', contact_email='')
        factory = RequestFactory()
        request = factory.get('/api/v1/profile/')
        request.user_id = 'cmail-fallback'
        request.supabase_user = {'id': 'cmail-fallback', 'email': 'login@gmail.com'}
        resp = ProfileView.as_view()(request)
        assert resp.data['contact_email'] == 'login@gmail.com'
        assert resp.data['contact_email_verified'] is True
        # DB row stays empty — the fallback is computed, not persisted
        profile = StudentProfile.objects.get(supabase_user_id='cmail-fallback')
        assert profile.contact_email == ''

    def test_get_profile_does_not_override_explicit_contact_email(self):
        """A user-set contact_email beats the auth email; verified flag tracks the DB."""
        StudentProfile.objects.create(
            supabase_user_id='cmail-explicit',
            contact_email='parent@example.com',
            contact_email_verified=False,
        )
        factory = RequestFactory()
        request = factory.get('/api/v1/profile/')
        request.user_id = 'cmail-explicit'
        request.supabase_user = {'id': 'cmail-explicit', 'email': 'login@gmail.com'}
        resp = ProfileView.as_view()(request)
        # Student-chosen contact email wins
        assert resp.data['contact_email'] == 'parent@example.com'
        # …and its verification status is the real DB flag (not auto-true)
        assert resp.data['contact_email_verified'] is False
