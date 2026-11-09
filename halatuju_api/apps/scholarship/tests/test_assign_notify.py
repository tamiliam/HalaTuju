"""A2.3 / TD-519 — the assignment's two emails are sent after the request, by the assign-emails cron.

``assign_reviewer`` writes its AssignmentEvent queued (``notify_state='pending'``) and sends nothing;
``assign_notify.send_pending`` sends the reviewer's and the student's emails with the same gates and
content. Every email function is mocked: no real mail is sent.
"""
import io
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import assign_notify
from apps.scholarship.models import AssignmentEvent
from apps.scholarship.pool import pool_ref
from apps.scholarship.services import assignment
from apps.scholarship.tests.factories import make_admin, make_application

REVIEWER_MAIL = 'apps.scholarship.emails.send_reviewer_assigned_email'
STUDENT_MAIL = 'apps.scholarship.emails.send_student_assigned_reviewer_email'


@override_settings(STUDENT_ASSIGNMENT_EMAIL_ENABLED=True)
class TestAssignNotifyQueue(TestCase):
    def setUp(self):
        self.app = make_application('profile_complete', notify_email='s@example.test')
        self.super = make_admin(super_admin=True)
        self.reviewer = make_admin('reviewer', owning_org=self.app.owning_organisation,
                                   name='Rohini', email='rohini@example.test')
        self.reviewer2 = make_admin('reviewer', owning_org=self.app.owning_organisation,
                                    name='Kavin', email='kavin@example.test')

    def _assign(self, reviewer):
        assignment.assign_reviewer(self.app, reviewer=reviewer, by_admin=self.super)
        self.app.refresh_from_db()

    def test_assign_sends_no_email_inline_and_queues_one_event(self):
        with patch(REVIEWER_MAIL) as rev, patch(STUDENT_MAIL) as stu:
            self._assign(self.reviewer)
            rev.assert_not_called()
            stu.assert_not_called()
        event = AssignmentEvent.objects.get(application=self.app)
        self.assertEqual((event.notify_state, event.notify_attempts), ('pending', 0))

    def test_the_cron_sends_both_emails_once_with_the_assignment_content(self):
        self._assign(self.reviewer)
        with patch(REVIEWER_MAIL) as rev, patch(STUDENT_MAIL) as stu:
            out = io.StringIO()
            call_command('send_pending_assign_emails', stdout=out)
            assign_notify.send_pending()                     # a second run sends nothing more
        self.assertIn('sent=1', out.getvalue())
        rev.assert_called_once()
        kw = rev.call_args.kwargs
        self.assertEqual((kw['to_email'], kw['reviewer_name'], kw['ref']),
                         ('rohini@example.test', 'Rohini', pool_ref(self.app.id)))
        from apps.scholarship import review_sla
        self.assertEqual(kw['review_by'], review_sla.review_due(
            self.app.assigned_at, self.app.owning_organisation).date().strftime('%d %b %Y'))
        stu.assert_called_once()
        self.assertEqual(stu.call_args.args[0], 's@example.test')
        self.assertEqual(stu.call_args.kwargs['reviewer_name'], 'Rohini')
        event = AssignmentEvent.objects.get(application=self.app)
        self.assertEqual((event.notify_state, event.notify_claimed_at), ('', None))

    def test_the_review_by_date_is_the_assignments_not_the_crons(self):
        self._assign(self.reviewer)
        later = timezone.now() + timedelta(days=3)
        from apps.scholarship import review_sla
        promised = review_sla.review_due(self.app.assigned_at, self.app.owning_organisation)
        with patch(REVIEWER_MAIL) as rev, patch('django.utils.timezone.now', return_value=later):
            assign_notify.send_assignment_emails(AssignmentEvent.objects.get(application=self.app))
        self.assertEqual(rev.call_args.kwargs['review_by'], promised.date().strftime('%d %b %Y'))

    @override_settings(STUDENT_ASSIGNMENT_EMAIL_ENABLED=False)
    def test_the_student_flag_is_still_asked(self):
        self._assign(self.reviewer)
        with patch(REVIEWER_MAIL) as rev, patch(STUDENT_MAIL) as stu:
            assign_notify.send_pending()
        rev.assert_called_once()
        stu.assert_not_called()

    def test_an_unassign_queues_nothing(self):
        self._assign(self.reviewer)
        AssignmentEvent.objects.update(notify_state='')    # as if already sent
        self.app.status = 'profile_complete'
        self._assign(None)
        self.assertEqual(AssignmentEvent.objects.filter(notify_state='pending').count(), 0)
        with patch(REVIEWER_MAIL) as rev, patch(STUDENT_MAIL) as stu:
            self.assertEqual(assign_notify.send_pending()['sent'], 0)
        rev.assert_not_called()
        stu.assert_not_called()

    def test_a_row_the_old_image_wrote_is_never_sent(self):
        AssignmentEvent.objects.create(application=self.app, to_admin=self.reviewer,
                                       by_email='x@example.test')   # notify_state '' (sent inline)
        with patch(REVIEWER_MAIL) as rev:
            self.assertEqual(assign_notify.send_pending()['sent'], 0)
        rev.assert_not_called()

    def test_a_reassignment_before_the_cron_mails_only_the_current_reviewer(self):
        self._assign(self.reviewer)
        self._assign(self.reviewer2)
        with patch(REVIEWER_MAIL) as rev, patch(STUDENT_MAIL) as stu:
            counts = assign_notify.send_pending()
        self.assertEqual((counts['sent'], counts['stale']), (1, 1))
        self.assertEqual([c.kwargs['to_email'] for c in rev.call_args_list], ['kavin@example.test'])
        self.assertEqual([c.kwargs['reviewer_name'] for c in stu.call_args_list], ['Kavin'])
        self.assertEqual(list(AssignmentEvent.objects.filter(application=self.app)
                              .values_list('notify_state', flat=True)), ['', ''])

    def test_an_unassign_before_the_cron_sends_no_email(self):
        self._assign(self.reviewer)
        self.app.status = 'profile_complete'
        self._assign(None)
        with patch(REVIEWER_MAIL) as rev, patch(STUDENT_MAIL) as stu:
            counts = assign_notify.send_pending()
        self.assertEqual((counts['sent'], counts['stale']), (0, 1))
        rev.assert_not_called()
        stu.assert_not_called()
        self.assertEqual(AssignmentEvent.objects.filter(notify_state='pending').count(), 0)

    def test_one_claim_wins_and_a_stale_claim_is_retried(self):
        self._assign(self.reviewer)
        event = AssignmentEvent.objects.get(application=self.app)
        now = timezone.now()
        self.assertTrue(assign_notify._claim_notify(event.id, now))
        self.assertEqual(assign_notify.send_one(event.id), 'not_claimed')   # held by the run above
        AssignmentEvent.objects.filter(pk=event.id).update(
            notify_claimed_at=now - assign_notify.STALE_CLAIM - timedelta(minutes=1))
        with patch(REVIEWER_MAIL) as rev, patch(STUDENT_MAIL):
            self.assertEqual(assign_notify.send_pending()['sent'], 1)
        rev.assert_called_once()

    def test_a_failed_email_is_logged_and_the_other_still_goes(self):
        self._assign(self.reviewer)
        with patch(REVIEWER_MAIL, side_effect=RuntimeError('brevo')), patch(STUDENT_MAIL) as stu:
            self.assertEqual(assign_notify.send_pending()['sent'], 1)
            self.assertEqual(assign_notify.send_pending()['sent'], 0)       # never re-sent
        stu.assert_called_once()

    def test_a_failing_run_retries_then_is_marked_failed(self):
        self._assign(self.reviewer)
        event = AssignmentEvent.objects.get(application=self.app)
        with patch('apps.scholarship.assign_notify.send_assignment_emails',
                   side_effect=RuntimeError('db')):
            outcomes = [assign_notify.send_one(event.id) for _ in range(assign_notify.MAX_ATTEMPTS)]
        self.assertEqual(outcomes, ['retry', 'retry', 'failed'])
        event.refresh_from_db()
        self.assertEqual(event.notify_state, assign_notify.FAILED)

    def test_the_cron_never_raises(self):
        self._assign(self.reviewer)
        with patch('apps.scholarship.assign_notify.send_one', side_effect=RuntimeError('db')):
            self.assertEqual(assign_notify.send_pending()['error'], 1)
