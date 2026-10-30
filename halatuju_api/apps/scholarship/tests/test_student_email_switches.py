"""Student maintenance S6a — the organisation's switch, at EVERY door that sends a switchable student
email, and the billing of the student sends that used to meter to no organisation.

Step 3b's list (docs/plans/2026-10-29-student-maintenance-roadmap.md, S6a): each switchable email and
every call site that sends it —
  application_received   services/intake.create_application (the submit)
  submission_received    services/confirmation.confirm_profile (flag off)
  profile_complete       services/confirmation.confirm_profile (flag on)
  question_reminder      services/query_emails.send_query_reminders (the daily sweep)
  interviewer_assigned   services/assignment.assign_reviewer
  interview_reminders    send_interview_reminders (1 day AND 1 hour — the student's copy only)
  results_due / _overdue / result_queried   student_comms.send_student_email (test_student_comms)
Each door: OFF sends nothing (and stamps nothing it would not have stamped without a send); ON still
sends, billed to her organisation. The endpoint: super / org_admin only, a locked email 400
`not_switchable`, POST only.
"""
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from io import StringIO

from django.core.management import call_command
from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.scholarship import sponsorship, student_email_catalogue as cat, usage
from apps.scholarship.models import ScholarshipApplication, StudentEmailSwitch, UsageEvent
from apps.scholarship.services import assignment, confirmation, query_emails
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, auth_token, authed_client, make_admin, make_application, make_cohort, make_student,
)

LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


def _off(app, key):
    StudentEmailSwitch.objects.create(organisation=app.owning_organisation, key=key, enabled=False)


def _billed_to(app, source):
    return list(UsageEvent.objects.filter(service=usage.EMAIL, source=source)
                .values_list('organisation_id', flat=True)) == [app.owning_organisation_id]


