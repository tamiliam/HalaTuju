"""TD-334 (2026-10-05): a super with NO organisation must name a gift on the money reads.

TD-246 closed on the WEB gift gate: Payments and Spending draw nothing until one gift is chosen.
The server did not refuse the request the gate never sends — a super with no organisation of
their own who named no `?programme=` read every organisation pooled. Now that request is
`400 programme_required` on the run list, the funding summary and the Spending screen (read and
correction, through `_spending_admin`, the one door).

Pinned beside it: who keeps exactly what they read before — a super WITH an organisation, an
organisation's own `org_admin`, and the org-less super once a gift is named (any organisation's).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.scholarship.models import PaymentRun
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)

RUNS = 'scholarship/payment-runs/'
FUNDING = 'scholarship/payments/funding-summary/'
SPENDING = 'scholarship/spending/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestAnOrglessSuperNamesAGift(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.orgs, cls.gifts = {}, {}
        for tag in ('a', 'b'):
            org = make_org()
            gift = make_programme(organisation=org, code=f'td334-{tag}')
            make_application('awarded', cohort=make_cohort(programme=gift, owning_organisation=org),
                             award_amount=Decimal('2000'))
            PaymentRun.objects.create(organisation=org, programme=gift, reference=f'PR-TD334-{tag}',
                                      payment_date=date(2026, 8, 1), period_month=date(2026, 8, 1))
            cls.orgs[tag], cls.gifts[tag] = org, gift
        cls.platform = make_admin('super', super_admin=True)          # no organisation
        cls.org_super = make_admin('super', super_admin=True, owning_org=cls.orgs['a'])
        cls.org_admin = make_admin('org_admin', owning_org=cls.orgs['a'])

    def _get(self, admin, path, q=''):
        return authed_client(admin).get(f'/api/v1/admin/{path}{q}')

    def test_no_gift_is_programme_required_on_all_three_reads(self):
        for path in (RUNS, FUNDING, SPENDING):
            with self.subTest(path=path):
                r = self._get(self.platform, path)
                self.assertEqual(r.status_code, 400, r.content[:200])
                self.assertEqual(r.json()['code'], 'programme_required')

    def test_the_spending_correction_takes_the_same_door(self):
        r = authed_client(self.platform).post(
            f'/api/v1/admin/{SPENDING}category/', {'merchant': 'A SHOP', 'category': 'food'},
            format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'programme_required'))

    def test_naming_any_organisations_gift_still_opens_it(self):
        for tag in ('a', 'b'):
            q = f'?programme={self.gifts[tag].code}'
            runs = self._get(self.platform, RUNS, q).json()['runs']
            self.assertEqual([r['reference'] for r in runs], [f'PR-TD334-{tag}'])
            self.assertEqual(self._get(self.platform, FUNDING, q).json()['totals']['students'], 1)
            self.assertEqual(self._get(self.platform, SPENDING, q).status_code, 200)

    def test_an_unknown_gift_is_still_404_not_400(self):
        for path in (RUNS, FUNDING, SPENDING):
            with self.subTest(path=path):
                self.assertEqual(self._get(self.platform, path, '?programme=nope').status_code, 404)

    def test_a_super_with_an_organisation_reads_as_before(self):
        # Unchanged by TD-334: the run list and Spending keep the platform reading a super has
        # always had (decisions.md 2026-09-11); the funding summary keeps the super's own org.
        runs = self._get(self.org_super, RUNS).json()['runs']
        self.assertEqual({r['reference'] for r in runs}, {'PR-TD334-a', 'PR-TD334-b'})
        self.assertEqual(self._get(self.org_super, FUNDING).json()['totals']['students'], 1)
        self.assertEqual(self._get(self.org_super, SPENDING).status_code, 200)

    def test_an_org_admin_keeps_the_whole_organisation_view(self):
        runs = self._get(self.org_admin, RUNS).json()['runs']
        self.assertEqual([r['reference'] for r in runs], ['PR-TD334-a'])
        self.assertEqual(self._get(self.org_admin, FUNDING).json()['totals']['students'], 1)
        self.assertEqual(self._get(self.org_admin, SPENDING).status_code, 200)
        # …and another organisation's gift is still a 404 for them, never a 400.
        self.assertEqual(self._get(self.org_admin, RUNS, f'?programme={self.gifts["b"].code}')
                         .status_code, 404)
