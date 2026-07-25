"""Funds per programme — the sponsor wallet is per (sponsor, programme) (P2, 2026-07-26).

The rule being pinned: **money given to one gift programme is never visible or spendable
in another** (decisions.md, "Restricted funds and sponsor acceptance attach to the
Programme"). A donor gives to "Sabah", not to the platform at large.

Also pinned: the source-guard that stops a spend path silently regressing to a
cross-programme total, and the reconciliation invariant that the backfill moves no money.
"""
import inspect
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import sponsorship as svc
from apps.scholarship import standing_gift
from apps.scholarship.models import (
    Consent, Donation, Programme, ScholarshipApplication, ScholarshipCohort, Sponsor,
    SponsorProfile, Sponsorship,
)


def _org(code='fund-org'):
    return PartnerOrganisation.objects.create(code=code, name=code.title())


def _programme(org, code, name='Gift'):
    return Programme.objects.create(organisation=org, code=code, name_en=name)


def _app(programme, org, award=Decimal('3000'), uid='fund-u1', code='fc-1'):
    """A FUNDABLE application in ``programme`` — mirrors the `_fundable_app` factory in
    test_contract_golive_t1.py: QC-cleared 'recommended', an award amount, an anon-published
    SponsorProfile and an active share consent (all four are `is_fundable`'s conditions)."""
    cohort = ScholarshipCohort.objects.create(
        code=code, name='C', year=2026, owning_organisation=org, programme=programme,
    )
    profile = StudentProfile.objects.create(supabase_user_id=uid, name='S')
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, award_amount=award, status='recommended',
    )
    SponsorProfile.objects.create(application=app, anon_markdown='Determined.',
                                  anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors',
                           version='e', is_active=True)
    return app


def _sponsor(email='funder@example.com'):
    return Sponsor.objects.create(name='Funder', email=email, status='approved')


class TestWalletIsPerProgramme(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _org()
        cls.flagship = _programme(cls.org, 'p-flagship', 'Flagship Bursary')
        cls.sabah = _programme(cls.org, 'p-sabah', 'Sabah Bursary')
        cls.sponsor = _sponsor()

    def test_money_given_to_one_programme_is_invisible_in_the_other(self):
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'),
                                programme=self.sabah)
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('10000'))
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.flagship), Decimal('0'))

    def test_holdings_only_reduce_their_own_programme(self):
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'), programme=self.sabah)
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('5000'), programme=self.flagship)
        app = _app(self.sabah, self.org)
        Sponsorship.objects.create(sponsor=self.sponsor, application=app,
                                   amount=Decimal('3000'), status='offered')
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('7000'))
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.flagship), Decimal('5000'))

    def test_null_programme_is_its_own_bucket_not_a_shared_pool(self):
        """A bare fixture's donation must not silently pool with real programme money."""
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('999'), programme=None)
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'), programme=self.sabah)
        self.assertEqual(svc.sponsor_balance(self.sponsor, None), Decimal('999'))
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('10000'))

    def test_programme_balances_lists_every_wallet(self):
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'), programme=self.sabah)
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('5000'), programme=self.flagship)
        balances = dict(
            (p.code if p else None, bal)
            for p, bal in svc.sponsor_programme_balances(self.sponsor)
        )
        self.assertEqual(balances, {'p-sabah': Decimal('10000'), 'p-flagship': Decimal('5000')})

    def test_available_total_is_the_sum_and_is_display_only(self):
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'), programme=self.sabah)
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('5000'), programme=self.flagship)
        self.assertEqual(svc.sponsor_available_total(self.sponsor), Decimal('15000'))


