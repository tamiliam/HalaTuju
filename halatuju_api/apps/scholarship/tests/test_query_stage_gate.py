"""WHO may ask the student anything, and WHEN. The owner's matrix (2026-07-13), pinned.

    Stage                      Machine   Officer   Open items
    ────────────────────────────────────────────────────────────────
    shortlisted                  ✗          ✗       (none — no Action Centre yet)
    profile_complete (Completed) ✓          ✓       live
    interviewing                 ✗          ✓       live
    interviewed (Awaiting QC)    ✗          ✗       left open
    recommended                  ✗          ✗       SET ASIDE
    awarded / active             ✗          ✗       SET ASIDE
    rejected / withdrawn         ✗          ✗       —

Why each boundary matters:
  * `interviewing` — the case belongs to a human. Auto-questions landing in the Action Centre
    mid-interview mean the reviewer is competing with the system for the student's attention.
  * `shortlisted` — the Action Centre doesn't render until the student submits, so an officer
    ticket raised here is a question NOBODY CAN SEE OR ANSWER. Silently raising one is worse than
    refusing it.
  * `recommended` — nobody may ask any more, so leaving old queries live would be soliciting an
    answer we no longer want.

An item already open when the student moves on is LEFT ALONE (owner: "what's open, leave it") —
we asked it in good faith and we don't withdraw it.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (ResolutionItem, ScholarshipApplication,
                                     ScholarshipCohort)
from apps.scholarship.services import (auto_queries_allowed,
                                       officer_queries_allowed)

_STAGES = ['shortlisted', 'profile_complete', 'interviewing', 'interviewed',
           'recommended', 'awarded', 'active', 'maintenance', 'rejected',
           'withdrawn', 'expired', 'closed']

# The matrix, as data. Anything not listed is False for both.
_MACHINE_MAY_ASK = {'profile_complete'}
_OFFICER_MAY_ASK = {'profile_complete', 'interviewing'}


class TestWhoMayAsk(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, status, *, submitted=True):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'u-{status}-{submitted}', name='KAVITHA A/P SURESH',
            nric='080214-08-1234', preferred_state='Perak', household_income=1500,
            household_size=4, receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status,
            profile_completed_at=timezone.now() if submitted else None,
        )

    def test_the_machine_asks_only_during_the_completed_stage(self):
        for stage in _STAGES:
            with self.subTest(stage=stage):
                self.assertEqual(auto_queries_allowed(self._app(stage)),
                                 stage in _MACHINE_MAY_ASK)

    def test_an_officer_asks_only_during_completed_and_interviewing(self):
        for stage in _STAGES:
            with self.subTest(stage=stage):
                self.assertEqual(officer_queries_allowed(self._app(stage)),
                                 stage in _OFFICER_MAY_ASK)

    def test_nobody_may_ask_before_the_student_submits(self):
        # Shortlisted, no profile_completed_at: the Action Centre doesn't render at all, so a
        # ticket raised here could never be seen or answered.
        app = self._app('shortlisted', submitted=False)
        self.assertFalse(auto_queries_allowed(app))
        self.assertFalse(officer_queries_allowed(app))

    def test_interviewing_is_the_human_handover(self):
        # THE headline change: the machine stops, the officer continues.
        app = self._app('interviewing')
        self.assertFalse(auto_queries_allowed(app))
        self.assertTrue(officer_queries_allowed(app))

    def test_awaiting_qc_closes_the_door_on_everyone(self):
        app = self._app('interviewed')
        self.assertFalse(auto_queries_allowed(app))
        self.assertFalse(officer_queries_allowed(app))


class TestAutoSyncsRespectTheStage(TestCase):
    """The two auto-engines must not CREATE outside the Completed stage — but must still do their
    housekeeping (auto-resolve a cleared gap) everywhere, and must never withdraw an open item."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, status):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'v-{status}', name='KAVITHA A/P SURESH', nric='080214-08-1234',
            preferred_state='Perak', household_income=1500, household_size=4,
            receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status,
            profile_completed_at=timezone.now(),
        )

    def test_no_new_system_items_once_interviewing(self):
        from apps.scholarship.resolution import sync_resolution_items
        app = self._app('interviewing')   # an empty application → plenty of verdict gaps
        sync_resolution_items(app)
        self.assertEqual(app.resolution_items.filter(source='system').count(), 0)

    def test_system_items_are_raised_during_completed(self):
        from apps.scholarship.resolution import sync_resolution_items
        app = self._app('profile_complete')
        sync_resolution_items(app)
        self.assertGreater(app.resolution_items.filter(source='system').count(), 0)

    def test_an_open_item_survives_the_move_to_interviewing(self):
        # "What's open, leave it" — we asked in good faith; we don't withdraw the question.
        from apps.scholarship.resolution import sync_resolution_items
        app = self._app('profile_complete')
        sync_resolution_items(app)
        opened = list(app.resolution_items.filter(source='system', status='open')
                      .values_list('code', flat=True))
        self.assertTrue(opened)
        app.status = 'interviewing'
        app.save(update_fields=['status'])
        sync_resolution_items(app)
        still_open = list(app.resolution_items.filter(source='system', status='open')
                          .values_list('code', flat=True))
        self.assertEqual(sorted(still_open), sorted(opened))


class TestOfficerEndpointRefusesTheBlockedStages(TestCase):
    """Through the real endpoint, not just the predicate — a refusal that only exists in a helper
    is a refusal that hasn't shipped."""
    URL = '/api/v1/admin/scholarship/applications/{}/resolution-items/'

    @classmethod
    def setUpTestData(cls):
        from apps.courses.models import PartnerAdmin
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='admin-uid', is_super_admin=True, is_active=True,
            name='R', email='r@x.com',
        )

    def _app(self, status, *, submitted=True):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'w-{status}-{submitted}', name='KAVITHA A/P SURESH',
            nric='080214-08-1234', preferred_state='Perak', household_income=1500,
            household_size=4, receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status,
            profile_completed_at=timezone.now() if submitted else None,
        )

    def _post(self, app):
        import jwt
        from rest_framework.test import APIClient
        c = APIClient()
        token = jwt.encode({'sub': 'admin-uid', 'aud': 'authenticated', 'role': 'authenticated'},
                           'test-supabase-jwt-secret', algorithm='HS256')
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return c.post(self.URL.format(app.id),
                      {'kind': 'explanation', 'prompt': 'Please explain.'}, format='json')

    def test_officer_may_raise_while_interviewing(self):
        from django.test import override_settings
        with override_settings(SUPABASE_JWT_SECRET='test-supabase-jwt-secret'):
            r = self._post(self._app('interviewing'))
        self.assertEqual(r.status_code, 200)

    def test_officer_refused_at_shortlisted(self):
        # The Action Centre doesn't render pre-submission — this ticket could never be seen.
        from django.test import override_settings
        with override_settings(SUPABASE_JWT_SECRET='test-supabase-jwt-secret'):
            r = self._post(self._app('shortlisted', submitted=False))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'querying_closed')

    def test_officer_refused_at_awaiting_qc(self):
        from django.test import override_settings
        with override_settings(SUPABASE_JWT_SECRET='test-supabase-jwt-secret'):
            r = self._post(self._app('interviewed'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'querying_closed')
