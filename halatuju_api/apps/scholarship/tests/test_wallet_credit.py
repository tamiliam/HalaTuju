"""Org-admin wallet credit — the off-platform funding path (P4a + P4b, 2026-07-26).

Until BrightPath's CLBG is registered, **every** sponsor pays into a personal account and an
org admin keys the credit in here: *"Real money is off the platform, but the consequences
aren't."* So this is the primary funding path, not an accommodation, and it is built with
the controls that implies.

Pinned here: one row per bank transfer with a mandatory external reference; the sign-off
chain REUSED from payments (`draft → admin_signed → [finance_checked] → confirmed`) with the
finance step conditional and live-evaluated; unconfirmed money is unspendable AND invisible
to the sponsor; the typed-name match and role gates (P4b, closing TD-176); pairwise
distinctness keyed on EMAIL not name; and source guards that `record_admin_credit` is the
only creator of an admin-recorded row and that every sponsor-facing donation read narrows
through `visible_donations`.
"""
import inspect
from decimal import Decimal

from django.test import TestCase

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Donation, Programme, Sponsor, SponsorProgrammeMembership,
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


def _admin(org, role, name, email, uid=None, active=True):
    return PartnerAdmin.objects.create(
        supabase_user_id=uid or f'cr-{email}', role=role, is_active=active,
        owning_organisation=org, name=name, email=email)


class CreditMixin:
    """The live BrightPath cast, with their REAL roles (verified against prod 2026-07-26):
    Poongulali is a plain `admin` — gating the maker on `org_admin` would lock out the
    person who actually does this work."""

    @classmethod
    def setUpTestData(cls):
        cls.org = _org()
        cls.sabah = _programme(cls.org)
        cls.sponsor = _sponsor()
        _accept(cls.sponsor, cls.sabah)
        cls.maker = _admin(cls.org, 'admin', 'Poongulali Veeran', 'kulaly@x.com')
        cls.approver = _admin(cls.org, 'org_admin', 'Suresh Thirugnanam', 'suresh@x.com')

    def _finance(self, name='Sam Finance', email='sam@x.com'):
        """An ACTIVE finance admin — what arms the conditional checker step."""
        return _admin(self.org, 'finance', name, email)

    def _record(self, amount='1000', ref='TRF-20260726-001', admin=None):
        return svc.record_admin_credit(
            sponsor=self.sponsor, programme=self.sabah, amount=Decimal(amount),
            external_reference=ref, admin=admin or self.maker)

    def _sign(self, credit, admin):
        """Sign with the admin's own name typed correctly — the happy path."""
        return svc.sign_admin_credit(credit, admin, admin.name)


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
                    external_reference=bad, admin=self.maker)
            self.assertEqual(ctx.exception.code, 'external_reference_required')

    def test_amount_must_be_positive(self):
        for bad in (Decimal('0'), Decimal('-5'), None):
            with self.assertRaises(svc.CreditError) as ctx:
                svc.record_admin_credit(
                    sponsor=self.sponsor, programme=self.sabah, amount=bad,
                    external_reference='T-1', admin=self.maker)
            self.assertEqual(ctx.exception.code, 'invalid_amount')

    def test_refuses_a_sponsor_not_accepted_into_the_programme(self):
        other = _programme(self.org, code='p-flagship', name='Flagship')
        with self.assertRaises(svc.CreditError) as ctx:
            svc.record_admin_credit(
                sponsor=self.sponsor, programme=other, amount=Decimal('1000'),
                external_reference='T-1', admin=self.maker)
        self.assertEqual(ctx.exception.code, 'sponsor_not_in_programme')

    def test_a_new_credit_opens_as_draft_and_is_admin_recorded(self):
        c = self._record()
        self.assertEqual(c.status, Donation.STATUS_DRAFT)
        self.assertEqual(c.source, Donation.SOURCE_ADMIN)
        self.assertFalse(c.is_spendable)

    def test_recording_stamps_no_signature(self):
        """Recording opens the chain; signing is a separate act with a typed name —
        the same separation payments keeps between create_run and sign."""
        c = self._record()
        self.assertEqual(c.recorded_by, '')
        self.assertEqual(c.recorded_by_email, '')
        self.assertIsNone(c.recorded_at)

    def test_only_the_maker_role_may_record(self):
        """Poongulali is `admin`. An org_admin (the approver) must not open the chain
        they will later countersign."""
        with self.assertRaises(svc.CreditError) as ctx:
            self._record(admin=self.approver)
        self.assertEqual(ctx.exception.code, 'wrong_role')


