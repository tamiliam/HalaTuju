"""Sprint THANKS (owner 2026-11-16): a graduation thank-you is read and moderated from the student's case
page by whoever holds the `review` KEY. The role is only a label; keys decide.

- POST `admin/graduation-messages/<pk>/review/` asks the key (it asked the reviewer label before), keeps
  the org fence (404 across organisations), the re-scan of the scrubbed text (400 `scrubbed_leak`) and the
  pending / blocked rules.
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
