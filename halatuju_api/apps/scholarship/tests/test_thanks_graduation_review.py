"""Sprint THANKS-SCHOLARS (owner 2026-11-16): "Thank yous are part of the scholar maintenance process."

A graduation thank-you is read and decided from the SCHOLAR FILE, under the file's own rules
(`views_admin/scholar_thanks.py`, `_ScholarsBase`), no longer by the `review` key from the case page:
- GET `admin/scholarship/scholars/<pk>/graduation-messages/` — `_file_for`: `scholars` holders in their own
  organisation, a super anywhere, a mentor ONLY for a current student (read-only, names never emails);
  everyone else one 404 (outside the fence) or 403 (no `scholars` key). It serves `may_decide`.
- POST `.../graduation-messages/<message_id>/review/` — `_may_write_file`; a mentor never decides. The order
  is fence → validate → lock: a message outside the file is the same 404 as a missing one; the re-scan of
  the scrubbed text (400 `scrubbed_leak`), `bad_text`, `bad_action` and the row lock stay.
- Review ALONE (a reviewer, even the assigned one) no longer reads or decides.
- A closed file's thank-you is still decidable: a student may thank their sponsor after closure.
"""
import datetime
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import mentoring
from apps.scholarship.maintenance_scope import has_file, is_in_maintenance
from apps.scholarship.models import GraduationMessage
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)
from apps.scholarship.tests.test_mentoring import make_mentor

THANKS_TEXT = 'Thank you for helping me finish my diploma.'
API = '/api/v1/admin/scholarship/scholars/'


def _read_url(app):
    return f'{API}{app.id}/graduation-messages/'


def _review_url(app, msg_id):
    return f'{API}{app.id}/graduation-messages/{msg_id}/review/'


