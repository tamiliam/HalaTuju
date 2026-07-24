"""The "you haven't submitted yet" nudge — one-time auto sweep + org-admin manual re-send.

Pins the behaviour the owner asked for (2026-07-24):
  * it applies ONLY to a shortlisted student who has consented but not pressed the final submit;
  * the automatic email fires exactly ONCE, ~30 min after consent, and never re-sweeps;
  * the manual button is super/org_admin only, blocked before the auto nudge and during the
    cooldown, and refused for a reviewer/qc that _require_app_write would otherwise admit.
"""
from datetime import timedelta
from unittest import mock

import jwt
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import Consent, ScholarshipApplication, ScholarshipCohort
from apps.scholarship import nudge as nudge_mod

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ORG_ADMIN, SUPER, QC, REVIEWER, OTHER_OA = 'nd-oa', 'nd-su', 'nd-qc', 'nd-rev', 'nd-other'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _consent(app, *, minutes_ago=0):
    """Create an active consent and backdate granted_at (auto_now_add can't be set on create)."""
    c = Consent.objects.create(application=app, version='t', granted_by='guardian',
                               guardian_name='Parent', is_active=True)
    if minutes_ago:
        Consent.objects.filter(pk=c.pk).update(
            granted_at=timezone.now() - timedelta(minutes=minutes_ago))
    return c


class TestNudgeState(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40 Programme', year=2026)

    def setUp(self):
        # The minimal test apps have no docs/sections, so consent_blockers would be non-empty;
        # patch it to "clear" (a ready-to-submit student) by default. Flip on a per-test basis.
        p = mock.patch('apps.scholarship.nudge._has_blockers', return_value=False)
        self.has_blockers = p.start(); self.addCleanup(p.stop)

    def _app(self, status='shortlisted', profile_completed=False):
        p = StudentProfile.objects.create(supabase_user_id=f'p{StudentProfile.objects.count()}',
                                          name='Janu')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status=status, notify_email='stu@x.com',
            profile_completed_at=timezone.now() if profile_completed else None)

    def test_applicable_only_when_shortlisted_consented_unsubmitted(self):
        app = self._app()
        self.assertFalse(nudge_mod.is_applicable(app))       # no consent yet
        _consent(app)
        self.assertTrue(nudge_mod.is_applicable(app))
        # A student who has submitted (profile_completed_at set) is past this stage.
        app.profile_completed_at = timezone.now(); app.save()
        self.assertFalse(nudge_mod.is_applicable(app))
        # And a non-shortlisted status never qualifies.
        app.profile_completed_at = None; app.status = 'profile_complete'; app.save()
        self.assertFalse(nudge_mod.is_applicable(app))

    def test_a_stuck_student_with_outstanding_items_is_excluded(self):
        """A consented student who edited something back into an incomplete/blocked state is stuck,
        not one-press-from-submit — the 'you haven't submitted yet' nudge must not apply."""
        app = self._app(); _consent(app)
        self.assertTrue(nudge_mod.is_applicable(app))
        self.has_blockers.return_value = True          # a blocker reappeared post-consent
        self.assertFalse(nudge_mod.is_applicable(app))
        self.assertFalse(nudge_mod.send_nudge(app, manual=False))
        self.assertEqual(len(mail.outbox), 0)

    def test_state_before_auto_is_blocked_and_reports_due_time(self):
        app = self._app(); _consent(app, minutes_ago=5)
        st = nudge_mod.nudge_state(app)
        self.assertTrue(st['applicable'])
        self.assertIsNone(st['sent_at'])
        self.assertFalse(st['available'])          # manual blocked until the auto has fired
        self.assertIsNotNone(st['available_at'])   # = consent granted + 30 min

    def test_state_after_send_respects_cooldown(self):
        app = self._app(); _consent(app)
        app.nudge_sent_at = timezone.now(); app.save()
        self.assertFalse(nudge_mod.nudge_state(app)['available'])   # inside 24h cooldown
        app.nudge_sent_at = timezone.now() - timedelta(hours=25); app.save()
        st = nudge_mod.nudge_state(app)
        self.assertTrue(st['available'])
        self.assertIsNone(st['available_at'])

    def test_send_nudge_sends_one_email_and_stamps(self):
        app = self._app(); _consent(app)
        self.assertTrue(nudge_mod.send_nudge(app, manual=False))
        app.refresh_from_db()
        self.assertIsNotNone(app.nudge_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['stu@x.com'])

    def test_manual_send_refused_before_available(self):
        app = self._app(); _consent(app, minutes_ago=5)   # pre-auto → not available
        self.assertFalse(nudge_mod.send_nudge(app, manual=True))
        self.assertEqual(len(mail.outbox), 0)


