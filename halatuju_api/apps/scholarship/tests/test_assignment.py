"""Tests for F7 reviewer assignment / reassignment (super-only, gated, audited)."""
from unittest.mock import ANY, patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import (
    AssignmentEvent, ReviewerProfile, ScholarshipApplication, ScholarshipCohort,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestReviewerAssignment(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@example.com',
        )
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Reviewer', email='rev@example.com',
        )
        cls.reviewer2 = PartnerAdmin.objects.create(
            supabase_user_id='rev2-uid', role='reviewer', is_active=True,
            name='Reviewer Two', email='rev2@example.com',
        )
        cls.viewer = PartnerAdmin.objects.create(
            supabase_user_id='view-uid', role='admin', is_active=True,
            name='Viewer', email='view@example.com',
        )
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud', nric='030101-14-1234', name='Priya',
        )

    def setUp(self):
        self.client = APIClient()
        # A submitted app with no open queries is ready for assignment.
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted', bucket='A',
            profile_completed_at=timezone.now(),
        )

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _assign(self, reviewer_id):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/assign/',
            {'reviewer_id': reviewer_id}, format='json')

    # --- F7 advance-notice email to the student (flag-gated) ------------------

    def _set_student_email(self):
        self.app.notify_email = 'priya@example.com'
        self.app.save(update_fields=['notify_email'])

    @override_settings(STUDENT_ASSIGNMENT_EMAIL_ENABLED=True)
    @patch('apps.scholarship.emails.send_student_assigned_reviewer_email')
    def test_student_email_passes_name_and_language(self, mock_send):
        # New contract: the student email gets the interviewer's NAME + the english_only
        # language flag — no phone/contact is shared anymore.
        self._set_student_email()
        self._auth('super-uid')
        self.assertEqual(self._assign(self.reviewer.id).status_code, 200)
        self.assertTrue(mock_send.called)
        kw = mock_send.call_args.kwargs
        self.assertEqual(kw['reviewer_name'], 'Reviewer')
        self.assertIn('english_only', kw)
        self.assertNotIn('reviewer_phone', kw)

    @patch('apps.scholarship.emails.send_student_assigned_reviewer_email')
    def test_student_email_not_sent_when_flag_off(self, mock_send):
        # default: STUDENT_ASSIGNMENT_EMAIL_ENABLED is off
        self._set_student_email()
        self._auth('super-uid')
        self._assign(self.reviewer.id)
        self.assertFalse(mock_send.called)

    def test_student_email_body_copy(self):
        from django.core import mail
        from apps.scholarship.emails import send_student_assigned_reviewer_email
        # Default: bilingual (EN + BM), HTML primary + plain-text fallback.
        self.assertTrue(send_student_assigned_reviewer_email(
            's@example.com', student_name='Priya Devi', reviewer_name='Rohini'))
        msg = mail.outbox[-1]
        self.assertEqual(msg.subject, 'Your BrightPath Bursary Programme interview — what happens next')
        self.assertEqual(msg.reply_to, ['interview@halatuju.xyz'])
        body = msg.body
        self.assertIn('Hi Priya,', body)                      # first name only
        self.assertIn('BrightPath Bursary Programme', body)
        self.assertIn('Program Bursari BrightPath', body)            # BM mirror present
        self.assertIn('your interview will be with Rohini', body)  # interviewer NAME woven in
        self.assertIn('camera on', body)                      # prep list
        self.assertIn('help@halatuju.xyz', body)              # safety contact
        self.assertNotIn('save the above number', body)       # old phone copy gone
        # HTML alternative present
        html, mime = msg.alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('<ul', html)                            # prep list as bullets
        # english_only drops the BM mirror
        send_student_assigned_reviewer_email(
            's@example.com', student_name='Priya Devi', english_only=True)
        body2 = mail.outbox[-1].body
        self.assertIn('BrightPath Bursary Programme', body2)
        self.assertNotIn('Program Bursari BrightPath', body2)

    # --- happy path -----------------------------------------------------------

    def test_super_assigns_ready_app(self):
        self._auth('super-uid')
        r = self._assign(self.reviewer.id)
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.assigned_to_id, self.reviewer.id)
        self.assertIsNotNone(self.app.assigned_at)
        ev = AssignmentEvent.objects.get(application=self.app)
        self.assertIsNone(ev.from_admin_id)
        self.assertEqual(ev.to_admin_id, self.reviewer.id)
        self.assertEqual(ev.by_email, 'super@example.com')

    # --- gating ---------------------------------------------------------------

    def test_cannot_assign_before_ready(self):
        self.app.profile_completed_at = None  # not submitted -> not ready
        self.app.save(update_fields=['profile_completed_at'])
        self._auth('super-uid')
        r = self._assign(self.reviewer.id)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_ready')
        self.assertFalse(AssignmentEvent.objects.exists())

    def test_only_super_can_assign(self):
        self._auth('rev-uid')
        self.assertEqual(self._assign(self.reviewer.id).status_code, 403)

    def test_requires_auth(self):
        self.assertEqual(self._assign(self.reviewer.id).status_code, 401)

    def test_cannot_assign_a_viewer(self):
        self._auth('super-uid')
        r = self._assign(self.viewer.id)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_reviewer')

    def test_bad_assignee(self):
        self._auth('super-uid')
        r = self._assign(999999)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_assignee')

    # --- reassign / unassign --------------------------------------------------

    def test_reassign_bypasses_ready_gate(self):
        # assign first while ready, then make it NOT ready and reassign — allowed.
        self.app.assigned_to = self.reviewer
        self.app.assigned_at = timezone.now()
        self.app.save(update_fields=['assigned_to', 'assigned_at'])
        self.app.profile_completed_at = None  # would block a first assign
        self.app.save(update_fields=['profile_completed_at'])
        self._auth('super-uid')
        r = self._assign(self.reviewer2.id)
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.assigned_to_id, self.reviewer2.id)
        ev = AssignmentEvent.objects.filter(application=self.app).first()  # latest
        self.assertEqual(ev.from_admin_id, self.reviewer.id)
        self.assertEqual(ev.to_admin_id, self.reviewer2.id)

    def test_unassign_clears_and_audits(self):
        self.app.assigned_to = self.reviewer
        self.app.assigned_at = timezone.now()
        self.app.save(update_fields=['assigned_to', 'assigned_at'])
        self._auth('super-uid')
        r = self._assign(None)
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.assigned_to_id)
        self.assertIsNone(self.app.assigned_at)
        self.assertTrue(AssignmentEvent.objects.filter(
            application=self.app, to_admin__isnull=True).exists())

    def test_noop_assign_writes_no_event(self):
        self.app.assigned_to = self.reviewer
        self.app.save(update_fields=['assigned_to'])
        self._auth('super-uid')
        r = self._assign(self.reviewer.id)  # same reviewer -> no change
        self.assertEqual(r.status_code, 200)
        self.assertFalse(AssignmentEvent.objects.exists())

    # --- reviewer-assigned email ---------------------------------------------

    def test_assign_emails_the_reviewer(self):
        self._auth('super-uid')
        from apps.scholarship.pool import pool_ref
        with patch('apps.scholarship.emails.send_reviewer_assigned_email') as m:
            self.assertEqual(self._assign(self.reviewer.id).status_code, 200)
        m.assert_called_once_with(
            to_email='rev@example.com', reviewer_name='Reviewer',
            ref=pool_ref(self.app.id), programme='B40', review_by=ANY)

    def test_unassign_sends_no_email(self):
        self.app.assigned_to = self.reviewer
        self.app.assigned_at = timezone.now()
        self.app.save(update_fields=['assigned_to', 'assigned_at'])
        self._auth('super-uid')
        with patch('apps.scholarship.emails.send_reviewer_assigned_email') as m:
            self.assertEqual(self._assign(None).status_code, 200)
        m.assert_not_called()

    def test_noop_assign_sends_no_email(self):
        self.app.assigned_to = self.reviewer
        self.app.save(update_fields=['assigned_to'])
        self._auth('super-uid')
        with patch('apps.scholarship.emails.send_reviewer_assigned_email') as m:
            self.assertEqual(self._assign(self.reviewer.id).status_code, 200)
        m.assert_not_called()
