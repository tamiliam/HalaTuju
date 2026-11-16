"""Sprint THANKS (owner 2026-11-16): a graduation thank-you is read and moderated from the student's case
page by whoever holds the `review` KEY. The role is only a label; keys decide.

- POST `admin/graduation-messages/<pk>/review/` asks the key (it asked the reviewer label before), keeps
  the org fence (404 across organisations), the re-scan of the scrubbed text (400 `scrubbed_leak`) and the
  pending / blocked rules.
- Review round: the POST keeps the CASE fence too (the GET's `_scoped_application`), and outside it the answer
  is 404 before the body is read; a decision locks the row; a text that is not a string is 400 `bad_text`.
- GET `admin/scholarship/applications/<pk>/graduation-messages/` serves the case's messages to a key holder,
  behind the case page's own read fence (`_scoped_application`).
"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings

from apps.scholarship.models import GraduationMessage
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

THANKS_TEXT = 'Thank you for helping me finish my diploma.'


def _review_url(msg):
    return f'/api/v1/admin/graduation-messages/{msg.id}/review/'


def _read_url(app):
    return f'/api/v1/admin/scholarship/applications/{app.id}/graduation-messages/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ThanksReviewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.cohort = make_cohort(owning_organisation=cls.org)
        cls.keyholder = make_admin('reviewer', owning_org=cls.org)
        cls.app = make_application('submitted', cohort=cls.cohort, reviewer=cls.keyholder)
        # The reviewer LABEL without the `review` key.
        cls.label_only = make_admin('reviewer', owning_org=cls.org, permissions=['see_all'])
        # An organisation admin who holds `review` (the preset does not; this row was given it).
        cls.org_admin_review = make_admin('org_admin', owning_org=cls.org, permissions=['review'])
        cls.org_admin_plain = make_admin('org_admin', owning_org=cls.org)
        cls.other_org_keyholder = make_admin('reviewer', owning_org=make_org(),
                                             permissions=['review', 'see_all'])
        cls.super = make_admin(super_admin=True)

    def setUp(self):
        self.msg = GraduationMessage.objects.create(application=self.app, raw_text=THANKS_TEXT, status='pending')

    def _post(self, admin, msg, body):
        return authed_client(admin).post(_review_url(msg), body, format='json')

    # ── the shapes the tests lean on ──────────────────────────────────────────────────────────
    def test_the_shapes_hold_what_the_tests_say(self):
        self.assertTrue(self.keyholder.has_perm('review'))
        self.assertFalse(self.label_only.has_perm('review'))
        self.assertTrue(self.org_admin_review.has_perm('review'))
        self.assertFalse(self.org_admin_plain.has_perm('review'))

    # ── the POST ──────────────────────────────────────────────────────────────────────────────
    def test_key_holder_approves_with_an_edited_text(self):
        r = self._post(self.keyholder, self.msg, {'action': 'approve', 'scrubbed_text': 'Thank you, truly.'})
        self.assertEqual(r.status_code, 200, r.content)
        self.msg.refresh_from_db()
        self.assertEqual((self.msg.status, self.msg.scrubbed_text), ('approved', 'Thank you, truly.'))
        self.assertEqual(self.msg.approved_by, self.keyholder.email)

    def test_key_holder_rejects_with_a_note(self):
        r = self._post(self.keyholder, self.msg, {'action': 'reject', 'review_note': 'Please write it again.'})
        self.assertEqual(r.status_code, 200, r.content)
        self.msg.refresh_from_db()
        self.assertEqual((self.msg.status, self.msg.review_note), ('rejected', 'Please write it again.'))

    def test_a_blocked_message_can_be_rejected_not_approved(self):
        self.msg.status, self.msg.scan_result = 'blocked', ['name']
        self.msg.save()
        r = self._post(self.keyholder, self.msg, {'action': 'approve'})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_reviewable'))
        r = self._post(self.keyholder, self.msg, {'action': 'reject'})
        self.assertEqual(r.status_code, 200, r.content)

    def test_reviewer_label_without_the_key_is_refused(self):
        r = self._post(self.label_only, self.msg, {'action': 'approve'})
        self.assertEqual(r.status_code, 403)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, 'pending')

    def test_org_admin_holding_review_is_allowed(self):
        r = self._post(self.org_admin_review, self.msg, {'action': 'approve'})
        self.assertEqual(r.status_code, 200, r.content)

    def test_org_admin_without_review_is_refused(self):
        self.assertEqual(self._post(self.org_admin_plain, self.msg, {'action': 'approve'}).status_code, 403)

    def test_super_is_allowed(self):
        self.assertEqual(self._post(self.super, self.msg, {'action': 'reject'}).status_code, 200)

    def test_another_organisation_gets_404(self):
        r = self._post(self.other_org_keyholder, self.msg, {'action': 'approve'})
        self.assertEqual(r.status_code, 404)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, 'pending')

    def test_a_scrubbed_text_that_leaks_is_400(self):
        with mock.patch('apps.scholarship.pool.scan_anon_for_identifiers', return_value=['name']):
            r = self._post(self.keyholder, self.msg, {'action': 'approve', 'scrubbed_text': 'leaky'})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'scrubbed_leak'))
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, 'pending')

    # ── review round: the case fence on the POST ──────────────────────────────────────────────
    def _assert_hidden(self, admin, body):
        r = self._post(admin, self.msg, body)
        self.assertEqual(r.status_code, 404, r.content)
        self.assertNotIn(THANKS_TEXT, r.content.decode())
        self.msg.refresh_from_db()
        self.assertEqual((self.msg.status, self.msg.approved_by), ('pending', ''))

    def test_an_unassigned_reviewer_in_the_same_org_gets_404(self):
        unassigned = make_admin('reviewer', owning_org=self.org)
        self.assertTrue(unassigned.has_perm('review'))
        for body in ({'action': 'approve'}, {'action': 'reject'}, {}):
            self._assert_hidden(unassigned, body)   # an empty action too: never 400 on a real message

    def test_finance_given_review_reaches_only_its_assigned_cases(self):
        finance = make_admin('finance', owning_org=self.org, permissions=['payments_approve', 'review'])
        self.assertTrue(finance.has_perm('review'))
        self.assertFalse(finance.has_perm('see_all'))
        self._assert_hidden(finance, {'action': 'approve'})

    def test_a_missing_message_and_a_fenced_one_answer_alike(self):
        unassigned = make_admin('reviewer', owning_org=self.org)
        r = authed_client(unassigned).post('/api/v1/admin/graduation-messages/999999/review/', {}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json(), self._post(unassigned, self.msg, {}).json())

    def test_a_see_all_holder_with_review_decides_on_an_unassigned_case(self):
        wide = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all'])
        r = self._post(wide, self.msg, {'action': 'approve'})
        self.assertEqual(r.status_code, 200, r.content)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, 'approved')

    def test_inside_the_fence_an_empty_action_is_still_bad_action(self):
        r = self._post(self.keyholder, self.msg, {})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_action'))

    # ── review round: a text that is not a string ─────────────────────────────────────────────
    def test_a_scrubbed_text_that_is_not_a_string_is_bad_text(self):
        for bad in (42, ['a', 'b'], {'x': 1}):
            r = self._post(self.keyholder, self.msg, {'action': 'approve', 'scrubbed_text': bad})
            self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_text'), bad)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, 'pending')

    def test_a_review_note_that_is_not_a_string_is_bad_text(self):
        r = self._post(self.keyholder, self.msg, {'action': 'reject', 'review_note': ['no']})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_text'))
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, 'pending')

    def test_an_action_that_is_not_a_string_is_bad_action(self):
        r = self._post(self.keyholder, self.msg, {'action': 7})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_action'))

    # ── review round: the decision reads the row's CURRENT status under a lock ────────────────
    def test_a_decision_on_a_stale_copy_meets_the_landed_one(self):
        from apps.scholarship import in_programme
        stale = GraduationMessage.objects.get(pk=self.msg.pk)       # read while still pending
        in_programme.reject_graduation_message(self.msg, by_email='first@example.test')
        with self.assertRaises(in_programme.InProgrammeError) as caught:
            in_programme.approve_graduation_message(stale, by_email='second@example.test')
        self.assertEqual(caught.exception.code, 'not_reviewable')
        with self.assertRaises(in_programme.InProgrammeError):
            in_programme.reject_graduation_message(
                GraduationMessage.objects.get(pk=self.msg.pk), by_email='third@example.test')
        self.msg.refresh_from_db()
        self.assertEqual((self.msg.status, self.msg.approved_by), ('rejected', 'first@example.test'))

    def test_the_decision_takes_a_row_lock(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.scholarship import in_programme
        with mock.patch.object(connection.features, 'has_select_for_update', True), \
                CaptureQueriesContext(connection) as ctx:
            try:
                in_programme.approve_graduation_message(self.msg, by_email='a@example.test')
            except Exception:   # SQLite cannot run FOR UPDATE; Postgres can. Only the SQL is asked here.
                pass
        self.assertTrue(any('FOR UPDATE' in q['sql'] for q in ctx.captured_queries),
                        [q['sql'] for q in ctx.captured_queries])

    # ── the GET ───────────────────────────────────────────────────────────────────────────────
    def test_key_holder_reads_the_case_messages(self):
        older = GraduationMessage.objects.create(application=self.app, raw_text='first try', status='blocked',
                                                 scan_result=['school'])
        GraduationMessage.objects.filter(pk=older.pk).update(created_at=self.msg.created_at - timedelta(days=1))
        r = authed_client(self.keyholder).get(_read_url(self.app))
        self.assertEqual(r.status_code, 200, r.content)
        rows = r.json()['messages']
        self.assertEqual([m['id'] for m in rows], [self.msg.id, older.id])
        self.assertEqual(rows[0]['raw_text'], THANKS_TEXT)
        self.assertEqual(rows[1]['scan_result'], ['school'])
        for key in ('status', 'raw_text', 'scrubbed_text', 'scan_result', 'review_note'):
            self.assertIn(key, rows[0])

    def test_the_read_is_hidden_without_the_key(self):
        for admin in (self.label_only, self.org_admin_plain):
            r = authed_client(admin).get(_read_url(self.app))
            self.assertEqual(r.status_code, 403, admin.role)
            self.assertNotIn(THANKS_TEXT, r.content.decode())

    def test_org_admin_holding_review_reads(self):
        self.assertEqual(authed_client(self.org_admin_review).get(_read_url(self.app)).status_code, 200)

    def test_the_read_keeps_the_case_fence(self):
        self.assertEqual(authed_client(self.other_org_keyholder).get(_read_url(self.app)).status_code, 404)
        unassigned = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(authed_client(unassigned).get(_read_url(self.app)).status_code, 403)
