"""Org-admin wallet credit — the off-platform funding path (P4, 2026-07-26).

Until BrightPath's CLBG is registered, **every** sponsor pays into a personal account and an
org admin keys the credit in here: *"Real money is off the platform, but the consequences
aren't."* So this is the primary funding path, not an accommodation, and it is built with
the controls that implies.

Pinned here: one row per bank transfer with a mandatory external reference; the sign-off
chain REUSED from payments (`draft → admin_signed → [finance_checked] → confirmed`) with the
finance step conditional and live-evaluated; unconfirmed money is unspendable; distinct
signers; and a source guard that ``record_admin_credit`` is the only creator of an
admin-recorded row.
"""
import inspect
from decimal import Decimal

from django.test import TestCase

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, Programme, ScholarshipApplication, ScholarshipCohort, Sponsor,
    SponsorProfile, SponsorProgrammeMembership,
)


def _org(code='credit-org'):
    return PartnerOrganisation.objects.create(code=code, name=code.title())


def _programme(org, code='p-sabah', name='Sabah Bursary'):
    return Programme.objects.create(organisation=org, code=code, name_en=name)


def _sponsor(email='benefactor@example.com', uid='cr-1'):
    return Sponsor.objects.create(supabase_user_id=uid, name='Benefactor', email=email,
                                  status='approved')


def _accept(sponsor, programme):
    return SponsorProgrammeMembership.objects.create(
        sponsor=sponsor, programme=programme, status='approved')


def _finance_admin(org):
    """An ACTIVE finance admin — what arms the conditional checker step."""
    return PartnerAdmin.objects.create(
        supabase_user_id='fin-1', role='finance', is_active=True,
        owning_organisation=org, name='Finance', email='fin@x.com')


class CreditMixin:
    @classmethod
    def setUpTestData(cls):
        cls.org = _org()
        cls.sabah = _programme(cls.org)
        cls.sponsor = _sponsor()
        _accept(cls.sponsor, cls.sabah)

    def _record(self, amount='1000', ref='TRF-20260726-001', by='Poongulali'):
        return svc.record_admin_credit(
            sponsor=self.sponsor, programme=self.sabah, amount=Decimal(amount),
            external_reference=ref, recorded_by=by)


class TestRecordingACredit(CreditMixin, TestCase):
    def test_one_row_per_bank_transfer_carrying_its_reference(self):
        """The owner's model: RM1,000 into the foundation account IS one entry."""
        c1 = self._record('1000', ref='TRF-001')
        c2 = self._record('1000', ref='TRF-002')
        self.assertNotEqual(c1.id, c2.id)
        self.assertEqual(
            sorted(self.sponsor.donations.values_list('external_reference', flat=True)),
            ['TRF-001', 'TRF-002'])

    def test_external_reference_is_mandatory(self):
        """It is the only thread back to money the platform cannot see."""
        for bad in ('', '   ', None):
            with self.assertRaises(svc.CreditError) as ctx:
                svc.record_admin_credit(
                    sponsor=self.sponsor, programme=self.sabah, amount=Decimal('1000'),
                    external_reference=bad, recorded_by='P')
            self.assertEqual(ctx.exception.code, 'external_reference_required')

    def test_amount_must_be_positive(self):
        for bad in (Decimal('0'), Decimal('-5'), None):
            with self.assertRaises(svc.CreditError) as ctx:
                svc.record_admin_credit(
                    sponsor=self.sponsor, programme=self.sabah, amount=bad,
                    external_reference='T-1', recorded_by='P')
            self.assertEqual(ctx.exception.code, 'invalid_amount')

    def test_refuses_a_sponsor_not_accepted_into_the_programme(self):
        other = _programme(self.org, code='p-flagship', name='Flagship')
        with self.assertRaises(svc.CreditError) as ctx:
            svc.record_admin_credit(
                sponsor=self.sponsor, programme=other, amount=Decimal('1000'),
                external_reference='T-1', recorded_by='P')
        self.assertEqual(ctx.exception.code, 'sponsor_not_in_programme')

    def test_a_new_credit_opens_as_draft_and_is_admin_recorded(self):
        c = self._record()
        self.assertEqual(c.status, Donation.STATUS_DRAFT)
        self.assertEqual(c.source, Donation.SOURCE_ADMIN)
        self.assertFalse(c.is_spendable)


class TestUnconfirmedMoneyIsUnspendable(CreditMixin, TestCase):
    def test_draft_credit_does_not_raise_balance(self):
        self._record('10000')
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('0'))

    def test_admin_signed_but_unconfirmed_still_does_not_raise_balance(self):
        c = self._record('10000')
        svc.sign_admin_credit(credit=c, signer='Poongulali')
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('0'))

    def test_only_confirmation_makes_it_spendable(self):
        c = self._record('10000')
        svc.sign_admin_credit(credit=c, signer='Poongulali')
        svc.confirm_admin_credit(credit=c, signer='Suresh')
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('10000'))

    def test_legacy_and_gateway_money_is_confirmed_by_arrival(self):
        """Existing rows must keep reading exactly as before — no balance moves."""
        Donation.objects.create(sponsor=self.sponsor, programme=self.sabah,
                                amount=Decimal('500'))
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('500'))


