"""A1.13b (TD-198, owner rulings 2026-11-08) — the award withdrawal is MAKER and CHECKER.

Pins: two DIFFERENT people (by account and by email, case-insensitively); a super in neither seat; no
preset holds either key and the organisation admin approves but never requests; one pending request per
case; only a pending, unexpired request is decided; a request expires lazily after EXPIRY_DAYS; the
approval refuses a stale snapshot, a paid case, a case no longer awarded; nothing changes before the
approval; the house lock order; ``no_checker``; the org fence; the audit row keeps both people and both
texts; the student's notice goes through Student comms. All on dummy data.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.db.models import QuerySet
from django.test import TestCase
from django.utils import timezone

from apps.courses import staff_permissions
from apps.scholarship import award_withdrawal as wd
from apps.scholarship import award_withdrawal_chain as chain
from apps.scholarship import my_pending, status_lock
from apps.scholarship.models import (
    AwardWithdrawalRequest, Disbursement, Donation, ScholarshipApplication, Sponsor,
    SponsorProgrammeMembership, Sponsorship, StaffActivity, StudentActivity,
)
from apps.scholarship.tests.factories import (
    make_admin, make_application, make_cohort, make_shortlistable_student,
)
from apps.scholarship.tests.withdrawal_helpers import EXPLANATION, checker_in, maker_in

AMOUNT = Decimal('2000')


def _refusal(fn, *a, **k):
    try:
        fn(*a, **k)
    except wd.AwardWithdrawalError as e:
        return e.code
    return None


class _Base(TestCase):
    def setUp(self):
        self.cohort = make_cohort()
        self.org = self.cohort.owning_organisation
        self.app = make_application('awarded', cohort=self.cohort,
                                    student=make_shortlistable_student(), award_amount=AMOUNT)
        sponsor = Sponsor.objects.create(
            supabase_user_id=f'wdc-{self.app.pk}', name='Test Sponsor', email=f'wdc{self.app.pk}@sponsor.example',
            phone='0123', source='friend', consent_at=timezone.now(), status='approved')
        SponsorProgrammeMembership.objects.create(sponsor=sponsor, programme=self.cohort.programme,
                                                  status='approved')
        Donation.objects.create(sponsor=sponsor, amount=AMOUNT, programme=self.cohort.programme,
                                status=Donation.STATUS_CONFIRMED)
        self.sponsor = sponsor
        self.sp = Sponsorship.objects.create(sponsor=sponsor, application=self.app, amount=AMOUNT,
                                             status='offered', offer_emailed_at=timezone.now())
        self.maker = maker_in(self.org, email='Maker.Person@example.org')
        self.checker = checker_in(self.org)

    def _request(self, admin=None, explanation=EXPLANATION):
        with self.captureOnCommitCallbacks(execute=True):
            return chain.request_withdrawal(self.app, by_admin=admin or self.maker, explanation=explanation)

    def _untouched(self):
        self.app.refresh_from_db()
        self.sp.refresh_from_db()
        self.assertEqual(self.app.status, 'awarded')
        self.assertEqual(self.sp.status, 'offered')
        self.assertFalse(StudentActivity.objects.filter(application=self.app, event='award_withdrawn').exists())


class TestTheSeats(_Base):
    def test_no_preset_holds_either_key_and_the_lead_only_approves(self):
        for role, preset in staff_permissions.PRESETS.items():
            with self.subTest(role=role):
                self.assertNotIn(chain.REQUEST_KEY, preset)
                self.assertNotIn(chain.APPROVE_KEY, preset)
        self.assertIn(chain.APPROVE_KEY, staff_permissions.LEAD_TIER)
        self.assertNotIn(chain.REQUEST_KEY, staff_permissions.LEAD_TIER)
        self.assertEqual(_refusal(self._request, self.checker), 'wrong_role')

    def test_the_maker_cannot_approve_even_with_a_different_email_case(self):
        row = self._request()
        twin = make_admin('admin', owning_org=self.org, email='maker.person@EXAMPLE.org',
                          permissions=['award_withdraw_approve'], first_seen_at=timezone.now())
        self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=twin), 'same_person')
        self.maker.permissions = ['award_withdraw_request', 'award_withdraw_approve']
        self.maker.save(update_fields=['permissions'])
        self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=self.maker), 'same_person')
        self.assertEqual(_refusal(chain.refuse_withdrawal, row.pk, by_admin=self.maker, reason='x'),
                         'same_person')
        self._untouched()

    def test_a_super_sits_in_neither_seat(self):
        sup = make_admin(super_admin=True, owning_org=self.org, first_seen_at=timezone.now())
        self.assertEqual(_refusal(self._request, sup), 'wrong_role')
        row = self._request()
        self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=sup), 'wrong_role')
        self.assertEqual(_refusal(chain.refuse_withdrawal, row.pk, by_admin=sup, reason='x'), 'wrong_role')
        self.assertEqual(_refusal(chain.cancel_withdrawal, row.pk, by_admin=sup), 'wrong_role')
        self.assertIsNone(chain.next_step_for(self.app, row, sup))
        self._untouched()

    def test_a_holder_who_never_signed_in_cannot_act_or_count(self):
        new = maker_in(self.org, first_seen_at=None)
        self.assertEqual(_refusal(self._request, new), 'wrong_role')
        AwardWithdrawalRequest.objects.all().delete()
        self.checker.first_seen_at = None
        self.checker.save(update_fields=['first_seen_at'])
        self.assertEqual(_refusal(self._request), 'no_checker')

    def test_no_checker_other_than_the_maker(self):
        self.checker.is_active = False
        self.checker.save(update_fields=['is_active'])
        self.maker.permissions = ['award_withdraw_request', 'award_withdraw_approve']
        self.maker.save(update_fields=['permissions'])
        self.assertEqual(_refusal(self._request), 'no_checker')
        self.assertFalse(AwardWithdrawalRequest.objects.exists())

    def test_another_organisations_staff_cannot_act(self):
        other_org = make_cohort().owning_organisation
        self.assertEqual(_refusal(self._request, maker_in(other_org)), 'wrong_role')
        row = self._request()
        self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=checker_in(other_org)),
                         'wrong_role')
        self.assertNotIn(checker_in(other_org).pk, [a.pk for a in chain.eligible_checkers(self.org.pk, self.maker)])
        self._untouched()


class TestTheRequest(_Base):
    def test_nothing_changes_before_the_approval(self):
        tranche = Disbursement.objects.create(application=self.app, sponsorship=self.sp, amount=Decimal('500'),
                                              status='scheduled', sequence=1)
        row = self._request()
        self.assertEqual(row.status, 'pending')
        self.assertEqual(row.snapshot, {'sponsorships': [{'id': self.sp.pk, 'amount': '2000.00'}],
                                        'amount_freed': '2000.00', 'tranches_to_withhold': [tranche.pk]})
        tranche.refresh_from_db()
        self.assertEqual(tranche.status, 'scheduled')
        self._untouched()
        self.assertTrue(StaffActivity.objects.filter(verb='withdrawal_requested').exists())

    def test_the_checkers_are_emailed_after_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            chain.request_withdrawal(self.app, by_admin=self.maker, explanation=EXPLANATION)
        self.assertEqual(len(mail.outbox), 0)
        for cb in callbacks:
            cb()
        self.assertEqual([m.to for m in mail.outbox], [[self.checker.email]])

    def test_a_second_pending_request_is_refused(self):
        self._request()
        other = maker_in(self.org)
        self.assertEqual(_refusal(self._request, other), 'already_pending')
        self.assertEqual(AwardWithdrawalRequest.objects.count(), 1)

    def test_a_paid_case_cannot_be_asked(self):
        Disbursement.objects.create(application=self.app, sponsorship=self.sp, amount=Decimal('500'),
                                    status='released', sequence=1)
        self.assertEqual(_refusal(self._request), 'has_payments')


class TestTheDecision(_Base):
    def test_only_a_pending_request_is_approved(self):
        for end in ('cancelled', 'refused', 'approved', 'expired'):
            with self.subTest(end=end):
                AwardWithdrawalRequest.objects.all().delete()
                row = self._request()
                AwardWithdrawalRequest.objects.filter(pk=row.pk).update(status=end)
                self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=self.checker), 'not_pending')
                self.assertEqual(_refusal(chain.refuse_withdrawal, row.pk, by_admin=self.checker, reason='x'),
                                 'not_pending')
                self.assertEqual(_refusal(chain.cancel_withdrawal, row.pk, by_admin=self.maker), 'not_pending')
        self._untouched()

    def test_a_request_expires_after_fourteen_days(self):
        row = self._request()
        old = timezone.now() - timedelta(days=chain.EXPIRY_DAYS, minutes=1)
        AwardWithdrawalRequest.objects.filter(pk=row.pk).update(requested_at=old)
        row.refresh_from_db()
        self.assertEqual(chain.payload_for(self.app, self.checker)['status'], 'expired')
        self.assertEqual(chain.waiting_for(self.checker), 0)
        self.assertFalse(chain.narrow_list(ScholarshipApplication.objects.all(), 'pending').exists())
        self.assertEqual(chain.next_step_for(self.app, row, self.checker), None)      # nothing to decide
        self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=self.checker), 'not_pending')
        row.refresh_from_db()
        self.assertEqual(row.status, 'expired')                                        # written under the lock
        self._untouched()
        self.assertEqual(self._request().status, 'pending')                           # a new request may follow

    def test_a_request_just_inside_fourteen_days_is_live(self):
        row = self._request()
        AwardWithdrawalRequest.objects.filter(pk=row.pk).update(
            requested_at=timezone.now() - timedelta(days=chain.EXPIRY_DAYS) + timedelta(minutes=5))
        self.assertEqual(chain.waiting_for(self.checker), 1)
        self.assertTrue(chain.narrow_list(ScholarshipApplication.objects.all(), 'pending').exists())

    def test_a_stale_snapshot_is_refused(self):
        row = self._request()
        Sponsorship.objects.filter(pk=self.sp.pk).update(amount=Decimal('1500'))
        self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=self.checker), 'stale')
        # the same amount under a NEW sponsorship id (a case holds one sponsorship at a time): still stale
        held_status = self.sp.status
        Sponsorship.objects.filter(pk=self.sp.pk).delete()
        Sponsorship.objects.create(sponsor=self.sponsor, application=self.app, amount=AMOUNT,
                                   status=held_status)
        self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=self.checker), 'stale')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'awarded')

    def test_paid_after_the_request_is_refused(self):
        row = self._request()
        Disbursement.objects.create(application=self.app, sponsorship=self.sp, amount=Decimal('500'),
                                    status='released', sequence=1)
        self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=self.checker), 'has_payments')
        self._untouched()

    def test_no_longer_awarded_is_refused(self):
        row = self._request()
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='active')
        self.assertEqual(_refusal(chain.approve_withdrawal, row.pk, by_admin=self.checker), 'not_awarded')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, 'offered')

    def test_refuse_needs_a_reason_and_leaves_the_award(self):
        row = self._request()
        self.assertEqual(_refusal(chain.refuse_withdrawal, row.pk, by_admin=self.checker, reason=' '),
                         'reason_required')
        self.assertEqual(_refusal(chain.refuse_withdrawal, row.pk, by_admin=self.checker,
                                  reason='x' * (chain.TEXT_MAX + 1)), 'reason_too_long')
        with self.captureOnCommitCallbacks(execute=True):
            chain.refuse_withdrawal(row.pk, by_admin=self.checker, reason='Not enough evidence.')
        row.refresh_from_db()
        self.assertEqual((row.status, row.decision_note, row.decided_by_id), ('refused', 'Not enough evidence.',
                                                                              self.checker.pk))
        self.assertEqual([m.to for m in mail.outbox][-1], [self.maker.email])
        self._untouched()

    def test_only_the_maker_cancels(self):
        row = self._request()
        self.assertEqual(_refusal(chain.cancel_withdrawal, row.pk, by_admin=self.checker), 'wrong_role')
        chain.cancel_withdrawal(row.pk, by_admin=self.maker)
        row.refresh_from_db()
        self.assertEqual(row.status, 'cancelled')
        self._untouched()

    def test_the_audit_row_keeps_both_people_and_both_texts(self):
        row = self._request()
        with self.captureOnCommitCallbacks(execute=True):
            chain.approve_withdrawal(row.pk, by_admin=self.checker, note='Confirmed with the college.')
        log = StudentActivity.objects.get(application=self.app, event='award_withdrawn')
        self.assertEqual(log.body, EXPLANATION)
        self.assertEqual(log.actor_email, self.checker.email)
        self.assertEqual(log.meta['withdrawal'], row.pk)
        self.assertEqual(log.meta['requested_by_email'], self.maker.email)
        self.assertEqual(log.meta['approved_by_email'], self.checker.email)
        self.assertEqual(log.meta['explanation'], EXPLANATION)
        self.assertEqual(log.meta['decision_note'], 'Confirmed with the college.')
        row.refresh_from_db()
        self.assertEqual(row.status, 'approved')
        self.assertTrue(StaffActivity.objects.filter(verb='withdrawal_approved').exists())
        recipients = [m.to for m in mail.outbox]
        self.assertIn([self.app.notify_email], recipients)        # the student
        self.assertIn([self.maker.email], recipients)             # the maker hears the outcome

    def test_the_student_notice_goes_through_student_comms(self):
        row = self._request()
        with patch('apps.scholarship.student_comms.send_student_email', return_value=True) as send:
            with self.captureOnCommitCallbacks(execute=True):
                chain.approve_withdrawal(row.pk, by_admin=self.checker)
        self.assertEqual(send.call_args.args[1], 'award_withdrawn')
        self.assertEqual(send.call_args.args[0].pk, self.app.pk)


class TestTheLockOrder(_Base):
    def _spy(self):
        order = []
        real_lock, real_sfu = status_lock.lock_application_for, QuerySet.select_for_update

        def lock(app, allowed):
            order.append('lock_application')
            return real_lock(app, allowed)

        def sfu(qs, *a, **k):
            order.append(f'sfu:{qs.model.__name__}')
            return real_sfu(qs, *a, **k)
        return order, (patch.object(status_lock, 'lock_application_for', lock),
                       patch.object(QuerySet, 'select_for_update', sfu))

    def test_approve_takes_the_application_then_the_request_then_the_sponsorships(self):
        row = self._request()
        order, (p1, p2) = self._spy()
        with p1, p2, self.captureOnCommitCallbacks(execute=True):
            chain.approve_withdrawal(row.pk, by_admin=self.checker)
        self.assertEqual(order[:4], ['lock_application', 'sfu:ScholarshipApplication',
                                     'sfu:AwardWithdrawalRequest', 'sfu:Sponsorship'])

    def test_refuse_and_cancel_take_the_application_first_too(self):
        for act in (lambda pk: chain.refuse_withdrawal(pk, by_admin=self.checker, reason='No.'),
                    lambda pk: chain.cancel_withdrawal(pk, by_admin=self.maker)):
            row = self._request()
            order, (p1, p2) = self._spy()
            with p1, p2, self.captureOnCommitCallbacks(execute=True):
                act(row.pk)
            self.assertEqual(order[:3], ['lock_application', 'sfu:ScholarshipApplication',
                                         'sfu:AwardWithdrawalRequest'])

    def test_request_takes_the_application_before_the_request_rows(self):
        order, (p1, p2) = self._spy()
        with p1, p2:
            self._request()
        self.assertEqual(order[:3], ['lock_application', 'sfu:ScholarshipApplication',
                                     'sfu:AwardWithdrawalRequest'])


class TestTheScreens(_Base):
    def test_your_step_per_person(self):
        self.assertEqual(chain.payload_for(self.app, self.maker), {'id': None, 'status': None, 'your_step': 'request'})
        self.assertIsNone(chain.payload_for(self.app, self.checker))       # the lead cannot ask
        row = self._request()
        self.assertEqual(chain.payload_for(self.app, self.maker)['your_step'], 'cancel')
        self.assertEqual(chain.payload_for(self.app, self.checker)['your_step'], 'decide')
        self.assertEqual(chain.next_step_for(self.app, row, self.checker), chain.STEP_DECIDE)
        p = chain.payload_for(self.app, self.checker)
        self.assertEqual((p['requested_by_name'], p['amount_freed'], p['sponsorship_count']),
                         (self.maker.name, '2000.00', 1))

    def test_no_query_outside_the_relevant_statuses(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='interviewing')
        self.app.refresh_from_db()
        with self.assertNumQueries(0):
            self.assertIsNone(chain.payload_for(self.app, self.maker))

    def test_my_pending_card_for_the_checker_only(self):
        self._request()
        cards = {c['key']: c for c in my_pending.pending_for(self.checker, b40_scope='all')}
        self.assertEqual(cards['award_withdrawals']['count'], 1)
        keys = [c['key'] for c in my_pending.pending_for(self.maker, b40_scope='all')]
        self.assertNotIn('award_withdrawals', keys)
        sup = make_admin(super_admin=True)
        self.assertNotIn('award_withdrawals', [c['key'] for c in my_pending.pending_for(sup, b40_scope='all')])

    def test_the_list_filter(self):
        self.assertFalse(chain.narrow_list(ScholarshipApplication.objects.all(), 'pending').exists())
        self._request()
        qs = chain.narrow_list(ScholarshipApplication.objects.all(), 'pending')
        self.assertEqual(list(qs.values_list('pk', flat=True)), [self.app.pk])
        self.assertEqual(chain.narrow_list(ScholarshipApplication.objects.all(), 'other').count(),
                         ScholarshipApplication.objects.count())
