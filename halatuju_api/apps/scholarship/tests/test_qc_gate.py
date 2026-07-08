"""QC (quality-control) gate — the repurposed `interviewed` stage (2026-07).

A reviewer's verify-accept lands a case in `interviewed` = AWAITING QC. A `qc`-role admin (or super)
then Accepts (→ recommended) or Reopens (→ back to the reviewer at `interviewing`, with the gaps
comments emailed to the assigned reviewer). Reviewers/admins/partners cannot QC.
"""
from unittest import mock

import jwt
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import pool
from apps.scholarship.models import (
    Consent, DecisionReopen, ScholarshipApplication, ScholarshipCohort,
    SponsorProfile,
)
from apps.scholarship.sponsorship import is_fundable

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestQcGate(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@example.com')
        cls.qc = PartnerAdmin.objects.create(
            supabase_user_id='qc-uid', role='qc', is_active=True,
            name='Quality Control', email='qc@example.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Reviewer', email='reviewer@example.com')
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='admin-uid', role='admin', is_active=True,
            name='Admin', email='admin@example.com')
        cls.partner = PartnerAdmin.objects.create(
            supabase_user_id='partner-uid', role='partner', is_active=True,
            name='Partner', email='partner@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        p = StudentProfile.objects.create(supabase_user_id='s1', nric='030101-14-0001', name='Aisha')
        # An AWAITING-QC case: reviewer submitted the verdict (verdict_decided_at set), assigned to them.
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='interviewed',
            profile_completed_at=timezone.now(), verdict_decided_at=timezone.now(),
            assigned_to=self.reviewer)
        # These fixtures carry no documents, so the REAL build_verdict would be all-gaps and the
        # V5 gap floor would refuse every accept. This class tests the gate mechanics, not the
        # floor — patch the seam to a clean verdict. The floor has its own class below.
        patcher = mock.patch('apps.scholarship.views_admin.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _qc(self, payload):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/qc-decision/',
            payload, format='json')

    # --- accept ---------------------------------------------------------------
    def test_qc_accept_by_qc_role_recommends(self):
        self._auth('qc-uid')
        r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')

    def test_qc_accept_by_super_recommends(self):
        self._auth('super-uid')
        self.assertEqual(self._qc({'decision': 'accept'}).status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')

    # --- reopen ---------------------------------------------------------------
    def test_qc_reopen_returns_to_reviewer_and_emails(self):
        mail.outbox = []
        self._auth('qc-uid')
        r = self._qc({'decision': 'reopen', 'comments': 'Household income evidence is thin — recheck payslips.'})
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interviewing')          # back to the reviewer's working state
        self.assertIsNotNone(self.app.decision_reopened_at)         # reopened banner
        row = DecisionReopen.objects.get(application=self.app)
        self.assertIn('payslips', row.reason)
        # the assigned reviewer is emailed the gaps
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('QC', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['reviewer@example.com'])
        self.assertIn('payslips', mail.outbox[0].body)

    def test_qc_reopen_requires_comments(self):
        self._auth('qc-uid')
        r = self._qc({'decision': 'reopen', 'comments': '  '})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'comments_required')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interviewed')            # unchanged

    # --- who can QC -----------------------------------------------------------
    def test_reviewer_cannot_qc(self):
        self._auth('rev-uid')
        self.assertEqual(self._qc({'decision': 'accept'}).status_code, 403)

    def test_admin_cannot_qc(self):
        self._auth('admin-uid')
        self.assertEqual(self._qc({'decision': 'accept'}).status_code, 403)

    def test_partner_cannot_qc(self):
        self._auth('partner-uid')
        self.assertEqual(self._qc({'decision': 'accept'}).status_code, 403)

    # --- only an awaiting-QC case ---------------------------------------------
    def test_qc_rejected_when_not_awaiting_qc(self):
        ScholarshipApplication.objects.filter(pk=self.app.id).update(status='recommended')
        self._auth('qc-uid')
        r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_awaiting_qc')

    # --- qc reads the queue (scope 'all', read-only) --------------------------
    def test_qc_can_read_the_case(self):
        self._auth('qc-uid')
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)

    # --- senior QC: assignable + reviews its own cases, but can't self-QC -------
    def test_qc_is_assignable(self):
        self._auth('super-uid')
        r = self.client.get('/api/v1/admin/scholarship/assignable-admins/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.qc.id, {a['id'] for a in r.json()['admins']})   # qc is now assignable

    def test_qc_can_review_its_assigned_case(self):
        # A senior qc assigned a case can act on it (reviewer write) — e.g. the mentoring flag.
        p = StudentProfile.objects.create(supabase_user_id='s-qc-rev', nric='030101-14-0007', name='Q')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='interviewing',
            profile_completed_at=timezone.now(), assigned_to=self.qc)
        self._auth('qc-uid')
        r = self.client.patch(f'/api/v1/admin/scholarship/applications/{app.id}/',
                              {'mentoring_candidate': True}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_qc_cannot_qc_its_own_reviewed_case(self):
        # An awaiting-QC case the qc themselves reviewed → self-QC guard blocks it (403).
        p = StudentProfile.objects.create(supabase_user_id='s-qc-own', nric='030101-14-0008', name='O')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='interviewed',
            profile_completed_at=timezone.now(), verdict_decided_at=timezone.now(),
            assigned_to=self.qc)
        self._auth('qc-uid')
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/qc-decision/',
                             {'decision': 'accept'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'self_qc_forbidden')
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')   # unchanged

    def test_super_can_qc_a_case_it_is_assigned(self):
        # Super is exempt from the self-QC guard (owner override).
        ScholarshipApplication.objects.filter(pk=self.app.id).update(assigned_to_id=self.superadmin.id)
        self._auth('super-uid')
        r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 200)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestPublishBoundToQc(TestCase):
    """Sponsor visibility is bound to the QC-Accept transition (→ 'recommended') — the SINGLE
    point a student becomes visible. The reviewer's verdict only PREPARES the profile; a case
    AWAITING QC is never in the pool, even if a profile is (accidentally) published. Belt: the
    pool read gate also hard-requires status=='recommended'."""

    @classmethod
    def setUpTestData(cls):
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@example.com')
        cls.qc = PartnerAdmin.objects.create(
            supabase_user_id='qc-uid', role='qc', is_active=True,
            name='Quality Control', email='qc@example.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Reviewer', email='reviewer@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        p = StudentProfile.objects.create(supabase_user_id='pq1', nric='030101-14-0003', name='Devi')
        # A case awaiting QC whose profile the reviewer PREPARED but did not publish.
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='interviewed',
            profile_completed_at=timezone.now(), verdict_decided_at=timezone.now(),
            assigned_to=self.reviewer, award_amount=3000)
        self.sp = SponsorProfile.objects.create(
            application=self.app, anon_markdown='A determined SPM leaver pursuing engineering.',
            anon_blurb='A determined SPM leaver.', anon_published=False)
        Consent.objects.create(application=self.app, consent_type='share_with_sponsors',
                               version='e2', is_active=True)
        # No documents on the fixture → patch the V5 gap floor's verdict seam (see TestQcGate).
        patcher = mock.patch('apps.scholarship.views_admin.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_awaiting_qc_prepared_profile_is_not_in_the_pool(self):
        # Prepared but unpublished → not visible; and the read gate would exclude it anyway.
        self.assertFalse(self.sp.anon_published)
        self.assertFalse(pool.is_pool_eligible(self.app))

    def test_qc_accept_publishes_and_pools(self):
        self._auth('qc-uid')
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/qc-decision/',
            {'decision': 'accept'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db(); self.sp.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')
        self.assertTrue(self.sp.anon_published)                 # published at QC-Accept
        self.assertIsNotNone(self.sp.anon_published_at)
        self.assertTrue(pool.is_pool_eligible(self.app))
        self.assertIn(self.app.id, set(
            pool.eligible_pool_queryset(ScholarshipApplication).values_list('id', flat=True)))

    def test_pool_read_gate_excludes_awaiting_qc_even_if_published(self):
        # Belt-and-suspenders: a stray publish while awaiting QC must NOT leak.
        SponsorProfile.objects.filter(pk=self.sp.pk).update(
            anon_published=True, anon_published_at=timezone.now())
        self.app.refresh_from_db()
        self.assertFalse(pool.is_pool_eligible(self.app))       # status != recommended
        self.assertNotIn(self.app.id, set(
            pool.eligible_pool_queryset(ScholarshipApplication).values_list('id', flat=True)))
        self.assertFalse(is_fundable(self.app))                 # and cannot be funded behind QC

    def test_qc_reopen_leaves_it_unpublished(self):
        self._auth('qc-uid')
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/qc-decision/',
            {'decision': 'reopen', 'comments': 'Recheck the income evidence.'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db(); self.sp.refresh_from_db()
        self.assertEqual(self.app.status, 'interviewing')
        self.assertFalse(self.sp.anon_published)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestQcGapFloor(TestCase):
    """V5 #5 (owner decision 1): QC-Accept is blocked while any verdict fact is red/'gap' —
    400 verdict_gap_floor naming the red facts. Only a `super` passes it, and only with a
    recorded override reason (qc_override_reason/_by/_at). The fixture app deliberately has
    NO documents, so the REAL build_verdict is all-gaps — no mocking on the refusal paths."""

    @classmethod
    def setUpTestData(cls):
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@example.com')
        cls.qc = PartnerAdmin.objects.create(
            supabase_user_id='qc-uid', role='qc', is_active=True,
            name='Quality Control', email='qc@example.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Reviewer', email='reviewer@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='gf', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        p = StudentProfile.objects.create(supabase_user_id='sgf', nric='030101-14-0005', name='Mala')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='interviewed',
            profile_completed_at=timezone.now(), verdict_decided_at=timezone.now(),
            assigned_to=self.reviewer)

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _qc(self, payload):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/qc-decision/',
            payload, format='json')

    def test_accept_refused_while_a_fact_is_gap(self):
        self._auth('qc-uid')
        r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertEqual(body['code'], 'verdict_gap_floor')
        self.assertIn('identity', body['facts'])                 # no IC on file → identity gap
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interviewed')         # unchanged

    def test_qc_role_overrides_with_reason_and_is_recorded(self):
        # Owner decision 2026-07-08: a `qc` may pass the red-fact floor too, with a recorded
        # reason (previously super-only). The reason is stored + attributed to the qc.
        self._auth('qc-uid')
        r = self._qc({'decision': 'accept', 'override_reason': 'I checked it by hand.'})
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')
        self.assertIn('by hand', self.app.qc_override_reason)
        self.assertEqual(self.app.qc_override_by, 'qc@example.com')
        self.assertIsNotNone(self.app.qc_override_at)

    def test_qc_without_reason_is_refused(self):
        # A qc still cannot pass the floor with no recorded reason.
        self._auth('qc-uid')
        r = self._qc({'decision': 'accept', 'override_reason': '   '})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'verdict_gap_floor')

    def test_super_without_reason_is_refused(self):
        self._auth('super-uid')
        r = self._qc({'decision': 'accept', 'override_reason': '   '})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'verdict_gap_floor')

    def test_super_with_reason_overrides_and_is_recorded(self):
        self._auth('super-uid')
        r = self._qc({'decision': 'accept',
                      'override_reason': 'Income verified offline with the school counsellor.'})
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')
        self.assertIn('counsellor', self.app.qc_override_reason)
        self.assertEqual(self.app.qc_override_by, 'super@example.com')
        self.assertIsNotNone(self.app.qc_override_at)

    def test_accept_passes_when_no_fact_is_gap(self):
        # Amber/blue facts are NOT floor-blocked — the floor is gap-only (soft floor by design).
        with mock.patch('apps.scholarship.views_admin.build_verdict', return_value=[
                {'fact': 'identity', 'status': 'verified', 'evidence': [], 'unresolved': []},
                {'fact': 'income', 'status': 'recommend', 'evidence': [], 'unresolved': []}]):
            self._auth('qc-uid')
            r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')
        self.assertEqual(self.app.qc_override_reason, '')        # no override recorded
