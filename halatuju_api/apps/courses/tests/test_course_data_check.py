"""Tests for the read-only course-data health check (command + admin trigger endpoint).

`check_url` is mocked everywhere so no real network. The check NEVER writes to the catalogue.
"""
import jwt
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import (
    PartnerAdmin, Institution, CourseInstitution, Course, FieldTaxonomy, CourseDataStatus,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
VCMD = 'apps.courses.management.commands.validate_course_urls'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _fake_check(url, timeout=10, retries=1):
    return ('dead', 404) if 'dead' in url else ('alive', 200)


def _seed_links():
    ft = FieldTaxonomy.objects.create(key='k', name_en='K', name_ms='K', name_ta='K', image_slug='k')
    c = Course.objects.create(course_id='C1', course='X', level='Diploma', department='D', field='F', field_key=ft)
    inst = Institution.objects.create(institution_id='I1', institution_name='U', type='IPTA',
                                      state='Selangor', url='http://alive.test')
    CourseInstitution.objects.create(course=c, institution=inst, hyperlink='http://dead.test')


class CourseDataCheckCommandTest(TestCase):
    @patch(f'{VCMD}.check_url', side_effect=_fake_check)
    def test_runs_both_and_records_status(self, _c):
        _seed_links()
        call_command('course_data_check', stdout=StringIO())
        # Both reporters recorded their dashboard status.
        self.assertTrue(CourseDataStatus.objects.filter(key='link_health').exists())
        self.assertTrue(CourseDataStatus.objects.filter(key='audit').exists())
        lh = CourseDataStatus.objects.get(key='link_health')
        # The seeded 'http://dead.test' is counted dead; at least one alive. (DB may carry seed URLs.)
        self.assertGreaterEqual(lh.summary['dead'], 1)
        self.assertGreaterEqual(lh.summary['alive'], 1)

    @patch(f'{VCMD}.check_url', side_effect=_fake_check)
    def test_never_clears_links(self, _c):
        _seed_links()
        call_command('course_data_check', stdout=StringIO())
        # No --fix anywhere → MY dead link is NOT cleared (read-only).
        self.assertEqual(Institution.objects.get(institution_id='I1').url, 'http://alive.test')
        self.assertTrue(CourseInstitution.objects.filter(hyperlink='http://dead.test').exists())


@override_settings(
    ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
    SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co',
)
class AdminCourseDataCheckViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@halatuju.com')
        cls.viewer = PartnerAdmin.objects.create(
            supabase_user_id='viewer-uid', role='viewer', is_active=True,
            name='Viewer', email='viewer@halatuju.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_requires_admin(self):
        self._auth('nobody')
        self.assertEqual(self.client.post('/api/v1/admin/course-data/check/').status_code, 403)

    def test_viewer_forbidden(self):
        self._auth('viewer-uid')
        self.assertEqual(self.client.post('/api/v1/admin/course-data/check/').status_code, 403)

    @patch(f'{VCMD}.check_url', side_effect=_fake_check)
    def test_super_runs_and_returns_fresh_payload(self, _c):
        _seed_links()
        self._auth('super-uid')
        resp = self.client.post('/api/v1/admin/course-data/check/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('statuses', data)
        self.assertIn('coverage', data)
        # the check ran → link_health now populated in the returned payload
        self.assertIsNotNone(data['statuses']['link_health'])
        self.assertGreaterEqual(data['statuses']['link_health']['summary']['dead'], 1)
