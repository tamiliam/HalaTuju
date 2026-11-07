"""A1.13 (TD-198 / CO-09, owner ruling D3) — a super admin withdraws an award.

Pins: super-only (403 for every other role), a REQUIRED reason (400), only an awarded case (409
``not_awarded``, which is also the double-click answer), a paid case refused under the same lock
(409 ``has_payments``, TD-591), and on success: the holding sponsorship cancelled (its amount back
in the sponsor's balance), the case back to ``recommended``, unpaid tranches withheld, an INTERNAL
activity row holding the reason / who / when, and the "award withdrawn" email after commit — never
carrying the reason, and not sent while the award itself is still in its cool-off (never told).
All on dummy data.
"""
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import award_withdrawal as svc
from apps.scholarship.models import (
    Disbursement, Donation, ScholarshipApplication, Sponsor, SponsorProgrammeMembership,
    Sponsorship, StudentActivity,
)
from apps.scholarship.sponsorship import sponsor_balance
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
    make_shortlistable_student,
)

REASON = 'Zxq internal reason: the offer letter was found to be for a different course.'
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
        self.app = make_application('awarded', cohort=self.cohort,
                                    student=make_shortlistable_student(), award_amount=AMOUNT)
        self.sponsor = _sponsor(self.programme, f'wd-spon-{self.app.pk}')
        self.sp = Sponsorship.objects.create(
            sponsor=self.sponsor, application=self.app, amount=AMOUNT, status='offered',
            offer_emailed_at=timezone.now())
        self.superadmin = make_admin(super_admin=True)

    def _tranche(self, status, seq=1):
        return Disbursement.objects.create(application=self.app, sponsorship=self.sp,
                                           amount=Decimal('500'), status=status, sequence=seq)


# ─── the service ─────────────────────────────────────────────────────────────

