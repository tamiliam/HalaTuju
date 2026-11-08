"""A1.13 (TD-198 / CO-09) — WHAT an award withdrawal does, and since A1.13b the four routes.

Since A1.13b the withdrawal is MAKER and CHECKER (`award_withdrawal_chain`, its own tests in
`test_award_withdrawal_chain.py`); every money assertion of A1.13 is kept here, reached through the chain
(`withdrawal_helpers.withdraw_now`: a request, then an approval by a different person). Pins: the holding
sponsorship cancelled (its amount back in the sponsor's balance), the case back to ``recommended``, unpaid
tranches withheld, an INTERNAL activity row holding the explanation / who / when, the "award withdrawn"
email after commit — never carrying the explanation, and not sent while the award itself is still in its
cool-off (never told) — and a paid case refused under the lock (``has_payments``, TD-591).
All on dummy data.
"""
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import award_withdrawal as svc
from apps.scholarship import award_withdrawal_chain as chain
from apps.scholarship.models import (
    AwardWithdrawalRequest, Disbursement, Donation, ScholarshipApplication, Sponsor,
    SponsorProgrammeMembership, Sponsorship, StudentActivity,
)
from apps.scholarship.sponsorship import sponsor_balance
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
    make_shortlistable_student,
)
from apps.scholarship.tests.withdrawal_helpers import EXPLANATION, checker_in, maker_in, withdraw_now

AMOUNT = Decimal('2000')


def _sponsor(programme, uid):
    sponsor = Sponsor.objects.create(
        supabase_user_id=uid, name='Test Sponsor', email=f'{uid}@sponsor.example',
        phone='0123', source='friend', consent_at=timezone.now(), status='approved')
    SponsorProgrammeMembership.objects.create(sponsor=sponsor, programme=programme, status='approved')
    Donation.objects.create(sponsor=sponsor, amount=AMOUNT, programme=programme,
                            status=Donation.STATUS_CONFIRMED)
    return sponsor


class _Base(TestCase):
    def setUp(self):
        self.cohort = make_cohort()
        self.programme = self.cohort.programme
        self.org = self.cohort.owning_organisation
        self.app = make_application('awarded', cohort=self.cohort,
                                    student=make_shortlistable_student(), award_amount=AMOUNT)
        self.sponsor = _sponsor(self.programme, f'wd-spon-{self.app.pk}')
        self.sp = Sponsorship.objects.create(
            sponsor=self.sponsor, application=self.app, amount=AMOUNT, status='offered',
            offer_emailed_at=timezone.now())
        self.maker = maker_in(self.org)
        self.checker = checker_in(self.org)

    def _tranche(self, status, seq=1):
        return Disbursement.objects.create(application=self.app, sponsorship=self.sp,
                                           amount=Decimal('500'), status=status, sequence=seq)

    def _withdraw(self, explanation=EXPLANATION):
        return withdraw_now(self.app, maker=self.maker, checker=self.checker, explanation=explanation)


# ─── what the approved withdrawal does ──────────────────────────────────────