@override_settings(SPONSOR_POOL_ENABLED=True)
class TestSpendIsProgrammeScoped(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _org()
        cls.flagship = _programme(cls.org, 'p-flagship', 'Flagship Bursary')
        cls.sabah = _programme(cls.org, 'p-sabah', 'Sabah Bursary')
        cls.sponsor = _sponsor()

    def test_cannot_fund_a_student_with_another_programmes_money(self):
        """The headline guarantee: RM10k earmarked for Sabah cannot fund a flagship
        student, even though the sponsor's cross-programme total would cover it."""
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'), programme=self.sabah)
        flagship_app = _app(self.flagship, self.org, award=Decimal('3000'))
        self.assertGreaterEqual(svc.sponsor_available_total(self.sponsor), Decimal('3000'))
        with self.assertRaises(svc.SponsorshipError) as ctx:
            svc.fund_student(self.sponsor, flagship_app)
        self.assertEqual(ctx.exception.code, 'insufficient_balance')

    def test_can_fund_a_student_in_the_programme_the_money_was_given_to(self):
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'), programme=self.sabah)
        sabah_app = _app(self.sabah, self.org, award=Decimal('3000'))
        sp = svc.fund_student(self.sponsor, sabah_app)
        self.assertEqual(sp.status, 'offered')
        self.assertEqual(svc.sponsor_balance(self.sponsor, self.sabah), Decimal('7000'))

    def test_standing_gift_will_not_auto_allocate_across_programmes(self):
        """A standing gift funded in one programme must not reach into another."""
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'), programme=self.sabah)
        standing_gift.StandingGift.objects.create(sponsor=self.sponsor, active=True)
        flagship_app = _app(self.flagship, self.org, award=Decimal('3000'))
        self.assertEqual(list(standing_gift.matching_gifts(flagship_app)), [])
        sabah_app = _app(self.sabah, self.org, award=Decimal('3000'), uid='u-2', code='fc-2')
        self.assertEqual([g.sponsor_id for g in standing_gift.matching_gifts(sabah_app)],
                         [self.sponsor.id])


class TestReconciliation(TestCase):
    def test_backfill_moves_no_money(self):
        """The invariant the prod runbook re-checks: attribution changes, totals do not."""
        org = _org()
        programme = _programme(org, 'p-flagship')
        sponsor = _sponsor()
        Donation.objects.create(sponsor=sponsor, amount=Decimal('1000'))
        Donation.objects.create(sponsor=sponsor, amount=Decimal('2500'))
        before = sum(d.amount for d in Donation.objects.all())

        Donation.objects.filter(programme__isnull=True).update(programme=programme)

        after = sum(d.amount for d in Donation.objects.all())
        self.assertEqual(before, after)
        self.assertEqual(svc.sponsor_balance(sponsor, programme), Decimal('3500'))
        self.assertEqual(Donation.objects.filter(programme__isnull=True).count(), 0)


class TestNoCrossProgrammeSpendAuthority(TestCase):
    """Source guard — a spend decision must never be taken from a cross-programme total.

    ``sponsor_available_total`` sums every wallet, so it is safe for display and wrong for
    authorisation. This asserts the spend paths don't call it, which a future edit could
    otherwise reintroduce silently (the same class of guard as the org-fence static test).
    """
    SPEND_FUNCTIONS = (svc.fund_student, standing_gift.matching_gifts)

    def test_spend_paths_do_not_consult_the_cross_programme_total(self):
        for fn in self.SPEND_FUNCTIONS:
            source = inspect.getsource(fn)
            self.assertNotIn(
                'sponsor_available_total', source,
                f'{fn.__qualname__} must authorise against sponsor_balance(sponsor, '
                f'programme) — a cross-programme total is not spendable anywhere.',
            )
            self.assertIn(
                'sponsor_balance', source,
                f'{fn.__qualname__} should authorise via sponsor_balance.',
            )

    def test_sponsor_balance_requires_an_explicit_programme(self):
        """No default — forgetting the programme must be a TypeError, never a silent
        cross-programme read."""
        sig = inspect.signature(svc.sponsor_balance)
        self.assertEqual(list(sig.parameters), ['sponsor', 'programme'])
        self.assertIs(sig.parameters['programme'].default, inspect.Parameter.empty)
