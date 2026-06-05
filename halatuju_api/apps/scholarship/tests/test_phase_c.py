"""Phase C: handoff hardening (confirm + accept-gate) + roles + assignment +
interview capture + request-info."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, Consent, FundingNeed, InterviewSession,
    ScholarshipApplication, ScholarshipCohort,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
SUPER = 'super-uid'
REVIEWER = 'reviewer-uid'
VIEWER = 'viewer-uid'
STUDENT = 'student-uid'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class PhaseCBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id=SUPER, is_super_admin=True, is_active=True,
            name='Super', email='super@example.com',
        )
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id=REVIEWER, role='reviewer', is_active=True,
            name='Reviewer', email='reviewer@example.com',
        )
        cls.viewer = PartnerAdmin.objects.create(
            supabase_user_id=VIEWER, role='viewer', is_active=True,
            name='Viewer', email='viewer@example.com',
        )
        # Adult profile (2003-born NRIC) so guardian_docs are trivially satisfied.
        cls.profile = StudentProfile.objects.create(
            supabase_user_id=STUDENT, nric='030101-14-1234', name='Priya', school='SMK X',
            grades={f'sub{i}': 'A' for i in range(10)},
            household_income=2500, receives_str=True,
            student_signals={'field_interest': {'it': 5}},
            address='No. 1 Jalan ABC', postal_code='62100', city='Putrajaya',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _make_app(self, status='shortlisted'):
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status=status, bucket='A',
            aspirations='Be an auditor', plans='Study hard',
            daily_life='Help at home each evening', fears='Worried about fees',
        )

    def _complete(self, app):
        """Satisfy all 7 completeness parts for ``app`` (gate v2: STR route + father
        earner, with a compulsory offer letter + the route's income docs)."""
        FundingNeed.objects.create(application=app, categories=['living'], programme_months=36)
        for dt in ('ic', 'results_slip', 'offer_letter', 'parent_ic', 'str'):
            ApplicantDocument.objects.create(application=app, doc_type=dt, storage_path=f'x/{dt}')
        Consent.objects.create(application=app, version='t', is_active=True)
        ScholarshipApplication.objects.filter(pk=app.id).update(income_route='str', income_earner='father')
        app.refresh_from_db()
        return app


class TestConfirm(PhaseCBase):
    def test_confirm_incomplete_returns_400_with_completeness(self):
        app = self._make_app()
        self._auth(STUDENT)
        r = self.client.post(f'/api/v1/scholarship/applications/{app.id}/confirm/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'incomplete_profile')
        self.assertIn('completeness', r.json())
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')

    @patch('apps.scholarship.services.send_profile_complete_admin_email')
    def test_confirm_complete_flips_status_and_emails(self, mock_email):
        app = self._complete(self._make_app())
        self._auth(STUDENT)
        r = self.client.post(f'/api/v1/scholarship/applications/{app.id}/confirm/')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')
        self.assertIsNotNone(app.profile_completed_at)
        mock_email.assert_called_once()

    @patch('apps.scholarship.services.send_profile_complete_admin_email')
    def test_confirm_is_idempotent(self, _mock):
        app = self._complete(self._make_app(status='profile_complete'))
        self._auth(STUDENT)
        r = self.client.post(f'/api/v1/scholarship/applications/{app.id}/confirm/')
        self.assertEqual(r.status_code, 200)  # no-op, not an error

    def test_student_can_still_edit_after_confirm(self):
        """Completion is not a freeze — PATCH details still works at profile_complete."""
        app = self._complete(self._make_app(status='profile_complete'))
        self._auth(STUDENT)
        r = self.client.patch(
            f'/api/v1/scholarship/applications/{app.id}/',
            {'aspirations': 'Updated'}, format='json',
        )
        self.assertEqual(r.status_code, 200)


class TestAcceptGate(PhaseCBase):
    def test_accept_incomplete_hard_blocked(self):
        app = self._make_app()
        self._auth(SUPER)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/verify-accept/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'incomplete_profile')
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')  # not accepted

    def test_accept_complete_succeeds(self):
        from django.utils import timezone
        app = self._complete(self._make_app(status='profile_complete'))
        # Check-3 audit gate: the reviewer must have recorded their verdict before close.
        ScholarshipApplication.objects.filter(pk=app.id).update(verdict_decided_at=timezone.now())
        self._auth(SUPER)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/verify-accept/')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'accepted')

    def test_viewer_cannot_accept(self):
        app = self._complete(self._make_app(status='profile_complete'))
        self._auth(VIEWER)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/verify-accept/')
        self.assertEqual(r.status_code, 403)


class TestListFilters(PhaseCBase):
    def _second_app(self, status='shortlisted'):
        """A second application needs a distinct cohort (one app per cohort+profile)."""
        cohort2 = ScholarshipCohort.objects.create(code='c2', name='B40-2', year=2025)
        return ScholarshipApplication.objects.create(
            cohort=cohort2, profile=self.profile, status=status, bucket='A',
        )

    def test_status_profile_complete_filter(self):
        self._complete(self._make_app(status='profile_complete'))
        self._second_app(status='shortlisted')
        self._auth(SUPER)
        r = self.client.get('/api/v1/admin/scholarship/applications/?status=profile_complete')
        self.assertEqual(r.json()['total_count'], 1)

    def test_assigned_me_and_none(self):
        a = self._make_app()
        a.assigned_to = self.reviewer
        a.save(update_fields=['assigned_to'])
        self._second_app()  # unassigned
        self._auth(REVIEWER)
        r_me = self.client.get('/api/v1/admin/scholarship/applications/?assigned=me')
        self.assertEqual(r_me.json()['total_count'], 1)
        r_none = self.client.get('/api/v1/admin/scholarship/applications/?assigned=none')
        self.assertEqual(r_none.json()['total_count'], 1)


class TestAssignment(PhaseCBase):
    def test_reviewer_can_assign(self):
        app = self._make_app()
        self._auth(SUPER)
        r = self.client.patch(
            f'/api/v1/admin/scholarship/applications/{app.id}/',
            {'assigned_to': self.reviewer.id}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.reviewer.id)

    def test_assign_unknown_admin_400(self):
        app = self._make_app()
        self._auth(SUPER)
        r = self.client.patch(
            f'/api/v1/admin/scholarship/applications/{app.id}/',
            {'assigned_to': 99999}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_viewer_cannot_assign(self):
        app = self._make_app()
        self._auth(VIEWER)
        r = self.client.patch(
            f'/api/v1/admin/scholarship/applications/{app.id}/',
            {'assigned_to': self.reviewer.id}, format='json',
        )
        self.assertEqual(r.status_code, 403)


class TestInterview(PhaseCBase):
    def test_draft_then_submit_advances_status(self):
        app = self._complete(self._make_app(status='profile_complete'))
        self._auth(REVIEWER)
        # Create a draft → status moves to interviewing.
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            {'findings': {'household_size_one': {'verdict': 'resolved', 'rationale': 'ok'}},
             'rubric': {'financial_need': 5}, 'overall_note': 'Solid.'}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')
        # Submit → status moves to interviewed.
        r2 = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/interview/submit/')
        self.assertEqual(r2.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertEqual(InterviewSession.objects.filter(application=app, status='submitted').count(), 1)

    def test_bad_verdict_rejected(self):
        app = self._complete(self._make_app(status='profile_complete'))
        self._auth(REVIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            {'findings': {'x': {'verdict': 'nonsense', 'rationale': 'y'}}}, format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_findings')

    def test_rationale_too_long_rejected(self):
        app = self._complete(self._make_app(status='profile_complete'))
        self._auth(REVIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            {'findings': {'x': {'verdict': 'resolved', 'rationale': 'z' * 200}}}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_viewer_cannot_write_interview(self):
        app = self._complete(self._make_app(status='profile_complete'))
        self._auth(VIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            {'findings': {}}, format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_viewer_can_read_interview(self):
        app = self._make_app()
        self._auth(VIEWER)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{app.id}/interview/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('agenda', r.json())


class TestRequestInfo(PhaseCBase):
    @patch('apps.scholarship.views_admin.send_request_info_email')
    def test_request_info_stores_note_and_emails(self, mock_email):
        app = self._complete(self._make_app(status='profile_complete'))
        self._auth(REVIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/request-info/',
            {'note': 'Please upload your latest payslip.'}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.info_request_note, 'Please upload your latest payslip.')
        self.assertIsNotNone(app.info_requested_at)
        self.assertEqual(app.status, 'profile_complete')  # unchanged
        mock_email.assert_called_once()

    def test_request_info_requires_note(self):
        app = self._make_app()
        self._auth(REVIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/request-info/',
            {'note': '  '}, format='json',
        )
        self.assertEqual(r.status_code, 400)


class TestRoleEndpoint(PhaseCBase):
    def test_role_returned(self):
        self._auth(REVIEWER)
        r = self.client.get('/api/v1/admin/role/')
        self.assertEqual(r.json()['role'], 'reviewer')

    def test_legacy_super_reported_as_super(self):
        self._auth(SUPER)
        r = self.client.get('/api/v1/admin/role/')
        self.assertEqual(r.json()['role'], 'super')


class TestStickyProfileCompleteRevert(PhaseCBase):
    """A profile_complete application that's edited back to incomplete (e.g. a
    compulsory doc removed) must roll back to 'shortlisted' — honest funnel."""

    def _confirmed(self):
        from django.utils import timezone
        app = self._complete(self._make_app(status='profile_complete'))
        app.profile_completed_at = timezone.now()
        app.save(update_fields=['profile_completed_at'])
        return app

    def test_helper_reverts_when_incomplete(self):
        from apps.scholarship.services import revert_if_profile_incomplete
        app = self._confirmed()
        ApplicantDocument.objects.filter(application=app, doc_type='results_slip').delete()
        self.assertTrue(revert_if_profile_incomplete(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')
        self.assertIsNone(app.profile_completed_at)

    def test_helper_noop_when_still_complete(self):
        from apps.scholarship.services import revert_if_profile_incomplete
        app = self._confirmed()
        self.assertFalse(revert_if_profile_incomplete(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')

    def test_helper_does_not_touch_interviewing(self):
        from apps.scholarship.services import revert_if_profile_incomplete
        app = self._make_app(status='interviewing')  # incomplete + past confirm
        self.assertFalse(revert_if_profile_incomplete(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')

    def test_deleting_compulsory_doc_reverts_via_api(self):
        app = self._confirmed()
        ic = ApplicantDocument.objects.get(application=app, doc_type='ic')
        self._auth(STUDENT)
        r = self.client.delete(f'/api/v1/scholarship/documents/{ic.id}/')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')
        self.assertIsNone(app.profile_completed_at)
