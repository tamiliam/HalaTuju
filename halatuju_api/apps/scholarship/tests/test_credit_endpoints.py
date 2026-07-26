"""Wallet-credit admin endpoints — P4b (2026-07-26).

The HTTP surface that finally lets the named people drive the P4a chain themselves. Before
this, every wallet credit — including the RM172,000 already on prod — was written by a
developer touching the database, which made the sign-off chain a control on paper.

Mirrors test_payment_endpoints.py's access-control style: reviewer/qc are refused (403), a
cross-org credit is 404 (no existence leak), admin/org_admin/super pass. Plus the credit
lifecycle over the wire (record → maker sign → approver countersign → spendable), and the
fence that matters most here — an admin cannot credit a wallet inside another tenant's gift.
"""
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Donation, Programme, Sponsor, SponsorProgrammeMembership,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
_CREDITS = '/api/v1/admin/scholarship/credits/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = PartnerOrganisation.objects.create(code='ce-a', name='Org A')
        cls.org_b = PartnerOrganisation.objects.create(code='ce-b', name='Org B')
        cls.prog_a = Programme.objects.create(
            organisation=cls.org_a, code='ce-pa', name_en='A Bursary')
        cls.prog_b = Programme.objects.create(
            organisation=cls.org_b, code='ce-pb', name_en='B Bursary')

        # A sponsor is a PLATFORM-level account — deliberately not org-fenced — and may hold
        # a membership in more than one organisation's gift. That is exactly why the fence
        # has to live on the programme.
        cls.sponsor = Sponsor.objects.create(
            supabase_user_id='ce-sp', name='Benefactor', email='ben@x.com', status='approved')
        for prog in (cls.prog_a, cls.prog_b):
            SponsorProgrammeMembership.objects.create(
                sponsor=cls.sponsor, programme=prog, status='approved')

        def admin(uid, role, name, email, org, super_flag=False, active=True):
            return PartnerAdmin.objects.create(
                supabase_user_id=uid, role=role, is_active=active, owning_organisation=org,
                name=name, email=email, is_super_admin=super_flag)

        cls.maker = admin('ce-mk', 'admin', 'Maker One', 'maker@x.com', cls.org_a)
        cls.approver = admin('ce-ap', 'org_admin', 'Approver One', 'appr@x.com', cls.org_a)
        cls.reviewer = admin('ce-rv', 'reviewer', 'Rev', 'rev@x.com', cls.org_a)
        cls.qc = admin('ce-qc', 'qc', 'Qc', 'qc@x.com', cls.org_a)
        # DORMANT by default — prod has ZERO active finance admins, so the live chain is
        # two-step. Tests that need the third step arm it explicitly via `_arm_finance()`;
        # leaving it active here would silently make every chain test three-step and hide
        # the path BrightPath actually runs.
        cls.finance = admin('ce-fi', 'finance', 'Fin', 'fin@x.com', cls.org_a, active=False)
        cls.b_maker = admin('ce-bmk', 'admin', 'B Maker', 'bmaker@x.com', cls.org_b)
        cls.boss = admin('ce-su', 'super', 'The Boss', 'boss@x.com', None, super_flag=True)

    def _arm_finance(self):
        self.finance.is_active = True
        self.finance.save(update_fields=['is_active'])
        return self.finance

    def client_for(self, admin):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(admin.supabase_user_id)}')
        return c

    def _draft(self, org_programme=None, amount='1000', ref='TRF-001', admin=None):
        """A draft credit created through the SERVICE (the endpoint path is tested
        separately) so lifecycle tests start from a known state."""
        return svc.record_admin_credit(
            sponsor=self.sponsor, programme=org_programme or self.prog_a,
            amount=Decimal(amount), external_reference=ref, admin=admin or self.maker)


class TestRoleGate(_Base):
    def test_reviewer_and_qc_are_refused(self):
        for who in (self.reviewer, self.qc):
            self.assertEqual(self.client_for(who).get(_CREDITS).status_code, 403)

    def test_admin_org_admin_finance_and_super_may_read(self):
        self._arm_finance()   # finance can only read once it is an active appointment
        for who in (self.maker, self.approver, self.finance, self.boss):
            self.assertEqual(self.client_for(who).get(_CREDITS).status_code, 200)

    def test_anonymous_is_refused(self):
        self.assertIn(APIClient().get(_CREDITS).status_code, (401, 403))