class TestUnconfirmedMoneyIsUnspendable(CreditMixin, TestCase):
    def test_draft_credit_does_not_raise_balance(self):
        self._record('10000')
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('0'))

    def test_admin_signed_but_unconfirmed_still_does_not_raise_balance(self):
        c = self._record('10000')
        self._sign(c, self.maker)
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('0'))

    def test_only_confirmation_makes_it_spendable(self):
        c = self._record('10000')
        self._sign(c, self.maker)
        self._sign(c, self.approver)
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('10000'))

    def test_legacy_and_gateway_money_is_confirmed_by_arrival(self):
        """Existing rows must keep reading exactly as before — no balance moves."""
        Donation.objects.create(sponsor=self.sponsor, programme=self.sabah,
                                amount=Decimal('500'))
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('500'))


class TestUnconfirmedMoneyIsInvisibleToTheSponsor(CreditMixin, TestCase):
    """P4b — the channel sweep. Unspendable was never enough: a draft credit showing on the
    sponsor's own statement would state that we hold money nobody has signed off."""

    def test_a_draft_credit_is_absent_from_the_giving_statement(self):
        self._record('10000', ref='TRF-DRAFT')
        st = svc.sponsor_statement(self.sponsor)
        self.assertEqual(st['donations'], [])
        self.assertEqual(st['total_in'], '0')

    def test_a_confirmed_credit_appears(self):
        c = self._record('10000', ref='TRF-OK')
        self._sign(c, self.maker)
        self._sign(c, self.approver)
        st = svc.sponsor_statement(self.sponsor)
        self.assertEqual([d['reference'] for d in st['donations']], ['TRF-OK'])
        self.assertEqual(Decimal(st['total_in']), Decimal('10000'))

    def test_a_cancelled_credit_never_appears(self):
        c = self._record('10000', ref='TRF-OOPS')
        svc.cancel_admin_credit(c, self.maker)
        self.assertEqual(svc.sponsor_statement(self.sponsor)['donations'], [])

    def test_a_draft_credit_does_not_conjure_a_wallet(self):
        """An unconfirmed credit must not make an unfunded programme appear in the
        sponsor's wallet list."""
        self._record('10000')
        self.assertEqual(svc.sponsor_programme_balances(self.sponsor), [])


class TestSignOffChain(CreditMixin, TestCase):
    def test_two_step_chain_while_the_checker_is_dark(self):
        """BrightPath today: maker then approver, no finance admin appointed."""
        c = self._record('10000')
        self._sign(c, self.maker)
        self._sign(c, self.approver)
        self.assertEqual(c.status, Donation.STATUS_CONFIRMED)
        self.assertEqual(c.recorded_by, 'Poongulali Veeran')
        self.assertEqual(c.confirmed_by, 'Suresh Thirugnanam')

    def test_appointing_finance_arms_the_check_for_a_credit_already_mid_chain(self):
        """The retroactivity that comes free from live evaluation — the same property
        the payment chain has, inherited rather than reimplemented."""
        c = self._record('10000')
        self._sign(c, self.maker)
        self._finance()                    # appointed AFTER the maker signed
        with self.assertRaises(svc.CreditError) as ctx:
            self._sign(c, self.approver)
        self.assertEqual(ctx.exception.code, 'finance_check_required')

    def test_three_step_chain_once_finance_exists(self):
        fin = self._finance()
        c = self._record('10000')
        self._sign(c, self.maker)
        self._sign(c, fin)
        self._sign(c, self.approver)
        self.assertEqual(c.status, Donation.STATUS_CONFIRMED)
        self.assertEqual(c.finance_checked_by, 'Sam Finance')

    def test_revoking_the_last_finance_admin_degrades_gracefully(self):
        fin = self._finance()
        c = self._record('10000')
        self._sign(c, self.maker)
        fin.is_active = False
        fin.save(update_fields=['is_active'])
        self._sign(c, self.approver)       # no longer blocked
        self.assertEqual(c.status, Donation.STATUS_CONFIRMED)

    def test_cannot_confirm_a_draft_that_was_never_signed(self):
        """The approver's step is not reachable from draft — that IS the maker's step,
        and the approver's role is refused there."""
        c = self._record('10000')
        with self.assertRaises(svc.CreditError) as ctx:
            self._sign(c, self.approver)
        self.assertEqual(ctx.exception.code, 'wrong_role')

    def test_a_confirmed_credit_cannot_be_signed_again(self):
        c = self._record('10000')
        self._sign(c, self.maker)
        self._sign(c, self.approver)
        with self.assertRaises(svc.CreditError) as ctx:
            self._sign(c, self.approver)
        self.assertEqual(ctx.exception.code, 'bad_state')

    def test_finance_cannot_check_when_no_finance_admin_exists(self):
        """With the checker dark the second step belongs to the approver, so a finance
        caller is simply the wrong role there."""
        fin = _admin(self.org, 'finance', 'Ghost', 'ghost@x.com', active=False)
        c = self._record('10000')
        self._sign(c, self.maker)
        with self.assertRaises(svc.CreditError) as ctx:
            self._sign(c, fin)
        self.assertEqual(ctx.exception.code, 'wrong_role')