@LOCMEM
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestApplicationReceived(TestCase):
    def setUp(self):
        self.cohort = make_cohort(name='B40 Assistance Programme 2026', year=2026, income_ceiling=5250)
        self.student = make_student(
            name='Priya', contact_email='priya@example.com',
            grades={'bm': 'B+', 'eng': 'B+', 'math': 'A', 'sej': 'A', 'tamil_lit': 'A+', 'eko': 'A-',
                    'sci': 'A-'})

    def _submit(self):
        client = authed_client(self.student.supabase_user_id)
        r = client.post('/api/v1/scholarship/applications/',
                        {'household_income': 2500, 'receives_str': True, 'consent_to_contact': True},
                        format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return ScholarshipApplication.objects.get(pk=r.json()['id'])

    def test_on_sends_billed_to_her_organisation(self):
        app = self._submit()
        self.assertIsNotNone(app.acknowledged_at)
        self.assertEqual([m.to for m in mail.outbox], [['priya@example.com']])
        self.assertTrue(_billed_to(app, 'send_acknowledgement_email'))

    def test_off_sends_nothing_and_does_not_claim_she_was_acknowledged(self):
        StudentEmailSwitch.objects.create(organisation=self.cohort.owning_organisation,
                                          key='application_received', enabled=False)
        app = self._submit()
        self.assertIsNone(app.acknowledged_at)
        self.assertEqual(mail.outbox, [])


@LOCMEM
class TestConfirmation(TestCase):
    def setUp(self):
        self.app = make_application('shortlisted')

    def _confirm(self):
        with patch('apps.scholarship.services.confirmation.application_completeness',
                   return_value={'complete': True}), \
                patch('apps.scholarship.services.confirmation.send_profile_complete_admin_email'):
            self.assertTrue(confirmation.confirm_profile(self.app))

    @patch('apps.scholarship.services.confirmation.send_submission_received_email')
    def test_submission_received_off(self, ack):
        _off(self.app, 'submission_received')
        self._confirm()
        ack.assert_not_called()
        self.assertEqual(self.app.status, 'profile_complete')          # the submit itself is untouched

    @patch('apps.scholarship.services.confirmation.send_submission_received_email')
    def test_submission_received_on(self, ack):
        self._confirm()
        ack.assert_called_once()

    @override_settings(PROFILE_COMPLETE_EMAIL_ENABLED=True)
    @patch('apps.scholarship.emails.send_profile_complete_student_email')
    @patch('apps.scholarship.services.confirmation.send_submission_received_email')
    def test_profile_complete_off_and_the_basic_notice_does_not_step_in(self, ack, rich):
        _off(self.app, 'profile_complete')
        self._confirm()
        rich.assert_not_called()
        ack.assert_not_called()


class TestQuestionReminder(TestCase):
    SLA = {'active': True, 'lapsed': False, 'days_left': 1, 'open_count': 2}

    def setUp(self):
        self.app = make_application('profile_complete', notify_email='q@example.test')

    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
    def test_off_sends_nothing_and_stamps_nothing(self):
        _off(self.app, 'question_reminder')
        with patch('apps.scholarship.services.query_emails.query_sla', return_value=self.SLA), \
                patch('apps.scholarship.emails.send_query_reminder_email') as send:
            self.assertEqual(query_emails.send_query_reminders()['reminded'], 0)
        send.assert_not_called()
        self.app.refresh_from_db()
        self.assertIsNone(self.app.query_reminder_at)

    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
    def test_the_dry_run_asks_the_switch_too(self):
        """Review L6: the dry run lists what the live run would do; a switched-off one is skipped."""
        out = StringIO()
        _off(self.app, 'question_reminder')
        cmd = 'apps.scholarship.management.commands.send_query_reminders'
        with patch(f'{cmd}.query_sla', return_value=self.SLA), \
                patch(f'{cmd}._elapsed_days_local', return_value=100):
            call_command('send_query_reminders', '--dry-run', stdout=out)
        self.assertIn(f'would skip app #{self.app.pk}', out.getvalue())
        self.assertIn('0 would be sent', out.getvalue())

    @LOCMEM
    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
    def test_on_sends_metered_and_billed_to_her_organisation(self):
        with patch('apps.scholarship.services.query_emails.query_sla', return_value=self.SLA):
            self.assertEqual(query_emails.send_query_reminders()['reminded'], 1)
        self.assertEqual([m.to for m in mail.outbox], [['q@example.test']])
        self.assertTrue(_billed_to(self.app, 'send_query_reminder_email'))


@override_settings(STUDENT_ASSIGNMENT_EMAIL_ENABLED=True)
class TestInterviewerAssigned(TestCase):
    def setUp(self):
        self.app = make_application('profile_complete', notify_email='s@example.test')
        self.super = make_admin(super_admin=True)
        self.reviewer = make_admin('reviewer', owning_org=self.app.owning_organisation)

    @patch('apps.scholarship.emails.send_student_assigned_reviewer_email')
    def test_off(self, send):
        _off(self.app, 'interviewer_assigned')
        assignment.assign_reviewer(self.app, reviewer=self.reviewer, by_admin=self.super)
        send.assert_not_called()
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.app.pk).assigned_to_id, self.reviewer.id)

    @patch('apps.scholarship.emails.send_student_assigned_reviewer_email')
    def test_on(self, send):
        assignment.assign_reviewer(self.app, reviewer=self.reviewer, by_admin=self.super)
        send.assert_called_once()


@LOCMEM
@override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
class TestInterviewReminders(TestCase):
    def setUp(self):
        self.reviewer = make_admin('reviewer', email='rohini@example.com')

    def _booked(self, hours):
        return make_application('interviewing', notify_email='priya@example.com', assigned_to=self.reviewer,
                                interview_status='booked', interview_booked_at=None,
                                interview_start=timezone.now() + timedelta(hours=hours))

    def test_off_the_student_gets_neither_reminder_the_reviewer_still_does(self):
        for hours, stamp in ((20, 'interview_reminded_1d_at'), (0.5, 'interview_reminded_1h_at')):
            with self.subTest(hours=str(hours)):
                mail.outbox.clear()
                app = self._booked(hours)
                _off(app, 'interview_reminders')
                call_command('send_interview_reminders')
                self.assertNotIn(['priya@example.com'], [m.to for m in mail.outbox])
                self.assertIn(['rohini@example.com'], [m.to for m in mail.outbox])
                app.refresh_from_db()
                self.assertIsNotNone(getattr(app, stamp))           # the reviewer's reminder went

    def test_on_the_student_gets_hers(self):
        self._booked(20)
        call_command('send_interview_reminders')
        self.assertIn(['priya@example.com'], [m.to for m in mail.outbox])

    def test_one_applications_error_does_not_stop_the_run(self):
        """Review L2: a database error on one application is logged; the next is still reminded."""
        from apps.scholarship.management.commands import send_interview_reminders as job
        broken, fine = self._booked(20), self._booked(20)
        real = job._student_identity

        def identity(app):
            if app.pk == broken.pk:
                raise DatabaseError('down')
            return real(app)
        with patch.object(job, '_student_identity', side_effect=identity), \
                self.assertLogs('apps.scholarship.interview_reminders', level='ERROR'):
            call_command('send_interview_reminders')
        fine.refresh_from_db()
        broken.refresh_from_db()
        self.assertIsNotNone(fine.interview_reminded_1d_at)
        self.assertIsNone(broken.interview_reminded_1d_at)

    def test_the_switch_is_read_only_when_a_reminder_is_due(self):
        """Review L4: an interview three days away asks nothing of the switch table."""
        self._booked(72)
        with CaptureQueriesContext(connection) as q:
            call_command('send_interview_reminders')
        self.assertFalse([x for x in q.captured_queries if 'student_email_switches' in x['sql']])


