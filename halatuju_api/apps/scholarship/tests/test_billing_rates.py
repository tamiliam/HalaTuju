"""Billing rates (platform-side) + build hours (org-side).

Owner design 2026-07-27: hours are recorded on the ORG side; the conversion rate and the
per-category margins are PLATFORM-side editable values.

Two properties carry the weight here, and both are about not lying on an invoice:

1. **A missing rate REFUSES.** It never defaults to zero, and never guesses. An unbilled month
   is a visible problem somebody fixes; a month billed at an invented rate is an invoice you
   have to withdraw and explain.
2. **Rates are effective-dated.** Editing the hourly rate today must not retroactively re-price
   a month that has already been billed. Quiet retroactive changes to a bill are exactly what
   destroys trust in one.
"""
from datetime import date
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import platform_cost
from apps.scholarship.models import BillingRate, OrgBuildHours
from rest_framework.test import APIClient

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
RATES_URL = '/api/v1/admin/scholarship/billing/rates/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='bp', name='BrightPath')
        cls.other = PartnerOrganisation.objects.create(code='in', name='Inspire')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')
        cls.org_admin = PartnerAdmin.objects.create(
            supabase_user_id='oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OA', email='oa@x.com')

    def _client(self, uid):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return c

    def _rate(self, category, kind, value, on='2026-07-01'):
        return BillingRate.objects.create(
            category=category, kind=kind, value=Decimal(str(value)),
            effective_from=date.fromisoformat(on))


class TestRateInForce(_Base):
    def test_a_missing_rate_raises_rather_than_defaulting(self):
        """The central guarantee. Nothing may quietly stand in for a rate nobody has set."""
        with self.assertRaises(platform_cost.RateMissing):
            platform_cost.rate_in_force('development', 'hourly_rate', date(2026, 7, 1))

    def test_the_rate_in_force_is_the_one_that_applied_THEN(self):
        """Raise the rate in August; July must still bill at July's rate."""
        self._rate('development', 'hourly_rate', 150, on='2026-06-01')
        self._rate('development', 'hourly_rate', 200, on='2026-08-01')
        self.assertEqual(
            platform_cost.rate_in_force('development', 'hourly_rate', date(2026, 7, 1)),
            Decimal('150.00'))
        self.assertEqual(
            platform_cost.rate_in_force('development', 'hourly_rate', date(2026, 8, 1)),
            Decimal('200.00'))

    def test_a_rate_starting_later_does_not_apply_earlier(self):
        self._rate('development', 'hourly_rate', 150, on='2026-08-01')
        with self.assertRaises(platform_cost.RateMissing):
            platform_cost.rate_in_force('development', 'hourly_rate', date(2026, 7, 1))


class TestDevelopmentCharge(_Base):
    def _hours(self, hours, month='2026-07', org=None):
        return OrgBuildHours.objects.create(
            organisation=org or self.org, period_month=month,
            module='Programme layer', hours=Decimal(str(hours)),
            basis='70 working days of commits, owner-set at 4h/day')

    def test_hours_times_rate_plus_margin(self):
        self._rate('development', 'hourly_rate', 150)
        self._rate('development', 'margin_pct', 50)
        self._hours(10)
        c = platform_cost.development_charge(self.org, '2026-07')
        self.assertEqual(c['hours'], Decimal('10.0'))
        self.assertEqual(c['subtotal_myr'], Decimal('1500.00'))
        self.assertEqual(c['charge_myr'], Decimal('2250.00'))     # +50%
        self.assertEqual(c['rate_myr'], Decimal('150.00'))

    def test_no_rate_blocks_the_charge_it_does_not_zero_it(self):
        """Hours exist, rates do not. The charge must REFUSE — a silent RM0.00 would read as
        'this month was free', which is a different and false statement."""
        self._hours(10)
        with self.assertRaises(platform_cost.RateMissing):
            platform_cost.development_charge(self.org, '2026-07')

    def test_no_hours_is_a_genuine_zero_and_needs_no_rate(self):
        """Distinct from the case above: nothing was built, so nothing is owed. That is a real
        zero and must not require a rate to express."""
        c = platform_cost.development_charge(self.org, '2026-07')
        self.assertEqual(c['charge_myr'], Decimal('0.00'))
        self.assertEqual(c['lines'], [])

    def test_hours_are_scoped_to_the_organisation(self):
        self._rate('development', 'hourly_rate', 100)
        self._rate('development', 'margin_pct', 0)
        self._hours(10, org=self.org)
        self._hours(99, org=self.other)
        self.assertEqual(
            platform_cost.development_charge(self.org, '2026-07')['hours'], Decimal('10.0'))

    def test_the_charge_shows_its_working(self):
        """A tenant is entitled to see how a figure was reached, including the reconstruction
        behind the hours — there is no time tracker, so the basis IS the evidence."""
        self._rate('development', 'hourly_rate', 100)
        self._rate('development', 'margin_pct', 15)
        self._hours(8)
        c = platform_cost.development_charge(self.org, '2026-07')
        self.assertEqual(c['margin_pct'], Decimal('15.00'))
        self.assertEqual(len(c['lines']), 1)
        self.assertIn('working days', c['lines'][0]['basis'])


