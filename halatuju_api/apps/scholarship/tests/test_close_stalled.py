"""TD-352 — an officer closes a stalled application; the student may then apply again.

Owner ruling (option A, 2026-10-06): no clock. An officer closes the case by hand, from ANY in-play
status, with a reason that fits the stage; a close REFUSES while a live sponsorship is attached (one
door per job — cancel the offer first); the close writes one AUDIT line naming the status it left
and, before an award, emails the student.
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from apps.scholarship import closure
from apps.scholarship.closure import ClosureError
from apps.scholarship.models import Disbursement, Sponsor, Sponsorship
from apps.scholarship.services import apply_gate
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, unique_suffix,
)
from apps.scholarship.tests.test_endpoints_disbursements import fund_through_the_product

API = '/api/v1/admin/scholarship/'
SENDER = 'apps.scholarship.closure.send_application_closed_email'

#: Each in-play status, and the factory stage that builds it.
PRE_AWARD = {
    'submitted': dict(stage='submitted'),
    'shortlisted': dict(stage='shortlisted'),
    'profile_complete': dict(stage='profile_complete'),
    'interviewing': dict(stage='interviewing'),
    'interviewed': dict(stage='awaiting_qc', outcome='recommend'),
    'recommended': dict(stage='recommended'),
}
FUNDED = {'active': dict(stage='active'), 'maintenance': dict(stage='maintenance')}


def _sponsor():
    return Sponsor.objects.create(
        supabase_user_id=unique_suffix('sponsor-uid-'), name='Test Funder',
        email=f'{unique_suffix("funder-")}@example.test', status='approved')


def _offer(app, status='offered'):
    return Sponsorship.objects.create(sponsor=_sponsor(), application=app,
                                      amount=Decimal('1000'), status=status)


class TestTheSetsAgree(TestCase):
    def test_closeable_from_is_the_apply_gates_in_play_set(self):
        self.assertIs(closure.CLOSEABLE_FROM, apply_gate.IN_PLAY_STATUSES)

    def test_every_in_play_status_has_reasons_and_stalled_is_always_one(self):
        self.assertEqual(closure.PRE_AWARD_STATUSES | closure.POST_AWARD_STATUSES,
                         apply_gate.IN_PLAY_STATUSES)
        for status in apply_gate.IN_PLAY_STATUSES:
            self.assertIn('stalled', closure.reasons_for(status), status)
        for status in apply_gate.FINISHED_STATUSES:
            self.assertEqual(closure.reasons_for(status), (), status)

    def test_pre_award_reasons_are_stalled_and_withdrawn_only(self):
        self.assertEqual(set(closure.PRE_AWARD_REASONS), {'stalled', 'withdrawn'})
        self.assertEqual(set(closure.POST_AWARD_REASONS),
                         {code for code, _ in closure.ScholarshipApplication.CLOSURE_REASONS})


@mock.patch(SENDER, return_value=True)
class TestCloseFromEveryInPlayStatus(TestCase):
    def test_each_pre_award_status_closes_stalled_or_withdrawn(self, _send):
        for status, how in PRE_AWARD.items():
            for reason in ('stalled', 'withdrawn'):
                with self.subTest(status=status, reason=reason):
                    app = make_application(**how)
                    self.assertEqual(app.status, status)
                    closure.close_application(app, closure_reason=reason, by_email='o@x.my')
                    app.refresh_from_db()
                    self.assertEqual((app.status, app.closure_reason, app.closed_by),
                                     ('closed', reason, 'o@x.my'))
                    self.assertIsNotNone(app.closed_at)

    def test_a_post_award_reason_is_refused_before_an_award(self, _send):
        for status, how in PRE_AWARD.items():
            for reason in ('graduated', 'completed', 'lapsed', 'terminated'):
                with self.subTest(status=status, reason=reason):
                    app = make_application(**how)
                    with self.assertRaises(ClosureError) as ctx:
                        closure.close_application(app, closure_reason=reason)
                    self.assertEqual(ctx.exception.code, 'reason_not_allowed')
                    app.refresh_from_db()
                    self.assertEqual(app.status, status)

    def test_a_funded_case_closes_with_every_reason_including_stalled(self, _send):
        for status, how in FUNDED.items():
            for reason in closure.POST_AWARD_REASONS:
                with self.subTest(status=status, reason=reason):
                    app = make_application(**how)
                    closure.close_application(app, closure_reason=reason)
                    app.refresh_from_db()
                    self.assertEqual((app.status, app.closure_reason), ('closed', reason))

    def test_a_finished_application_is_not_closeable(self, _send):
        finished = [make_application('closed'), make_application('rejected'),
                    make_application('expired'),
                    # Nothing in the product writes 'withdrawn' today; the status exists and is
                    # FINISHED, so it must refuse like the others.
                    make_application('submitted', status='withdrawn')]
        for app in finished:
            with self.subTest(status=app.status):
                before = app.status
                with self.assertRaises(ClosureError) as ctx:
                    closure.close_application(app, closure_reason='stalled')
                self.assertEqual(ctx.exception.code, 'not_closeable')
                app.refresh_from_db()
                self.assertEqual(app.status, before)

    def test_an_unknown_reason_is_bad_reason_not_reason_not_allowed(self, _send):
        app = make_application('recommended')
        for bad in ('', None, 'moved_away'):
            with self.assertRaises(ClosureError) as ctx:
                closure.close_application(app, closure_reason=bad)
            self.assertEqual(ctx.exception.code, 'bad_reason')

    def test_the_status_is_judged_on_the_row_not_a_stale_object(self, _send):
        app = make_application('recommended')
        stale = type(app).objects.get(pk=app.pk)
        app.status = 'rejected'
        app.save(update_fields=['status'])
        with self.assertRaises(ClosureError) as ctx:
            closure.close_application(stale, closure_reason='stalled')
        self.assertEqual(ctx.exception.code, 'not_closeable')


@mock.patch(SENDER, return_value=True)
class TestOneDoorPerJob(TestCase):
    """A live sponsorship refuses the close (before a funded state); the officer cancels it first."""

    def test_an_awarded_case_with_its_offer_out_is_refused(self, _send):
        app = make_application('awarded')
        sp = _offer(app)
        with self.assertRaises(ClosureError) as ctx:
            closure.close_application(app, closure_reason='stalled')
        self.assertEqual(ctx.exception.code, 'sponsorship_open')
        self.assertIn('It cannot be closed here', str(ctx.exception))
        self.assertIn('TD-366', str(ctx.exception))
        app.refresh_from_db()
        sp.refresh_from_db()
        self.assertEqual((app.status, sp.status), ('awarded', 'offered'))   # nothing cancelled
        _send.assert_not_called()

    def test_an_accepted_award_in_its_cool_off_is_refused(self, _send):
        cohort = make_cohort()
        app, _sponsor_row, sp = fund_through_the_product(
            cohort, reviewer=make_admin('reviewer', owning_org=cohort.owning_organisation),
            cooloff_days=2)
        self.assertEqual((app.status, sp.status), ('awarded', 'active'))
        with self.assertRaises(ClosureError) as ctx:
            closure.close_application(app, closure_reason='withdrawn')
        self.assertEqual(ctx.exception.code, 'sponsorship_open')

    def test_released_money_refuses_even_without_a_holding_sponsorship(self, _send):
        app = make_application('recommended')
        Disbursement.objects.create(application=app, amount=Decimal('500'), status='released')
        with self.assertRaises(ClosureError) as ctx:
            closure.close_application(app, closure_reason='stalled')
        self.assertEqual(ctx.exception.code, 'sponsorship_open')

    def test_a_cancelled_or_lapsed_offer_and_an_unpaid_tranche_do_not_refuse(self, _send):
        for i, status in enumerate(('cancelled', 'lapsed')):
            with self.subTest(status=status):
                app = make_application('recommended')
                _offer(app, status=status)
                Disbursement.objects.create(application=app, amount=Decimal('500'),
                                            status='scheduled')
                closure.close_application(app, closure_reason='stalled')
                app.refresh_from_db()
                self.assertEqual(app.status, 'closed')

    def test_a_funded_case_with_its_live_sponsorship_still_closes_as_before(self, _send):
        cohort = make_cohort()
        app, _sponsor_row, sp = fund_through_the_product(
            cohort, reviewer=make_admin('reviewer', owning_org=cohort.owning_organisation))
        self.assertEqual((app.status, sp.status), ('active', 'active'))
        closure.close_application(app, closure_reason='stalled')
        app.refresh_from_db()
        sp.refresh_from_db()
        self.assertEqual((app.status, sp.status), ('closed', 'active'))   # S6: no money effect
        _send.assert_not_called()


class TestAuditAndEmail(TestCase):
    def test_the_audit_line_names_the_status_it_left(self):
        app = make_application('recommended')
        with mock.patch(SENDER, return_value=True), \
                self.assertLogs('apps.scholarship.closure', 'INFO') as logs:
            closure.close_application(app, closure_reason='stalled', by_email='o@x.my')
        self.assertIn(f'INFO:apps.scholarship.closure:AUDIT application_closed app_id={app.id} '
                      f'from=recommended reason=stalled by=o@x.my', logs.output)

    def test_a_pre_award_close_emails_the_student(self):
        app = make_application('interviewing')
        with mock.patch(SENDER, return_value=True) as send:
            closure.close_application(app, closure_reason='stalled')
        send.assert_called_once()
        kwargs = send.call_args.kwargs
        self.assertEqual((kwargs['to_email'], kwargs['programme_name'], kwargs['lang'],
                          kwargs['closure_reason']),
                         (app.notify_email, app.cohort.name, app.locale, 'stalled'))

    def test_the_officer_close_email_says_a_later_round_not_begin_again(self):
        """Review round 1, item 4: the real text, every language. The auto-expiry wording ("not
        completed in time", "begin again here") stays for expiry only."""
        from django.core import mail
        from apps.scholarship import emails
        later = {'en': 'later round', 'ms': 'pusingan akan datang', 'ta': 'அடுத்த சுற்றில்'}
        for lang, phrase in later.items():
            with self.subTest(lang=lang):
                app = make_application('recommended', locale=lang)
                mail.outbox.clear()
                closure.close_application(app, closure_reason='stalled')
                self.assertEqual(len(mail.outbox), 1)
                body = mail.outbox[0].body
                self.assertIn(phrase, body)
                self.assertNotIn(emails.CLOSED_BODIES[lang].split('{programme}')[1][:25], body)
        mail.outbox.clear()
        self.assertTrue(emails.send_application_closed_email(
            'x@example.test', 'Priya', 'B40', lang='en'))
        self.assertIn('not completed in time', mail.outbox[0].body)   # expiry keeps its wording
        self.assertNotIn('later round', mail.outbox[0].body)

    def test_a_failed_email_is_a_warning_naming_the_application(self):
        app = make_application('shortlisted')
        with mock.patch(SENDER, return_value=False), \
                self.assertLogs('apps.scholarship.closure', 'WARNING') as logs:
            closure.close_application(app, closure_reason='withdrawn')
        warnings = [line for line in logs.output if line.startswith('WARNING')]
        self.assertEqual(len(warnings), 1)
        self.assertIn(f'app {app.id} is closed but the closed email did not go', warnings[0])
        app.refresh_from_db()
        self.assertEqual(app.status, 'closed')   # the close stands; the email is best-effort

    def test_a_post_award_close_sends_no_email(self):
        for stage in ('active', 'maintenance'):
            app = make_application(stage)
            with mock.patch(SENDER, return_value=True) as send:
                closure.close_application(app, closure_reason='stalled')
            send.assert_not_called()

    def test_a_refused_close_writes_no_audit_line_and_sends_nothing(self):
        app = make_application('recommended')
        with mock.patch(SENDER, return_value=True) as send, \
                mock.patch.object(closure.logger, 'info') as info:
            with self.assertRaises(ClosureError):
                closure.close_application(app, closure_reason='graduated')
        send.assert_not_called()
        info.assert_not_called()


class TestTheStudentMayApplyAgain(TestCase):
    """End to end through the apply gate: in play blocks; the officer's close releases her."""

    def test_a_stalled_recommended_case_closed_frees_her_for_another_round(self):
        app = make_application('recommended')
        other_round = make_cohort()
        verdict = apply_gate.apply_verdict(app.profile, other_round)
        self.assertEqual((verdict.reason, verdict.application.id),
                         (apply_gate.IN_PROGRESS, app.id))
        with mock.patch(SENDER, return_value=True):
            closure.close_application(app, closure_reason='stalled', by_email='o@x.my')
        self.assertTrue(apply_gate.apply_verdict(app.profile, other_round).allowed)
        # ⚠ The SAME round still refuses: rule 1 (already_applied) counts any non-expired
        # application in that round, a closed one included. Pinned so a change is deliberate.
        self.assertEqual(apply_gate.apply_verdict(app.profile, app.cohort).reason,
                         apply_gate.ALREADY_APPLIED)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@mock.patch(SENDER, return_value=True)
class TestTheEndpoint(TestCase):
    """The view. A PRE-award close is super / org_admin only (lead decision, review round 1 —
    the `AdminOrgRejectView` gate); a funded close keeps the S6 gate (the assigned reviewer may)."""

    def setUp(self):
        self.cohort = make_cohort()
        org = self.cohort.owning_organisation
        self.reviewer = make_admin('reviewer', owning_org=org)
        self.org_admin = make_admin('org_admin', owning_org=org)
        self.client = authed_client(self.org_admin)

    def _close(self, app, reason, client=None):
        return (client or self.client).post(f'{API}applications/{app.id}/close/',
                                            {'closure_reason': reason}, format='json')

    def test_a_stalled_case_closes_and_answers_the_detail(self, _send):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        r = self._close(app, 'stalled')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['status'], r.json()['closure_reason']), ('closed', 'stalled'))

    def test_a_super_closes_a_pre_award_case(self, _send):
        app = make_application('recommended', cohort=self.cohort, reviewer=self.reviewer)
        r = self._close(app, 'stalled', client=authed_client(make_admin('super', super_admin=True)))
        self.assertEqual(r.status_code, 200, r.content)

    def test_the_assigned_reviewer_and_a_qc_are_refused_before_an_award(self, _send):
        qc = make_admin('qc', owning_org=self.cohort.owning_organisation)
        for who in (self.reviewer, qc):
            with self.subTest(role=who.role):
                app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
                r = self._close(app, 'stalled', client=authed_client(who))
                self.assertEqual(r.status_code, 403, r.content)
                app.refresh_from_db()
                self.assertEqual(app.status, 'interviewing')

    def test_the_assigned_reviewer_may_still_close_a_funded_case(self, _send):
        app = make_application('active', cohort=self.cohort, reviewer=self.reviewer)
        r = self._close(app, 'graduated', client=authed_client(self.reviewer))
        self.assertEqual(r.status_code, 200, r.content)

    def test_another_organisations_org_admin_gets_404(self, _send):
        stranger = make_admin('org_admin', owning_org=make_cohort().owning_organisation)
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        r = self._close(app, 'stalled', client=authed_client(stranger))
        self.assertEqual(r.status_code, 404)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')

    def test_the_new_refusals_reach_the_client_as_400_codes(self, _send):
        app = make_application('recommended', cohort=self.cohort, reviewer=self.reviewer)
        r = self._close(app, 'graduated')
        self.assertEqual((r.status_code, r.json()), (400, {'error': 'reason_not_allowed'}))
        awarded = make_application('awarded', cohort=self.cohort, reviewer=self.reviewer)
        _offer(awarded)
        r = self._close(awarded, 'stalled')
        self.assertEqual((r.status_code, r.json()), (400, {'error': 'sponsorship_open'}))