class TestIdentityGates(CreditMixin, TestCase):
    """P4b — TD-176. Before this, the service took the signer as a free string: it
    enforced that two signatures differed, but not WHOSE they were."""

    def test_typed_name_must_match_the_signers_own_record(self):
        c = self._record('10000')
        with self.assertRaises(svc.CreditError) as ctx:
            svc.sign_admin_credit(c, self.maker, 'Someone Else')
        self.assertEqual(ctx.exception.code, 'name_mismatch')

    def test_typed_name_match_is_case_and_space_insensitive(self):
        c = self._record('10000')
        svc.sign_admin_credit(c, self.maker, '  poongulali veeran ')
        self.assertEqual(c.status, Donation.STATUS_ADMIN_SIGNED)

    def test_an_empty_typed_name_never_matches(self):
        c = self._record('10000')
        with self.assertRaises(svc.CreditError) as ctx:
            svc.sign_admin_credit(c, self.maker, '')
        self.assertEqual(ctx.exception.code, 'name_mismatch')

    def test_a_reviewer_cannot_sign_at_any_step(self):
        rev = _admin(self.org, 'reviewer', 'Rev Iewer', 'rev@x.com')
        c = self._record('10000')
        with self.assertRaises(svc.CreditError) as ctx:
            self._sign(c, rev)
        self.assertEqual(ctx.exception.code, 'wrong_role')

    def test_one_person_cannot_fill_two_slots(self):
        """A super has every role, so pairwise distinctness — not the role gate — is what
        confines them to one signature."""
        boss = _admin(None, 'super', 'The Boss', 'boss@x.com')
        boss.is_super_admin = True
        boss.save()
        c = self._record('10000')
        self._sign(c, boss)
        with self.assertRaises(svc.CreditError) as ctx:
            self._sign(c, boss)
        self.assertEqual(ctx.exception.code, 'same_signer')

    def test_distinctness_keys_on_email_not_on_the_displayed_name(self):
        """Prod carries TWO active admins both named "Ve. Elanjelian" (a super and an
        org_admin, genuinely different accounts). A name-keyed rule would refuse the
        second one; identity is the email."""
        namesake = _admin(self.org, 'org_admin', 'Poongulali Veeran', 'other@x.com')
        c = self._record('10000')
        self._sign(c, self.maker)                       # kulaly@x.com
        self._sign(c, namesake)                         # same NAME, different person
        self.assertEqual(c.status, Donation.STATUS_CONFIRMED)
        self.assertEqual(c.recorded_by_email, 'kulaly@x.com')
        self.assertEqual(c.confirmed_by_email, 'other@x.com')


