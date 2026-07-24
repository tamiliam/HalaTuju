"""Income-route reconciliation — align the stored route with the evidence that cleared the gate.

Two changes tested together (they belong together, per the owner 2026-07-24):

  1. SYMMETRIC GATE — the salary route now honours a dispositive STR (household_str_status), exactly
     as the STR route already honours a complete salary cluster. Without it, a genuinely-STR student
     who picked 'salary' was trapped before ever reaching consent.
  2. RECONCILE AT CONSENT — when the student consents, the route is silently switched to whichever
     evidence actually settled income, so the officer's verdict reads the correct route (no false
     route-mismatch red, e.g. #114).
"""
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship import services

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ENGINE = 'apps.scholarship.income_engine'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40 Programme', year=2026)

    def _app(self, *, route, uid=None):
        p = StudentProfile.objects.create(
            supabase_user_id=uid or f'u{StudentProfile.objects.count()}', name='Stu')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='shortlisted', notify_email='s@x.com',
            income_route=route, income_earner='father' if route == 'str' else '')


def _patch_signals(*, str_status, salary_ok, members=('father',)):
    """Patch the four income-engine signals reconcile/gate read (imported at call time)."""
    return [
        mock.patch(f'{ENGINE}.household_str_status', return_value=str_status),
        mock.patch(f'{ENGINE}.salary_income_satisfied', return_value=salary_ok),
        mock.patch(f'{ENGINE}.effective_working_members', return_value=list(members)),
        mock.patch(f'{ENGINE}.member_cluster_complete', return_value=True),
    ]


class TestReconcileLogic(_Base):
    """reconcile_income_route: switch only when the DECLARED route isn't what cleared income."""

    def _run(self, *, route, str_status, salary_ok, members=('father',)):
        patches = _patch_signals(str_status=str_status, salary_ok=salary_ok, members=members)
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        app = self._app(route=route)
        with mock.patch.object(services, 'switch_income_route') as sw:
            result = services.reconcile_income_route(app, by='test')
        return result, sw

    def test_str_route_cleared_by_salary_switches_to_salary(self):
        # #114: declared STR, no valid STR on file, but a complete salary cluster.
        result, sw = self._run(route='str', str_status=(None, None), salary_ok=True)
        self.assertEqual(result, 'salary')
        sw.assert_called_once()
        self.assertEqual(sw.call_args.kwargs['route'], 'salary')
        self.assertEqual(sw.call_args.kwargs['members'], ['father'])

    def test_salary_route_cleared_by_str_switches_to_str(self):
        result, sw = self._run(route='salary', str_status=('current', 'father'), salary_ok=False)
        self.assertEqual(result, 'str')
        sw.assert_called_once()
        self.assertEqual(sw.call_args.kwargs['route'], 'str')
        self.assertEqual(sw.call_args.kwargs['earner'], 'father')

    def test_no_switch_when_declared_str_matches_a_valid_str(self):
        _result, sw = self._run(route='str', str_status=('current', 'father'), salary_ok=False)
        sw.assert_not_called()

    def test_no_switch_when_declared_salary_matches_a_cluster(self):
        _result, sw = self._run(route='salary', str_status=(None, None), salary_ok=True)
        sw.assert_not_called()

    def test_no_switch_when_both_hold(self):
        # An honest household with both a valid STR and a full salary cluster keeps its declaration.
        _result, sw = self._run(route='str', str_status=('current', 'father'), salary_ok=True)
        sw.assert_not_called()


class TestSalaryGateHonoursStr(_Base):
    """income_doc_blockers: the salary route clears on a dispositive STR (the symmetric-gate fix)."""

    def test_valid_str_clears_the_salary_route(self):
        app = self._app(route='salary')   # no workers ticked, no docs
        with mock.patch(f'{ENGINE}.household_str_status', return_value=('current', 'father')):
            self.assertEqual(services.income_doc_blockers(app), [])

    def test_no_str_and_no_workers_still_blocks(self):
        app = self._app(route='salary')
        with mock.patch(f'{ENGINE}.household_str_status', return_value=(None, None)):
            self.assertEqual(services.income_doc_blockers(app), ['income_incomplete'])


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestConsentReconcilesRoute(_Base):
    """The consent endpoint fires the reconcile — a mismatched student is switched on consent."""

    def test_consent_switches_str_to_salary(self):
        app = self._app(route='str', uid='consent-uid')
        app.profile.nric = '850101-01-5555'   # clear the NRIC gate (adult, unverified)
        app.profile.save(update_fields=['nric'])
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("consent-uid")}')
        patches = _patch_signals(str_status=(None, None), salary_ok=True)
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        # Bypass the (separately-tested) consent gate + minor path; capture the switch.
        with mock.patch('apps.scholarship.views.consent_blockers', return_value=[]), \
             mock.patch('apps.scholarship.views.is_minor', return_value=False), \
             mock.patch.object(services, 'switch_income_route') as sw:
            r = client.post('/api/v1/scholarship/consent/', {'granted_by': 'self'}, format='json')
        self.assertEqual(r.status_code, 201)
        sw.assert_called_once()
        self.assertEqual(sw.call_args.kwargs['route'], 'salary')
