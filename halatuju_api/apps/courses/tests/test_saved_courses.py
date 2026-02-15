"""
Tests for saved course CRUD operations.

Covers:
- Save a course (POST /api/v1/saved-courses/)
- List saved courses (GET /api/v1/saved-courses/)
- Delete a saved course (DELETE /api/v1/saved-courses/<course_id>/)
"""
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.courses.models import Course

TEST_USER_ID = 'test-user-saved-123'


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestSavedCourseCRUD(TestCase):
    """Full save → list → delete flow for saved courses."""

    def setUp(self):
        self.client = APIClient()
        # Create a test course
        self.course = Course.objects.create(
            course_id='TEST_COURSE_001',
            course='Test Diploma in Engineering',
            level='Diploma',
            department='Engineering',
            field='Mekanikal & Automotif',
            frontend_label='Mekanikal & Automotif',
        )
        # Patch JWT decode to simulate authenticated user
        self._patcher = patch(
            'halatuju.middleware.supabase_auth.jwt.decode',
            return_value={
                'sub': TEST_USER_ID,
                'aud': 'authenticated',
                'role': 'authenticated',
            },
        )
        self._patcher.start()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer fake-but-patched')

    def tearDown(self):
        self._patcher.stop()

    def test_save_course_returns_201(self):
        response = self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_COURSE_001'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)

    def test_save_course_appears_in_list(self):
        # Save the course
        self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_COURSE_001'},
            format='json',
        )
        # List saved courses
        response = self.client.get('/api/v1/saved-courses/')
        self.assertEqual(response.status_code, 200)
        course_ids = [c['course_id'] for c in response.data['saved_courses']]
        self.assertIn('TEST_COURSE_001', course_ids)

    def test_delete_saved_course(self):
        # Save then delete
        self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'TEST_COURSE_001'},
            format='json',
        )
        response = self.client.delete('/api/v1/saved-courses/TEST_COURSE_001/')
        self.assertEqual(response.status_code, 200)

        # Verify it's gone
        response = self.client.get('/api/v1/saved-courses/')
        course_ids = [c['course_id'] for c in response.data['saved_courses']]
        self.assertNotIn('TEST_COURSE_001', course_ids)
