"""The exchange rate that turns a dollar invoice into a ringgit cost (2026-09-11).

Owner ruling: *"As to the currency exchange, just use the exchange at the end of the billing
month."* Two providers invoice in USD, so every ringgit total in the ledger rests on this.

⚠ **NO TEST HERE TOUCHES THE NETWORK.** The live call was verified by hand once (USD->MYR was
4.0865 on 31 July 2026 and 4.026 on 31 August) and pinning a live rate in a test would make the
suite fail on a public holiday. What is tested is the CONTRACT: the date actually published, the
refusal, and the ringgit-passthrough.
"""
import json
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import fx, platform_cost


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ecb(payload):
    return mock.patch('urllib.request.urlopen', return_value=_FakeResponse(payload))


class TestTheMonthEndIsOneRule(SimpleTestCase):
    """`month_end` has one home. Two date rules give two answers, and one of them is wrong."""

    def test_it_finds_the_last_day_of_ordinary_months(self):
        self.assertEqual(platform_cost.month_end('2026-08'), date(2026, 8, 31))
        self.assertEqual(platform_cost.month_end('2026-09'), date(2026, 9, 30))

    def test_it_crosses_a_year_boundary(self):
        self.assertEqual(platform_cost.month_end('2026-12'), date(2026, 12, 31))

    def test_it_knows_february_in_a_leap_year(self):
        self.assertEqual(platform_cost.month_end('2028-02'), date(2028, 2, 29))
        self.assertEqual(platform_cost.month_end('2026-02'), date(2026, 2, 28))


class TestTheRate(SimpleTestCase):
    def test_ringgit_needs_no_rate_and_makes_no_call(self):
        """⚠ Google Workspace invoices in MYR. It must not be able to fail on an exchange-rate
        outage — so this path never reaches the network at all."""
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('called!')):
            rate, _used = fx.closing_rate('MYR', date(2026, 8, 31))
        self.assertEqual(rate, Decimal('1'))

    def test_it_returns_the_rate_and_the_date_it_was_published(self):
        with _ecb({'base': 'USD', 'date': '2026-08-31', 'rates': {'MYR': 4.026}}):
            rate, used = fx.closing_rate('USD', date(2026, 8, 31))
        self.assertEqual(rate, Decimal('4.026'))
        self.assertEqual(used, date(2026, 8, 31))

    def test_a_weekend_month_end_records_the_day_actually_published(self):
        """⚠ THE DATE RETURNED, NEVER THE DATE ASKED FOR. The ECB publishes on business days, so
        a month ending on a Sunday has no rate of its own. Recording the asked-for date would
        claim a Sunday publication that never happened, and nobody could look the figure up."""
        with _ecb({'base': 'USD', 'date': '2026-08-28', 'rates': {'MYR': 4.026}}):
            _rate, used = fx.closing_rate('USD', date(2026, 8, 30))
        self.assertEqual(used, date(2026, 8, 28))

    def test_a_failed_lookup_raises_rather_than_guessing(self):
        """⚠ It never falls back to last month, a cache, or a plausible figure. An invoice with
        no ringgit amount is already an honest state the ledger reports as incomplete."""
        with mock.patch('urllib.request.urlopen', side_effect=OSError('no network')):
            with self.assertRaises(fx.RateUnavailable):
                fx.closing_rate('USD', date(2026, 8, 31))

    def test_a_response_with_no_MYR_in_it_raises(self):
        with _ecb({'base': 'USD', 'date': '2026-08-31', 'rates': {'EUR': 0.9}}):
            with self.assertRaises(fx.RateUnavailable):
                fx.closing_rate('USD', date(2026, 8, 31))

    def test_it_names_itself_to_the_service_it_depends_on(self):
        """The host answers urllib's default agent with a flat 403, which arrives looking exactly
        like an outage. It cost one debugging round; the header is pinned so it cannot be lost."""
        captured = {}

        def _capture(req, **kw):
            captured['ua'] = req.get_header('User-agent')
            return _FakeResponse({'date': '2026-08-31', 'rates': {'MYR': 4.026}})

        with mock.patch('urllib.request.urlopen', side_effect=_capture):
            fx.closing_rate('USD', date(2026, 8, 31))
        self.assertIn('halatuju', (captured['ua'] or '').lower())


class TestConversion(SimpleTestCase):
    def test_it_rounds_once_at_the_end(self):
        """Money rounds once, and only after the multiplication."""
        with _ecb({'date': '2026-08-31', 'rates': {'MYR': 4.026}}):
            myr, rate, used = fx.to_myr('25.00', 'USD', date(2026, 8, 31))
        self.assertEqual(myr, Decimal('100.65'))
        self.assertEqual(rate, Decimal('4.026'))
        self.assertEqual(used, date(2026, 8, 31))

    def test_a_ringgit_amount_passes_straight_through(self):
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('called!')):
            myr, rate, _used = fx.to_myr('18.90', 'MYR', date(2026, 8, 31))
        self.assertEqual(myr, Decimal('18.90'))
        self.assertEqual(rate, Decimal('1'))
