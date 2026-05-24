"""Tests for the release-due-decisions command (send_pending_decision_emails, S8)."""
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import score_application


class TestReleaseDueDecisions(TestCase):

    def setUp(self):
        self.cohort = ScholarshipCohort.objects.create(code='c', name='B40 Programme', year=2026)

    def _scored(self, verdict, due_in_hours, email='who@example.com'):
        """A silently-scored application (status still 'submitted') with a due time."""
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, status='submitted', verdict=verdict,
            bucket=('A' if verdict == 'shortlisted' else ''),
            notify_email=email,
            decision_due_at=timezone.now() + timedelta(hours=due_in_hours),
        )

    def test_releases_due_decline(self):
        app = self._scored('rejected', due_in_hours=-1)   # due an hour ago
        call_command('send_pending_decision_emails')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        self.assertIsNotNone(app.decision_released_at)
        self.assertIsNotNone(app.decision_email_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('who@example.com', mail.outbox[0].to)

    def test_releases_due_shortlist(self):
        app = self._scored('shortlisted', due_in_hours=-1)
        call_command('send_pending_decision_emails')
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')
        self.assertIsNotNone(app.shortlisted_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_skips_not_yet_due(self):
        app = self._scored('rejected', due_in_hours=5)    # due in the future
        call_command('send_pending_decision_emails')
        app.refresh_from_db()
        self.assertEqual(app.status, 'submitted')
        self.assertEqual(len(mail.outbox), 0)

    def test_idempotent_no_resend(self):
        self._scored('rejected', due_in_hours=-1)
        call_command('send_pending_decision_emails')
        call_command('send_pending_decision_emails')
        self.assertEqual(len(mail.outbox), 1)             # released once only

    def test_dry_run_changes_nothing(self):
        app = self._scored('rejected', due_in_hours=-1)
        call_command('send_pending_decision_emails', '--dry-run')
        app.refresh_from_db()
        self.assertEqual(app.status, 'submitted')
        self.assertIsNone(app.decision_released_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_already_released(self):
        app = self._scored('shortlisted', due_in_hours=-1)
        app.status = 'shortlisted'
        app.decision_released_at = timezone.now()
        app.save(update_fields=['status', 'decision_released_at'])
        call_command('send_pending_decision_emails')
        self.assertEqual(len(mail.outbox), 0)


class TestSilentScoring(TestCase):
    """score_application stores the verdict silently and sets the per-verdict due time."""

    def test_score_sets_verdict_and_due_at_per_verdict(self):
        cohort = ScholarshipCohort.objects.create(
            code='b40-x', name='X', year=2026, success_delay_hours=2, decline_delay_hours=48)
        # Shortlisted: STR + at-floor grades (4 A + 1 B+) → due in success_delay_hours
        p1 = StudentProfile.objects.create(
            supabase_user_id='s1', receives_str=True,
            grades={'a': 'A', 'b': 'A', 'c': 'A', 'd': 'A', 'e': 'B+'})
        a1 = ScholarshipApplication.objects.create(
            cohort=cohort, profile=p1, consent_to_contact=True, intends_tertiary_2026=True)
        score_application(a1)
        a1.refresh_from_db()
        self.assertEqual(a1.verdict, 'shortlisted')
        self.assertEqual(a1.status, 'submitted')          # silent — status not flipped
        self.assertEqual(round((a1.decision_due_at - a1.submitted_at).total_seconds() / 3600), 2)

        # Declined: no grades → academic fail → due in decline_delay_hours
        p2 = StudentProfile.objects.create(supabase_user_id='s2', receives_str=True, grades={})
        a2 = ScholarshipApplication.objects.create(
            cohort=cohort, profile=p2, consent_to_contact=True, intends_tertiary_2026=True)
        score_application(a2)
        a2.refresh_from_db()
        self.assertEqual(a2.verdict, 'rejected')
        self.assertEqual(round((a2.decision_due_at - a2.submitted_at).total_seconds() / 3600), 48)