class TestCancelling(CreditMixin, TestCase):
    def test_a_mis_keyed_draft_can_be_voided(self):
        c = self._record('99999', ref='TRF-TYPO')
        svc.cancel_admin_credit(c, self.maker)
        self.assertEqual(c.status, Donation.STATUS_CANCELLED)
        self.assertFalse(c.is_spendable)

    def test_a_confirmed_credit_cannot_be_cancelled(self):
        """Once money is spendable it is reversed by a compensating entry, never by
        editing history."""
        c = self._record('10000')
        self._sign(c, self.maker)
        self._sign(c, self.approver)
        with self.assertRaises(svc.CreditError) as ctx:
            svc.cancel_admin_credit(c, self.maker)
        self.assertEqual(ctx.exception.code, 'bad_state')

    def test_a_reviewer_cannot_cancel(self):
        rev = _admin(self.org, 'reviewer', 'Rev', 'rev2@x.com')
        c = self._record('10000')
        with self.assertRaises(svc.CreditError) as ctx:
            svc.cancel_admin_credit(c, rev)
        self.assertEqual(ctx.exception.code, 'wrong_role')

    def test_a_cancelled_credit_never_becomes_spendable(self):
        c = self._record('10000')
        svc.cancel_admin_credit(c, self.maker)
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('0'))


class TestCreditRespectsTheProgrammeWallet(CreditMixin, TestCase):
    def test_a_confirmed_credit_lands_only_in_its_own_programme(self):
        flagship = _programme(self.org, code='p-flagship', name='Flagship')
        _accept(self.sponsor, flagship)
        c = self._record('10000')
        self._sign(c, self.maker)
        self._sign(c, self.approver)
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


class TestEverySponsorFacingReadNarrows(TestCase):
    """Source guard, the P3 pattern applied to money instead of students.

    P3's lesson was that fencing the API surface is not fencing the DATA: the same rows
    reach the same audience through several channels. Money has the same shape — the
    statement, the wallet endpoint and the per-programme balance list all read donations.
    This asserts every sponsor-facing read narrows through `visible_donations`, so the
    NEXT such surface fails CI until it does too.
    """

    #: (module, callable-or-region) that a sponsor's own eyes can reach.
    SPONSOR_FACING = [
        ('sponsorship.py', 'sponsor_statement'),
        ('sponsorship.py', 'sponsor_programme_balances'),
    ]

    def test_sponsor_facing_service_reads_go_through_the_seam(self):
        import apps.scholarship.sponsorship as mod
        for _file, fn_name in self.SPONSOR_FACING:
            source = inspect.getsource(getattr(mod, fn_name))
            self.assertNotIn(
                'sponsor.donations', source,
                f'{fn_name} reads donations directly — a draft/cancelled credit would be '
                f'shown to the sponsor as money we hold. Narrow via visible_donations().')

    def test_the_sponsor_wallet_endpoint_goes_through_the_seam(self):
        import pathlib
        import apps.scholarship.views_sponsor as vs
        text = pathlib.Path(vs.__file__).read_text(encoding='utf-8')
        self.assertNotIn(
            'sponsor.donations.all()', text,
            'the sponsor wallet endpoint must list donations via '
            'sponsorship.visible_donations(), not every row regardless of sign-off state')

    def test_the_seam_admits_only_confirmed_money(self):
        source = inspect.getsource(svc.visible_donations)
        self.assertIn('STATUS_CONFIRMED', source)


class TestTheTwoChainsStayOneDesign(TestCase):
    """Currency rule (decisions.md): the wallet-credit chain and the payment-run chain are
    ONE design. This is the mechanical half of that promise — the credit chain must keep
    CALLING the payments module rather than growing a private copy of its rules, so a
    change to the control lands in both or fails here."""

    def test_the_credit_chain_reuses_the_payments_primitives(self):
        source = inspect.getsource(svc.sign_admin_credit)
        for primitive in ('payments._name_matches', 'payments.finance_check_required'):
            self.assertIn(primitive, source,
                          f'{primitive} must be REUSED, not reimplemented — see the '
                          f'currency rule in docs/decisions.md')

    def test_the_credit_chain_uses_the_same_guard_codes(self):
        """Same failures, same names — an operator reading two screens must not have to
        learn two vocabularies for one control."""
        source = inspect.getsource(svc.sign_admin_credit)
        for code in ('bad_state', 'name_mismatch', 'wrong_role', 'same_signer',
                     'finance_check_required'):
            self.assertIn(f"'{code}'", source)
