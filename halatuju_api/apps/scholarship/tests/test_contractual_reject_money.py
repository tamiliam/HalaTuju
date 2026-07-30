"""Code-health S3 (#6/#7/#11): money-side integrity of the contractual reject +
owner-send email commands.

#6 — rejecting a funded student must LAPSE the sponsorship (balance returns; sponsor
surfaces stop counting the student), and cancelling that decline within the embargo
window reinstates it when the balance still covers it.
#7 — a FAILED award-offer send must not be stamped as emailed (the release cron filters
on the stamp, so a stamped failure was permanently suppressed).
#11 — the sign-invitation command is a no-op while the bursary chain is dark.
"""
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import services
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, ScholarshipApplication, ScholarshipCohort, Sponsor, SponsorProfile,
    Sponsorship,
)


@override_settings(DECLINE_COOLOFF_DAYS=7)
class TestContractualRejectLapsesSponsorship(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='crm-admin', role='super', is_super_admin=True,
            is_active=True, name='A', email='admin@x.com')

    def _funded_app(self):
        n = StudentProfile.objects.count()
        p = StudentProfile.objects.create(
            supabase_user_id=f'crm{n}', name='Zxq', nric=f'00010{n}-10-123{n}',
            grades={'bm': 'A'}, contact_email='s@x.com')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='recommended', award_amount=Decimal('3000'),
            notify_email='s@x.com')
        SponsorProfile.objects.create(application=app, anon_markdown='x', anon_published=True)
        Consent.objects.create(application=app, consent_type='share_with_sponsors',
                               version='e', is_active=True)
        s = Sponsor.objects.create(
            supabase_user_id=f'crmsp{n}', name='Jane', email=f'crmj{n}@x.com',
            phone='0123', source='friend', consent_at=timezone.now(), status='approved')
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        svc.fund_student(s, app)                                  # → 'awarded', 'offered' row
        svc.respond_to_award(app, action='accept')                # sponsorship → 'active'
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            status='active', award_due_at=None)                   # executed/funded
        app.refresh_from_db()
        return app, s

    def test_contractual_reject_lapses_and_returns_balance(self):
        app, s = self._funded_app()
        self.assertEqual(svc.sponsor_balance(s, None), Decimal('0'))    # money held
        services.admin_reject(app, self.admin, 'contractual')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        self.assertFalse(app.sponsorships.filter(status__in=Sponsorship.HOLDING).exists())
        self.assertEqual(svc.sponsor_balance(s, None), Decimal('3000'))  # returned to the sponsor

    def test_cancel_reinstates_sponsorship_and_funded_status(self):
        app, s = self._funded_app()
        services.admin_reject(app, self.admin, 'contractual')
        self.assertTrue(services.cancel_pending_decline(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')                     # snapshot restore (S1)
        self.assertTrue(app.sponsorships.filter(status='active').exists())
        self.assertEqual(svc.sponsor_balance(s, None), Decimal('0'))     # held again

    def test_cancel_without_covering_balance_leaves_lapsed(self):
        app, s = self._funded_app()
        services.admin_reject(app, self.admin, 'contractual')
        # The sponsor redirected the returned money in the window → can't reinstate.
        other = self._funded_app()[0]  # a second funded app consumes a fresh RM3000 of its own
        Donation.objects.filter(sponsor=s).delete()                # simulate: balance gone
        self.assertTrue(services.cancel_pending_decline(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')                     # status restored anyway
        self.assertFalse(app.sponsorships.filter(status__in=Sponsorship.HOLDING).exists())
        self.assertEqual(other.status, 'active')                   # unrelated app untouched

    def test_interview_reject_touches_no_sponsorship(self):
        app, s = self._funded_app()
        ScholarshipApplication.objects.filter(pk=app.pk).update(status='interviewed')
        app.refresh_from_db()
        services.admin_reject(app, self.admin, 'interview')
        # A pre-award bucket never reaches the lapse branch (funded states can't be
        # 'interview'-rejected anyway; this pins the category scoping).
        self.assertTrue(app.sponsorships.filter(status='active').exists())


@override_settings(DECLINE_COOLOFF_DAYS=7)
class TestRejectClearsAwardAmount(TestCase):
    """A REJECTED application holds no money — on every reject path, not just the verdict one.

    `award_amount` was cleared only by the verdict recorder, which is one of THREE decline
    routes. A student accepted, reopened, then declined through the `interview` bucket kept
    their amount: apps 21 and 71 on production did (RM5,000 between them). Every test here
    was checked to FAIL with the `_record_reject` clear removed.
    """

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='rca', name='B40', year=2026)
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='rca-admin', role='super', is_super_admin=True,
            is_active=True, name='A', email='rca@x.com')

    def _app(self, status, amount='3000'):
        n = StudentProfile.objects.count()
        p = StudentProfile.objects.create(
            supabase_user_id=f'rca{n}', name='Zxq', nric=f'00020{n}-10-123{n}',
            grades={'bm': 'A'}, contact_email='s@x.com')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status=status, notify_email='s@x.com',
            award_amount=Decimal(amount) if amount is not None else None)

    def test_interview_bucket_decline_clears_it(self):
        # Apps 21 and 71 exactly: accepted, reopened to 'interviewing', then declined.
        app = self._app('interviewing')
        services.admin_reject(app, self.admin, 'interview')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        self.assertIsNone(app.award_amount)
        self.assertEqual(app.pre_decline_award_amount, Decimal('3000'))   # recoverable

    def test_org_admin_reject_clears_it(self):
        app = self._app('shortlisted')
        services.org_admin_reject(app, self.admin, 'Stopped responding')
        app.refresh_from_db()
        self.assertIsNone(app.award_amount)

    def test_contractual_decline_clears_it(self):
        app = self._app('active')
        services.admin_reject(app, self.admin, 'contractual')
        app.refresh_from_db()
        self.assertIsNone(app.award_amount)

    def test_cancelled_decline_gives_the_money_back(self):
        # The load-bearing one: the clear is only safe because it is reversible. A funded
        # student restored WITHOUT their amount is silently unpayable (payments.amount_due
        # caps at award − paid), which would be worse than the stale amount.
        app = self._app('active')
        services.admin_reject(app, self.admin, 'contractual')
        self.assertTrue(services.cancel_pending_decline(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')
        self.assertEqual(app.award_amount, Decimal('3000'))
        self.assertIsNone(app.pre_decline_award_amount)   # snapshot consumed, not left behind

    def test_reject_without_an_amount_invents_nothing(self):
        app = self._app('interviewing', amount=None)
        services.admin_reject(app, self.admin, 'interview')
        app.refresh_from_db()
        self.assertIsNone(app.award_amount)
        self.assertIsNone(app.pre_decline_award_amount)
        self.assertTrue(services.cancel_pending_decline(app))
        app.refresh_from_db()
        self.assertIsNone(app.award_amount)               # cancel can't conjure one

    def test_a_second_reject_does_not_destroy_the_snapshot(self):
        app = self._app('interviewing')
        services.admin_reject(app, self.admin, 'interview')
        services._record_reject(app, 'interview', 'again@x.com')   # re-record on a cleared row
        app.refresh_from_db()
        self.assertEqual(app.pre_decline_award_amount, Decimal('3000'))

    def test_reopen_deliberately_keeps_the_amount(self):
        # ⚠ A REOPEN IS NOT A DECLINE — do not "fix" this to clear the amount. Application 99
        # on production sits exactly here (accepted 29 Jul, reopened the same day): the amount
        # is held pending the re-decision, and is cleared only if that decision is a decline.
        from apps.scholarship import reopen
        app = self._app('recommended')
        app.officer_verdict = {'overall': 'accept'}
        app.verdict_decided_at = timezone.now()
        app.verdict_decided_by = 'rca@x.com'
        app.save(update_fields=['officer_verdict', 'verdict_decided_at', 'verdict_decided_by'])
        reopen.reopen_decision(app, by_admin=self.admin, reason='Merit re-check')
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('3000'))


class TestAwardOfferEmailStamp(TestCase):
    def _awarded(self):
        cohort = ScholarshipCohort.objects.create(code='ce', name='B40', year=2026)
        p = StudentProfile.objects.create(supabase_user_id='em1', name='Z')
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=p, status='awarded', notify_email='s@x.com')
        s = Sponsor.objects.create(
            supabase_user_id='emsp', name='J', email='emj@x.com', phone='0',
            source='friend', consent_at=timezone.now(), status='approved')
        sp = Sponsorship.objects.create(
            application=app, sponsor=s, amount=Decimal('3000'), status='offered')
        return app, sp

    @override_settings(AWARD_EMAIL_APP_IDS='')
    def test_no_ids_no_send(self):
        call_command('send_award_offer_emails')   # smoke: no crash, nothing to assert

    def test_failed_send_is_not_stamped(self):
        app, sp = self._awarded()
        with override_settings(AWARD_EMAIL_APP_IDS=str(app.id)), \
             patch('apps.scholarship.management.commands.send_award_offer_emails'
                   '.send_award_offer_email', return_value=False):
            call_command('send_award_offer_emails')
        sp.refresh_from_db()
        self.assertIsNone(sp.offer_emailed_at)     # #7: still eligible for the release cron

    def test_successful_send_is_stamped(self):
        app, sp = self._awarded()
        with override_settings(AWARD_EMAIL_APP_IDS=str(app.id)), \
             patch('apps.scholarship.management.commands.send_award_offer_emails'
                   '.send_award_offer_email', return_value=True):
            call_command('send_award_offer_emails')
        sp.refresh_from_db()
        self.assertIsNotNone(sp.offer_emailed_at)


class TestSignInvitationDarkGate(TestCase):
    def _awarded(self):
        cohort = ScholarshipCohort.objects.create(code='cs', name='B40', year=2026)
        p = StudentProfile.objects.create(supabase_user_id='sg1', name='Z')
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=p, status='awarded', notify_email='s@x.com')
        s = Sponsor.objects.create(
            supabase_user_id='sgsp', name='J', email='sgj@x.com', phone='0',
            source='friend', consent_at=timezone.now(), status='approved')
        Sponsorship.objects.create(
            application=app, sponsor=s, amount=Decimal('3000'), status='offered')
        return app

    def test_dark_chain_sends_nothing_even_with_ids(self):
        app = self._awarded()
        with override_settings(BURSARY_AGREEMENT_ENABLED=False,
                               SIGN_INVITE_APP_IDS=str(app.id)), \
             patch('apps.scholarship.management.commands.send_sign_invitation_emails'
                   '.send_sign_invitation_email') as mock_send:
            call_command('send_sign_invitation_emails')
        mock_send.assert_not_called()              # #11: dark chain → dead-end email blocked

    def test_flag_on_sends(self):
        app = self._awarded()
        with override_settings(BURSARY_AGREEMENT_ENABLED=True,
                               SIGN_INVITE_APP_IDS=str(app.id)), \
             patch('apps.scholarship.management.commands.send_sign_invitation_emails'
                   '.send_sign_invitation_email', return_value=True) as mock_send:
            call_command('send_sign_invitation_emails')
        mock_send.assert_called_once()
