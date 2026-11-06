"""Sprint A1.5 (TD-383 part 2) — the lifecycle writers re-read the status under the row lock.

  * TD-368: an interview proposal or booking refuses a case that FINISHED after the page read it,
    and a close that lands during the Meet call wins (the new event is dropped);
  * TD-365 (decline side): `admin_reject` re-reads the status under the lock, as `fund_student` does;
  * TD-442: a QC reject is one unit: a decline that raises leaves the case NOT reopened;
  * TD-348 / TD-351: the submit asks the one-application rule again under a lock on the student's
    profile, and a same-round insert that meets the constraint answers 409, never a 500;
  * the tranche writers (Withhold, Return, Mark due) lock and re-read like Release, and a Release
    whose tranche row has gone answers bad_state, never a 500;
  * one sponsor's wallet is locked before its balance is read (two funds cannot overspend it).

As in `test_status_lock.py`, SQLite ignores `select_for_update`, so each race is staged as a STALE
copy (read before the winner committed) that must refuse on the re-read. The wallet race has no
stale copy to stage (the balance is read from the database each time), so its pin is the call order.
"""
from datetime import timedelta
from unittest import mock

from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import org_config
from apps.scholarship import disbursement, pool, scheduling, status_lock
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    DecisionReopen, Disbursement, InterviewSlot, ScholarshipApplication, StaffActivity,
)
from apps.scholarship.services import admin_reject, apply_gate
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_student,
)
from apps.scholarship.tests.test_endpoints_disbursements import fund_through_the_product
from apps.scholarship.tests.test_status_lock import _funded_sponsor
from apps.scholarship.views_admin.base import _AdminBase


def _stale(app):
    return ScholarshipApplication.objects.get(pk=app.pk)


def _soon(**kw):
    return timezone.now() + timedelta(**kw)


# ── TD-368: interview scheduling on a case that has finished ───────────────────────────────────

@override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
class TestSchedulingRereadsTheCase(TestCase):
    def setUp(self):
        self.reviewer = make_admin('reviewer')
        self.app = make_application('interviewing', reviewer=self.reviewer)

    def test_a_proposal_on_a_case_closed_since_the_page_loaded_is_refused(self):
        stale = _stale(self.app)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='closed')
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(stale, reviewer=self.reviewer, starts=[_soon(days=3)])
        self.assertEqual(str(cm.exception), 'case_closed')
        self.assertFalse(InterviewSlot.objects.filter(application=self.app).exists())

    def test_a_reopened_decision_still_takes_a_proposal(self):        # guard: not a regression
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            status='rejected', decision_reopened_at=timezone.now())
        slots = scheduling.propose_slots(_stale(self.app), reviewer=self.reviewer,
                                         starts=[_soon(days=3)])
        self.assertEqual(len(slots), 1)

    def _slot(self):
        return InterviewSlot.objects.create(application=self.app, reviewer=self.reviewer,
                                            start=_soon(days=3), duration_min=30)

    @mock.patch('apps.scholarship.meeting.cancel_event')
    @mock.patch('apps.scholarship.meeting.create_event',
                return_value={'url': 'https://meet.example.test/x', 'event_id': 'evt-new'})
    def test_a_booking_on_a_case_rejected_since_the_page_loaded_is_refused(self, _create, cancel):
        slot, stale = self._slot(), _stale(self.app)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='rejected')
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(stale, slot_id=slot.id)
        self.assertEqual(str(cm.exception), 'case_closed')
        cancel.assert_called_once_with('evt-new')
        self.app.refresh_from_db()
        self.assertEqual((self.app.status, self.app.interview_status), ('rejected', ''))

    @mock.patch('apps.scholarship.meeting.cancel_event')
    def test_a_close_that_lands_during_the_meet_call_wins(self, cancel):
        slot = self._slot()

        def close_meanwhile(**_kw):
            ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='closed')
            return {'url': 'https://meet.example.test/y', 'event_id': 'evt-late'}

        with mock.patch('apps.scholarship.meeting.create_event', side_effect=close_meanwhile), \
                self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(self.app, slot_id=slot.id)
        self.assertEqual(str(cm.exception), 'case_closed')
        cancel.assert_called_once_with('evt-late')
        row = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertEqual((row.status, row.interview_status, row.interview_slot_id),
                         ('closed', '', None))


# ── TD-365 (decline side): admin_reject re-reads the status under the lock ─────────────────────

