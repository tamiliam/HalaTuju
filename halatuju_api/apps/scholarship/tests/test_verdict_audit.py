"""S5 verdict audit / override capture: pure override logic (audit.py) + the
record-verdict + verdict-metrics admin endpoints."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import audit
from apps.scholarship.models import (
    InterviewSession, ScholarshipApplication, ScholarshipCohort, SponsorProfile,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
REVIEWER, VIEWER, STUDENT = 'audit-reviewer', 'audit-viewer', 'audit-student'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _snapshot(identity='verified', academic='review', income='gap', pathway='verified'):
    """A build_verdict-shaped snapshot (list of four fact dicts)."""
    return [
        {'fact': 'identity', 'status': identity, 'evidence': [], 'unresolved': []},
        {'fact': 'academic', 'status': academic, 'evidence': [], 'unresolved': []},
        {'fact': 'income', 'status': income, 'evidence': [], 'unresolved': []},
        {'fact': 'pathway', 'status': pathway, 'evidence': [], 'unresolved': []},
    ]


# ── Pure override logic ──────────────────────────────────────────────────────

class TestAuditPure(TestCase):
    def test_ai_fact_pass_only_verified(self):
        self.assertTrue(audit.ai_fact_pass('verified'))
        for s in ('review', 'recommend', 'gap', '', None):
            self.assertFalse(audit.ai_fact_pass(s))

    def test_override_when_ai_green_but_officer_fails(self):
        # identity: AI verified, officer FAIL → override (AI too generous)
        r = audit.compute_overrides(_snapshot(identity='verified'),
                                    {'identity': 'fail', 'academic': '', 'income': '', 'pathway': ''})
        ident = next(f for f in r['facts'] if f['fact'] == 'identity')
        self.assertTrue(ident['overridden'])
        self.assertEqual(r['override_count'], 1)
        self.assertEqual(r['decided_count'], 1)

    def test_override_when_ai_cautious_but_officer_passes(self):
        # income: AI gap, officer PASS → override (AI too cautious)
        r = audit.compute_overrides(_snapshot(income='gap'),
                                    {'identity': '', 'academic': '', 'income': 'pass', 'pathway': ''})
        inc = next(f for f in r['facts'] if f['fact'] == 'income')
        self.assertTrue(inc['overridden'])
        self.assertEqual(r['override_count'], 1)

    def test_agreement_is_not_override(self):
        # identity verified+pass (agree green), academic review+fail (agree not-green)
        r = audit.compute_overrides(_snapshot(identity='verified', academic='review'),
                                    {'identity': 'pass', 'academic': 'fail', 'income': '', 'pathway': ''})
        self.assertEqual(r['override_count'], 0)
        self.assertEqual(r['decided_count'], 2)

    def test_undecided_fact_not_counted(self):
        r = audit.compute_overrides(_snapshot(), {})   # officer decided nothing
        self.assertEqual(r['decided_count'], 0)
        self.assertEqual(r['override_count'], 0)
        self.assertTrue(all(not f['decided'] for f in r['facts']))

    def test_facts_order_fixed(self):
        r = audit.compute_overrides(_snapshot(), {})
        self.assertEqual([f['fact'] for f in r['facts']],
                         ['identity', 'academic', 'pathway', 'income'])

    def test_metrics_empty_is_zero_rate(self):
        m = audit.override_metrics([])
        self.assertEqual(m['applications'], 0)
        self.assertEqual(m['override_rate'], 0.0)

    def test_metrics_aggregate_and_rate(self):
        # App1: identity override (verified+fail). App2: income override (gap+pass) + academic agree.
        records = [
            (_snapshot(identity='verified'), {'identity': 'fail', 'academic': '', 'income': '', 'pathway': ''}),
            (_snapshot(income='gap', academic='review'),
             {'identity': '', 'academic': 'fail', 'income': 'pass', 'pathway': ''}),
        ]
        m = audit.override_metrics(records)
        self.assertEqual(m['applications'], 2)
        self.assertEqual(m['fact_decisions'], 3)   # 1 + 2
        self.assertEqual(m['overrides'], 2)
        self.assertEqual(m['override_rate'], round(2 / 3, 4))
        self.assertEqual(m['per_fact']['identity'], {'decided': 1, 'overrides': 1})
        self.assertEqual(m['per_fact']['income'], {'decided': 1, 'overrides': 1})
        self.assertEqual(m['per_fact']['academic'], {'decided': 1, 'overrides': 0})


# ── record-verdict + verdict-metrics endpoints ───────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestRecordVerdictEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id=STUDENT, nric='030101-14-1234', name='Priya')
        cls.app = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile, status='interviewed')
        cls.reviewer = PartnerAdmin.objects.create(supabase_user_id=REVIEWER, role='reviewer', is_active=True, name='Rev', email='r@x.com')
        cls.app.assigned_to = cls.reviewer   # reviewer reviews their assigned applicant
        cls.app.save(update_fields=['assigned_to'])
        PartnerAdmin.objects.create(supabase_user_id=VIEWER, role='admin', is_active=True, name='Vie', email='v@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/record-verdict/'

    def _verdict(self, **kw):
        v = {'identity': 'pass', 'academic': 'fail', 'income': 'pass', 'pathway': 'pass', 'overall': 'accept'}
        v.update(kw)
        return v

    def test_reviewer_records_and_snapshots(self):
        self._auth(REVIEWER)
        r = self.client.post(self._url(), {'officer_verdict': self._verdict(), 'reason': 'Solid case.'}, format='json')
        self.assertEqual(r.status_code, 200)
        app = ScholarshipApplication.objects.get(pk=self.app.id)
        # AI verdict snapshotted (4 facts), officer verdict + audit anchor stored.
        self.assertEqual(len(app.ai_verdict_snapshot), 4)
        self.assertEqual(app.officer_verdict['overall'], 'accept')
        self.assertEqual(app.verdict_reason, 'Solid case.')
        self.assertEqual(app.verdict_decided_by, 'r@x.com')
        self.assertIsNotNone(app.verdict_decided_at)

    def test_viewer_forbidden(self):
        self._auth(VIEWER)
        r = self.client.post(self._url(), {'officer_verdict': self._verdict()}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_missing_verdict_400(self):
        self._auth(REVIEWER)
        r = self.client.post(self._url(), {'reason': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'verdict_required')

    def test_bad_fact_value_400(self):
        self._auth(REVIEWER)
        r = self.client.post(self._url(), {'officer_verdict': self._verdict(identity='maybe')}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_verdict')

    def test_incomplete_verdict_rejected_and_not_recorded(self):
        # A blank fact must NOT record a decision (the app #4 'Save with blanks' bug).
        self._auth(REVIEWER)
        r = self.client.post(self._url(),
                             {'officer_verdict': self._verdict(academic=''), 'finalise': True},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'verdict_incomplete')
        self.assertIn('academic', r.json()['facts'])
        self.assertIsNone(ScholarshipApplication.objects.get(pk=self.app.id).verdict_decided_at)

    @patch('apps.scholarship.views_admin.refine_sponsor_profile')
    def test_finalise_runs_when_draft_and_interview_exist(self, mock_refine):
        mock_refine.return_value = {'markdown': '## Final v2', 'model_used': 'gemini-2.5-flash'}
        SponsorProfile.objects.create(application=self.app, draft_markdown='## Draft')
        InterviewSession.objects.create(application=self.app, status='submitted', submitted_at=timezone.now())
        self._auth(REVIEWER)
        r = self.client.post(self._url(), {'officer_verdict': self._verdict(), 'finalise': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['finalise_result']['ok'])
        sp = SponsorProfile.objects.get(application=self.app)
        self.assertEqual(sp.final_markdown, '## Final v2')
        # One profile: the final is mirrored onto the sponsor/pool field too.
        self.assertEqual(sp.anon_markdown, '## Final v2')

    @patch('apps.scholarship.views_admin.refine_sponsor_profile')
    def test_finalise_skipped_without_draft_but_verdict_still_recorded(self, mock_refine):
        # No draft profile → finalise can't run, but the verdict audit must still persist.
        self._auth(REVIEWER)
        r = self.client.post(self._url(), {'officer_verdict': self._verdict(), 'finalise': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['finalise_result'], {'ok': False, 'code': 'no_draft'})
        mock_refine.assert_not_called()
        self.assertIsNotNone(ScholarshipApplication.objects.get(pk=self.app.id).verdict_decided_at)

    def test_detail_get_exposes_audit_fields(self):
        self.app.assigned_to = PartnerAdmin.objects.get(supabase_user_id=REVIEWER)
        self.app.save(update_fields=['assigned_to'])
        self._auth(REVIEWER)
        self.client.post(self._url(), {'officer_verdict': self._verdict(), 'reason': 'note'}, format='json')
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['officer_verdict']['overall'], 'accept')
        self.assertEqual(body['verdict_reason'], 'note')
        self.assertEqual(len(body['ai_verdict_snapshot']), 4)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestVerdictMetricsEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        PartnerAdmin.objects.create(supabase_user_id=REVIEWER, role='reviewer', is_active=True, name='Rev', email='r@x.com')
        # Two decided apps (one override each) + one undecided (must be excluded).
        for i, (snap, ov) in enumerate([
            (_snapshot(identity='verified'), {'identity': 'fail', 'academic': '', 'income': '', 'pathway': ''}),
            (_snapshot(income='gap'), {'identity': '', 'academic': '', 'income': 'pass', 'pathway': ''}),
        ]):
            p = StudentProfile.objects.create(supabase_user_id=f'm{i}', nric=f'03010{i}-14-1234', name=f'A{i}')
            ScholarshipApplication.objects.create(
                cohort=cls.cohort, profile=p, status='interviewed',
                ai_verdict_snapshot=snap, officer_verdict=ov, verdict_decided_at=timezone.now())
        pu = StudentProfile.objects.create(supabase_user_id='undecided', nric='030199-14-1234', name='U')
        ScholarshipApplication.objects.create(cohort=cls.cohort, profile=pu, status='interviewed')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_metrics_excludes_undecided_and_computes_rate(self):
        self._auth(REVIEWER)
        r = self.client.get('/api/v1/admin/scholarship/verdict-metrics/')
        self.assertEqual(r.status_code, 200)
        m = r.json()
        self.assertEqual(m['applications'], 2)          # the undecided app is excluded
        self.assertEqual(m['overrides'], 2)
        self.assertEqual(m['fact_decisions'], 2)
        self.assertEqual(m['override_rate'], 1.0)

    def test_requires_admin(self):
        # No credentials → 401 (not authenticated); a valid non-admin token → 403 (admin guard).
        self.assertEqual(self.client.get('/api/v1/admin/scholarship/verdict-metrics/').status_code, 401)
        self._auth(STUDENT)
        self.assertEqual(self.client.get('/api/v1/admin/scholarship/verdict-metrics/').status_code, 403)
