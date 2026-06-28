"""Decision reopen / cancel-reopen — reversing a finalised decision.

Covers: super-only reopen holds the sponsor profile from the pool + opens an audit
row; cancel restores the prior published state with NO reviewer correction;
re-recording (record-verdict / reject) closes the reopen as a real correction
(counting model B) and the corrections count surfaces internally.
"""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import (
    DecisionReopen, InterviewSession, ScholarshipApplication, ScholarshipCohort,
    SponsorProfile,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
SUPER, REVIEWER, STUDENT = 'reopen-super', 'reopen-reviewer', 'reopen-student'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDecisionReopen(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        self.profile = StudentProfile.objects.create(
            supabase_user_id=STUDENT, nric='030101-14-1234', name='Priya')
        self.reviewer = PartnerAdmin.objects.create(
            supabase_user_id=REVIEWER, role='reviewer', is_active=True, name='Rev', email='r@x.com')
        self.superadmin = PartnerAdmin.objects.create(
            supabase_user_id=SUPER, is_super_admin=True, is_active=True, name='Boss', email='s@x.com')
        # A decided, accepted application with a PUBLISHED sponsor profile.
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='recommended',
            assigned_to=self.reviewer, verdict_decided_at=timezone.now(),
            officer_verdict={'identity': 'pass', 'academic': 'pass',
                             'income': 'pass', 'pathway': 'pass', 'overall': 'accept'})
        self.sp = SponsorProfile.objects.create(
            application=self.app, draft_markdown='## Draft', anon_markdown='## Pool',
            anon_published=True, anon_published_at=timezone.now())

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _reopen_url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/reopen-decision/'

    def _cancel_url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/cancel-reopen/'

    def _record_url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/record-verdict/'

    # ── reopen ───────────────────────────────────────────────────────────────
    def test_reopen_holds_profile_and_opens_audit_row(self):
        self._auth(SUPER)
        r = self.client.post(self._reopen_url(), {'reason': 'Income mis-read by reviewer.'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db(); self.sp.refresh_from_db()
        self.assertIsNotNone(self.app.decision_reopened_at)        # panel unlocks
        self.assertFalse(self.sp.anon_published)                   # held from the pool
        self.assertIsNone(self.sp.anon_published_at)
        row = DecisionReopen.objects.get(application=self.app)
        self.assertIsNone(row.closed_at)                          # open
        self.assertTrue(row.was_published)
        self.assertEqual(row.reviewer_id, self.reviewer.id)        # attributed to the reviewer
        self.assertEqual(row.reopened_by, 's@x.com')
        self.assertFalse(row.resulted_in_change)
        # The detail GET surfaces the reopened state + reason for the banner.
        body = r.json()
        self.assertIsNotNone(body['decision_reopened_at'])
        self.assertEqual(body['decision_reopen_reason'], 'Income mis-read by reviewer.')

    def test_reopen_requires_reason(self):
        self._auth(SUPER)
        r = self.client.post(self._reopen_url(), {'reason': '   '}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'reason_required')

    def test_reopen_requires_a_recorded_decision(self):
        self.app.verdict_decided_at = None
        self.app.save(update_fields=['verdict_decided_at'])
        self._auth(SUPER)
        r = self.client.post(self._reopen_url(), {'reason': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_decided')

    def test_double_reopen_rejected(self):
        self._auth(SUPER)
        self.client.post(self._reopen_url(), {'reason': 'first'}, format='json')
        r = self.client.post(self._reopen_url(), {'reason': 'again'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'already_reopened')

    def test_reviewer_cannot_reopen(self):
        self._auth(REVIEWER)
        r = self.client.post(self._reopen_url(), {'reason': 'x'}, format='json')
        self.assertEqual(r.status_code, 403)

    # ── reopen returns an accepted case to the decision point (interviewed) ───
    def test_reopen_moves_accepted_to_interviewed(self):
        from apps.scholarship import reopen as reopen_service
        reopen_service.reopen_decision(self.app, by_admin=self.superadmin, reason='wrong institution')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interviewed')

    def test_cancel_reopen_restores_accepted_status(self):
        from apps.scholarship import reopen as reopen_service
        reopen_service.reopen_decision(self.app, by_admin=self.superadmin, reason='check')
        reopen_service.cancel_reopen(self.app)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')

    def test_reopen_clears_pending_decline(self):
        from datetime import timedelta
        self.app.pending_rejection_category = 'contractual'
        self.app.decline_due_at = timezone.now() + timedelta(days=7)
        self.app.pending_decline_by = 's@x.com'
        self.app.save(update_fields=['pending_rejection_category', 'decline_due_at', 'pending_decline_by'])
        from apps.scholarship import reopen as reopen_service
        reopen_service.reopen_decision(self.app, by_admin=self.superadmin, reason='reconsider')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interviewed')
        self.assertEqual(self.app.pending_rejection_category, '')
        self.assertIsNone(self.app.decline_due_at)

    def test_reject_after_reopen_is_interview_not_contractual(self):
        # Reopen an accepted case → 'interviewed'; declining then buckets as 'interview'
        # (reviewed-but-not-selected), NOT 'contractual'. Cool-off is 0 in tests → immediate.
        from apps.scholarship import reopen as reopen_service
        from apps.scholarship.services import admin_reject
        reopen_service.reopen_decision(self.app, by_admin=self.superadmin, reason='private college')
        self.app.refresh_from_db()
        admin_reject(self.app, self.superadmin, 'interview')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'rejected')
        self.assertEqual(self.app.rejection_category, 'interview')

    # ── cancel-reopen (no change → restore, no correction) ───────────────────
    def test_cancel_restores_published_state_without_counting(self):
        self._auth(SUPER)
        self.client.post(self._reopen_url(), {'reason': 'check something'}, format='json')
        r = self.client.post(self._cancel_url(), {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db(); self.sp.refresh_from_db()
        self.assertIsNone(self.app.decision_reopened_at)          # re-locked
        self.assertTrue(self.sp.anon_published)                   # restored to the pool
        row = DecisionReopen.objects.get(application=self.app)
        self.assertIsNotNone(row.closed_at)
        self.assertFalse(row.resulted_in_change)                  # NOT a correction
        # No correction counted against the reviewer.
        self.assertEqual(self._corrections_for(self.reviewer.id), 0)

    def test_cancel_without_open_reopen_400(self):
        self._auth(SUPER)
        r = self.client.post(self._cancel_url(), {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_reopened')

    # ── re-record (real change → correction counts) ──────────────────────────
    @patch('apps.scholarship.views_admin.refine_sponsor_profile')
    def test_rerecord_counts_correction_and_republishes(self, mock_refine):
        mock_refine.return_value = {'markdown': '## Corrected', 'model_used': 'gemini-2.5-pro'}
        InterviewSession.objects.create(application=self.app, status='submitted', submitted_at=timezone.now())
        self._auth(SUPER)
        self.client.post(self._reopen_url(), {'reason': 'wrong income verdict'}, format='json')
        self.sp.refresh_from_db()
        self.assertFalse(self.sp.anon_published)                  # held during reopen
        # Re-record the (corrected) decision with finalise → regenerate + republish.
        r = self.client.post(self._record_url(), {
            'officer_verdict': {'identity': 'pass', 'academic': 'pass', 'income': 'pass',
                                'pathway': 'pass', 'overall': 'accept'},
            'reason': 'corrected', 'finalise': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['finalise_result']['ok'])
        self.app.refresh_from_db(); self.sp.refresh_from_db()
        self.assertIsNone(self.app.decision_reopened_at)          # re-locked
        self.assertTrue(self.sp.anon_published)                   # republished
        row = DecisionReopen.objects.get(application=self.app)
        self.assertTrue(row.resulted_in_change)                   # COUNTS
        self.assertIsNotNone(row.closed_at)
        self.assertEqual(self._corrections_for(self.reviewer.id), 1)

    def test_reject_after_reopen_counts_correction_and_stays_unpublished(self):
        self._auth(SUPER)
        self.client.post(self._reopen_url(), {'reason': 'should be declined'}, format='json')
        # Reopen moved the accepted case back to 'interviewed', so the decline is bucketed
        # as 'interview' (reviewed-but-not-selected), not 'contractual'.
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/reject/',
            {'category': 'interview'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db(); self.sp.refresh_from_db()
        self.assertEqual(self.app.status, 'rejected')
        self.assertIsNone(self.app.decision_reopened_at)
        self.assertFalse(self.sp.anon_published)                  # a decline never republishes
        row = DecisionReopen.objects.get(application=self.app)
        self.assertTrue(row.resulted_in_change)
        self.assertEqual(self._corrections_for(self.reviewer.id), 1)

    # ── reopen unlocks the whole case (Check 2 + Interview), not just the panel ──
    def test_reopen_unlocks_querying(self):
        from apps.scholarship import services
        self.assertTrue(services.querying_locked(self.app))    # accepted → Check 2 locked
        self.app.decision_reopened_at = timezone.now()
        self.app.save(update_fields=['decision_reopened_at'])
        self.assertFalse(services.querying_locked(self.app))   # reopened → unlocked

    def test_reopened_interview_edits_submitted_session_in_place(self):
        InterviewSession.objects.create(
            application=self.app, status='submitted', submitted_at=timezone.now(),
            findings={'a': {'verdict': 'resolved', 'rationale': 'ok'}})
        self.app.decision_reopened_at = timezone.now()
        self.app.save(update_fields=['decision_reopened_at'])
        self._auth(SUPER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/interview/',
            {'findings': {'a': {'verdict': 'resolved', 'rationale': 'edited'}}}, format='json')
        self.assertEqual(r.status_code, 200)
        # Edited in place — no duplicate session spawned (the app #15 trap).
        self.assertEqual(InterviewSession.objects.filter(application=self.app).count(), 1)

    # ── corrections count surfaces internally ────────────────────────────────
    def _corrections_for(self, reviewer_id):
        """Read the reviewer's corrections tally from the assignable-admins endpoint."""
        self._auth(SUPER)
        r = self.client.get('/api/v1/admin/scholarship/assignable-admins/')
        self.assertEqual(r.status_code, 200)
        for a in r.json()['admins']:
            if a['id'] == reviewer_id:
                return a['corrections']
        return None

    def test_assignable_admins_exposes_corrections(self):
        self.assertEqual(self._corrections_for(self.reviewer.id), 0)
