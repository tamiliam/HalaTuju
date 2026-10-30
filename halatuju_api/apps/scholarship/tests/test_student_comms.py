"""Student maintenance Sprint 4b — the emails a funded student receives about her results
(`student_comms`, the `results-due-reminders` / `results-overdue-flag` jobs, and the queried notice).

Pinned from the harm:
  * THE KILL SWITCH — with `MAINTENANCE_REMINDERS_ENABLED` off nothing is sent AND nothing is stamped,
    so switching on later still reaches every student who is due or late;
  * each job is idempotent: a reminder at most once per `results_reminder_every_days`, an overdue
    flag once per term (one activity line, one email);
  * she is written to in HER language, from HER organisation, and the tenant is billed (metered);
  * an organisation's wording is its own: the settings tab is fenced to the caller's organisation,
    and a token the kind does not supply, or a banned phrase, refuses the save;
  * the platform defaults are complete in en / ms / ta and use only the kind's tokens.
"""
import datetime
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import email_templates, results_expectations as rx, results_review, student_comms
from apps.scholarship.models import (
    ResultsExpectation, StudentActivity, StudentEmailLog, StudentEmailSwitch, StudentEmailTemplate,
    UsageEvent,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, record_result,
)

ON = override_settings(MAINTENANCE_REMINDERS_ENABLED=True,
                       EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
API = '/api/v1/admin/scholarship/organisation/student-emails/'


def _student(locale='en', **over):
    app = make_application('maintenance', active_at=timezone.now() - timedelta(days=30),
                           notify_email='aisyah@example.test', locale=locale, **over)
    rx.ensure_expectations(app)
    return app, ResultsExpectation.objects.get(application=app)


def _due_in(exp, days):
    ResultsExpectation.objects.filter(pk=exp.pk).update(due_on=timezone.localdate() + timedelta(days=days))


class TestTheDefaults(TestCase):
    def test_every_kind_has_wording_in_every_language_using_only_its_tokens(self):
        for kind in student_comms.KINDS:
            for lang in student_comms.LANGUAGES:
                with self.subTest(kind=kind, lang=lang):
                    subject, body = student_comms.DEFAULTS[kind][lang]
                    self.assertTrue(subject.strip() and body.strip())
                    self.assertEqual(email_templates.unknown_placeholders(
                        student_comms.PLACEHOLDERS[kind], subject, body), ())
                    self.assertIn('{link}', body)
                    self.assertEqual(email_templates.banned_phrases(student_comms.BANNED, subject, body), ())


@ON
class TestTheReminder(TestCase):
    def test_inside_the_lead_once_per_cadence_never_while_waiting_for_review(self):
        app, exp = _student()
        _due_in(exp, 20)                                         # lead is 14: too early
        self.assertEqual(rx.send_due_reminders(), 0)
        _due_in(exp, 10)
        self.assertEqual(rx.send_due_reminders(), 1)
        self.assertEqual(rx.send_due_reminders(), 0)            # same day: idempotent
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['aisyah@example.test'])
        ResultsExpectation.objects.filter(pk=exp.pk).update(reminded_at=timezone.now() - timedelta(days=7))
        self.assertEqual(rx.send_due_reminders(), 1)            # a week on: again
        ResultsExpectation.objects.filter(pk=exp.pk).update(reminded_at=None)
        record_result(app, semester='S1', cgpa='3.10')         # waiting for the officer
        self.assertEqual(rx.send_due_reminders(), 0)

    def test_she_is_written_to_in_her_language_with_the_date_in_it(self):
        _app, exp = _student(locale='ms')
        _due_in(exp, 5)
        rx.send_due_reminders()
        due = timezone.localdate() + timedelta(days=5)
        self.assertIn(student_comms.format_day(due, 'ms'), mail.outbox[0].subject)
        self.assertIn('Salam', mail.outbox[0].body)

    def test_the_send_is_metered_to_her_organisation(self):
        app, exp = _student()
        _due_in(exp, 5)
        rx.send_due_reminders()
        row = UsageEvent.objects.get(source='send_student_email')
        self.assertEqual(row.organisation_id, app.owning_organisation_id)

    def test_the_organisation_wording_is_used(self):
        app, exp = _student()
        student_comms.save(app.owning_organisation, 'results_due', 'en', 'Due {due_date}',
                           'Hello {name}, your result is due {due_date}. {link}')
        _due_in(exp, 5)
        rx.send_due_reminders()
        self.assertTrue(mail.outbox[0].subject.startswith('Due '))