class TestWithdrawService(_Base):
    def test_the_balance_is_held_before(self):
        self.assertEqual(sponsor_balance(self.sponsor, self.programme), Decimal('0'))

    def test_withdraw_returns_case_to_pool_and_frees_balance(self):
        with self.captureOnCommitCallbacks(execute=True):
            self._withdraw(f'  {EXPLANATION}  ')
        self.app.refresh_from_db()
        self.sp.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')
        self.assertEqual(self.sp.status, 'cancelled')
        self.assertIsNotNone(self.sp.decided_at)
        self.assertEqual(sponsor_balance(self.sponsor, self.programme), AMOUNT)

    def test_the_explanation_is_stored_internally_with_who_and_when(self):
        with self.captureOnCommitCallbacks(execute=True):
            self._withdraw(f'  {EXPLANATION}  ')
        row = StudentActivity.objects.get(application=self.app, event='award_withdrawn')
        self.assertEqual(row.body, EXPLANATION)              # trimmed, whole
        self.assertTrue(row.internal)                        # the student never sees it
        self.assertEqual(row.actor_email, self.checker.email)   # the person who approved it
        self.assertIsNotNone(row.created_at)
        self.assertEqual(row.meta['sponsorship_ids'], [self.sp.pk])
        self.assertEqual(row.meta['amount_freed'], '2000.00')
        self.assertEqual(row.meta['to'], 'recommended')
        self.assertTrue(row.meta['student_emailed'])

    def test_unpaid_tranches_stop(self):
        scheduled, due = self._tranche('scheduled', 1), self._tranche('due', 2)
        with self.captureOnCommitCallbacks(execute=True):
            self._withdraw()
        scheduled.refresh_from_db()
        due.refresh_from_db()
        self.assertEqual((scheduled.status, due.status), ('withheld', 'withheld'))
        self.assertEqual(scheduled.actioned_by, self.checker.email)
        row = StudentActivity.objects.get(application=self.app, event='award_withdrawn')
        self.assertEqual(row.meta['tranches_withheld'], [scheduled.pk, due.pk])

    def test_the_student_is_emailed_after_commit_without_the_explanation(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self._withdraw()
        self.assertEqual(len(mail.outbox), 0)                # nothing before the commit
        for cb in callbacks:
            cb()
        student = [m for m in mail.outbox if m.to == [self.app.notify_email]]
        self.assertEqual(len(student), 1)
        msg = student[0]
        self.assertIn('withdrawn', msg.body)
        self.assertNotIn('Zxq', msg.body)                    # the explanation is internal
        self.assertNotIn('Zxq', msg.subject)
        for alt, _mime in getattr(msg, 'alternatives', []):
            self.assertNotIn('Zxq', alt)

    def test_the_email_is_in_her_language(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(locale='ms')
        self.app.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            self._withdraw()
        student = [m for m in mail.outbox if m.to == [self.app.notify_email]]
        self.assertIn('ditarik balik', student[0].body)

    def test_no_email_while_the_award_is_still_in_its_cool_off(self):
        Sponsorship.objects.filter(pk=self.sp.pk).update(offer_emailed_at=None)
        with self.captureOnCommitCallbacks(execute=True):
            self._withdraw()
        self.assertFalse([m for m in mail.outbox if m.to == [self.app.notify_email]])   # never told
        row = StudentActivity.objects.get(application=self.app, event='award_withdrawn')
        self.assertFalse(row.meta['student_emailed'])
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')

    def test_a_failing_email_never_undoes_the_withdrawal(self):
        with patch('apps.scholarship.student_comms.send_student_email', side_effect=RuntimeError):
            with self.captureOnCommitCallbacks(execute=True):
                self._withdraw()
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')

    def test_the_explanation_is_required(self):
        for bad in (None, '', '   ', 42):
            with self.subTest(explanation=bad):
                with self.assertRaises(svc.AwardWithdrawalError) as ctx:
                    chain.request_withdrawal(self.app, by_admin=self.maker, explanation=bad)
                self.assertEqual(ctx.exception.code, 'explanation_required')
        self.assertFalse(AwardWithdrawalRequest.objects.exists())

    def test_an_over_long_explanation_is_refused_not_cut(self):
        with self.assertRaises(svc.AwardWithdrawalError) as ctx:
            chain.request_withdrawal(self.app, by_admin=self.maker, explanation='x' * (chain.TEXT_MAX + 1))
        self.assertEqual(ctx.exception.code, 'explanation_too_long')
        chain.request_withdrawal(self.app, by_admin=self.maker, explanation='x' * chain.TEXT_MAX)   # the limit

    def test_only_an_awarded_case(self):
        for status in ('recommended', 'active', 'maintenance', 'interviewed', 'closed'):
            with self.subTest(status=status):
                ScholarshipApplication.objects.filter(pk=self.app.pk).update(status=status)
                with self.assertRaises(svc.AwardWithdrawalError) as ctx:
                    chain.request_withdrawal(self.app, by_admin=self.maker, explanation=EXPLANATION)
                self.assertEqual(ctx.exception.code, 'not_awarded')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, 'offered')          # nothing touched

    def test_the_double_click_on_approve_is_harmless(self):
        with self.captureOnCommitCallbacks(execute=True):
            row = self._withdraw()
        with self.assertRaises(svc.AwardWithdrawalError) as ctx:
            chain.approve_withdrawal(row.pk, by_admin=self.checker)
        self.assertEqual(ctx.exception.code, 'not_awarded')  # the case is no longer awarded
        self.assertEqual(StudentActivity.objects.filter(
            application=self.app, event='award_withdrawn').count(), 1)
        self.assertEqual(len([m for m in mail.outbox if m.to == [self.app.notify_email]]), 1)

    def test_a_paid_case_is_refused_and_nothing_moves(self):
        for paid in ('released', 'returned'):
            with self.subTest(paid=paid):
                tranche = self._tranche(paid)
                pending = self._tranche('scheduled', 2)
                with self.assertRaises(svc.AwardWithdrawalError) as ctx:
                    chain.request_withdrawal(self.app, by_admin=self.maker, explanation=EXPLANATION)
                self.assertEqual(ctx.exception.code, 'has_payments')
                self.app.refresh_from_db()
                self.sp.refresh_from_db()
                pending.refresh_from_db()
                self.assertEqual(self.app.status, 'awarded')
                self.assertEqual(self.sp.status, 'offered')
                self.assertEqual(pending.status, 'scheduled')
                self.assertEqual(sponsor_balance(self.sponsor, self.programme), Decimal('0'))
                tranche.delete()
                pending.delete()

    def test_the_paid_check_reads_after_the_lock(self):
        """Both checks run INSIDE the locked block: a payment committed after the caller read the case
        (but before the request, or before the approval) is seen."""
        order = []
        from apps.scholarship import status_lock
        real_lock = status_lock.lock_application_for

        def spy_lock(app, allowed):
            order.append('lock')
            return real_lock(app, allowed)

        real_has = svc.has_payments

        def spy_has(app):
            order.append('check')
            return real_has(app)

        with patch.object(status_lock, 'lock_application_for', spy_lock), \
                patch.object(svc, 'has_payments', spy_has):
            with self.captureOnCommitCallbacks(execute=True):
                self._withdraw()
        self.assertEqual(order, ['lock', 'check', 'lock', 'check'])

    def test_withheld_tranches_do_not_count_as_paid(self):
        self._tranche('withheld')
        self.assertTrue(svc.can_withdraw(self.app))
        self._tranche('released', 2)
        self.assertFalse(svc.can_withdraw(self.app))

    def test_an_awarded_case_with_no_sponsorship_is_withdrawn_and_told(self):
        self.sp.delete()
        with self.captureOnCommitCallbacks(execute=True):
            self._withdraw()
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')
        self.assertEqual(len([m for m in mail.outbox if m.to == [self.app.notify_email]]), 1)


# ─── the four routes ────────────────────────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestWithdrawalEndpoints(_Base):
    BASE = '/api/v1/admin/scholarship'

    def _post(self, admin, url, body=None):
        with self.captureOnCommitCallbacks(execute=True):
            return authed_client(admin).post(url, body or {}, format='json')

    def _request(self, admin=None, explanation=EXPLANATION):
        return self._post(admin or self.maker, f'{self.BASE}/applications/{self.app.id}/withdrawal-request/',
                          {'explanation': explanation})

    def _act(self, admin, pk, step, body=None):
        # Each route spelled out, so test_endpoint_exercise's static scan sees all three driven.
        if step == 'approve':
            return self._post(admin, f'{self.BASE}/withdrawal-requests/{pk}/approve/', body)
        if step == 'refuse':
            return self._post(admin, f'{self.BASE}/withdrawal-requests/{pk}/refuse/', body)
        assert step == 'cancel', step
        return self._post(admin, f'{self.BASE}/withdrawal-requests/{pk}/cancel/', body)

    def test_request_then_approve(self):
        r = self._request()
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body['status'], 'awarded')                       # nothing changed yet
        self.assertEqual(body['withdrawal_request']['status'], 'pending')
        self.assertEqual(body['withdrawal_request']['your_step'], 'cancel')
        pk = body['withdrawal_request']['id']
        r = self._act(self.checker, pk, 'approve', {'note': 'Agreed.'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['status'], 'recommended')
        self.assertEqual(r.json()['withdrawal_request']['status'], 'approved')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, 'cancelled')

    def test_refuse_and_cancel(self):
        pk = self._request().json()['withdrawal_request']['id']
        r = self._act(self.checker, pk, 'refuse', {'reason': '   '})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'reason_required'))
        r = self._act(self.checker, pk, 'refuse', {'reason': 'Not enough evidence.'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['withdrawal_request']['status'], 'refused')
        pk = self._request().json()['withdrawal_request']['id']
        self.assertEqual(self._act(self.checker, pk, 'cancel').status_code, 403)   # not the maker
        r = self._act(self.maker, pk, 'cancel')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['withdrawal_request']['status'], 'cancelled')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'awarded')

    def test_the_status_codes(self):
        self.assertEqual(self._request(explanation='  ').status_code, 400)
        self.assertEqual(self._request(admin=self.checker).json()['code'], 'wrong_role')   # lead cannot ask
        pk = self._request().json()['withdrawal_request']['id']
        r = self._request()
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_pending'))
        r = self._act(self.maker, pk, 'approve')                          # the maker holds no approve key
        self.assertEqual((r.status_code, r.json()['code']), (403, 'wrong_role'))
        self.maker.permissions = list(self.maker.permissions) + ['award_withdraw_approve']
        self.maker.save(update_fields=['permissions'])
        r = self._act(self.maker, pk, 'approve')                          # ... and with it, still not
        self.assertEqual((r.status_code, r.json()['code']), (403, 'same_person'))
        self._tranche('released')
        r = self._act(self.checker, pk, 'approve')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'has_payments'))

    def test_a_super_is_403_in_every_seat(self):
        sup = make_admin(super_admin=True)
        self.assertEqual(self._request(admin=sup).status_code, 403)
        pk = self._request().json()['withdrawal_request']['id']
        for step in ('approve', 'refuse', 'cancel'):
            with self.subTest(step=step):
                r = self._act(sup, pk, step, {'reason': 'x'})
                self.assertEqual((r.status_code, r.json()['code']), (403, 'wrong_role'))
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'awarded')

    def test_every_preset_role_is_403_on_the_request(self):
        for role in ('reviewer', 'qc', 'admin', 'finance'):
            with self.subTest(role=role):
                r = self._request(admin=make_admin(role, owning_org=self.org, first_seen_at=timezone.now()))
                self.assertEqual(r.status_code, 403, (role, r.content))
        self.assertFalse(AwardWithdrawalRequest.objects.exists())

    def test_anonymous_is_refused(self):
        r = self.client.post(f'{self.BASE}/applications/{self.app.id}/withdrawal-request/',
                             {'explanation': EXPLANATION}, format='json')
        self.assertIn(r.status_code, (401, 403))

    def test_an_unknown_case_or_request_is_404(self):
        r = self._post(self.maker, f'{self.BASE}/applications/999999/withdrawal-request/',
                       {'explanation': EXPLANATION})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self._act(self.checker, 999999, 'approve').status_code, 404)

    def test_another_organisations_request_is_404(self):
        pk = self._request().json()['withdrawal_request']['id']
        other = checker_in(make_cohort().owning_organisation)
        for step in ('approve', 'refuse', 'cancel'):
            with self.subTest(step=step):
                self.assertEqual(self._act(other, pk, step, {'reason': 'x'}).status_code, 404)
        self.assertEqual(AwardWithdrawalRequest.objects.get(pk=pk).status, 'pending')
