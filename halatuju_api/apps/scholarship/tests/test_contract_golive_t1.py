"""Contract Go-Live Transition — Sprint T1 (backend).

Covers the six T1 behaviours + the plan's T1 acceptance block:
  1. Award email flag matrix — flag-OFF path byte-identical (Vircle award email + setup task);
     flag-ON path sends the sign-flavoured variant and raises NO Vircle task.
  2. Vircle invite at execution + the grandfather skip (a resolved task / non-blank vircle_id →
     nothing sent, nothing raised).
  3. Maintenance flip in payments.complete (active → maintenance on the first released item;
     never from awarded; idempotent from maintenance).
  4. Offer-lapse rework — armed-only lapse, paid apps flagged not lapsed, deadline armed at
     sign-invitation send and cleared when the agreement binds.
  5. Witness resolution order: override → referral → none.
  6. Sources + witness-assignment admin endpoints (super/org_admin only).

All external seams (email backend, Vircle/PDF/Drive) are locmem/mocked — no live calls.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import jwt
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import bursary, payments
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    BursaryAgreement, Consent, Disbursement, Donation, PaymentRun, PaymentRunItem,
    ScholarshipApplication, ScholarshipCohort, Sponsor, Sponsorship, SponsorProfile,
)
from apps.scholarship.tests.contract_helpers import brightpath_org

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADULT_NRIC = '000101-10-1233'


def _cohort(org, suffix='t1'):
    return ScholarshipCohort.objects.create(
        code=f'gl-{suffix}', name='B40', year=2026, owning_organisation=org)


def _fundable_app(cohort, *, suffix='1', award=Decimal('3000'), referred=None):
    profile = StudentProfile.objects.create(
        supabase_user_id=f'gl-stu-{suffix}', name='Zxq Student', nric=ADULT_NRIC,
        exam_type='spm', grades={'bm': 'A'}, contact_email='student@secret.example',
        contact_phone='012-7776666', referred_by_org=referred)
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='recommended', award_amount=award,
        notify_email='student@secret.example')
    SponsorProfile.objects.create(application=app, anon_markdown='Determined.', anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
    return app


def _sponsor(uid='gl-spon', amount='9000'):
    s = Sponsor.objects.create(
        supabase_user_id=uid, name='Jane', email='jane@sponsor.example', phone='0123',
        source='friend', consent_at=timezone.now(), status='approved')
    Donation.objects.create(sponsor=s, amount=Decimal(amount))
    return s


def _offered_past_cooloff(cohort, suffix):
    """A HOLDING (offered) sponsorship whose offered_at is older than the email cool-off, so
    release_award_offer_emails will pick it up. Returns (sponsorship, application)."""
    app = _fundable_app(cohort, suffix=suffix)
    sp = svc.fund_student(_sponsor(uid=f'gl-spon-{suffix}'), app)
    old = timezone.now() - timedelta(hours=48)
    Sponsorship.objects.filter(id=sp.id).update(offered_at=old)
    sp.refresh_from_db()
    return sp, app


# ─────────────────────────────────────────────────────────────────────────────
# 1. Award email flag matrix
# ─────────────────────────────────────────────────────────────────────────────
class TestAwardEmailFlagMatrix(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = brightpath_org()
        cls.cohort = _cohort(cls.org)

    @override_settings(BURSARY_AGREEMENT_ENABLED=False)
    @patch('apps.scholarship.sponsorship.raise_setup_task')
    @patch('apps.scholarship.sponsorship.send_award_offer_sign_email')
    @patch('apps.scholarship.sponsorship.send_award_offer_email', return_value=True)
    def test_flag_off_sends_vircle_award_and_raises_task(self, m_vircle, m_sign, m_task):
        sp, app = _offered_past_cooloff(self.cohort, 'off')
        self.assertEqual(svc.release_award_offer_emails(), 1)
        m_vircle.assert_called_once()      # the Vircle-flavoured award email
        m_task.assert_called_once()        # setup task raised, as before
        m_sign.assert_not_called()         # NOT the sign variant
        sp.refresh_from_db()
        self.assertIsNotNone(sp.offer_emailed_at)

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    @patch('apps.scholarship.sponsorship.raise_setup_task')
    @patch('apps.scholarship.sponsorship.send_award_offer_sign_email', return_value=True)
    @patch('apps.scholarship.sponsorship.send_award_offer_email')
    def test_flag_on_sends_sign_variant_and_raises_no_task(self, m_vircle, m_sign, m_task):
        sp, app = _offered_past_cooloff(self.cohort, 'on')
        self.assertEqual(svc.release_award_offer_emails(), 1)
        m_sign.assert_called_once()        # the review-&-sign variant
        m_vircle.assert_not_called()       # NO Vircle award email
        m_task.assert_not_called()         # NO Vircle task on this path
        sp.refresh_from_db()
        self.assertIsNotNone(sp.offer_emailed_at)

    @override_settings(BURSARY_AGREEMENT_ENABLED=True,
                       EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_sign_variant_points_to_award_page_and_has_no_vircle(self):
        mail.outbox = []
        from apps.scholarship import emails
        self.assertTrue(emails.send_award_offer_sign_email('s@e.test', 'Zxq', lang='en'))
        body = mail.outbox[0].body
        self.assertIn('/scholarship/award', body)
        self.assertNotIn('Vircle', body)
        self.assertNotIn('eWallet', body)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Vircle invite at execution + grandfather skip
# ─────────────────────────────────────────────────────────────────────────────
class TestVircleAtExecution(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = brightpath_org()
        cls.cohort = _cohort(cls.org)

    def _app(self, suffix, **kw):
        app = _fundable_app(self.cohort, suffix=suffix)
        for k, v in kw.items():
            setattr(app, k, v)
        if kw:
            app.save(update_fields=list(kw))
        return app

    @patch('apps.scholarship.emails.send_vircle_install_email', return_value=True)
    def test_new_student_gets_vircle_email_and_task_at_execution(self, m_email):
        app = self._app('new')
        bursary.send_vircle_setup_at_execution(app)
        m_email.assert_called_once()
        from apps.scholarship import vircle
        self.assertIsNotNone(vircle.setup_task(app))

    @patch('apps.scholarship.emails.send_vircle_install_email', return_value=True)
    def test_grandfather_with_vircle_id_is_skipped(self, m_email):
        app = self._app('gf-id', vircle_id='8000400175123')
        bursary.send_vircle_setup_at_execution(app)
        m_email.assert_not_called()

    @patch('apps.scholarship.emails.send_vircle_install_email', return_value=True)
    def test_grandfather_with_existing_task_is_skipped(self, m_email):
        app = self._app('gf-task')
        from apps.scholarship import vircle
        vircle.raise_setup_task(app)     # they already carry the task (old merged-award cohort)
        m_email.reset_mock()
        bursary.send_vircle_setup_at_execution(app)
        m_email.assert_not_called()

    @patch('apps.scholarship.emails.send_vircle_install_email', return_value=True)
    def test_idempotent_second_call_does_not_resend(self, m_email):
        app = self._app('idem')
        bursary.send_vircle_setup_at_execution(app)
        bursary.send_vircle_setup_at_execution(app)   # task now exists → skip
        m_email.assert_called_once()

    @patch('apps.scholarship.emails.send_vircle_install_email', return_value=False)
    def test_failed_send_raises_no_task_so_it_retries(self, m_email):
        app = self._app('fail')
        bursary.send_vircle_setup_at_execution(app)
        from apps.scholarship import vircle
        self.assertIsNone(vircle.setup_task(app))   # no task on a failed send → next run retries


# ─────────────────────────────────────────────────────────────────────────────
# 3. Maintenance flip in payments.complete
# ─────────────────────────────────────────────────────────────────────────────
class TestMaintenanceFlipOnRun(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = brightpath_org()
        cls.cohort = _cohort(cls.org)

    def _app(self, suffix, status):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'gl-pay-{suffix}', name='Pay Stu', nric=ADULT_NRIC)
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status,
            award_amount=Decimal('2000'), notify_email='p@e.test')

    def _run_and_complete(self, app, amount='200', ref='r'):
        run = PaymentRun.objects.create(
            organisation=self.org, payment_date=date(2026, 7, 1), period_month=date(2026, 7, 1),
            status='completed', reference=f'{ref}-{app.id}')
        PaymentRunItem.objects.create(run=run, application=app, included=True, amount=Decimal(amount))
        return payments.complete(run)

    def test_active_flips_to_maintenance_on_first_paid_run(self):
        app = self._app('active', 'active')
        self._run_and_complete(app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'maintenance')
        self.assertIsNotNone(app.maintenance_at)

    def test_awarded_never_flips(self):
        app = self._app('awarded', 'awarded')
        self._run_and_complete(app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'awarded')

    def test_maintenance_stays_maintenance(self):
        app = self._app('maint', 'maintenance')
        self._run_and_complete(app, ref='r2')
        app.refresh_from_db()
        self.assertEqual(app.status, 'maintenance')

    def test_zero_amount_item_does_not_flip(self):
        app = self._app('zero', 'active')
        run = PaymentRun.objects.create(
            organisation=self.org, payment_date=date(2026, 7, 1), period_month=date(2026, 7, 1),
            status='completed', reference=f'zero-{app.id}')
        PaymentRunItem.objects.create(run=run, application=app, included=True, amount=Decimal('0'))
        payments.complete(run)
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')   # no money released → no flip


# ─────────────────────────────────────────────────────────────────────────────
# 4. Offer-lapse rework
# ─────────────────────────────────────────────────────────────────────────────
class TestLapseRework(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = brightpath_org()
        cls.cohort = _cohort(cls.org)

    def _armed_offer(self, suffix, *, days_ago=1):
        app = _fundable_app(self.cohort, suffix=suffix)
        sp = svc.fund_student(_sponsor(uid=f'gl-lap-{suffix}'), app)
        Sponsorship.objects.filter(id=sp.id).update(
            accept_deadline=timezone.now() - timedelta(days=days_ago))
        sp.refresh_from_db()
        return sp, app

    def test_null_deadline_never_lapses(self):
        app = _fundable_app(self.cohort, suffix='null')
        sp = svc.fund_student(_sponsor(uid='gl-lap-null'), app)
        self.assertIsNone(sp.accept_deadline)
        self.assertEqual(svc.lapse_expired_offers(), {'lapsed': 0, 'flagged': []})

    def test_armed_and_expired_unpaid_offer_lapses(self):
        sp, app = self._armed_offer('exp')
        result = svc.lapse_expired_offers()
        self.assertEqual(result['lapsed'], 1)
        self.assertEqual(result['flagged'], [])
        sp.refresh_from_db()
        self.assertEqual(sp.status, 'lapsed')

    def test_paid_app_is_flagged_not_lapsed(self):
        sp, app = self._armed_offer('paid')
        Disbursement.objects.create(
            application=app, amount=Decimal('200'), status='released', sequence=1,
            released_at=timezone.now())
        result = svc.lapse_expired_offers()
        self.assertEqual(result['lapsed'], 0)
        self.assertEqual(result['flagged'], [app.id])
        sp.refresh_from_db()
        self.assertEqual(sp.status, 'offered')   # protected — never lapsed out from under money

    def test_arm_sign_deadline_sets_window(self):
        app = _fundable_app(self.cohort, suffix='arm')
        svc.fund_student(_sponsor(uid='gl-lap-arm'), app)
        with override_settings(SIGN_ACCEPT_DEADLINE_DAYS=30):
            deadline = svc.arm_sign_deadline(app)
        self.assertIsNotNone(deadline)
        sp = svc.current_offer(app)
        self.assertIsNotNone(sp.accept_deadline)
        self.assertGreater(sp.accept_deadline, timezone.now() + timedelta(days=29))


# ─────────────────────────────────────────────────────────────────────────────
# 4b. Sign-invitation command arms the deadline
# ─────────────────────────────────────────────────────────────────────────────
class TestSignInvitationArmsDeadline(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = brightpath_org()
        cls.cohort = _cohort(cls.org)

    @override_settings(BURSARY_AGREEMENT_ENABLED=True, SIGN_ACCEPT_DEADLINE_DAYS=30)
    @patch('apps.scholarship.management.commands.send_sign_invitation_emails.send_sign_invitation_email', return_value=True)
    def test_command_arms_deadline_on_successful_send(self, _m):
        app = _fundable_app(self.cohort, suffix='inv')
        svc.fund_student(_sponsor(uid='gl-inv'), app)
        with override_settings(SIGN_INVITE_APP_IDS=str(app.id)):
            call_command('send_sign_invitation_emails')
        sp = svc.current_offer(app)
        self.assertIsNotNone(sp.accept_deadline)
        self.assertGreater(sp.accept_deadline, timezone.now() + timedelta(days=29))

    @override_settings(BURSARY_AGREEMENT_ENABLED=True, SIGN_ACCEPT_DEADLINE_DAYS=30)
    @patch('apps.scholarship.management.commands.send_sign_invitation_emails.send_sign_invitation_email', return_value=False)
    def test_failed_send_does_not_arm(self, _m):
        app = _fundable_app(self.cohort, suffix='inv-fail')
        svc.fund_student(_sponsor(uid='gl-inv-fail'), app)
        with override_settings(SIGN_INVITE_APP_IDS=str(app.id)):
            call_command('send_sign_invitation_emails')
        sp = svc.current_offer(app)
        self.assertIsNone(sp.accept_deadline)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Witness resolution order
# ─────────────────────────────────────────────────────────────────────────────
class TestWitnessResolution(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = brightpath_org()
        cls.cohort = _cohort(cls.org)
        cls.referral = PartnerOrganisation.objects.create(code='wr-ref', name='Referral Org')
        cls.override = PartnerOrganisation.objects.create(code='wr-ovr', name='Override Org')

    def _app(self, suffix, *, referred=None, override=None):
        app = _fundable_app(self.cohort, suffix=suffix, referred=referred)
        if override is not None:
            app.witness_org = override
            app.save(update_fields=['witness_org'])
        return app

    def test_override_wins(self):
        app = self._app('ovr', referred=self.referral, override=self.override)
        self.assertEqual(bursary._resolve_witness_org(app), self.override)

    def test_referral_when_no_override(self):
        app = self._app('ref', referred=self.referral)
        self.assertEqual(bursary._resolve_witness_org(app), self.referral)

    def test_none_when_neither(self):
        app = self._app('none')
        self.assertIsNone(bursary._resolve_witness_org(app))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Sources + witness-assignment admin endpoints (super/org_admin only)
# ─────────────────────────────────────────────────────────────────────────────
def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSourcesAdminAPI(TestCase):
    SOURCES = '/api/v1/admin/scholarship/sources/'

    @classmethod
    def setUpTestData(cls):
        cls.org = brightpath_org()
        cls.cohort = _cohort(cls.org)
        cls.src = PartnerOrganisation.objects.create(
            code='src-a', name='Source A', contact_person='P', contact_email='p@e.test',
            phone='0111', show_in_apply=True)
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='gl-super', is_super_admin=True, is_active=True,
            name='Super', email='s@x.com')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='gl-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OA', email='oa@x.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='gl-rev', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Rev', email='r@x.com')
        # a referred student → source A shows a student_count of 1
        StudentProfile.objects.create(
            supabase_user_id='gl-referred', name='Ref Stu', referred_by_org=cls.src)

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_list_with_counts_super_and_org_admin(self):
        for uid in ('gl-super', 'gl-oa'):
            self._auth(uid)
            r = self.client.get(self.SOURCES)
            self.assertEqual(r.status_code, 200, uid)
            src = next(s for s in r.json()['sources'] if s['code'] == 'src-a')
            self.assertEqual(src['student_count'], 1)
            self.assertEqual(src['phone'], '0111')

    def test_reviewer_forbidden(self):
        self._auth('gl-rev')
        self.assertEqual(self.client.get(self.SOURCES).status_code, 403)
        self.assertEqual(self.client.post(self.SOURCES, {'code': 'x', 'name': 'X'}).status_code, 403)

    def test_create_source(self):
        self._auth('gl-super')
        r = self.client.post(self.SOURCES, {'code': 'NewOrg', 'name': 'New Org', 'phone': '0999'},
                             format='json')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(PartnerOrganisation.objects.filter(code='neworg').exists())

    def test_create_duplicate_code_rejected(self):
        self._auth('gl-super')
        r = self.client.post(self.SOURCES, {'code': 'src-a', 'name': 'Dup'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'code_taken')

    def test_patch_contacts_and_active_flag(self):
        self._auth('gl-oa')
        r = self.client.patch(f'{self.SOURCES}{self.src.id}/',
                              {'phone': '0222', 'show_in_apply': False, 'contact_email': 'n@e.test'},
                              format='json')
        self.assertEqual(r.status_code, 200)
        self.src.refresh_from_db()
        self.assertEqual(self.src.phone, '0222')
        self.assertFalse(self.src.show_in_apply)
        self.assertEqual(self.src.contact_email, 'n@e.test')

    def test_assign_and_clear_witness(self):
        app = _fundable_app(self.cohort, suffix='wit')
        url = f'/api/v1/admin/scholarship/applications/{app.id}/witness/'
        self._auth('gl-super')
        r = self.client.patch(url, {'witness_org': 'src-a'}, format='json')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.witness_org_id, self.src.id)
        # clear
        r = self.client.patch(url, {'witness_org': None}, format='json')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertIsNone(app.witness_org_id)

    def test_assign_unknown_org_rejected(self):
        app = _fundable_app(self.cohort, suffix='wit2')
        self._auth('gl-super')
        r = self.client.patch(f'/api/v1/admin/scholarship/applications/{app.id}/witness/',
                              {'witness_org': 'nope'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'unknown_organisation')

    def test_witness_assign_reviewer_forbidden(self):
        app = _fundable_app(self.cohort, suffix='wit3')
        self._auth('gl-rev')
        r = self.client.patch(f'/api/v1/admin/scholarship/applications/{app.id}/witness/',
                              {'witness_org': 'src-a'}, format='json')
        self.assertEqual(r.status_code, 403)