class TestWithdrawService(_Base):
    def test_the_balance_is_held_before(self):
        self.assertEqual(sponsor_balance(self.sponsor, self.programme), Decimal('0'))

    def test_withdraw_returns_case_to_pool_and_frees_balance(self):
        with self.captureOnCommitCallbacks(execute=True):
            svc.withdraw_award(self.app, by_admin=self.superadmin, reason=f'  {REASON}  ')
        self.app.refresh_from_db()
        self.sp.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')
        self.assertEqual(self.sp.status, 'cancelled')
        self.assertIsNotNone(self.sp.decided_at)
        self.assertEqual(sponsor_balance(self.sponsor, self.programme), AMOUNT)

    def test_the_reason_is_stored_internally_with_who_and_when(self):
        with self.captureOnCommitCallbacks(execute=True):
            svc.withdraw_award(self.app, by_admin=self.superadmin, reason=f'  {REASON}  ')
        row = StudentActivity.objects.get(application=self.app, event='award_withdrawn')
        self.assertEqual(row.body, REASON)                  # trimmed, whole
        self.assertTrue(row.internal)                        # the student never sees it
        self.assertEqual(row.actor_email, self.superadmin.email)
        self.assertIsNotNone(row.created_at)
        self.assertEqual(row.meta['sponsorship_ids'], [self.sp.pk])
        self.assertEqual(row.meta['amount_freed'], '2000.00')
        self.assertEqual(row.meta['to'], 'recommended')
        self.assertTrue(row.meta['student_emailed'])

    def test_unpaid_tranches_stop(self):
        scheduled, due = self._tranche('scheduled', 1), self._tranche('due', 2)
        with self.captureOnCommitCallbacks(execute=True):
            svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
        scheduled.refresh_from_db()
        due.refresh_from_db()
        self.assertEqual((scheduled.status, due.status), ('withheld', 'withheld'))
        self.assertEqual(scheduled.actioned_by, self.superadmin.email)
        row = StudentActivity.objects.get(application=self.app, event='award_withdrawn')
        self.assertEqual(row.meta['tranches_withheld'], [scheduled.pk, due.pk])

    def test_the_student_is_emailed_after_commit_without_the_reason(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
        self.assertEqual(len(mail.outbox), 0)                # nothing before the commit
        for cb in callbacks:
            cb()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, [self.app.notify_email])
        self.assertIn('withdrawn', msg.body)
        self.assertNotIn('Zxq', msg.body)                    # the reason is internal
        self.assertNotIn('Zxq', msg.subject)
        for alt, _mime in getattr(msg, 'alternatives', []):
            self.assertNotIn('Zxq', alt)

    def test_the_email_is_in_her_language(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(locale='ms')
        self.app.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
        self.assertIn('ditarik balik', mail.outbox[0].body)

    def test_no_email_while_the_award_is_still_in_its_cool_off(self):
        Sponsorship.objects.filter(pk=self.sp.pk).update(offer_emailed_at=None)
        with self.captureOnCommitCallbacks(execute=True):
            svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
        self.assertEqual(len(mail.outbox), 0)                # she was never told of the award
        row = StudentActivity.objects.get(application=self.app, event='award_withdrawn')
        self.assertFalse(row.meta['student_emailed'])
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')

    def test_a_failing_email_never_undoes_the_withdrawal(self):
        with patch('apps.scholarship.emails.send_award_withdrawn_email', side_effect=RuntimeError):
            with self.captureOnCommitCallbacks(execute=True):
                svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')

    def test_the_reason_is_required(self):
        for bad in (None, '', '   ', 42):
            with self.subTest(reason=bad):
                with self.assertRaises(svc.AwardWithdrawalError) as ctx:
                    svc.withdraw_award(self.app, by_admin=self.superadmin, reason=bad)
                self.assertEqual(ctx.exception.code, 'reason_required')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'awarded')

    def test_an_over_long_reason_is_refused_not_cut(self):
        with self.assertRaises(svc.AwardWithdrawalError) as ctx:
            svc.withdraw_award(self.app, by_admin=self.superadmin, reason='x' * (svc.REASON_MAX + 1))
        self.assertEqual(ctx.exception.code, 'reason_too_long')

    def test_only_an_awarded_case(self):
        for status in ('recommended', 'active', 'maintenance', 'interviewed', 'closed'):
            with self.subTest(status=status):
                ScholarshipApplication.objects.filter(pk=self.app.pk).update(status=status)
                with self.assertRaises(svc.AwardWithdrawalError) as ctx:
                    svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
                self.assertEqual(ctx.exception.code, 'not_awarded')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, 'offered')          # nothing touched

    def test_a_stale_copy_is_re_read_under_the_lock(self):
        stale = ScholarshipApplication.objects.get(pk=self.app.pk)    # still says 'awarded'
        with self.captureOnCommitCallbacks(execute=True):
            svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
        self.assertEqual(stale.status, 'awarded')
        with self.assertRaises(svc.AwardWithdrawalError) as ctx:      # the double click
            svc.withdraw_award(stale, by_admin=self.superadmin, reason=REASON)
        self.assertEqual(ctx.exception.code, 'not_awarded')
        self.assertEqual(StudentActivity.objects.filter(
            application=self.app, event='award_withdrawn').count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_paid_case_is_refused_and_nothing_moves(self):
        for paid in ('released', 'returned'):
            with self.subTest(paid=paid):
                tranche = self._tranche(paid)
                pending = self._tranche('scheduled', 2)
                with self.assertRaises(svc.AwardWithdrawalError) as ctx:
                    svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
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
        """The check runs INSIDE the locked block: a payment committed after the caller read the
        case (but before the withdrawal) is seen."""
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
                svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
        self.assertEqual(order[:2], ['lock', 'check'])

    def test_withheld_tranches_do_not_count_as_paid(self):
        self._tranche('withheld')
        self.assertTrue(svc.can_withdraw(self.app))
        self._tranche('released', 2)
        self.assertFalse(svc.can_withdraw(self.app))

    def test_an_awarded_case_with_no_sponsorship_is_withdrawn_and_told(self):
        self.sp.delete()
        with self.captureOnCommitCallbacks(execute=True):
            svc.withdraw_award(self.app, by_admin=self.superadmin, reason=REASON)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')
        self.assertEqual(len(mail.outbox), 1)


# ─── the endpoint ────────────────────────────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestWithdrawEndpoint(_Base):
    def _url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/withdraw-award/'

    def _post(self, admin, reason=REASON):
        with self.captureOnCommitCallbacks(execute=True):
            return authed_client(admin).post(self._url(), {'reason': reason}, format='json')

    def test_super_withdraws(self):
        r = self._post(self.superadmin)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['status'], 'recommended')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, 'cancelled')
        self.assertEqual(len(mail.outbox), 1)

    def test_every_other_role_is_403(self):
        from apps.courses.models import PartnerAdmin
        org = self.cohort.owning_organisation
        for role, _label in PartnerAdmin.ROLE_CHOICES:
            if role == 'super':
                continue
            with self.subTest(role=role):
                admin = make_admin(role, owning_org=org)
                r = self._post(admin)
                self.assertEqual(r.status_code, 403, (role, r.content))
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'awarded')
        self.assertFalse(StudentActivity.objects.filter(event='award_withdrawn').exists())

    def test_anonymous_is_refused(self):
        r = self.client.post(self._url(), {'reason': REASON}, format='json')
        self.assertIn(r.status_code, (401, 403))

    def test_empty_reason_is_400(self):
        r = self._post(self.superadmin, reason='   ')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'reason_required')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'awarded')

    def test_a_case_not_awarded_is_409(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='recommended')
        r = self._post(self.superadmin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['code'], 'not_awarded')

    def test_the_double_click_is_409_and_harmless(self):
        self.assertEqual(self._post(self.superadmin).status_code, 200)
        r = self._post(self.superadmin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['code'], 'not_awarded')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(StudentActivity.objects.filter(event='award_withdrawn').count(), 1)

    def test_a_paid_case_is_409_has_payments(self):
        self._tranche('released')
        r = self._post(self.superadmin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['code'], 'has_payments')

    def test_an_unknown_case_is_404(self):
        r = authed_client(self.superadmin).post(
            '/api/v1/admin/scholarship/applications/999999/withdraw-award/',
            {'reason': REASON}, format='json')
        self.assertEqual(r.status_code, 404)