class TestTheKillSwitch(TestCase):
    @override_settings(MAINTENANCE_REMINDERS_ENABLED=False,
                       EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_off_sends_nothing_and_stamps_no_email(self):
        """Off: no email, no `reminded_at` / `overdue_emailed_at` — so switching on later still reaches
        her. The file's "not submitted" line is staff-side and is written either way (review L8)."""
        app, exp = _student()
        _due_in(exp, 5)
        self.assertEqual((rx.send_due_reminders(), rx.flag_overdue()), (0, 0))
        ResultsExpectation.objects.filter(pk=exp.pk).update(due_on=timezone.localdate() - timedelta(days=30))
        self.assertEqual(rx.flag_overdue(), 1)
        results_review.review(record_result(app, semester='S', cgpa='3.0'), decision='queried', note='Blurred.')
        exp.refresh_from_db()
        self.assertEqual((exp.reminded_at, exp.overdue_emailed_at, len(mail.outbox)), (None, None, 0))
        self.assertIsNotNone(exp.overdue_flagged_at)


@ON
class TestTheOrganisationSwitch(TestCase):
    """S6a: each of the three doors, switched off by HER organisation, sends nothing, stamps nothing
    and logs nothing; the platform flag still outranks a row that says on."""

    def _off(self, app, kind):
        StudentEmailSwitch.objects.create(organisation=app.owning_organisation, key=kind, enabled=False)

    def test_results_due_off(self):
        """Off writes NOTHING (review L3): the switch is asked before the claim, so there is no claim
        and no give-back on `results_expectations`."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        app, exp = _student()
        self._off(app, 'results_due')
        _due_in(exp, 5)
        with CaptureQueriesContext(connection) as q:
            self.assertEqual(rx.send_due_reminders(), 0)
        self.assertFalse([x for x in q.captured_queries
                          if x['sql'].lstrip().upper().startswith('UPDATE') and 'results_expectations' in x['sql']])
        exp.refresh_from_db()
        self.assertEqual((exp.reminded_at, len(mail.outbox), StudentEmailLog.objects.count()), (None, 0, 0))

    def test_a_failed_log_write_does_not_undo_the_send(self):
        """Review L2: the email has gone; a broken log row is logged, never raised."""
        from unittest.mock import patch
        from django.db import DatabaseError
        app, exp = _student()
        _due_in(exp, 5)
        with patch.object(StudentEmailLog.objects, 'create', side_effect=DatabaseError('down')), \
                self.assertLogs('apps.scholarship.student_comms', level='ERROR'):
            self.assertEqual(rx.send_due_reminders(), 1)
        exp.refresh_from_db()
        self.assertIsNotNone(exp.reminded_at)

    def test_results_overdue_off_still_flags_the_file(self):
        app, exp = _student()
        self._off(app, 'results_overdue')
        ResultsExpectation.objects.filter(pk=exp.pk).update(due_on=timezone.localdate() - timedelta(days=30))
        self.assertEqual(rx.flag_overdue(), 1)
        exp.refresh_from_db()
        self.assertEqual((exp.overdue_emailed_at, len(mail.outbox)), (None, 0))
        self.assertIsNotNone(exp.overdue_flagged_at)

    def test_result_queried_off(self):
        app, _exp = _student()
        self._off(app, 'result_queried')
        with self.captureOnCommitCallbacks(execute=True):
            results_review.review(record_result(app, semester='S1', cgpa='3.0'), decision='queried', note='x')
        self.assertEqual(len(mail.outbox), 0)

    def test_on_each_send_is_logged_for_last_sent(self):
        app, exp = _student()
        _due_in(exp, 5)
        rx.send_due_reminders()
        self.assertEqual(list(StudentEmailLog.objects.values_list('application_id', 'key', 'ok', 'recipient')),
                         [(app.id, 'results_due', True, 'aisyah@example.test')])

    @override_settings(MAINTENANCE_REMINDERS_ENABLED=False)
    def test_the_platform_flag_outranks_a_row_that_says_on(self):
        app, exp = _student()
        StudentEmailSwitch.objects.create(organisation=app.owning_organisation, key='results_due', enabled=True)
        _due_in(exp, 5)
        self.assertEqual((rx.send_due_reminders(), len(mail.outbox)), (0, 0))


@ON
class TestOverdue(TestCase):
    def test_flagged_once_with_one_line_and_one_email(self):
        app, exp = _student()
        ResultsExpectation.objects.filter(pk=exp.pk).update(due_on=timezone.localdate() - timedelta(days=14))
        self.assertEqual(rx.flag_overdue(), 0)                   # inside the grace
        ResultsExpectation.objects.filter(pk=exp.pk).update(due_on=timezone.localdate() - timedelta(days=15))
        self.assertEqual(rx.flag_overdue(), 1)
        self.assertEqual(rx.flag_overdue(), 0)                   # idempotent
        self.assertEqual(StudentActivity.objects.filter(application=app, event='results_overdue').count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_closed_student_is_never_written_to(self):
        app, exp = _student()
        ResultsExpectation.objects.filter(pk=exp.pk).update(due_on=timezone.localdate() - timedelta(days=60))
        type(app).objects.filter(pk=app.pk).update(status='closed')
        self.assertEqual((rx.flag_overdue(), rx.send_due_reminders()), (0, 0))


@ON
class TestTheQueriedNotice(TestCase):
    def test_a_query_tells_her_with_the_officer_note_after_commit(self):
        app, _exp = _student(locale='ta')
        row = record_result(app, semester='Sem 2', cgpa='3.0')
        with self.captureOnCommitCallbacks(execute=True):
            results_review.review(row, decision='queried', note='The slip is cut off at the bottom.')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('The slip is cut off at the bottom.', mail.outbox[0].body)
        self.assertIn('Sem 2', mail.outbox[0].subject)
        with self.captureOnCommitCallbacks(execute=True):
            results_review.review(row, decision='accepted')
        self.assertEqual(len(mail.outbox), 1)                    # an accept sends nothing


class TestSavingWording(TestCase):
    def setUp(self):
        self.org = make_cohort().owning_organisation

    def test_refusals(self):
        for subject, body, code in (('', 'x {link}', 'empty'),
                                    ('Due', 'Hi {name}, {iban}', 'unknown_placeholders'),
                                    ('Due', 'This is tax deductible. {link}', 'banned_phrase')):
            with self.subTest(code=code):
                with self.assertRaises(student_comms.StudentCommsError) as ctx:
                    student_comms.save(self.org, 'results_due', 'en', subject, body)
                self.assertEqual(ctx.exception.code, code)
        with self.assertRaises(student_comms.StudentCommsError):
            student_comms.save(self.org, 'welcome', 'en', 'x', 'y')

    def test_save_then_reset_returns_to_the_default(self):
        student_comms.save(self.org, 'result_queried', 'ms', 'Soalan', 'Hai {name}. {note} {link}')
        self.assertEqual(student_comms.wording(self.org, 'result_queried', 'ms')[:2],
                         ('Soalan', 'Hai {name}. {note} {link}'))
        student_comms.reset(self.org, 'result_queried', 'ms')
        self.assertEqual(student_comms.wording(self.org, 'result_queried', 'ms')[:2],
                         student_comms.DEFAULTS['result_queried']['ms'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheSettingsTab(TestCase):
    def setUp(self):
        self.mine = make_cohort().owning_organisation
        self.theirs = make_cohort().owning_organisation
        self.admin = make_admin('org_admin', owning_org=self.mine)
        StudentEmailTemplate.objects.create(organisation=self.theirs, kind='results_due', language='en',
                                            subject='THEIRS', body='theirs {link}')

    def test_fenced_to_the_callers_own_organisation(self):
        body = authed_client(self.admin).get(API).json()
        self.assertEqual(body['organisation']['code'], self.mine.code)
        self.assertEqual(len(body['templates']), 12)                # 4 kinds (S6b: + letter_issued) x 3 languages
        self.assertNotIn('THEIRS', [t['subject'] for t in body['templates']])
        self.assertEqual(authed_client(self.admin).get(API, {'org': self.theirs.code}).status_code, 404)
        r = authed_client(self.admin).put(API, {'kind': 'results_due', 'language': 'en', 'subject': 'Mine',
                                                'body': 'Hi {name} {link}'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(StudentEmailTemplate.objects.get(organisation=self.mine).subject, 'Mine')
        self.assertEqual(StudentEmailTemplate.objects.get(organisation=self.theirs).subject, 'THEIRS')

    def test_reset_and_refusals_and_roles(self):
        client = authed_client(self.admin)
        client.put(API, {'kind': 'results_due', 'language': 'ta', 'subject': 'S', 'body': 'B {link}'}, format='json')
        r = client.put(API, {'kind': 'results_due', 'language': 'ta', 'reset': True}, format='json')
        row = next(t for t in r.json()['templates'] if t['key'] == 'results_due.ta')
        self.assertFalse(row['customised'])
        r = client.put(API, {'kind': 'results_due', 'language': 'en', 'subject': 'S', 'body': '{iban}'}, format='json')
        self.assertEqual((r.status_code, r.json()['code'], r.json()['placeholders']), (400, 'unknown_placeholders', ['iban']))
        for role in ('finance', 'reviewer', 'admin'):
            with self.subTest(role=role):
                other = make_admin(role, owning_org=self.mine)
                self.assertEqual(authed_client(other).get(API).status_code, 403)