class TestSignOffChain(CreditMixin, TestCase):
    def test_two_step_chain_while_the_checker_is_dark(self):
        """BrightPath today: maker then approver, no finance admin appointed."""
        c = self._record('10000')
        svc.sign_admin_credit(credit=c, signer='Poongulali')
        svc.confirm_admin_credit(credit=c, signer='Suresh')
        self.assertEqual(c.status, Donation.STATUS_CONFIRMED)
        self.assertEqual(c.recorded_by, 'Poongulali')
        self.assertEqual(c.confirmed_by, 'Suresh')

    def test_appointing_finance_arms_the_check_for_a_credit_already_mid_chain(self):
        """The retroactivity that comes free from live evaluation — the same property
        the payment chain has, inherited rather than reimplemented."""
        c = self._record('10000')
        svc.sign_admin_credit(credit=c, signer='Poongulali')
        _finance_admin(self.org)          # appointed AFTER the maker signed
        with self.assertRaises(svc.CreditError) as ctx:
            svc.confirm_admin_credit(credit=c, signer='Suresh')
        self.assertEqual(ctx.exception.code, 'finance_check_required')

    def test_three_step_chain_once_finance_exists(self):
        _finance_admin(self.org)
        c = self._record('10000')
        svc.sign_admin_credit(credit=c, signer='Poongulali')
        svc.finance_check_admin_credit(credit=c, signer='Sam')
        svc.confirm_admin_credit(credit=c, signer='Suresh')
        self.assertEqual(c.status, Donation.STATUS_CONFIRMED)
        self.assertEqual(c.finance_checked_by, 'Sam')

    def test_revoking_the_last_finance_admin_degrades_gracefully(self):
        fin = _finance_admin(self.org)
        c = self._record('10000')
        svc.sign_admin_credit(credit=c, signer='Poongulali')
        fin.is_active = False
        fin.save(update_fields=['is_active'])
        svc.confirm_admin_credit(credit=c, signer='Suresh')   # no longer blocked
        self.assertEqual(c.status, Donation.STATUS_CONFIRMED)

    def test_signers_must_be_distinct(self):
        c = self._record('10000')
        svc.sign_admin_credit(credit=c, signer='Suresh')
        with self.assertRaises(svc.CreditError) as ctx:
            svc.confirm_admin_credit(credit=c, signer='suresh')   # case-insensitive
        self.assertEqual(ctx.exception.code, 'signer_not_distinct')

    def test_cannot_confirm_a_draft_that_was_never_signed(self):
        c = self._record('10000')
        with self.assertRaises(svc.CreditError) as ctx:
            svc.confirm_admin_credit(credit=c, signer='Suresh')
        self.assertEqual(ctx.exception.code, 'bad_state')

    def test_finance_cannot_check_when_no_finance_admin_exists(self):
        c = self._record('10000')
        svc.sign_admin_credit(credit=c, signer='Poongulali')
        with self.assertRaises(svc.CreditError) as ctx:
            svc.finance_check_admin_credit(credit=c, signer='Sam')
        self.assertEqual(ctx.exception.code, 'finance_check_not_required')


class TestCreditRespectsTheProgrammeWallet(CreditMixin, TestCase):
    def test_a_confirmed_credit_lands_only_in_its_own_programme(self):
        flagship = _programme(self.org, code='p-flagship', name='Flagship')
        _accept(self.sponsor, flagship)
        c = self._record('10000')
        svc.sign_admin_credit(credit=c, signer='P')
        svc.confirm_admin_credit(credit=c, signer='S')
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('10000'))
        self.assertEqual(svc.sponsor_balance(self.sponsor, flagship), Decimal('0'))


class TestOnlyTheServiceMintsAdminCredits(TestCase):
    """Source guard — ``record_admin_credit`` must be the ONLY creator of an admin-recorded
    row. Anything else could mint an unconfirmed credit by a side door, or a confirmed one
    without a bank reference. Same mechanical class as the org-fence completeness map.
    """
    def test_no_other_production_path_creates_an_admin_recorded_donation(self):
        import pathlib
        app_dir = pathlib.Path(svc.__file__).parent
        offenders = []
        for path in app_dir.rglob('*.py'):
            if 'tests' in path.parts or 'migrations' in path.parts:
                continue
            text = path.read_text(encoding='utf-8')
            if 'SOURCE_ADMIN' in text and path.name not in ('models.py', 'sponsorship.py'):
                offenders.append(path.name)
        self.assertEqual(offenders, [], f'Only sponsorship.record_admin_credit may mint an '
                                        f'admin-recorded credit; also found in: {offenders}')

    def test_record_admin_credit_always_opens_at_draft(self):
        source = inspect.getsource(svc.record_admin_credit)
        self.assertIn('STATUS_DRAFT', source,
                      'an admin-recorded credit must open unconfirmed — never spendable on '
                      'a single person keying it in')
