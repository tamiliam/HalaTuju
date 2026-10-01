"""TD-257 — applicant data: the verdict briefing, a referee DELETE, and the help a student reads.

Three routes the TD-219 guard listed as never driven by any test:
  * `applications/<pk>/verdict-summary/`         GET    (AdminVerdictSummaryView) — dark behind
                                                         VERDICT_CASE_SUMMARY_ENABLED
  * `applications/<pk>/referees/<ref_id>/`       DELETE (AdminRefereeDetailView)
  * `scholarship/documents/<pk>/help/`           GET    (DocumentHelpView) — the student's own

The fourth route of this family, `applications/<pk>/interview-slots/<slot_id>/` (DELETE), is NOT
tested here, on purpose: no screen calls it. `withdrawInterviewSlot` in
`halatuju-web/src/lib/admin-api/interviews.ts` is exported and re-exported and called by nothing,
and no cron reaches the view. TD-257's brief was to report a dead route rather than test it for its
own sake, so it stays in the TD-219 ledger with that reason, for the lead to decide.

Both Gemini calls are mocked at the shared prose seam each module names (`_call_gemini_text`);
what is asserted is what the SERVICE put into the prompt and what it made of the reply.
"""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument, Referee
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_student,
)

API = '/api/v1/admin/scholarship/'
GEMINI_REPLY = {'markdown': 'Identity is clear; income needs the payslip.', 'model_used': 'gm-x'}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _ReviewerCase(TestCase):
    def setUp(self):
        cache.clear()           # the summary and the help throttle both live in the cache
        self.cohort = make_cohort()
        self.reviewer = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
        self.app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        self.client = authed_client(self.reviewer)


@override_settings(VERDICT_CASE_SUMMARY_ENABLED=True)
class TestVerdictSummary(_ReviewerCase):
    def _get(self, client=None):
        return (client or self.client).get(f'{API}applications/{self.app.id}/verdict-summary/')

    @mock.patch('apps.scholarship.verdict_narrative._call_gemini_text', return_value=GEMINI_REPLY)
    def test_the_assigned_reviewer_gets_a_briefing_built_from_the_verdict(self, gemini):
        r = self._get()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json(), {'summary': GEMINI_REPLY['markdown'], 'cached': False,
                                    'model': 'gm-x', 'enabled': True})
        # The prompt is the service's: the verdict's own open facts, never the raw row.
        prompt = gemini.call_args.args[0]
        self.assertIn('VERDICT:', prompt)
        self.assertIn('FACT:', prompt)

    @mock.patch('apps.scholarship.verdict_narrative._call_gemini_text', return_value=GEMINI_REPLY)
    def test_a_second_open_is_served_from_the_cache_without_a_second_call(self, gemini):
        self._get()
        r = self._get()
        self.assertEqual((r.json()['cached'], gemini.call_count), (True, 1))

    @mock.patch('apps.scholarship.verdict_narrative._call_gemini_text', return_value=GEMINI_REPLY)
    def test_dark_by_default_and_then_no_model_is_called(self, gemini):
        with override_settings(VERDICT_CASE_SUMMARY_ENABLED=False):
            r = self._get()
        self.assertEqual((r.status_code, r.json()), (200, {'enabled': False}))
        gemini.assert_not_called()

    @mock.patch('apps.scholarship.verdict_narrative._call_gemini_text', return_value=GEMINI_REPLY)
    def test_a_reviewer_not_assigned_to_the_case_reads_nothing(self, gemini):
        other = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
        self.assertEqual(self._get(client=authed_client(other)).status_code, 403)
        gemini.assert_not_called()


class TestDeleteReferee(_ReviewerCase):
    def _add(self, app, name):
        r = self.client.post(f'{API}applications/{app.id}/referees/',
                             {'name': name, 'role': 'teacher'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()['id']

    def _delete(self, app_id, ref_id, client=None):
        return (client or self.client).delete(f'{API}applications/{app_id}/referees/{ref_id}/')

    def test_the_assigned_reviewer_removes_a_referee(self):
        keep = self._add(self.app, 'Puan Kamala')
        drop = self._add(self.app, 'Encik Ravi')
        self.assertEqual(self._delete(self.app.id, drop).status_code, 204)
        self.assertEqual(list(Referee.objects.filter(application=self.app)
                              .values_list('id', flat=True)), [keep])

    def test_a_referee_is_reached_only_through_its_own_application(self):
        other_app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        theirs = self._add(other_app, 'Cikgu Lim')
        self.assertEqual(self._delete(self.app.id, theirs).status_code, 404)
        self.assertTrue(Referee.objects.filter(pk=theirs).exists())

    def test_a_reviewer_not_assigned_to_the_case_cannot_remove_one(self):
        ref = self._add(self.app, 'Puan Kamala')
        other = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
        self.assertEqual(self._delete(self.app.id, ref, client=authed_client(other)).status_code,
                         403)
        self.assertTrue(Referee.objects.filter(pk=ref).exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDocumentHelp(TestCase):
    """GET scholarship/documents/<pk>/help/ — the coach reacts to the document's soft verdict."""

    def setUp(self):
        cache.clear()
        self.student = make_student(name='Kavitha Raman')
        self.app = make_application('shortlisted', student=self.student)
        self.doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', storage_path='test/ic.jpg',
            vision_run_at=timezone.now(), vision_error='image too blurred')

    def _get(self, doc, student=None):
        return authed_client(student or self.student).get(
            f'/api/v1/scholarship/documents/{doc.id}/help/')

    @mock.patch('apps.scholarship.profile_engine._call_gemini_text',
                return_value={'markdown': 'Try again in daylight, Kavitha.', 'model_used': 'gm-x'})
    def test_an_unreadable_ic_gets_a_message_written_for_that_student(self, gemini):
        r = self._get(self.doc)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual((body['source'], body['verdict'], body['message']),
                         ('ai', 'unreadable', 'Try again in daylight, Kavitha.'))
        # The engine is handed the FIRST name only (its firewall), which the service derived.
        prompt = gemini.call_args.args[0].upper()
        self.assertIn('FIRST NAME IS: KAVITHA', prompt)
        self.assertNotIn('RAMAN', prompt)

    @mock.patch('apps.scholarship.profile_engine._call_gemini_text', return_value=GEMINI_REPLY)
    def test_a_document_with_nothing_wrong_spends_no_ai_call(self, gemini):
        unread = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', storage_path='test/ic2.jpg')
        r = self._get(unread)
        self.assertEqual((r.status_code, r.json()), (200, {'message': '', 'source': 'none'}))
        gemini.assert_not_called()

    @mock.patch('apps.scholarship.profile_engine._call_gemini_text', return_value=GEMINI_REPLY)
    def test_another_students_document_is_not_found(self, gemini):
        self.assertEqual(self._get(self.doc, student=make_student()).status_code, 404)
        gemini.assert_not_called()
