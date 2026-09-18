"""TD-258 — the three holes on the sponsor money path, closed and pinned.

The finding (code health H3, 2026-09-18) was that a sponsor's FUND endpoint read the
application by bare id, so the endpoint answered three DIFFERENT things about any
application id on the platform — `not_found` / `not_fundable` / `insufficient_balance` —
which is an existence-and-state oracle across every tenant and every gift. Alongside it,
a **mock** donation endpoint was live in production (self-minted, programme-less,
CONFIRMED balance) and the NULL-programme bucket that mock credits was spendable on any
application whose own programme was NULL.

What is pinned here:

1. **The fund view resolves through the fence.** Everything the sponsor may not SEE is
   ONE answer — 404 `not_found` — whether the id does not exist, belongs to a gift they
   were never accepted into, or exists but is not in the pool at all. Distinctions
   survive only INSIDE what they can already see (`insufficient_balance` on a visible
   card is useful and leaks nothing).
2. **The mock donation endpoint is gated OFF.** With the flag off it answers exactly like
   a route that is not there for this caller — 404 `pool_not_available`, the body the
   pool gate already uses for a hidden feature — and writes nothing.
3. **A NULL-programme application can never be funded.** The NULL bucket exists so bare
   fixtures self-partition (see `sponsorship.sponsor_balance`); it must never be a wallet
   anything can be bought with.
"""
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, Programme, ScholarshipApplication, ScholarshipCohort, Sponsor,
    SponsorProfile, SponsorProgrammeMembership, Sponsorship,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'

#: An id no row can hold — the "no such application" arm of the three-way comparison.
MISSING_APPLICATION_ID = 99_999_999


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
                       'email': 'funder@example.com', 'is_anonymous': False},
                      TEST_JWT_SECRET, algorithm='HS256')


def _pool_app(programme, org, *, code, uid, award=Decimal('3000'), published=True):
    """An application in ``programme``. With ``published`` it is fully pool-eligible and
    fundable (QC-cleared 'recommended' + award amount + anon-published profile + active
    share consent); without it, it is a real row that is simply not in the pool."""
    cohort = ScholarshipCohort.objects.create(
        code=code, name='Intake', year=2026, owning_organisation=org, programme=programme)
    profile = StudentProfile.objects.create(supabase_user_id=uid, name='Pooled Student')
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, award_amount=award, status='recommended')
    SponsorProfile.objects.create(application=app, anon_markdown='Determined.',
                                  anon_published=published)
    Consent.objects.create(application=app, consent_type='share_with_sponsors',
                           version='e', is_active=True)
    return app


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SPONSOR_POOL_ENABLED=True)
class TestFundGoesThroughTheFence(TestCase):
    """ONE ANSWER for everything outside the sponsor's own visible pool."""

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='td258-org', name='TD258 Org')
        cls.mine = Programme.objects.create(
            organisation=cls.org, code='td258-mine', name_en='Accepted Gift')
        cls.theirs = Programme.objects.create(
            organisation=cls.org, code='td258-theirs', name_en='Other Gift')
        cls.sponsor = Sponsor.objects.create(
            supabase_user_id='td258-spon', name='Funder', email='funder@example.com',
            phone='0123', source='friend', consent_at=timezone.now(), status='approved')
        # Accepted into ONE gift only — the whole point of the fence.
        SponsorProgrammeMembership.objects.create(
            sponsor=cls.sponsor, programme=cls.mine, status='approved')

        cls.visible = _pool_app(cls.mine, cls.org, code='td258-a', uid='td258-s1')
        # A real, fundable student in a gift this sponsor was never accepted into.
        cls.other_gift = _pool_app(cls.theirs, cls.org, code='td258-b', uid='td258-s2')
        # A real row in the sponsor's OWN gift that is simply not in the pool.
        cls.not_in_pool = _pool_app(cls.mine, cls.org, code='td258-c', uid='td258-s3',
                                    published=False)

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("td258-spon")}')

    def _fund(self, application_id):
        return self.client.post(f'/api/v1/sponsor/pool/{application_id}/fund/', {},
                                format='json')

    def test_outside_the_visible_pool_is_always_the_same_answer(self):
        """No row · another gift's row · a row that is not pooled → indistinguishable."""
        missing = self._fund(MISSING_APPLICATION_ID)
        other_gift = self._fund(self.other_gift.id)
        not_in_pool = self._fund(self.not_in_pool.id)

        # Equal TO EACH OTHER first — that is the property being bought, and it holds
        # even if the shared answer is later reworded.
        self.assertEqual(missing.status_code, other_gift.status_code)
        self.assertEqual(missing.status_code, not_in_pool.status_code)
        self.assertEqual(missing.json(), other_gift.json())
        self.assertEqual(missing.json(), not_in_pool.json())
        # …and the shared answer is the fence's own 404, never a 400 that admits a row.
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json(), {'error': 'not_found'})
        # Nothing was allocated against any of them.
        self.assertEqual(Sponsorship.objects.count(), 0)

    def test_a_visible_card_they_cannot_afford_still_says_insufficient_balance(self):
        """A distinction INSIDE the visible pool is legitimate and useful: the sponsor can
        already see this card, so the only news is about their own wallet."""
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('100'),
                                programme=self.mine)
        r = self._fund(self.visible.id)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {'error': 'insufficient_balance'})
        self.assertEqual(Sponsorship.objects.count(), 0)

    def test_the_happy_path_still_funds(self):
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('5000'),
                                programme=self.mine)
        r = self._fund(self.visible.id)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['status'], 'offered')
        self.visible.refresh_from_db()
        self.assertEqual(self.visible.status, 'awarded')
        self.assertEqual(
            Sponsorship.objects.filter(sponsor=self.sponsor,
                                       application=self.visible).count(), 1)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SPONSOR_POOL_ENABLED=True)
