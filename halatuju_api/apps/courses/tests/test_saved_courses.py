"""
Tests for saved course CRUD operations.

Covers:
- Save an SPM course (POST /api/v1/saved-courses/)
- Save an STPM course (POST with stpm- prefix or course_type)
- List saved courses (GET /api/v1/saved-courses/)
- List with qualification filter (GET ?qualification=SPM|STPM)
- Delete a saved course (DELETE /api/v1/saved-courses/<course_id>/)
- Patch interest status (PATCH /api/v1/saved-courses/<course_id>/)
- Idempotent save (same course twice → 201, no duplicate)
- Auto-detect STPM from stpm-* prefix
- course_type field in response
- Check constraint enforcement (model level)
"""
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.db import IntegrityError
from rest_framework.test import APIClient
from apps.courses.models import Course, StpmCourse, SavedCourse, StudentProfile

TEST_USER_ID = 'test-user-saved-123'


def _setup_auth(test_case):
    """Shared JWT mock setup for authenticated requests."""
    test_case._header_patcher = patch(
        'halatuju.middleware.supabase_auth.jwt.get_unverified_header',
        return_value={'alg': 'HS256'},
    )
    test_case._decode_patcher = patch(
        'halatuju.middleware.supabase_auth.jwt.decode',
        return_value={
            'sub': TEST_USER_ID,
            'aud': 'authenticated',
            'role': 'authenticated',
        },
    )
    test_case._header_patcher.start()
    test_case._decode_patcher.start()
    test_case.client.credentials(HTTP_AUTHORIZATION='Bearer fake-but-patched')


