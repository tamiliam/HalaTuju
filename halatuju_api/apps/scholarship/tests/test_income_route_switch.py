"""Student self-serve income route-switch (post-submit Action Centre).

Endpoint POST /api/v1/scholarship/applications/<id>/income-route/. Real-ORM fixtures.
Covers both directions, the recompute of the resolution queue, the no-re-block guarantee
(a submitted student stays profile_complete), validation, auth/scope, and the status gate.
"""
import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ResolutionItem, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.resolution import sync_resolution_items
from apps.scholarship.income_engine import _member_ic_doc

_TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      _TEST_JWT_SECRET, algorithm='HS256')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        # Father route by default (father needs no relationship doc — keeps the ticket set tight).
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'irs-{self.id()}', name='ARJUN A/L MURUGAN',
            nric='080115-05-0132', household_income=1800, household_size=4)
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='profile_complete',
            profile_completed_at=timezone.now(), income_route='str', income_earner='father')

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(self.profile.supabase_user_id)}')

    def _post(self, body):
        self._auth()
        return self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/income-route/', body, format='json')

    def _codes(self, status='open'):
        return sorted(i.code for i in self.app.resolution_items.filter(status=status))


@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestSwitch(_Base):
    def test_str_to_salary_closes_str_gap_keeps_submission(self):
        sync_resolution_items(self.app)                       # seed STR-route tickets
        self.assertIn('income_proof_missing', self._codes('open'))
        r = self._post({'income_route': 'salary', 'income_working_members': ['father']})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['income_route'], 'salary')
        self.app.refresh_from_db()
        self.assertEqual(self.app.income_route, 'salary')
        self.assertEqual(self.app.income_working_members, ['father'])
        self.assertEqual(self.app.income_earner, '')          # inactive field cleared
        # The STR income gap auto-resolved; the salary route still wants father's IC.
        self.assertNotIn('income_proof_missing', self._codes('open'))
        self.assertIn('earner_ic_missing', self._codes('open'))
        # The crux: a submitted student is NOT reverted by gaining new requirements.
        self.assertEqual(self.app.status, 'profile_complete')

    def test_salary_to_str(self):
        self.app.income_route = 'salary'
        self.app.income_earner = ''
        self.app.income_working_members = ['mother']
        self.app.save()
        sync_resolution_items(self.app)
        r = self._post({'income_route': 'str', 'income_earner': 'mother'})
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.income_route, 'str')
        self.assertEqual(self.app.income_earner, 'mother')
        self.assertEqual(self.app.income_working_members, [])
        # STR route now wants the STR document.
        self.assertIn('income_proof_missing', self._codes('open'))

    def test_response_carries_new_requirements(self):
        r = self._post({'income_route': 'salary', 'income_working_members': ['father', 'mother']})
        reqs = r.json()['requirements']
        self.assertEqual(reqs['route'], 'salary')
        self.assertTrue(reqs['members'])                      # per-member doc blocks present

    def test_audit_logged(self):
        with self.assertLogs('apps.scholarship.services', level='INFO') as cm:
            self._post({'income_route': 'salary', 'income_working_members': ['father']})
        self.assertTrue(any('income_route_switch' in m and 'from=str' in m and 'to=salary' in m
                            for m in cm.output))


@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestValidation(_Base):
    def test_str_requires_earner(self):
        r = self._post({'income_route': 'str'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('income_earner', r.json())

    def test_salary_requires_a_member(self):
        r = self._post({'income_route': 'salary', 'income_working_members': []})
        self.assertEqual(r.status_code, 400)
        self.assertIn('income_working_members', r.json())

    def test_salary_rejects_duplicate_members(self):
        r = self._post({'income_route': 'salary', 'income_working_members': ['father', 'father']})
        self.assertEqual(r.status_code, 400)

    def test_bad_route_rejected(self):
        r = self._post({'income_route': 'nonsense', 'income_earner': 'father'})
        self.assertEqual(r.status_code, 400)


@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestAuthAndGate(_Base):
    def test_unauthenticated_401(self):
        r = self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/income-route/',
            {'income_route': 'salary', 'income_working_members': ['father']}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_not_owner_404(self):
        other = StudentProfile.objects.create(supabase_user_id='other-uid', name='X', nric='1')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(other.supabase_user_id)}')
        r = self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/income-route/',
            {'income_route': 'salary', 'income_working_members': ['father']}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_blocked_outside_editable_funnel(self):
        # A recommended/sponsored application is past the editable funnel → 403.
        self.app.status = 'recommended'
        self.app.save(update_fields=['status'])
        r = self._post({'income_route': 'salary', 'income_working_members': ['father']})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json().get('code'), 'not_editable')


@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestTolerantClusterReader(_Base):
    """Slot model (TD-115) tolerant reader: on the STR route the earner's IC is found whether
    it carries the legacy blank tag (pre-backfill) or the earner tag (post-backfill); the
    salary route reads the member tag only (a blank is never attributed to a member)."""

    def _ic(self, member):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='parent_ic', household_member=member,
            storage_path=f'p/{member or "blank"}.png', vision_name='MURUGAN A/L SAMY')

    def test_str_earner_ic_found_when_blank_tagged(self):
        self._ic('')                                   # legacy: untagged earner IC
        self.assertIsNotNone(_member_ic_doc(self.app, 'father'))

    def test_str_earner_ic_found_when_earner_tagged(self):
        self._ic('father')                             # post-backfill: tagged to the earner
        self.assertIsNotNone(_member_ic_doc(self.app, 'father'))

    def test_salary_route_reads_member_tag_only(self):
        self.app.income_route = 'salary'
        self.app.save(update_fields=['income_route'])
        self._ic('')                                   # a stray blank on the salary route
        self.assertIsNone(_member_ic_doc(self.app, 'father'))   # blank never attributed
        self._ic('father')
        self.assertIsNotNone(_member_ic_doc(self.app, 'father'))