class TestMockDonationIsGatedOff(TestCase):
    """The mock mints money. It must be invisible unless somebody switched it on."""

    @classmethod
    def setUpTestData(cls):
        cls.sponsor = Sponsor.objects.create(
            supabase_user_id='td258-donor', name='Donor', email='funder@example.com',
            phone='0123', source='friend', consent_at=timezone.now(), status='approved')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("td258-donor")}')

    def _donate(self):
        return self.client.post('/api/v1/sponsor/wallet/donate/', {'amount': '5000'},
                                format='json')

    @override_settings(SPONSOR_MOCK_DONATIONS_ENABLED=False)
    def test_flag_off_answers_like_a_route_that_is_not_there_and_writes_nothing(self):
        r = self._donate()
        self.assertEqual(r.status_code, 404)
        # The SAME body the pool gate uses for a feature that is switched off — saying
        # 'mock_disabled' would advertise that a money-minting route exists.
        self.assertEqual(r.json(), {'error': 'pool_not_available'})
        self.assertEqual(Donation.objects.count(), 0)

    def test_the_flag_is_off_by_default(self):
        """Not merely off in this test — off in the shipped settings."""
        from django.conf import settings
        self.assertFalse(getattr(settings, 'SPONSOR_MOCK_DONATIONS_ENABLED', False))

    @override_settings(SPONSOR_MOCK_DONATIONS_ENABLED=True)
    def test_flag_on_behaves_exactly_as_before(self):
        r = self._donate()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Decimal(r.json()['balance']), Decimal('5000'))
        self.assertEqual(Donation.objects.filter(sponsor=self.sponsor).count(), 1)


class TestNullProgrammeIsNeverSpendable(TestCase):
    """The back door TD-258 named: a mock credit lands in the NULL bucket, and an
    application whose own programme is NULL would have matched it exactly."""

    @classmethod
    def setUpTestData(cls):
        # A BARE cohort — no organisation, no programme — so the application's derived
        # `programme` is NULL, exactly like the fixtures the NULL bucket exists for.
        cls.cohort = ScholarshipCohort.objects.create(code='td258-bare', name='Bare',
                                                      year=2026)
        cls.sponsor = Sponsor.objects.create(
            supabase_user_id='td258-null', name='Donor', email='null@example.com',
            status='approved')

    def _bare_app(self, uid):
        profile = StudentProfile.objects.create(supabase_user_id=uid, name='Bare Student')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, award_amount=Decimal('3000'),
            status='recommended')
        SponsorProfile.objects.create(application=app, anon_markdown='Determined.',
                                      anon_published=True)
        Consent.objects.create(application=app, consent_type='share_with_sponsors',
                               version='e', is_active=True)
        return app

    def test_a_confirmed_null_programme_credit_cannot_buy_a_null_programme_student(self):
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('5000'),
                                programme=None)
        app = self._bare_app('td258-bare-1')
        self.assertIsNone(app.programme_id)
        # The arithmetic alone would have allowed this: the NULL wallet covers the award.
        self.assertGreaterEqual(svc.sponsor_balance(self.sponsor, None), app.award_amount)

        with self.assertRaises(svc.SponsorshipError) as ctx:
            svc.fund_student(self.sponsor, app)
        self.assertEqual(ctx.exception.code, 'programme_required')

        self.assertEqual(Sponsorship.objects.count(), 0)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')   # never left the pool

    def test_the_named_award_entry_point_is_refused_too(self):
        """`award_and_notify` is what the Support button and the admin batch call — the
        refusal must live at the choke point both go through, not at one caller."""
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('5000'),
                                programme=None)
        app = self._bare_app('td258-bare-2')
        with self.assertRaises(svc.SponsorshipError) as ctx:
            svc.award_and_notify(self.sponsor, app)
        self.assertEqual(ctx.exception.code, 'programme_required')
        self.assertEqual(Sponsorship.objects.count(), 0)