class TestAdminRejectRereadsTheStatus(TestCase):
    def setUp(self):
        self.admin = make_admin('admin')

    def test_an_interview_decline_from_a_copy_read_before_a_close_is_refused(self):
        app = make_application('interviewing')
        stale = _stale(app)
        ScholarshipApplication.objects.filter(pk=app.pk).update(status='closed')
        with self.assertRaises(ValueError) as cm:
            admin_reject(stale, self.admin, 'interview')
        self.assertEqual(str(cm.exception), 'bad_status')
        row = ScholarshipApplication.objects.get(pk=app.pk)
        self.assertEqual((row.status, row.rejected_at, row.pre_decline_status), ('closed', None, ''))

    def test_a_contractual_decline_from_a_copy_read_before_a_close_is_refused(self):
        app = make_application('active')
        stale = _stale(app)
        ScholarshipApplication.objects.filter(pk=app.pk).update(status='closed')
        with self.assertRaises(ValueError):
            admin_reject(stale, self.admin, 'contractual')
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).status, 'closed')

    def test_two_declines_from_stale_copies_record_one(self):
        app = make_application('interviewing')
        first, second = _stale(app), _stale(app)
        admin_reject(first, self.admin, 'interview')
        with self.assertRaises(ValueError):
            admin_reject(second, self.admin, 'interview')
        row = ScholarshipApplication.objects.get(pk=app.pk)
        self.assertEqual((row.status, row.pre_decline_status), ('rejected', 'interviewing'))


# ── TD-442: a QC reject whose decline raises leaves the case as it was ─────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestQcRejectIsOneUnit(TestCase):
    def setUp(self):
        cohort = make_cohort()
        self.qc = make_admin('qc', owning_org=cohort.owning_organisation)
        self.app = make_application('awaiting_qc', outcome='recommend', cohort=cohort,
                                    reviewer=make_admin('reviewer',
                                                        owning_org=cohort.owning_organisation))

    @mock.patch('apps.scholarship.views_admin.verdict.admin_reject',
                side_effect=ValueError('bad_status'))
    def test_a_decline_that_raises_rolls_the_reopen_back(self, _reject):
        r = authed_client(self.qc).post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/qc-decision/',
            {'decision': 'reject', 'comments': 'Income evidence does not hold up.'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_status'))
        row = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertEqual((row.status, row.decision_reopened_at), ('interviewed', None))
        self.assertFalse(DecisionReopen.objects.filter(application=self.app).exists())
        self.assertFalse(StaffActivity.objects.filter(actor=self.qc).exists())

    def _reject(self):
        return authed_client(self.qc).post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/qc-decision/',
            {'decision': 'reject', 'comments': 'Income evidence does not hold up.'}, format='json')

    def test_a_zero_hold_reject_sends_the_decline_after_the_commit(self):
        seen = []
        real_value = org_config.value

        def zero_hold(org, key, *a, **kw):
            return 0 if key == 'qc_decline_hold_hours' else real_value(org, key, *a, **kw)

        def send(app):
            seen.append(ScholarshipApplication.objects.get(pk=app.pk).status)

        with mock.patch.object(org_config, 'value', side_effect=zero_hold), \
                mock.patch('apps.scholarship.services._send_decline_for', side_effect=send):
            r = self._reject()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(seen, ['rejected'])      # one email, sent on the committed decline

    def test_a_held_reject_sends_no_decline_now(self):                  # guard: the embargo
        with mock.patch('apps.scholarship.services._send_decline_for') as send:
            r = self._reject()
        self.assertEqual(r.status_code, 200, r.content)
        send.assert_not_called()


# ── A1.5 review: QC accept and QC reject lock and re-read before they write ─────────────────────

