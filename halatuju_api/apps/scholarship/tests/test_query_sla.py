"""Tests for Check 2 STEP 2/3 — the query SLA clock + reminder sweep (services)."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    FundingNeed, ResolutionItem, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.services import (
    autogenerate_ready_profiles, is_ready_for_assignment, query_sla,
    send_due_query_emails, send_query_reminders,
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


class TestStep3AutoGenerate(_Base):
    """Check 2 STEP 3: the flag-gated auto-generation sweep drafts a profile for ready
    applications and never regenerates an existing one."""
    def test_off_by_default(self):
        with self.settings(CHECK2_AUTO_GENERATE=False):
            self.assertEqual(autogenerate_ready_profiles()['generated'], 0)

    @patch('apps.scholarship.profile_engine.generate_sponsor_profile',
           return_value={'markdown': '# Profile', 'model_used': 'gemini-2.5-flash'})
    def test_generates_for_ready_app_when_enabled(self, mock_gen):
        # Ready: no open clarify queries.
        with self.settings(CHECK2_AUTO_GENERATE=True):
            result = autogenerate_ready_profiles()
        self.assertEqual(result['generated'], 1)
        self.assertTrue(mock_gen.called)
        self.app.refresh_from_db()
        self.assertEqual(self.app.sponsor_profile.draft_markdown, '# Profile')

    @patch('apps.scholarship.profile_engine.generate_sponsor_profile')
    def test_skips_when_not_ready(self, mock_gen):
        self._clarify()  # an open clarify query, inside the window → not ready
        with self.settings(CHECK2_AUTO_GENERATE=True):
            result = autogenerate_ready_profiles()
        self.assertEqual(result['generated'], 0)
        self.assertFalse(mock_gen.called)

    @patch('apps.scholarship.profile_engine.generate_sponsor_profile',
           return_value={'markdown': '# Profile', 'model_used': 'gemini-2.5-flash'})
    def test_does_not_regenerate(self, mock_gen):
        with self.settings(CHECK2_AUTO_GENERATE=True):
            autogenerate_ready_profiles()
            mock_gen.reset_mock()
            again = autogenerate_ready_profiles()
        self.assertEqual(again['generated'], 0)
        self.assertFalse(mock_gen.called)


class TestDueQueryEmails(_Base):
    """Check 2 STEP 2: the delayed 'we have a few questions' email (~2h after submit)."""
    @patch('apps.scholarship.emails.send_query_raised_email', return_value=True)
    def test_sends_after_delay_once(self, mock_email):
        # Submitted 3h ago, with completeness gaps → sync raises clarify queries → email.
        self.app.profile_completed_at = timezone.now() - timedelta(hours=3)
        self.app.save()
        self.assertEqual(send_due_query_emails()['sent'], 1)
        self.assertTrue(mock_email.called)
        self.app.refresh_from_db()
        self.assertIsNotNone(self.app.query_raised_notified_at)
        # idempotent — a second sweep sends nothing.
        mock_email.reset_mock()
        self.assertEqual(send_due_query_emails()['sent'], 0)
        self.assertFalse(mock_email.called)

    @patch('apps.scholarship.emails.send_query_raised_email', return_value=True)
    def test_no_email_before_the_delay(self, mock_email):
        # Submitted just now → too early for the ~2h email.
        self.assertEqual(send_due_query_emails()['sent'], 0)
        self.assertFalse(mock_email.called)

    @patch('apps.scholarship.emails.send_query_raised_email', return_value=True)
    def test_no_email_when_no_questions(self, mock_email):
        # No clarify gaps: course set, sibling known, device ticked, residential pathway.
        self.app.profile_completed_at = timezone.now() - timedelta(hours=3)
        self.app.field_of_study = 'Education'
        self.app.siblings_in_tertiary = 0
        self.app.chosen_pathway = 'matric'
        self.app.pathway_certainty = 'sure'
        self.app.save()
        FundingNeed.objects.create(application=self.app, categories=['device'])
        self.assertEqual(send_due_query_emails()['sent'], 0)
        self.assertFalse(mock_email.called)
