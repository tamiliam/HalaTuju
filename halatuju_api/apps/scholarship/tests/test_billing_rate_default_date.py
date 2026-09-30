"""TD-248 — a billing rate saved with no `effective_from` starts on the MALAYSIAN 1st.

The default was `timezone.now().date().replace(day=1)`: the UTC date, TD-209's shape a fourth
time. For the eight hours between Malaysian midnight and 08:00 on the 1st, a rate saved with no
date took effect from the PREVIOUS month — re-pricing a month that may already be invoiced.
"""
from datetime import UTC, date, datetime
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import BillingRate
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin

URL = '/api/v1/admin/scholarship/billing/rates/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class BillingRateDefaultDateTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sup = make_admin('super', super_admin=True)

    def _post(self, **extra):
        body = {'category': BillingRate.CATEGORY_CHOICES[0][0],
                'kind': BillingRate.KIND_CHOICES[0][0], 'value': '10'}
        body.update(extra)
        return authed_client(self.sup).post(URL, body, format='json')

    def test_the_default_is_the_new_month_at_0730_on_the_1st_in_malaysia(self):
        # 23:30 UTC on 30 September = 07:30 on 1 October in Kuala Lumpur.
        instant = datetime(2026, 9, 30, 23, 30, tzinfo=UTC)
        with mock.patch.object(timezone, 'now', return_value=instant):
            r = self._post()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['effective_from'], '2026-10-01')
        self.assertTrue(BillingRate.objects.filter(effective_from=date(2026, 10, 1)).exists())

    def test_outside_the_window_both_clocks_agree(self):
        instant = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)   # 18:00 MYT, same date either way
        with mock.patch.object(timezone, 'now', return_value=instant):
            r = self._post()
        self.assertEqual(r.json()['effective_from'], '2026-09-01')

    def test_an_explicit_date_is_kept(self):
        r = self._post(effective_from='2026-07-01')
        self.assertEqual(r.json()['effective_from'], '2026-07-01')