#: The five review-track writes behind `_require_open_case` (test_closed_case_writes.REVIEW_WRITES).
VERDICT_BODY = {
    'officer_verdict': {'identity': 'pass', 'academic': 'pass', 'pathway': 'pass',
                        'income': 'pass', 'overall': 'accept'},
    'reason': 'A recorded justification.',
}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@mock.patch(SENDER, return_value=True)
class TestAStalledCloseShutsTheReviewTrack(TestCase):
    """TD-352 opened 'closed' to a case that was never decided, so 'closed' joined
    CASE_CLOSED_STATES: no verdict, award amount or interview lands on the file afterwards."""

    def setUp(self):
        self.cohort = make_cohort()
        self.reviewer = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
        self.client = authed_client(self.reviewer)

    def _closed(self, stage='interviewing'):
        app = make_application(stage, cohort=self.cohort, reviewer=self.reviewer)
        closure.close_application(app, closure_reason='stalled', by_email='o@x.my')
        return app

    def _post(self, app, suffix, body):
        return self.client.post(f'{API}applications/{app.id}/{suffix}', body, format='json')

    def test_every_review_write_answers_case_closed_and_writes_nothing(self, _send):
        for suffix, body in (('record-verdict/', VERDICT_BODY), ('interview/', {'findings': {}}),
                             ('interview/submit/', {}), ('interview/reopen/', {}),
                             ('suggest-gaps/', {})):
            with self.subTest(endpoint=suffix):
                app = self._closed()
                r = self._post(app, suffix, body)
                self.assertEqual((r.status_code, r.json().get('code')), (400, 'case_closed'))
                app.refresh_from_db()
                self.assertEqual(app.status, 'closed')
                self.assertIsNone(app.verdict_decided_at)
                self.assertFalse(app.interview_sessions.exists())

    def test_the_decline_refuses_a_closed_case(self, _send):
        from apps.scholarship.services import admin_reject, org_admin_reject
        for category in ('interview', 'contractual'):
            with self.subTest(category=category):
                app = self._closed('profile_complete')
                with self.assertRaises(ValueError) as ctx:
                    admin_reject(app, self.reviewer, category)
                self.assertEqual(str(ctx.exception), 'bad_status')
        app = self._closed('shortlisted')
        with self.assertRaises(ValueError):
            org_admin_reject(app, self.reviewer, 'A reason.')
        app.refresh_from_db()
        self.assertEqual(app.status, 'closed')