def _teardown_auth(test_case):
    test_case._decode_patcher.stop()
    test_case._header_patcher.stop()


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestSavedCourseSPM(TestCase):
    """SPM save → list → delete flow (existing behaviour, preserved)."""

    def setUp(self):
        self.client = APIClient()
        self.course = Course.objects.create(
            course_id='TEST_COURSE_001',
            course='Test Diploma in Engineering',
            level='Diploma',
            department='Engineering',
            field='Mekanikal & Automotif',
            field_key_id='mekanikal',
        )
        _setup_auth(self)

    def tearDown(self):
        _teardown_auth(self)

    def test_save_spm_course_returns_201(self):
        response = self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_COURSE_001'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)

    def test_save_spm_course_appears_in_list(self):
        self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_COURSE_001'},
            format='json',
        )
        response = self.client.get('/api/v1/saved-courses/')
        self.assertEqual(response.status_code, 200)
        course_ids = [c['course_id'] for c in response.data['saved_courses']]
        self.assertIn('TEST_COURSE_001', course_ids)

    def test_list_includes_course_type_spm(self):
        self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_COURSE_001'},
            format='json',
        )
        response = self.client.get('/api/v1/saved-courses/')
        self.assertEqual(response.data['saved_courses'][0]['course_type'], 'spm')

    def test_delete_spm_saved_course(self):
        self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_COURSE_001'},
            format='json',
        )
        response = self.client.delete('/api/v1/saved-courses/TEST_COURSE_001/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/api/v1/saved-courses/')
        course_ids = [c['course_id'] for c in response.data['saved_courses']]
        self.assertNotIn('TEST_COURSE_001', course_ids)

    def test_idempotent_save_no_duplicate(self):
        self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_COURSE_001'},
            format='json',
        )
        response = self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_COURSE_001'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        response = self.client.get('/api/v1/saved-courses/')
        self.assertEqual(len(response.data['saved_courses']), 1)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestSavedCourseSTPM(TestCase):
    """STPM course save/list/delete/patch flow."""

    def setUp(self):
        self.client = APIClient()
        self.spm_course = Course.objects.create(
            course_id='TEST_SPM_001',
            course='Test Diploma',
            level='Diploma',
            department='Engineering',
            field='Mekanikal',
            field_key_id='mekanikal',
        )
        self.stpm_course = StpmCourse.objects.create(
            course_id='stpm-sains-001',
            course_name='Sarjana Muda Sains Komputer',
            university='Universiti Malaya',
            stream='science',
            field='Computer Science',
            field_key_id='it-perisian',
        )
        _setup_auth(self)

    def tearDown(self):
        _teardown_auth(self)

    def test_save_stpm_course_returns_201(self):
        response = self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'stpm-sains-001'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)

    def test_save_stpm_auto_detect_from_prefix(self):
        """stpm- prefix triggers STPM lookup without explicit course_type."""
        response = self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'stpm-sains-001'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        saved = SavedCourse.objects.get(student_id=TEST_USER_ID)
        self.assertIsNotNone(saved.stpm_course_id)
        self.assertIsNone(saved.course_id)

    def test_save_stpm_explicit_course_type(self):
        """Explicit course_type='stpm' also works."""
        response = self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'stpm-sains-001', 'course_type': 'stpm'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)

    def test_list_stpm_includes_course_type(self):
        self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'stpm-sains-001'},
            format='json',
        )
        response = self.client.get('/api/v1/saved-courses/')
        stpm_entry = [c for c in response.data['saved_courses']
                      if c['course_id'] == 'stpm-sains-001']
        self.assertEqual(len(stpm_entry), 1)
        self.assertEqual(stpm_entry[0]['course_type'], 'stpm')

    def test_list_both_types(self):
        """Saving one SPM and one STPM → list returns both."""
        self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_SPM_001'},
            format='json',
        )
        self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'stpm-sains-001'},
            format='json',
        )
        response = self.client.get('/api/v1/saved-courses/')
        self.assertEqual(len(response.data['saved_courses']), 2)
        types = {c['course_type'] for c in response.data['saved_courses']}
        self.assertEqual(types, {'spm', 'stpm'})

    def test_filter_by_qualification_spm(self):
        self.client.post('/api/v1/saved-courses/', {'course_id': 'TEST_SPM_001'}, format='json')
        self.client.post('/api/v1/saved-courses/', {'course_id': 'stpm-sains-001'}, format='json')

        response = self.client.get('/api/v1/saved-courses/?qualification=SPM')
        self.assertEqual(len(response.data['saved_courses']), 1)
        self.assertEqual(response.data['saved_courses'][0]['course_type'], 'spm')

    def test_filter_by_qualification_stpm(self):
        self.client.post('/api/v1/saved-courses/', {'course_id': 'TEST_SPM_001'}, format='json')
        self.client.post('/api/v1/saved-courses/', {'course_id': 'stpm-sains-001'}, format='json')

        response = self.client.get('/api/v1/saved-courses/?qualification=STPM')
        self.assertEqual(len(response.data['saved_courses']), 1)
        self.assertEqual(response.data['saved_courses'][0]['course_type'], 'stpm')

    def test_delete_stpm_saved_course(self):
        self.client.post('/api/v1/saved-courses/', {'course_id': 'stpm-sains-001'}, format='json')
        response = self.client.delete('/api/v1/saved-courses/stpm-sains-001/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/api/v1/saved-courses/')
        self.assertEqual(len(response.data['saved_courses']), 0)

    def test_patch_stpm_interest_status(self):
        self.client.post('/api/v1/saved-courses/', {'course_id': 'stpm-sains-001'}, format='json')
        response = self.client.patch(
            '/api/v1/saved-courses/stpm-sains-001/',
            {'interest_status': 'applied'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        saved = SavedCourse.objects.get(student_id=TEST_USER_ID, stpm_course_id='stpm-sains-001')
        self.assertEqual(saved.interest_status, 'applied')

    def test_save_nonexistent_stpm_returns_404(self):
        response = self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'stpm-fake-999'},
            format='json',
        )
        self.assertEqual(response.status_code, 404)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestSavedCourseConstraint(TestCase):
    """Check constraint: exactly one FK must be set."""

    def test_both_null_rejected(self):
        profile = StudentProfile.objects.create(supabase_user_id='constraint-test')
        with self.assertRaises(IntegrityError):
            SavedCourse.objects.create(
                student=profile,
                course=None,
                stpm_course=None,
            )

    def test_both_set_rejected(self):
        profile = StudentProfile.objects.create(supabase_user_id='constraint-test-2')
        course = Course.objects.create(
            course_id='CONST-SPM', course='Test', level='Diploma',
            field_key_id='umum',
        )
        stpm = StpmCourse.objects.create(
            course_id='stpm-const-001', course_name='Test STPM',
            university='UM', stream='science',
            field_key_id='umum',
        )
        with self.assertRaises(IntegrityError):
            SavedCourse.objects.create(
                student=profile,
                course=course,
                stpm_course=stpm,
            )