class TestAutoSweep(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40 Programme', year=2026)

    def setUp(self):
        p = mock.patch('apps.scholarship.nudge._has_blockers', return_value=False)
        self.has_blockers = p.start(); self.addCleanup(p.stop)

    def _app(self):
        p = StudentProfile.objects.create(supabase_user_id=f'a{StudentProfile.objects.count()}')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='shortlisted', notify_email='stu@x.com')

    def test_fires_once_for_an_eligible_student(self):
        app = self._app(); _consent(app, minutes_ago=40)
        self.assertEqual(nudge_mod.send_application_nudges()['nudged'], 1)
        self.assertEqual(len(mail.outbox), 1)
        # Never re-sweeps: nudge_sent_at is now set.
        self.assertEqual(nudge_mod.send_application_nudges()['nudged'], 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_skips_a_just_consented_student(self):
        app = self._app(); _consent(app, minutes_ago=5)   # < 30 min → not due
        self.assertEqual(nudge_mod.send_application_nudges()['nudged'], 0)

    def test_skips_the_unconsented_and_the_submitted(self):
        self._app()                                        # no consent
        app2 = self._app(); _consent(app2, minutes_ago=40)
        app2.profile_completed_at = timezone.now(); app2.save()   # already submitted
        self.assertEqual(nudge_mod.send_application_nudges()['nudged'], 0)


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestNudgeEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(name='Tamil Foundation', code='tf')
        cls.other = PartnerOrganisation.objects.create(name='Other Org', code='oo')
        cls.cohort = ScholarshipCohort.objects.create(
            code='c', name='B40 Programme', year=2026, owning_organisation=cls.org)
        mk = PartnerAdmin.objects.create
        mk(supabase_user_id=ORG_ADMIN, role='org_admin', is_active=True, name='OA',
           email='oa@x.com', owning_organisation=cls.org)
        mk(supabase_user_id=SUPER, role='super', is_super_admin=True, is_active=True,
           name='SU', email='su@x.com')
        cls.reviewer = mk(supabase_user_id=REVIEWER, role='reviewer', is_active=True, name='R',
                          email='r@x.com', owning_organisation=cls.org)
        mk(supabase_user_id=QC, role='qc', is_active=True, name='Q', email='q@x.com',
           owning_organisation=cls.org)
        mk(supabase_user_id=OTHER_OA, role='org_admin', is_active=True, name='OO',
           email='oo@x.com', owning_organisation=cls.other)

    def setUp(self):
        self.client = APIClient()
        p = mock.patch('apps.scholarship.nudge._has_blockers', return_value=False)
        self.has_blockers = p.start(); self.addCleanup(p.stop)

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _app(self, *, consent=True, available=True):
        p = StudentProfile.objects.create(supabase_user_id=f'e{StudentProfile.objects.count()}')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='shortlisted', notify_email='stu@x.com',
            assigned_to=self.reviewer)
        if consent:
            _consent(app)
        if available:   # a past nudge whose cooldown has elapsed → manual send allowed now
            app.nudge_sent_at = timezone.now() - timedelta(hours=25)
            app.save()
        return app

    def _url(self, app):
        return f'/api/v1/admin/scholarship/applications/{app.id}/nudge/'

    def test_org_admin_may_nudge(self):
        app = self._app(); self._auth(ORG_ADMIN)
        self.assertEqual(self.client.post(self._url(app)).status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_super_may_nudge(self):
        app = self._app(); self._auth(SUPER)
        self.assertEqual(self.client.post(self._url(app)).status_code, 200)

    def test_qc_refused(self):
        app = self._app(); self._auth(QC)
        self.assertEqual(self.client.post(self._url(app)).status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_assigned_reviewer_refused(self):
        app = self._app(); self._auth(REVIEWER)
        self.assertEqual(self.client.post(self._url(app)).status_code, 403)

    def test_cross_org_404(self):
        app = self._app(); self._auth(OTHER_OA)
        self.assertEqual(self.client.post(self._url(app)).status_code, 404)

    def test_not_applicable_400(self):
        app = self._app(consent=False, available=False); self._auth(ORG_ADMIN)
        r = self.client.post(self._url(app))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_applicable')

    def test_unavailable_400_before_auto(self):
        app = self._app(available=False); self._auth(ORG_ADMIN)   # consented, never nudged
        r = self.client.post(self._url(app))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'nudge_unavailable')

    def test_stuck_student_400_not_applicable(self):
        """A consented student who fell back into a blocked state is excluded, even for a manual
        send — the reminder wouldn't be relevant while they still owe items."""
        app = self._app(); self._auth(ORG_ADMIN)
        self.has_blockers.return_value = True
        r = self.client.post(self._url(app))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_applicable')
        self.assertEqual(len(mail.outbox), 0)
