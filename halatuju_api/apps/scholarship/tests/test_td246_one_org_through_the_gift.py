"""TD-246 (closed 2026-10-04, overtaken): Payments and Spending ARE narrowed to one organisation —
through the gift.

The entry (2026-09-11) said a super saw every organisation pooled on both screens and the
organisation crumb could not narrow them. Since 2026-09-28 neither page draws anything until ONE
gift is chosen (`halatuju-web/src/lib/useGiftGate.ts`: several gifts and none chosen sends the
person to the Programmes page), and a gift belongs to exactly one organisation. So the gift the
crumb names already IS the organisation narrowing; a second `?org=` control on these two screens
would be two controls answering one question on the screen that moves money — the TD-241 ruling
("one control, one answer").

What has to hold on the SERVER for that to be true is pinned here, for the role the entry was
about — a super, who alone sees more than one organisation: naming a gift returns that gift's
organisation and nothing of another's. (Spending's twin is
`test_spend_report.py::…test_even_the_platform_scope_still_narrows_by_gift`.) The organisation
crumb on Sponsors, Sources and Requests is TD-228, still open.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.scholarship.models import PaymentRun
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestASuperNamingAGiftSeesOneOrganisation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gifts = {}
        for tag in ('a', 'b'):
            org = make_org()
            gift = make_programme(organisation=org, code=f'td246-{tag}')
            make_application('awarded', cohort=make_cohort(programme=gift, owning_organisation=org),
                             award_amount=Decimal('2000'))
            PaymentRun.objects.create(organisation=org, programme=gift, reference=f'PR-TD246-{tag}',
                                      payment_date=date(2026, 8, 1), period_month=date(2026, 8, 1))
            cls.gifts[tag] = gift
        cls.platform = make_admin('super', super_admin=True)    # no organisation of its own

    def _get(self, path, gift):
        r = authed_client(self.platform).get(f'/api/v1/admin/{path}?programme={gift.code}')
        self.assertEqual(r.status_code, 200, r.content[:200])
        return r.json()

    def test_the_run_list_names_only_that_gifts_organisation(self):
        for tag in ('a', 'b'):
            runs = self._get('scholarship/payment-runs/', self.gifts[tag])['runs']
            self.assertEqual([r['reference'] for r in runs], [f'PR-TD246-{tag}'])

    def test_the_funding_summary_counts_only_that_gifts_students(self):
        body = self._get('scholarship/payments/funding-summary/', self.gifts['b'])
        self.assertEqual(body['totals']['students'], 1)
        self.assertEqual(body['totals']['award_total'], '2000.00')

    def test_an_unknown_gift_is_404_not_everything(self):
        r = authed_client(self.platform).get(
            '/api/v1/admin/scholarship/payment-runs/?programme=td246-none')
        self.assertEqual(r.status_code, 404)
