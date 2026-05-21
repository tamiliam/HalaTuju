"""Tests for the send_pending_decision_emails management command (delayed fail emails)."""
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort


class TestDecisionEmailCommand(TestCase):

    def setUp(self):
        self.cohort = ScholarshipCohort.objects.create(
            code='c', name='B40 Programme', year=2026, fail_email_delay_days=3,
        )

    def _rejected(self, days_ago, email='reject@example.com'):
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, status='rejected', notify_email=email,
            shortlisted_at=timezone.now() - timedelta(days=days_ago),
        )

    def test_sends_when_past_delay(self):
        app = self._rejected(4)
        call_command('send_pending_decision_emails')
        app.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('reject@example.com', mail.outbox[0].to)
        self.assertIsNotNone(app.decision_email_sent_at)

    def test_skips_when_not_due(self):
        app = self._rejected(1)
        call_command('send_pending_decision_emails')
        app.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(app.decision_email_sent_at)

    def test_does_not_resend(self):
        app = self._rejected(4)
        app.decision_email_sent_at = timezone.now()
        app.save(update_fields=['decision_email_sent_at'])
        call_command('send_pending_decision_emails')
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_shortlisted(self):
        ScholarshipApplication.objects.create(
            cohort=self.cohort, status='shortlisted', bucket='A',
            notify_email='pass@example.com',
            shortlisted_at=timezone.now() - timedelta(days=5),
        )
        call_command('send_pending_decision_emails')
        self.assertEqual(len(mail.outbox), 0)

    def test_dry_run_sends_nothing(self):
        app = self._rejected(4)
        call_command('send_pending_decision_emails', '--dry-run')
        app.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(app.decision_email_sent_at)

    def test_skips_when_no_email(self):
        app = self._rejected(4, email='')
        call_command('send_pending_decision_emails')
        app.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(app.decision_email_sent_at)