class TestAFundedClosedCaseKeepsItsWrites(TestCase):
    """What a funded closed case loses by joining CASE_CLOSED_STATES: only the review-track
    writes, which had no business on it. Every other door stays as it was."""

    def test_only_the_five_review_writes_go_through_the_open_case_gate(self):
        from pathlib import Path
        views = Path(__file__).resolve().parents[1] / 'views_admin'
        callers = sorted(
            f'{path.name}:{line.strip()[:60]}'
            for path in views.glob('*.py')
            for line in path.read_text(encoding='utf-8').splitlines()
            if 'self._require_open_case(' in line)
        self.assertEqual(len(callers), 5, callers)
        self.assertEqual(sorted({c.split(':')[0] for c in callers}),
                         ['interviews.py', 'profiles.py', 'verdict.py'])

    def test_the_graduation_thank_you_still_lands_on_a_closed_funded_case(self):
        from apps.scholarship.in_programme import submit_graduation_message
        from apps.scholarship.services import review_writes_closed
        cohort = make_cohort()
        app, _sponsor_row, _sp = fund_through_the_product(
            cohort, reviewer=make_admin('reviewer', owning_org=cohort.owning_organisation))
        closure.close_application(app, closure_reason='graduated')
        self.assertTrue(review_writes_closed(app))
        msg = submit_graduation_message(app, raw_text='Thank you for believing in me.')
        self.assertEqual(msg.application_id, app.id)