class TestApplyMargin(_Base):
    def test_infrastructure_margin_applies_to_a_cost(self):
        self._rate('infrastructure', 'margin_pct', 15)
        self.assertEqual(
            platform_cost.apply_margin(Decimal('190.71'), 'infrastructure', '2026-07'),
            Decimal('219.32'))

    def test_a_missing_category_margin_refuses(self):
        with self.assertRaises(platform_cost.RateMissing):
            platform_cost.apply_margin(Decimal('100.00'), 'metered', '2026-07')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestRatesEndpoint(_Base):
    def test_super_can_read_and_set(self):
        r = self._client('super-uid').post(RATES_URL, {
            'category': 'development', 'kind': 'hourly_rate', 'value': '150',
            'effective_from': '2026-07-01'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self._client('super-uid').get(RATES_URL).status_code, 200)

    def test_org_admin_is_FORBIDDEN_not_404(self):
        """Deliberately different from the dark usage screen. There is nothing to hide about
        this route existing — only about its contents. The margin applied to a tenant is a
        commercial disclosure they must not read, let alone set."""
        self.assertEqual(self._client('oa').get(RATES_URL).status_code, 403)
        self.assertEqual(self._client('oa').post(RATES_URL, {
            'category': 'development', 'kind': 'hourly_rate', 'value': '1'},
            format='json').status_code, 403)

    def test_setting_a_new_value_adds_a_ROW_and_keeps_the_old_one(self):
        """History is the audit trail: an old rate is never overwritten, so a past month can
        always be re-derived exactly as it was billed."""
        c = self._client('super-uid')
        c.post(RATES_URL, {'category': 'development', 'kind': 'hourly_rate',
                           'value': '150', 'effective_from': '2026-06-01'}, format='json')
        c.post(RATES_URL, {'category': 'development', 'kind': 'hourly_rate',
                           'value': '200', 'effective_from': '2026-08-01'}, format='json')
        self.assertEqual(BillingRate.objects.filter(
            category='development', kind='hourly_rate').count(), 2)

    def test_a_negative_value_is_refused(self):
        """Almost certainly a typo, and it would silently produce a credit note."""
        r = self._client('super-uid').post(RATES_URL, {
            'category': 'development', 'kind': 'margin_pct', 'value': '-10'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'negative_value')

    def test_bad_category_and_kind_are_refused(self):
        c = self._client('super-uid')
        self.assertEqual(c.post(RATES_URL, {'category': 'nope', 'kind': 'margin_pct',
                                            'value': '1'}, format='json').status_code, 400)
        self.assertEqual(c.post(RATES_URL, {'category': 'development', 'kind': 'nope',
                                            'value': '1'}, format='json').status_code, 400)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestBuildHoursEndpoint(_Base):
    def _url(self, org):
        return f'/api/v1/admin/scholarship/billing/hours/{org.id}/'

    def test_basis_is_REQUIRED(self):
        """The model exists to keep the reconstruction attached to the number. Without it an
        hours figure is unauditable, and this endpoint is the only place that can insist."""
        r = self._client('super-uid').post(self._url(self.org), {
            'period_month': '2026-07', 'module': 'Payments', 'hours': '10'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'basis_required')

    def test_super_records_hours(self):
        r = self._client('super-uid').post(self._url(self.org), {
            'period_month': '2026-07', 'module': 'Payments', 'hours': '10',
            'basis': '3 sprints, owner-estimated'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(OrgBuildHours.objects.count(), 1)

    def test_org_admin_may_NOT_record_its_own_hours(self):
        """A tenant recording what it will be billed for is not a control anyone would accept."""
        r = self._client('oa').post(self._url(self.org), {
            'period_month': '2026-07', 'module': 'X', 'hours': '1', 'basis': 'y'},
            format='json')
        self.assertEqual(r.status_code, 403)

    def test_org_admin_reads_its_own_hours(self):
        OrgBuildHours.objects.create(organisation=self.org, period_month='2026-07',
                                     module='Payments', hours=Decimal('10.0'), basis='b')
        r = self._client('oa').get(self._url(self.org))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['lines']), 1)

    def test_another_orgs_hours_are_404_not_403(self):
        """Consistent with every other org-fenced surface: no existence signal."""
        self.assertEqual(self._client('oa').get(self._url(self.other)).status_code, 404)

    def test_a_missing_rate_is_reported_not_rendered_as_zero(self):
        """The endpoint must say WHY there is no charge, so nobody reads a blank as 'free'."""
        OrgBuildHours.objects.create(organisation=self.org, period_month='2026-07',
                                     module='Payments', hours=Decimal('10.0'), basis='b')
        body = self._client('super-uid').get(self._url(self.org) + '?month=2026-07').json()
        self.assertIsNone(body['charge'])
        self.assertIn('No hourly_rate in force', body['charge_blocked'])
