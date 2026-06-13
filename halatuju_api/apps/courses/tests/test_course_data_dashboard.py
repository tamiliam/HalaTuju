"""Tests for the Course Data dashboard: status helper, live coverage, admin endpoint."""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import (
    PartnerAdmin, Course, CourseRequirement, StpmCourse, MascoOccupation,
    FieldTaxonomy, CourseDataStatus,
)
from apps.courses.course_data_status import (
    record_status, coverage_snapshot, EPANDUAN_STPM, UPTVET, LINK_HEALTH,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


def _course(cid, source_type, level='Diploma'):
    field = FieldTaxonomy.objects.get_or_create(
        key='general',
        defaults={'name_en': 'General', 'name_ms': 'Umum', 'name_ta': 'Pothu', 'image_slug': 'general'},
    )[0]
    c = Course.objects.create(course_id=cid, course=f'Course {cid}', level=level,
                              department='Dept', field='General', field_key=field)
    CourseRequirement.objects.create(course=c, source_type=source_type)
    return c


class TestRecordStatus(TestCase):
    def test_creates_row(self):
        record_status(EPANDUAN_STPM, {'stpm_total': 5}, detail='cmd')
        row = CourseDataStatus.objects.get(key=EPANDUAN_STPM)
        self.assertEqual(row.summary['stpm_total'], 5)
        self.assertEqual(row.detail, 'cmd')
        self.assertIsNotNone(row.last_run_at)

    def test_upserts_not_duplicates(self):
        record_status(LINK_HEALTH, {'dead': 1})
        record_status(LINK_HEALTH, {'dead': 0})
        self.assertEqual(CourseDataStatus.objects.filter(key=LINK_HEALTH).count(), 1)
        self.assertEqual(CourseDataStatus.objects.get(key=LINK_HEALTH).summary['dead'], 0)


class TestCoverageSnapshot(TestCase):
    def test_counts_by_source_and_qualification(self):
        # The test DB may carry migration-seeded rows, so assert DELTAS from a baseline.
        base = coverage_snapshot()
        _course('POLY-1', 'poly')
        _course('TV-1', 'tvet')
        _course('TV-2', 'tvet')
        field = FieldTaxonomy.objects.get(key='general')
        StpmCourse.objects.create(course_id='U1', course_name='Deg', university='UM', is_active=True, field_key=field)
        StpmCourse.objects.create(course_id='U2', course_name='Old', university='UM', is_active=False, field_key=field)
        MascoOccupation.objects.create(masco_code='ZZ-test', job_title='Job')

        snap = coverage_snapshot()
        self.assertEqual(snap['spm_total'] - base['spm_total'], 3)
        self.assertEqual(snap['spm_by_source'].get('tvet', 0) - base['spm_by_source'].get('tvet', 0), 2)
        self.assertEqual(snap['tvet_have'] - base['tvet_have'], 2)
        self.assertEqual(snap['stpm_total'] - base['stpm_total'], 2)
        self.assertEqual(snap['stpm_active'] - base['stpm_active'], 1)
        self.assertEqual(snap['emasco_total'] - base['emasco_total'], 1)

    def test_uptvet_gap_from_stored_inventory(self):
        record_status(UPTVET, {'total': 99999})  # large sentinel, clearly above any seed count
        snap = coverage_snapshot()
        self.assertEqual(snap['uptvet_available'], 99999)
        self.assertEqual(snap['uptvet_gap'], 99999 - snap['tvet_have'])  # gap = available − held

    def test_uptvet_gap_none_without_inventory(self):
        snap = coverage_snapshot()
        self.assertIsNone(snap['uptvet_available'])
        self.assertIsNone(snap['uptvet_gap'])


@override_settings(
    ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
    SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co',
)
class TestAdminCourseDataView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='admin-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@halatuju.com',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid='admin-uid'):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_requires_admin(self):
        self._auth('not-an-admin')
        self.assertEqual(self.client.get('/api/v1/admin/course-data/').status_code, 403)

    def test_returns_statuses_and_coverage(self):
        record_status(EPANDUAN_STPM, {'stpm_total': 7})
        self._auth()
        resp = self.client.get('/api/v1/admin/course-data/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('coverage', data)
        self.assertIn('statuses', data)
        # the recorded key carries its summary...
        self.assertEqual(data['statuses']['epanduan_stpm']['summary']['stpm_total'], 7)
        # ...and every known key is present, missing ones as null ("never run")
        self.assertIn('epanduan_spm', data['statuses'])
        self.assertIsNone(data['statuses']['epanduan_spm'])

    def test_all_six_keys_present(self):
        self._auth()
        data = self.client.get('/api/v1/admin/course-data/').json()
        for key in ('epanduan_stpm', 'epanduan_spm', 'uptvet', 'emasco', 'link_health', 'audit'):
            self.assertIn(key, data['statuses'])
