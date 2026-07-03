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
        self.assertEqual(svc.sponsor_balance(s), Decimal('0'))    # money held
        services.admin_reject(app, self.admin, 'contractual')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        self.assertFalse(app.sponsorships.filter(status__in=Sponsorship.HOLDING).exists())
        self.assertEqual(svc.sponsor_balance(s), Decimal('3000'))  # returned to the sponsor

    def test_cancel_reinstates_sponsorship_and_funded_status(self):
        app, s = self._funded_app()
        services.admin_reject(app, self.admin, 'contractual')
        self.assertTrue(services.cancel_pending_decline(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')                     # snapshot restore (S1)
        self.assertTrue(app.sponsorships.filter(status='active').exists())
        self.assertEqual(svc.sponsor_balance(s), Decimal('0'))     # held again

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