class TestOrgFence(_Base):
    def test_the_list_shows_only_this_organisations_credits(self):
        self._draft(self.prog_a, ref='TRF-A')
        svc.record_admin_credit(sponsor=self.sponsor, programme=self.prog_b,
                                amount=Decimal('500'), external_reference='TRF-B',
                                admin=self.b_maker)
        body = self.client_for(self.maker).get(_CREDITS).json()
        self.assertEqual([c['external_reference'] for c in body['credits']], ['TRF-A'])

    def test_a_super_sees_every_organisation(self):
        self._draft(self.prog_a, ref='TRF-A')
        svc.record_admin_credit(sponsor=self.sponsor, programme=self.prog_b,
                                amount=Decimal('500'), external_reference='TRF-B',
                                admin=self.b_maker)
        body = self.client_for(self.boss).get(_CREDITS).json()
        self.assertEqual(sorted(c['external_reference'] for c in body['credits']),
                         ['TRF-A', 'TRF-B'])

    def test_signing_another_tenants_credit_is_404_not_403(self):
        """404, never 403 — a 403 would confirm the row exists."""
        other = svc.record_admin_credit(
            sponsor=self.sponsor, programme=self.prog_b, amount=Decimal('500'),
            external_reference='TRF-B', admin=self.b_maker)
        r = self.client_for(self.maker).post(
            f'{_CREDITS}{other.id}/sign/', {'typed_name': 'Maker One'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_cannot_record_a_credit_into_another_tenants_programme(self):
        """The sponsor is legitimately a member of BOTH gifts, so only the programme
        fence stops org A crediting org B's wallet."""
        r = self.client_for(self.maker).post(_CREDITS, {
            'sponsor_id': self.sponsor.id, 'programme_id': self.prog_b.id,
            'amount': '1000', 'external_reference': 'TRF-X'}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Donation.objects.filter(external_reference='TRF-X').exists())


class TestRecordEndpoint(_Base):
    def test_records_a_draft_carrying_its_bank_reference(self):
        r = self.client_for(self.maker).post(_CREDITS, {
            'sponsor_id': self.sponsor.id, 'programme_id': self.prog_a.id,
            'amount': '10000', 'external_reference': 'TRF-20260726-001'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['status'], Donation.STATUS_DRAFT)
        self.assertEqual(r.json()['external_reference'], 'TRF-20260726-001')
        self.assertFalse(r.json()['is_spendable'])

    def test_the_approver_cannot_open_the_chain_they_will_countersign(self):
        r = self.client_for(self.approver).post(_CREDITS, {
            'sponsor_id': self.sponsor.id, 'programme_id': self.prog_a.id,
            'amount': '10000', 'external_reference': 'TRF-1'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'wrong_role')

    def test_a_missing_bank_reference_is_refused(self):
        r = self.client_for(self.maker).post(_CREDITS, {
            'sponsor_id': self.sponsor.id, 'programme_id': self.prog_a.id,
            'amount': '10000', 'external_reference': '  '}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'external_reference_required')

    def test_a_non_numeric_amount_is_refused_cleanly(self):
        r = self.client_for(self.maker).post(_CREDITS, {
            'sponsor_id': self.sponsor.id, 'programme_id': self.prog_a.id,
            'amount': 'ten thousand', 'external_reference': 'TRF-1'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'invalid_amount')

    def test_an_unknown_sponsor_is_404(self):
        r = self.client_for(self.maker).post(_CREDITS, {
            'sponsor_id': 999999, 'programme_id': self.prog_a.id,
            'amount': '10000', 'external_reference': 'TRF-1'}, format='json')
        self.assertEqual(r.status_code, 404)


class TestSignEndpoint(_Base):
    def test_the_full_two_step_chain_over_the_wire(self):
        c = self._draft(amount='10000')
        r1 = self.client_for(self.maker).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Maker One'}, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()['status'], Donation.STATUS_ADMIN_SIGNED)
        self.assertFalse(r1.json()['is_spendable'])

        r2 = self.client_for(self.approver).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Approver One'}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], Donation.STATUS_CONFIRMED)
        self.assertTrue(r2.json()['is_spendable'])
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.prog_a), Decimal('10000'))

    def test_a_wrong_typed_name_is_refused(self):
        c = self._draft()
        r = self.client_for(self.maker).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Somebody Else'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'name_mismatch')

    def test_the_maker_cannot_also_countersign(self):
        c = self._draft()
        self.client_for(self.maker).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Maker One'}, format='json')
        r = self.client_for(self.maker).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Maker One'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'wrong_role')
        c.refresh_from_db()
        self.assertEqual(c.status, Donation.STATUS_ADMIN_SIGNED)

    def test_an_org_admin_is_told_why_when_the_finance_check_is_armed(self):
        """Not a bare wrong_role — from the approver's seat nothing looks amiss."""
        c = self._draft()
        self.client_for(self.maker).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Maker One'}, format='json')
        self._arm_finance()          # appointed AFTER the maker signed — arms retroactively
        r = self.client_for(self.approver).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Approver One'}, format='json')
        self.assertEqual(r.json()['code'], 'finance_check_required')

    def test_the_three_step_chain_when_finance_is_appointed(self):
        self._arm_finance()
        c = self._draft(amount='10000')
        self.client_for(self.maker).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Maker One'}, format='json')
        rf = self.client_for(self.finance).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Fin'}, format='json')
        self.assertEqual(rf.json()['status'], Donation.STATUS_FINANCE_CHECKED)
        ra = self.client_for(self.approver).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Approver One'}, format='json')
        self.assertEqual(ra.json()['status'], Donation.STATUS_CONFIRMED)


class TestCancelEndpoint(_Base):
    def test_a_mis_keyed_draft_can_be_voided(self):
        c = self._draft(amount='99999', ref='TRF-TYPO')
        r = self.client_for(self.maker).post(f'{_CREDITS}{c.id}/cancel/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], Donation.STATUS_CANCELLED)

    def test_a_confirmed_credit_cannot_be_cancelled(self):
        c = self._draft(amount='10000')
        self.client_for(self.maker).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Maker One'}, format='json')
        self.client_for(self.approver).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Approver One'}, format='json')
        r = self.client_for(self.maker).post(f'{_CREDITS}{c.id}/cancel/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_state')

    def test_cancelling_another_tenants_credit_is_404(self):
        other = svc.record_admin_credit(
            sponsor=self.sponsor, programme=self.prog_b, amount=Decimal('500'),
            external_reference='TRF-B', admin=self.b_maker)
        r = self.client_for(self.maker).post(
            f'{_CREDITS}{other.id}/cancel/', {}, format='json')
        self.assertEqual(r.status_code, 404)


class TestPayloadIsAnAllowlist(_Base):
    def test_the_credit_payload_has_an_exact_key_set(self):
        """A snapshot, so adding a column to Donation cannot silently surface it on an
        admin screen — the same discipline the sponsor allowlists carry."""
        c = self._draft()
        body = self.client_for(self.maker).get(_CREDITS).json()['credits'][0]
        self.assertEqual(set(body), {
            'id', 'sponsor_id', 'sponsor_name', 'programme_id', 'programme_name',
            'amount', 'source', 'external_reference', 'status', 'is_spendable',
            'recorded_by', 'recorded_at', 'finance_checked_by', 'finance_checked_at',
            'confirmed_by', 'confirmed_at', 'created_at',
        })

    def test_signer_emails_are_not_exposed(self):
        """The email is the identity KEY, not display data — the name is what an operator
        needs to see on a sign-off card."""
        c = self._draft()
        self.client_for(self.maker).post(
            f'{_CREDITS}{c.id}/sign/', {'typed_name': 'Maker One'}, format='json')
        body = self.client_for(self.maker).get(_CREDITS).json()['credits'][0]
        self.assertNotIn('recorded_by_email', body)
        self.assertEqual(body['recorded_by'], 'Maker One')