@mock.patch(SENDER, return_value=True)
class TestAPreAwardCloseReleasesTheInterview(TestCase):
    """Review round 1, item 3: a close must not leave a booked interview live, or proposed times
    she could still book. The existing teardown (`scheduling.release_for_unassign`) runs inside
    the close, without its "your application is still active" student notice."""

    def _booked(self, **kw):
        from datetime import timedelta
        from django.utils import timezone
        from apps.scholarship.models import InterviewSlot
        reviewer = make_admin('reviewer')
        start = timezone.now() + timedelta(days=2)
        app = make_application('interviewing', reviewer=reviewer, interview_status='booked',
                               interview_start=start, interview_meeting_url='https://meet.test/x',
                               **kw)
        slot = InterviewSlot.objects.create(application=app, reviewer=reviewer, start=start)
        app.interview_slot = slot
        app.save(update_fields=['interview_slot'])
        return app, slot

    @mock.patch('apps.scholarship.meeting.cancel_event')
    @mock.patch('apps.scholarship.scheduling.emails.send_reviewer_interview_cancelled_email')
    @mock.patch('apps.scholarship.scheduling.emails.send_interview_released_email')
    def test_a_booked_interview_is_voided_the_reviewer_told_the_student_not(
            self, released, reviewer_notice, cancel_event, _send):
        app, slot = self._booked(interview_calendar_event_id='evt-1')
        closure.close_application(app, closure_reason='stalled', by_email='o@x.my')
        app.refresh_from_db()
        slot.refresh_from_db()
        self.assertEqual((app.status, app.interview_status), ('closed', 'cancelled'))
        self.assertIsNone(app.interview_start)
        self.assertEqual((app.interview_meeting_url, app.interview_calendar_event_id), ('', ''))
        self.assertEqual(app.interview_cancel_reason, 'Application closed by an officer')
        self.assertFalse(slot.is_active)
        cancel_event.assert_called_once_with('evt-1')
        reviewer_notice.assert_called_once()
        self.assertEqual(reviewer_notice.call_args.kwargs['reason'],
                         'The application was closed by an officer.')
        released.assert_not_called()   # her one email is the close's own

    def test_proposed_times_are_withdrawn_so_she_cannot_book_after_the_close(self, _send):
        from datetime import timedelta
        from django.utils import timezone
        from apps.scholarship import scheduling
        from apps.scholarship.models import InterviewSlot
        reviewer = make_admin('reviewer')
        app = make_application('interviewing', reviewer=reviewer)
        slot = InterviewSlot.objects.create(application=app, reviewer=reviewer,
                                            start=timezone.now() + timedelta(days=3))
        closure.close_application(app, closure_reason='stalled')
        slot.refresh_from_db()
        self.assertFalse(slot.is_active)
        with self.assertRaises(scheduling.SchedulingError):
            scheduling.book_slot(app, slot_id=slot.id)

    def test_no_reminder_goes_for_a_closed_case_even_if_a_booking_were_left_on_it(self, _send):
        """The belt and braces: the reminder sweep reads only in-play applications."""
        from datetime import timedelta
        from django.core import mail
        from django.core.management import call_command
        from django.utils import timezone
        start = timezone.now() + timedelta(hours=20)
        left = make_application('submitted', status='closed', closure_reason='stalled',
                                interview_status='booked', interview_start=start,
                                notify_email='left@example.test')
        live = make_application('interviewing', interview_status='booked', interview_start=start,
                                notify_email='live@example.test')
        mail.outbox.clear()
        with override_settings(INTERVIEW_SCHEDULING_ENABLED=True):
            call_command('send_interview_reminders')
        recipients = {to for m in mail.outbox for to in m.to}
        self.assertNotIn(left.notify_email, recipients)
        self.assertIn(live.notify_email, recipients)
        left.refresh_from_db()
        self.assertIsNone(left.interview_reminded_1d_at)


@mock.patch(SENDER, return_value=True)
class TestClosedBeforeQcIsNotRecommended(TestCase):
    """Review round 1, item 5 (api): the reviewer figures read `closed` as recommended only when the
    case carries `recommended_at` — a stalled close before QC accepted it is not a recommendation."""

    def test_the_reviewer_figures(self, _send):
        from apps.scholarship.views_admin.reviewers import _reviewer_workloads
        reviewer = make_admin('reviewer')
        declined = make_application('awaiting_qc', outcome='decline', reviewer=reviewer)
        closure.close_application(declined, closure_reason='stalled')
        accepted = make_application('awaiting_qc', outcome='recommend', reviewer=reviewer)
        closure.close_application(accepted, closure_reason='stalled')
        make_application('closed', reviewer=reviewer)              # a funded close: recommended_at
        self.assertIsNone(declined.recommended_at)
        work = _reviewer_workloads([reviewer])[reviewer.id]
        self.assertEqual((work['completed'], work['recommended'], work['declined'],
                          work['unaccounted']), (3, 1, 1, 1))
