"""Tests for F7 reviewer assignment / reassignment (super-only, gated, audited)."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import (
    AssignmentEvent, ScholarshipApplication, ScholarshipCohort,
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