def _scholar(cohort, **over):
    return make_application('maintenance', cohort=cohort,
                            active_at=timezone.now() - datetime.timedelta(days=60), **over)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ThanksOnTheScholarFileTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.cohort = make_cohort(owning_organisation=cls.org)
        cls.reviewer = make_admin('reviewer', owning_org=cls.org, permissions=['review', 'see_all'])
        cls.app = _scholar(cls.cohort, reviewer=cls.reviewer)
        cls.other_app = _scholar(cls.cohort)
        cls.org_admin = make_admin('org_admin', owning_org=cls.org, name='Siti Lead')
        cls.officer = make_admin('admin', owning_org=cls.org)
        cls.super = make_admin(super_admin=True)
        cls.other_org_admin = make_admin('org_admin', owning_org=make_org())
        # Keys decide, not labels: a reviewer LABEL given the `scholars` key decides.
        cls.reviewer_with_scholars = make_admin('reviewer', owning_org=cls.org, permissions=['review', 'scholars'])

    def setUp(self):
        self.msg = GraduationMessage.objects.create(application=self.app, raw_text=THANKS_TEXT, status='pending')

    def _post(self, admin, body, app=None, msg_id=None):
        return authed_client(admin).post(_review_url(app or self.app, msg_id or self.msg.id), body, format='json')

    def _get(self, admin, app=None):
        return authed_client(admin).get(_read_url(app or self.app))

    def _assert_untouched(self):
        self.msg.refresh_from_db()
        self.assertEqual((self.msg.status, self.msg.approved_by), ('pending', ''))

    # ── the shapes the tests lean on ──────────────────────────────────────────────────────────
    def test_the_shapes_hold_what_the_tests_say(self):
        self.assertTrue(self.org_admin.has_perm('scholars'))
        self.assertTrue(self.officer.has_perm('scholars'))
        self.assertTrue(self.reviewer.has_perm('review'))
        self.assertFalse(self.reviewer.has_perm('scholars'))
        self.assertEqual(self.app.assigned_to_id, self.reviewer.id)
        self.assertTrue(is_in_maintenance(self.app))

    # ── the decision ──────────────────────────────────────────────────────────────────────────
    def test_an_org_admin_approves_with_an_edited_text(self):
        r = self._post(self.org_admin, {'action': 'approve', 'scrubbed_text': 'Thank you, truly.'})
        self.assertEqual(r.status_code, 200, r.content)
        self.msg.refresh_from_db()
        self.assertEqual((self.msg.status, self.msg.scrubbed_text), ('approved', 'Thank you, truly.'))
        self.assertEqual(self.msg.approved_by, self.org_admin.email)

    def test_an_org_admin_rejects_with_a_note(self):
        r = self._post(self.org_admin, {'action': 'reject', 'review_note': 'Please write it again.'})
        self.assertEqual(r.status_code, 200, r.content)
        self.msg.refresh_from_db()
        self.assertEqual((self.msg.status, self.msg.review_note), ('rejected', 'Please write it again.'))

    def test_every_scholars_holder_decides(self):
        for admin in (self.officer, self.super, self.reviewer_with_scholars):
            msg = GraduationMessage.objects.create(application=self.app, raw_text=THANKS_TEXT, status='pending')
            r = self._post(admin, {'action': 'reject'}, msg_id=msg.id)
            self.assertEqual(r.status_code, 200, (admin.role, r.content))

    def test_a_blocked_message_can_be_rejected_not_approved(self):
        self.msg.status, self.msg.scan_result = 'blocked', ['name']
        self.msg.save()
        r = self._post(self.org_admin, {'action': 'approve'})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_reviewable'))
        self.assertEqual(self._post(self.org_admin, {'action': 'reject'}).status_code, 200)

    def test_a_closed_file_is_still_decidable(self):
        closed = make_application('closed', cohort=self.cohort)
        self.assertTrue(has_file(closed))
        self.assertFalse(is_in_maintenance(closed))
        msg = GraduationMessage.objects.create(application=closed, raw_text=THANKS_TEXT, status='pending')
        self.assertEqual(self._get(self.org_admin, closed).json()['may_decide'], True)
        r = self._post(self.org_admin, {'action': 'approve'}, app=closed, msg_id=msg.id)
        self.assertEqual(r.status_code, 200, r.content)

    # ── review ALONE no longer reads or decides ───────────────────────────────────────────────
    def test_review_alone_no_longer_reads_or_decides_even_the_assigned_reviewer(self):
        unassigned = make_admin('reviewer', owning_org=self.org)
        finance = make_admin('finance', owning_org=self.org, permissions=['payments_approve', 'review'])
        for admin in (self.reviewer, unassigned, finance):
            self.assertTrue(admin.has_perm('review'))
            self.assertFalse(admin.has_perm('scholars'))
            r = self._get(admin)
            self.assertEqual(r.status_code, 403, admin.role)
            self.assertNotIn(THANKS_TEXT, r.content.decode())
            for body in ({'action': 'approve'}, {'action': 'reject'}, {}):
                r = self._post(admin, body)
                self.assertEqual(r.status_code, 403, (admin.role, body))
                self.assertNotIn(THANKS_TEXT, r.content.decode())
        self._assert_untouched()

    # ── the fence: one 404 ────────────────────────────────────────────────────────────────────
    def test_another_organisation_gets_404(self):
        self.assertEqual(self._get(self.other_org_admin).status_code, 404)
        self.assertEqual(self._post(self.other_org_admin, {'action': 'approve'}).status_code, 404)
        self._assert_untouched()

    def test_a_message_outside_the_file_answers_like_a_missing_one(self):
        theirs = GraduationMessage.objects.create(application=self.other_app, raw_text='other', status='pending')
        missing = self._post(self.org_admin, {'action': 'approve'}, msg_id=999999)
        elsewhere = self._post(self.org_admin, {'action': 'approve'}, msg_id=theirs.id)
        self.assertEqual((missing.status_code, elsewhere.status_code), (404, 404))
        self.assertEqual(missing.json(), elsewhere.json())
        theirs.refresh_from_db()
        self.assertEqual(theirs.status, 'pending')

    def test_an_application_without_a_file_is_404(self):
        no_file = make_application('submitted', cohort=self.cohort)
        msg = GraduationMessage.objects.create(application=no_file, raw_text=THANKS_TEXT, status='pending')
        self.assertEqual(self._get(self.org_admin, no_file).status_code, 404)
        self.assertEqual(self._post(self.org_admin, {'action': 'approve'}, app=no_file, msg_id=msg.id).status_code,
                         404)

    # ── the mentor: read-only, names never emails ─────────────────────────────────────────────
    def _mentor_of(self, app):
        mentor = make_mentor(self.org)
        mentoring.assign(self.org_admin, app, mentor, email_student=False)
        mail.outbox.clear()
        return mentoring._login(mentor)

    def test_a_mentor_reads_their_student_read_only_with_names(self):
        login = self._mentor_of(self.app)
        self._post(self.org_admin, {'action': 'reject', 'review_note': 'Please write it again.'})
        r = self._get(login)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertIs(body['may_decide'], False)
        self.assertEqual(body['messages'][0]['approved_by'], 'Siti Lead')
        self.assertNotIn(self.org_admin.email, r.content.decode())
        # The reject note is staff-only: a mentor gets it blank, never the words.
        self.assertEqual(body['messages'][0]['review_note'], '')
        self.assertNotIn('Please write it again.', r.content.decode())

    def test_staff_still_read_the_reject_note(self):
        self._post(self.org_admin, {'action': 'reject', 'review_note': 'Please write it again.'})
        self.assertEqual(self._get(self.org_admin).json()['messages'][0]['review_note'],
                         'Please write it again.')

    def test_a_mentor_never_decides(self):
        login = self._mentor_of(self.app)
        for body in ({'action': 'approve'}, {'action': 'reject'}):
            self.assertEqual(self._post(login, body).status_code, 403)
        self._assert_untouched()

    def _staff_mentor_of(self, app):
        person = make_admin('reviewer', owning_org=self.org)
        from apps.scholarship.models import Mentor
        person.mentor = Mentor.objects.create(organisation=self.org)
        person.save(update_fields=['mentor'])
        mentoring.assign(self.org_admin, app, person.mentor, email_student=False)
        return person

    def test_staff_who_mentor_read_but_never_decide(self):
        person = self._staff_mentor_of(self.app)
        self.assertIs(self._get(person).json()['may_decide'], False)
        self.assertEqual(self._post(person, {'action': 'approve'}).status_code, 403)
        self._assert_untouched()

    def test_staff_who_mentor_never_read_the_reject_note(self):
        person = self._staff_mentor_of(self.app)
        self._post(self.org_admin, {'action': 'reject', 'review_note': 'Please write it again.'})
        body = self._get(person).json()
        self.assertEqual(body['messages'][0]['review_note'], '')
        self.assertNotIn('Please write it again.', str(body))

    def test_a_mentor_login_of_another_student_reads_404_and_posts_403(self):
        login = self._mentor_of(self.other_app)
        self.assertEqual(self._get(login).status_code, 404)
        # A mentor LOGIN may only GET (`mentor_methods`), so its POST stops at the door: 403.
        self.assertEqual(self._post(login, {'action': 'approve'}).status_code, 403)
        self._assert_untouched()

    def test_staff_who_mentor_another_student_read_and_post_404(self):
        person = self._staff_mentor_of(self.other_app)
        # Staff pass the door, then the file fence finds no assignment here: the same 404 as no file.
        self.assertEqual(self._get(person).status_code, 404)
        self.assertEqual(self._post(person, {'action': 'approve'}).status_code, 404)
        self._assert_untouched()

    # ── validation, inside the fence ──────────────────────────────────────────────────────────
    def test_a_scrubbed_text_that_leaks_is_400(self):
        with mock.patch('apps.scholarship.pool.scan_anon_for_identifiers', return_value=['name']):
            r = self._post(self.org_admin, {'action': 'approve', 'scrubbed_text': 'leaky'})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'scrubbed_leak'))
        self._assert_untouched()

    def test_an_empty_or_odd_action_is_bad_action(self):
        for body in ({}, {'action': 7}, {'action': 'publish'}):
            r = self._post(self.org_admin, body)
            self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_action'), body)
        self._assert_untouched()

    def test_a_scrubbed_text_that_is_not_a_string_is_bad_text(self):
        for bad in (42, ['a', 'b'], {'x': 1}):
            r = self._post(self.org_admin, {'action': 'approve', 'scrubbed_text': bad})
            self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_text'), bad)
        self._assert_untouched()

    def test_a_review_note_that_is_not_a_string_is_bad_text(self):
        r = self._post(self.org_admin, {'action': 'reject', 'review_note': ['no']})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_text'))
        self._assert_untouched()

    # ── the decision reads the row's CURRENT status under a lock ──────────────────────────────
    def test_a_decision_on_a_stale_copy_meets_the_landed_one(self):
        from apps.scholarship import in_programme
        stale = GraduationMessage.objects.get(pk=self.msg.pk)       # read while still pending
        in_programme.reject_graduation_message(self.msg, by_email='first@example.test')
        with self.assertRaises(in_programme.InProgrammeError) as caught:
            in_programme.approve_graduation_message(stale, by_email='second@example.test')
        self.assertEqual(caught.exception.code, 'not_reviewable')
        self.msg.refresh_from_db()
        self.assertEqual((self.msg.status, self.msg.approved_by), ('rejected', 'first@example.test'))

    def test_the_decision_takes_a_row_lock(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with mock.patch.object(connection.features, 'has_select_for_update', True), \
                CaptureQueriesContext(connection) as ctx:
            try:
                self._post(self.org_admin, {'action': 'approve'})
            except Exception:   # SQLite cannot run FOR UPDATE; Postgres can. Only the SQL is asked here.
                pass
        self.assertTrue(any('FOR UPDATE' in q['sql'] for q in ctx.captured_queries),
                        [q['sql'] for q in ctx.captured_queries])

    # ── the read ──────────────────────────────────────────────────────────────────────────────
    def test_a_holder_reads_the_messages_newest_first_and_may_decide(self):
        older = GraduationMessage.objects.create(application=self.app, raw_text='first try', status='blocked',
                                                 scan_result=['school'])
        GraduationMessage.objects.filter(pk=older.pk).update(created_at=self.msg.created_at - timedelta(days=1))
        GraduationMessage.objects.create(application=self.other_app, raw_text='not this file', status='pending')
        r = self._get(self.org_admin)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertIs(body['may_decide'], True)
        rows = body['messages']
        self.assertEqual([m['id'] for m in rows], [self.msg.id, older.id])
        self.assertEqual(rows[0]['raw_text'], THANKS_TEXT)
        self.assertEqual(rows[1]['scan_result'], ['school'])
        for key in ('status', 'raw_text', 'scrubbed_text', 'scan_result', 'review_note', 'ref'):
            self.assertIn(key, rows[0])

    def test_the_old_review_key_routes_are_gone(self):
        from django.urls import Resolver404, resolve
        for path in (f'/api/v1/admin/graduation-messages/{self.msg.id}/review/',
                     f'/api/v1/admin/scholarship/applications/{self.app.id}/graduation-messages/'):
            with self.assertRaises(Resolver404):
                resolve(path)
