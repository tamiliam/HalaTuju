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
        self.assertIn('Cancel the offer first', str(ctx.exception))
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
        self.assertEqual((kwargs['to_email'], kwargs['programme_name'], kwargs['lang']),
                         (app.notify_email, app.cohort.name, app.locale))

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
    def setUp(self):
        self.cohort = make_cohort()
        self.reviewer = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
        self.client = authed_client(self.reviewer)

    def _close(self, app, reason):
        return self.client.post(f'{API}applications/{app.id}/close/',
                                {'closure_reason': reason}, format='json')

    def test_a_stalled_case_closes_and_answers_the_detail(self, _send):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        r = self._close(app, 'stalled')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['status'], r.json()['closure_reason']), ('closed', 'stalled'))

    def test_the_new_refusals_reach_the_client_as_400_codes(self, _send):
        app = make_application('recommended', cohort=self.cohort, reviewer=self.reviewer)
        r = self._close(app, 'graduated')
        self.assertEqual((r.status_code, r.json()), (400, {'error': 'reason_not_allowed'}))
        awarded = make_application('awarded', cohort=self.cohort, reviewer=self.reviewer)
        _offer(awarded)
        r = self._close(awarded, 'stalled')
        self.assertEqual((r.status_code, r.json()), (400, {'error': 'sponsorship_open'}))