def _after_require_qc(meanwhile):
    """Run ``meanwhile`` just after `_require_qc` read the case: another writer commits then."""
    real = _AdminBase._require_qc

    def hooked(view, request, pk):
        out = real(view, request, pk)
        meanwhile()
        return out
    return mock.patch.object(_AdminBase, '_require_qc', hooked)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestQcDecisionRereadsTheCase(TestCase):
    def setUp(self):
        cohort = make_cohort()
        org = cohort.owning_organisation
        self.qc = make_admin('qc', owning_org=org)
        self.app = make_application('awaiting_qc', outcome='recommend', cohort=cohort,
                                    reviewer=make_admin('reviewer', owning_org=org))
        # The fixture has no documents; a clean verdict lets the accept reach its write.
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, payload):
        return authed_client(self.qc).post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/qc-decision/', payload,
            format='json')

    def _set(self, **fields):
        return lambda: ScholarshipApplication.objects.filter(pk=self.app.pk).update(**fields)

    def _reject(self):
        return self._post({'decision': 'reject', 'comments': 'Income evidence does not hold up.'})

    def test_a_reject_during_a_close_does_not_write_over_it(self):          # scenario A
        with _after_require_qc(self._set(status='closed')), \
                mock.patch('apps.scholarship.emails.send_qc_rejected_email') as reviewer_mail:
            r = self._reject()
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_awaiting_qc'))
        row = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertEqual((row.status, row.rejected_at, row.decision_reopened_at),
                         ('closed', None, None))
        self.assertFalse(DecisionReopen.objects.filter(application=self.app).exists())
        reviewer_mail.assert_not_called()

    def test_a_second_qc_reject_at_the_same_moment_records_nothing(self):   # scenario B
        with _after_require_qc(self._set(status='rejected', rejected_at=timezone.now())), \
                mock.patch('apps.scholarship.emails.send_qc_rejected_email') as reviewer_mail:
            r = self._reject()
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_awaiting_qc'))
        self.assertFalse(DecisionReopen.objects.filter(application=self.app).exists())
        reviewer_mail.assert_not_called()

    def test_an_accept_after_a_reject_committed_does_not_recommend(self):
        with _after_require_qc(self._set(status='rejected', rejected_at=timezone.now())), \
                mock.patch.object(pool, 'publish_profile_to_pool') as publish:
            r = self._post({'decision': 'accept'})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_awaiting_qc'))
        row = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertEqual((row.status, row.recommended_by), ('rejected', ''))
        publish.assert_not_called()

    def test_a_clean_accept_still_recommends(self):                      # guard: not a regression
        r = self._post({'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.app.pk).status, 'recommended')


# ── TD-348 / TD-351: the submit asks the rule again under the lock ─────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheSubmitRereadsTheRule(TestCase):
    URL = '/api/v1/scholarship/applications/'

    def setUp(self):
        self.gift = make_programme(organisation=make_org())
        self.round = make_cohort(programme=self.gift)
        self.student = make_student(contact_email='s@example.test')
        self.real = apply_gate.apply_verdict

    def _post_with(self, on_call):
        """Post the submit; ``on_call[n]`` runs just AFTER the rule's n-th answer (1-based), as the
        commit of another tab's submit would land. Call 1 is the view's early gate; call 2 is the
        re-ask under the profile lock."""
        calls = []

        def verdict(profile, cohort):
            calls.append(1)
            answer = self.real(profile, cohort)
            if len(calls) in on_call:
                on_call[len(calls)]()
            return answer

        with mock.patch.object(apply_gate, 'apply_verdict', side_effect=verdict):
            return authed_client(self.student).post(
                self.URL, {'programme_code': self.gift.code}, format='json')

    def _other_round_submit(self):
        make_application('submitted', student=self.student,
                         cohort=make_cohort(programme=make_programme(organisation=make_org()),
                                            is_open=False))

    def _same_round_submit(self):
        make_application('submitted', student=self.student, cohort=self.round)

    def test_td348_a_submit_to_another_round_meanwhile_is_a_409(self):
        r = self._post_with({1: self._other_round_submit})   # after the page's gate passed
        self.assertEqual((r.status_code, r.json()['code']), (409, apply_gate.IN_PROGRESS))
        self.assertFalse(ScholarshipApplication.objects.filter(cohort=self.round).exists())

    def test_td351_a_submit_to_the_same_round_meanwhile_is_a_409_not_a_500(self):
        # The other tab's application is in play, so the rule answers in-progress (its own order).
        r = self._post_with({1: self._same_round_submit})
        self.assertEqual((r.status_code, r.json()['code']), (409, apply_gate.IN_PROGRESS))
        self.assertEqual(ScholarshipApplication.objects.filter(cohort=self.round).count(), 1)

    def test_td351_an_insert_that_meets_the_constraint_is_a_409(self):
        # Lands AFTER the re-ask under the lock: only the (cohort, profile) constraint stops it.
        r = self._post_with({2: self._same_round_submit})
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn(r.json()['code'], (apply_gate.IN_PROGRESS, apply_gate.ALREADY_APPLIED))

    def test_a_clean_submit_still_files_one_application(self):     # guard: not a regression
        r = self._post_with({})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(ScholarshipApplication.objects.filter(cohort=self.round).count(), 1)


# ── coordinator items 1+2: the tranche writers lock and re-read like Release ───────────────────

class TestTrancheWritersUnderTheLock(TestCase):
    def setUp(self):
        self.app, _, _ = fund_through_the_product(make_cohort(), reviewer=make_admin('reviewer'))
        self.tranche = disbursement.schedule_tranche(self.app, amount='500')

    def _stale(self):
        return Disbursement.objects.select_related('application').get(pk=self.tranche.pk)

    def _status(self):
        return Disbursement.objects.get(pk=self.tranche.pk).status

    def test_mark_due_never_writes_due_over_a_release(self):
        stale = self._stale()
        disbursement.release_tranche(self._stale(), by_email='o@x.test')
        with self.assertRaises(disbursement.DisbursementError) as cm:
            disbursement.mark_due(stale)
        self.assertEqual(cm.exception.code, 'bad_state')
        self.assertEqual(self._status(), 'released')

    def test_a_withhold_from_a_copy_read_before_a_release_is_refused(self):
        stale = self._stale()
        disbursement.release_tranche(self._stale(), by_email='o@x.test')
        with self.assertRaises(disbursement.DisbursementError) as cm:
            disbursement.withhold_tranche(stale, by_email='o@x.test')
        self.assertEqual(cm.exception.code, 'bad_state')
        self.assertEqual(self._status(), 'released')

    def test_two_returns_from_stale_copies_record_one(self):
        disbursement.release_tranche(self._stale(), by_email='o@x.test')
        first, second = self._stale(), self._stale()
        disbursement.return_tranche(first, by_email='o@x.test')
        Disbursement.objects.filter(pk=self.tranche.pk).update(note='after the first return')
        with self.assertRaises(disbursement.DisbursementError) as cm:
            disbursement.return_tranche(second, by_email='o@x.test', note='second')
        self.assertEqual(cm.exception.code, 'bad_state')
        self.assertEqual(Disbursement.objects.get(pk=self.tranche.pk).note, 'after the first return')

    def test_a_release_whose_tranche_row_has_gone_is_bad_state_not_a_crash(self):
        stale = self._stale()
        Disbursement.objects.filter(pk=self.tranche.pk).delete()
        with self.assertRaises(disbursement.DisbursementError) as cm:
            disbursement.release_tranche(stale, by_email='o@x.test')
        self.assertEqual(cm.exception.code, 'bad_state')


# ── coordinator item 3: one sponsor's wallet is locked before its balance is read ──────────────

class TestTheWalletIsLockedBeforeTheBalance(TestCase):
    def test_the_helper_refuses_outside_a_transaction(self):
        sponsor = _funded_sponsor(make_application('recommended'))
        conn = transaction.get_connection()
        saved = conn.in_atomic_block
        conn.in_atomic_block = False
        try:
            with self.assertRaises(RuntimeError):
                status_lock.lock_sponsor_wallet(sponsor)
        finally:
            conn.in_atomic_block = saved

    def test_fund_student_locks_the_wallet_before_it_reads_the_balance(self):
        app = make_application('recommended')
        sponsor = _funded_sponsor(app)
        order = []
        real_balance = svc.sponsor_balance

        def balance(*a, **kw):
            order.append('balance')
            return real_balance(*a, **kw)

        with mock.patch.object(status_lock, 'lock_sponsor_wallet', create=True,
                               side_effect=lambda s: order.append(('lock', s.pk))), \
                mock.patch.object(svc, 'sponsor_balance', side_effect=balance):
            svc.fund_student(sponsor, app)
        self.assertEqual(order[:2], [('lock', sponsor.pk), 'balance'])

    def test_a_reinstatement_locks_the_wallet_before_it_reads_the_balance(self):
        app = make_application('recommended')
        sponsor = _funded_sponsor(app)
        svc.fund_student(sponsor, app)
        since = timezone.now() - timedelta(seconds=1)
        self.assertTrue(svc.lapse_holding_sponsorships(app))
        order = []
        real_balance = svc.sponsor_balance

        def balance(*a, **kw):
            order.append('balance')
            return real_balance(*a, **kw)

        with mock.patch.object(status_lock, 'lock_sponsor_wallet', create=True,
                               side_effect=lambda s: order.append(('lock', s.pk))), \
                mock.patch.object(svc, 'sponsor_balance', side_effect=balance):
            sp = svc.reinstate_lapsed_sponsorship(app, since=since)
        self.assertEqual(order[:2], [('lock', sponsor.pk), 'balance'])
        self.assertEqual(sp.status, 'active')
