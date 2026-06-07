"""Tests for Check 2 STEP 2/3 — the query SLA clock + reminder sweep (services)."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ResolutionItem, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.services import (
    is_ready_for_assignment, query_sla, send_query_reminders,
)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(
            code='c', name='B40', year=2026, query_response_sla_days=5)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'sla-{self.id()}', nric='030101-14-1234', name='Priya')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='profile_complete',
            profile_completed_at=timezone.now(), notify_email='p@example.com', locale='en')

    def _clarify(self, code='transport_cost_unknown'):
        return ResolutionItem.objects.create(
            application=self.app, source='check2', code=code, fact='other',
            kind='clarify', status='open')


class TestQuerySla(_Base):
    def test_not_ready_before_submission(self):
        self.app.profile_completed_at = None
        self.app.save()
        self.assertFalse(is_ready_for_assignment(self.app))

    def test_ready_when_no_open_queries(self):
        self.assertTrue(is_ready_for_assignment(self.app))
        self.assertEqual(query_sla(self.app)['open_count'], 0)

    def test_not_ready_with_open_query_inside_window(self):
        self._clarify()
        self.assertFalse(is_ready_for_assignment(self.app))
        sla = query_sla(self.app)
        self.assertTrue(sla['active'])
        self.assertFalse(sla['lapsed'])

    def test_ready_when_window_lapsed_even_with_open_query(self):
        self._clarify()
        self.app.profile_completed_at = timezone.now() - timedelta(days=6)
        self.app.save()
        sla = query_sla(self.app)
        self.assertTrue(sla['lapsed'])
        self.assertTrue(is_ready_for_assignment(self.app))  # proceed-as-is

    def test_ready_when_query_answered(self):
        item = self._clarify()
        self.assertFalse(is_ready_for_assignment(self.app))
        item.status = 'resolved'
        item.save()
        self.assertTrue(is_ready_for_assignment(self.app))


class TestQueryReminders(_Base):
    @patch('apps.scholarship.emails.send_query_reminder_email', return_value=True)
    def test_reminds_near_deadline_once(self, mock_email):
        self._clarify()
        # 3 days in (sla 5 → nudge from day 3) → due.
        self.app.profile_completed_at = timezone.now() - timedelta(days=3)
        self.app.save()
        self.assertEqual(send_query_reminders()['reminded'], 1)
        self.assertTrue(mock_email.called)
        self.app.refresh_from_db()
        self.assertIsNotNone(self.app.query_reminder_at)
        # idempotent — a second run sends nothing.
        mock_email.reset_mock()
        self.assertEqual(send_query_reminders()['reminded'], 0)
        self.assertFalse(mock_email.called)

    @patch('apps.scholarship.emails.send_query_reminder_email', return_value=True)
    def test_no_reminder_early_in_window(self, mock_email):
        self._clarify()  # submitted just now → too early (nudge starts day 3)
        self.assertEqual(send_query_reminders()['reminded'], 0)
        self.assertFalse(mock_email.called)

    @patch('apps.scholarship.emails.send_query_reminder_email', return_value=True)
    def test_no_reminder_when_lapsed(self, mock_email):
        self._clarify()
        self.app.profile_completed_at = timezone.now() - timedelta(days=7)
        self.app.save()
        self.assertEqual(send_query_reminders()['reminded'], 0)

    @patch('apps.scholarship.emails.send_query_reminder_email', return_value=True)
    def test_no_reminder_without_open_queries(self, mock_email):
        self.app.profile_completed_at = timezone.now() - timedelta(days=3)
        self.app.save()
        self.assertEqual(send_query_reminders()['reminded'], 0)
