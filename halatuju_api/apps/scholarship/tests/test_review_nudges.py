"""Tests for the verdict-completion SLA nudges (TD-131) — send_review_nudges cron."""
from datetime import timedelta

from django.core.management import call_command
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.pool import pool_ref


@override_settings(REVIEW_NUDGES_ENABLED=True, REVIEW_SLA_DAYS=10,
                   REVIEW_NUDGE_SOON_DAYS=2, REVIEW_ESCALATE_GRACE_DAYS=3)
class ReviewNudgeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rohini', email='rohini@example.com')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='sup-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud', nric='030101-14-1234', name='Priya')

    def _app(self, *, assigned_days_ago, status='interviewing', **kw):
        now = timezone.now()
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status=status,
            notify_email='priya@example.com', assigned_to=self.reviewer,
            assigned_at=now - timedelta(days=assigned_days_ago), **kw)

    def test_inert_when_flag_off(self):
        self._app(assigned_days_ago=20)
        with override_settings(REVIEW_NUDGES_ENABLED=False):
            call_command('send_review_nudges')
        self.assertEqual(len(mail.outbox), 0)

    def test_approaching_nudge_fires_once(self):
        app = self._app(assigned_days_ago=9)   # due in 1 day → inside the 2-day soon window
        call_command('send_review_nudges')
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['rohini@example.com'])
        self.assertIn('Verdict due soon', msg.subject)
        self.assertIn(pool_ref(app.id), msg.subject)
        app.refresh_from_db()
        self.assertIsNotNone(app.review_nudged_soon_at)
        # Idempotent: a second run sends nothing new.
        mail.outbox.clear()
        call_command('send_review_nudges')
        self.assertEqual(len(mail.outbox), 0)

    def test_overdue_nudge_fires(self):
        self._app(assigned_days_ago=11)    # due yesterday → overdue, not yet at escalation
        call_command('send_review_nudges')
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any('Verdict overdue' in s for s in subjects))
        self.assertFalse(any('needs attention' in s for s in subjects))  # no escalation yet

    def test_escalation_to_super_admins(self):
        self._app(assigned_days_ago=14)    # due 4 days ago → past the +3 grace
        call_command('send_review_nudges')
        esc = [m for m in mail.outbox if 'needs attention' in m.subject]
        self.assertEqual(len(esc), 1)
        self.assertEqual(esc[0].to, ['super@example.com'])

    def test_recorded_verdict_cancels_nudge(self):
        self._app(assigned_days_ago=20, verdict_decided_at=timezone.now())
        call_command('send_review_nudges')
        self.assertEqual(len(mail.outbox), 0)

    def test_terminal_status_excluded(self):
        self._app(assigned_days_ago=20, status='rejected')
        call_command('send_review_nudges')
        self.assertEqual(len(mail.outbox), 0)

    def test_reassignment_resets_nudge_stamps(self):
        from apps.scholarship.services import assign_reviewer
        other = PartnerAdmin.objects.create(
            supabase_user_id='rev2-uid', role='reviewer', is_active=True,
            name='Bala', email='bala@example.com')
        app = self._app(assigned_days_ago=11)
        call_command('send_review_nudges')           # sends overdue, stamps it
        app.refresh_from_db()
        self.assertIsNotNone(app.review_nudged_overdue_at)
        # Reassigning to a DIFFERENT reviewer starts a fresh clock: stamps clear.
        assign_reviewer(app, reviewer=other, by_admin=self.super)
        app.refresh_from_db()
        self.assertIsNone(app.review_nudged_overdue_at)
        self.assertIsNone(app.review_nudged_soon_at)
        self.assertIsNone(app.review_escalated_at)