@LOCMEM
class TestAwardConfirmed(TestCase):
    """LOCKED (owner, 2026-10-30, S6a review M1): it carries her onboarding link, so it always goes."""

    def test_sent_billed_to_her_organisation(self):
        app = make_application('awarded', notify_email='a@example.test')
        sponsorship._finalise_award(app)
        self.assertEqual([m.to for m in mail.outbox], [['a@example.test']])
        self.assertTrue(_billed_to(app, 'send_award_confirmed_email'))

    def test_it_cannot_be_switched_off_and_a_row_behind_the_api_does_not_stop_it(self):
        app = make_application('awarded', notify_email='a@example.test')
        with self.assertRaises(cat.NotSwitchable):
            cat.set_switch(app.owning_organisation, 'award_confirmed', False)
        _off(app, 'award_confirmed')
        sponsorship._finalise_award(app)
        self.assertEqual([m.to for m in mail.outbox], [['a@example.test']])
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).status, 'active')


@LOCMEM
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheSendsNowBilledToTheirOrganisation(TestCase):
    """The locked emails S6a moved onto the organisation's bill (forward-only, no backfill)."""

    def test_an_officers_request_for_information(self):
        app = make_application('profile_complete', notify_email='r@example.test')
        r = authed_client(make_admin(super_admin=True)).post(
            f'/api/v1/admin/scholarship/applications/{app.id}/request-info/', {'note': 'Your IC, please.'},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(_billed_to(app, 'send_request_info_email'))

    def test_the_questions_raised_notice_is_metered_at_all(self):
        from apps.scholarship.emails import send_query_raised_email
        app = make_application('profile_complete')
        with usage.usage_context(application=app):
            self.assertTrue(send_query_raised_email('x@example.test', 'Priya', 'Gift', 2))
        self.assertTrue(_billed_to(app, 'send_query_raised_email'))

    def test_the_vircle_setup_email(self):
        from apps.scholarship import bursary
        app = make_application('awarded', notify_email='v@example.test')
        bursary.send_vircle_setup_at_execution(app)
        self.assertTrue(_billed_to(app, 'send_vircle_install_email'))

    def test_no_existing_usage_row_is_given_an_organisation(self):
        """FORWARD-ONLY (Billing, 2026-10-30): nothing in S6a writes to an old row."""
        old = UsageEvent.objects.create(service=usage.EMAIL, source='send_acknowledgement_email')
        app = make_application('profile_complete', notify_email='r@example.test')
        authed_client(make_admin(super_admin=True)).post(
            f'/api/v1/admin/scholarship/applications/{app.id}/request-info/', {'note': 'x'}, format='json')
        old.refresh_from_db()
        self.assertIsNone(old.organisation_id)


@LOCMEM
class TestNoPromiseOfAReminder(TestCase):
    """Review L7: the interview reminders can be switched off, so no email promises one."""

    def test_the_profile_complete_email_never_promises_a_reminder(self):
        from apps.scholarship.emails import send_profile_complete_student_email
        self.assertTrue(send_profile_complete_student_email('p@example.test', student_name='Priya'))
        msg = mail.outbox[0]
        for body in [msg.body] + [alt[0] for alt in getattr(msg, 'alternatives', [])]:
            self.assertNotIn('reminder before the call', body)
            self.assertNotIn('peringatan sebelum panggilan', body)


API = '/api/v1/admin/scholarship/organisation/student-emails/'
SWITCH = API + 'switch/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheSwitchEndpoint(TestCase):
    def setUp(self):
        self.mine = make_cohort().owning_organisation
        self.theirs = make_cohort().owning_organisation
        self.admin = make_admin('org_admin', owning_org=self.mine)

    def test_the_page_lists_every_email_under_its_heading(self):
        body = authed_client(self.admin).get(API).json()
        self.assertEqual(body['groups'], list(cat.GROUPS))
        self.assertEqual([r['key'] for r in body['catalogue']],
                         [e.key for e in sorted(cat.CATALOGUE, key=lambda e: cat.GROUPS.index(e.group))])
        self.assertEqual(len(body['templates']), 9)                     # the S4b editor still has its rows

    def test_an_org_admin_switches_a_safe_email_for_her_own_organisation_only(self):
        with patch.object(cat, 'last_sent', side_effect=AssertionError('last sent read on a write')):
            r = authed_client(self.admin).post(SWITCH, {'key': 'application_received', 'enabled': False},
                                               format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'key': 'application_received', 'enabled': False})   # review L4/L5
        row = next(x for x in authed_client(self.admin).get(API).json()['catalogue']
                   if x['key'] == 'application_received')
        self.assertFalse(row['enabled'])
        self.assertEqual(list(StudentEmailSwitch.objects.values_list('organisation_id', 'key', 'enabled')),
                         [(self.mine.id, 'application_received', False)])
        r = authed_client(self.admin).post(SWITCH + f'?org={self.theirs.code}',
                                           {'key': 'results_due', 'enabled': False}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertFalse(StudentEmailSwitch.objects.filter(organisation=self.theirs).exists())

    def test_a_wording_save_answers_without_the_catalogue(self):
        with patch.object(cat, 'last_sent', side_effect=AssertionError('last sent read on a write')):
            r = authed_client(self.admin).put(API, {'kind': 'results_due', 'language': 'en', 'subject': 'S',
                                                    'body': 'Hi {name} {link}'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('catalogue', r.json())
        self.assertEqual(len(r.json()['templates']), 9)

    def test_a_locked_or_unknown_email_or_a_non_bool_is_refused(self):
        client = authed_client(self.admin)
        for payload in ({'key': 'declined', 'enabled': False}, {'key': 'verify_email', 'enabled': False},
                        {'key': 'award_confirmed', 'enabled': False},
                        {'key': 'partner_access', 'enabled': False}, {'key': 'nope', 'enabled': False},
                        {'key': 'results_due', 'enabled': 'false'}, {}):
            with self.subTest(payload=str(payload)):
                r = client.post(SWITCH, payload, format='json')
                self.assertEqual((r.status_code, r.json().get('code')), (400, 'not_switchable'))
        self.assertFalse(StudentEmailSwitch.objects.exists())

    def test_only_super_and_org_admin_and_only_post(self):
        for role in ('finance', 'reviewer', 'admin', 'qc'):
            with self.subTest(role=role):
                r = authed_client(make_admin(role, owning_org=self.mine)).post(
                    SWITCH, {'key': 'results_due', 'enabled': False}, format='json')
                self.assertEqual(r.status_code, 403)
        self.assertEqual(authed_client(self.admin).get(SWITCH).status_code, 405)
        self.assertEqual(authed_client(self.admin).put(SWITCH, {}, format='json').status_code, 405)
        sup = make_admin(super_admin=True)
        r = authed_client(sup).post(SWITCH + f'?org={self.theirs.code}', {'key': 'results_due', 'enabled': False},
                                    format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(StudentEmailSwitch.objects.filter(organisation=self.theirs, enabled=False).exists())

    def test_a_student_cannot_reach_it(self):
        student = make_student()
        from rest_framework.test import APIClient
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {auth_token(student.supabase_user_id)}')
        self.assertIn(client.post(SWITCH, {'key': 'results_due', 'enabled': False}, format='json').status_code,
                      (401, 403))
