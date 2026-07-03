"""Tests for Check 2 STEP 2/3 — the query SLA clock + reminder sweep (services)."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
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
        item = self._clarify()
        self.app.profile_completed_at = timezone.now() - timedelta(days=6)
        self.app.save()
        # V3 (#8): lapse is now PER-ITEM — back-date the query's own clock so its window has passed.
        ResolutionItem.objects.filter(pk=item.pk).update(created_at=timezone.now() - timedelta(days=6))
        sla = query_sla(self.app)
        self.assertTrue(sla['lapsed'])
        self.assertTrue(is_ready_for_assignment(self.app))  # proceed-as-is

    def test_late_query_not_born_lapsed_but_floor_ready(self):
        # V3 (#8): a query raised LATE (submit was 6 days ago, query created just now) is NOT
        # born-lapsed — it gets its own fresh 5-day window (per-item). But the reviewer can still
        # proceed because the SUBMIT-window FLOOR (submit + SLA) has passed (owner decision).
        self.app.profile_completed_at = timezone.now() - timedelta(days=6)
        self.app.save()
        self._clarify()                               # created now → fresh per-item window
        sla = query_sla(self.app)
        self.assertFalse(sla['lapsed'])               # per-item: not born-lapsed
        self.assertTrue(is_ready_for_assignment(self.app))  # floor: submit+SLA passed → ready

    def test_ready_when_query_answered(self):
        item = self._clarify()
        self.assertFalse(is_ready_for_assignment(self.app))
        item.status = 'resolved'
        item.save()
        self.assertTrue(is_ready_for_assignment(self.app))


@override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestQueryReminders(_Base):
    @patch('apps.scholarship.emails.send_query_reminder_email', return_value=True)
    def test_reminds_near_deadline_once(self, mock_email):
        item = self._clarify()
        # 3 days into the query's OWN window (sla 5 → nudge from day 3) → due. V3 (#8): the reminder
        # clock is per-item, so back-date the query's created_at, not just submit.
        self.app.profile_completed_at = timezone.now() - timedelta(days=3)
        self.app.save()
        ResolutionItem.objects.filter(pk=item.pk).update(created_at=timezone.now() - timedelta(days=3))
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
        item = self._clarify()
        self.app.profile_completed_at = timezone.now() - timedelta(days=7)
        self.app.save()
        # V3 (#8): lapse is per-item — back-date the query's own clock so it's genuinely lapsed.
        ResolutionItem.objects.filter(pk=item.pk).update(created_at=timezone.now() - timedelta(days=7))
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


@override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
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
    def test_sends_for_a_missing_doc_only(self, mock_email):
        # No clarify queries, but a compulsory document is missing → the "review assistant"
        # upload request counts, so the delayed email still goes out.
        self.app.profile_completed_at = timezone.now() - timedelta(hours=3)
        self.app.save()
        ResolutionItem.objects.create(
            application=self.app, source='system', code='birth_cert_missing',
            fact='income', kind='doc', doc_type='birth_certificate', status='open')
        self.assertEqual(send_due_query_emails()['sent'], 1)
        self.assertTrue(mock_email.called)

    @patch('apps.scholarship.emails.send_query_raised_email', return_value=True)
    def test_no_email_when_no_questions(self, mock_email):
        # No clarify gaps: course set, sibling known, device ticked, residential pathway,
        # AND household income complete (father earns + payslip, mother homemaker — S1).
        self.app.profile_completed_at = timezone.now() - timedelta(hours=3)
        self.app.field_of_study = 'Education'
        self.app.siblings_in_tertiary = 0
        self.app.chosen_pathway = 'matric'
        self.app.pathway_certainty = 'sure'
        self.app.father_occupation = 'gov'
        self.app.mother_occupation = 'homemaker'
        self.app.save()
        from apps.scholarship.models import ApplicantDocument
        ApplicantDocument.objects.create(
            application=self.app, doc_type='salary_slip', household_member='father',
            storage_path='x/slip')
        FundingNeed.objects.create(application=self.app, categories=['device'])
        self.assertEqual(send_due_query_emails()['sent'], 0)
        self.assertFalse(mock_email.called)

    @patch('apps.scholarship.emails.send_query_raised_email', return_value=True)
    def test_sends_for_an_officer_item_only(self, mock_email):
        # No clarify gaps, no system docs — but the reviewer raised a doc-request. Officer
        # items always show in the Action Centre, so they now count toward this delayed
        # email (previously ignored → a reviewer request/re-request went unnotified).
        self.app.profile_completed_at = timezone.now() - timedelta(hours=3)
        self.app.field_of_study = 'Education'
        self.app.siblings_in_tertiary = 0
        self.app.chosen_pathway = 'matric'
        self.app.pathway_certainty = 'sure'
        self.app.save()
        FundingNeed.objects.create(application=self.app, categories=['device'])
        ResolutionItem.objects.create(
            application=self.app, source='officer', code='officer_1', fact='pathway',
            kind='doc', doc_type='offer_letter', prompt='Upload your offer letter.', status='open')
        self.assertEqual(send_due_query_emails()['sent'], 1)
        self.assertTrue(mock_email.called)

    @patch('apps.scholarship.emails.send_query_raised_email', return_value=True)
    def test_sends_for_a_pathway_confirm_only(self, mock_email):
        # No clarify gaps, but the offer clashes with the declared school → the one-tap
        # pathway confirm is an open Check-2 query, so the email still goes out.
        from apps.scholarship.models import ApplicantDocument
        self.app.profile_completed_at = timezone.now() - timedelta(hours=3)
        self.app.field_of_study = 'Education'
        self.app.siblings_in_tertiary = 0
        self.app.chosen_pathway = 'matric'
        self.app.pathway_certainty = 'sure'
        self.app.pre_u_institution = 'SMK Mentakab'
        self.app.aspirations = 'Teach.'
        self.app.save()
        FundingNeed.objects.create(application=self.app, categories=['device'])
        ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter', storage_path=f'{self.app.id}/o/x',
            vision_fields={'fields': {'candidate_name': 'Priya', 'candidate_nric': '030101141234',
                           'programme': 'Program Matrikulasi', 'institution': 'SMK Temerloh'},
                           'student_verdict': 'ok', 'warnings': [], 'error': ''},
            vision_run_at=timezone.now())
        self.assertEqual(send_due_query_emails()['sent'], 1)
        self.assertTrue(mock_email.called)

    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=False)
    @patch('apps.scholarship.emails.send_query_raised_email', return_value=True)
    def test_held_when_flag_off(self, mock_email):
        # Even when due, no email goes out while student queries are held.
        self.app.profile_completed_at = timezone.now() - timedelta(hours=3)
        self.app.save()
        self.assertEqual(send_due_query_emails()['sent'], 0)
        self.assertFalse(mock_email.called)
