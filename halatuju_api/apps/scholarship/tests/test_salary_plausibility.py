"""TD-151 (2) — a payslip's monthly figure outside the plausibility window is a misread, not a fact.

It takes the existing "unreliable read" path (`_salary_monthly_amount` → None → income 'unknown',
verify at interview), exactly as net > gross already does — no new state, no new copy. The bounds
and where they come from are in `income_engine/salary_figures.py` and docs/decisions.md 2026-10-02.

Helpers are borrowed through the MODULE so no TestCase is collected twice (lessons.md 2026-09-30).
"""
from django.test import SimpleTestCase

from apps.scholarship.income_engine import earner_monthly_income
from apps.scholarship.income_engine.salary_figures import (_SLIP_MONTHLY_MAX, _SLIP_MONTHLY_MIN,
                                                           _salary_monthly_amount)
from apps.scholarship.tests import test_income_engine as tie


class SalaryPlausibilityTest(SimpleTestCase):

    def test_a_hundredfold_misread_with_no_net_to_contradict_it_is_unusable(self):
        # #66's ringgit|sen concatenation (RM326.00 → 32600) on a slip that printed no net: the
        # net > gross rule cannot fire, so only the window catches it.
        self.assertIsNone(_salary_monthly_amount({'gross_income': '32600'}))

    def test_a_dropped_decimal_misread_is_unusable(self):
        self.assertIsNone(_salary_monthly_amount({'gross_income': 'RM0.50'}))
        self.assertIsNone(_salary_monthly_amount({'net_income': 'RM17.00'}))

    def test_the_window_edges(self):
        self.assertEqual(_salary_monthly_amount({'gross_income': str(_SLIP_MONTHLY_MIN)}), 100.0)
        self.assertEqual(_salary_monthly_amount({'gross_income': str(_SLIP_MONTHLY_MAX)}), 20000.0)
        self.assertIsNone(_salary_monthly_amount({'gross_income': '99.99'}))
        self.assertIsNone(_salary_monthly_amount({'gross_income': '20000.01'}))

    def test_the_real_extremes_we_hold_still_read(self):
        # The smallest and largest real monthly figures in the 2026-10-02 corpus measurement.
        self.assertEqual(_salary_monthly_amount({'gross_income': 'RM357.22'}), 357.22)
        self.assertEqual(_salary_monthly_amount({'gross_income': 'RM9,900.04'}), 9900.04)

    def test_an_implausible_year_to_date_falls_back_to_the_month(self):
        # A YTD misread (×100) must not inflate the figure, nor throw the good month away.
        self.assertEqual(_salary_monthly_amount({'gross_income': 'RM3,000',
                                                 'gross_income_ytd': 'RM3,600,000'}), 3000.0)

    def test_the_window_applies_before_the_currency_conversion(self):
        # Review F4b: a S$7,000 Singapore slip is inside the window in its OWN currency and is then
        # converted (×3.15 → RM22,050) — above the ceiling, and rightly kept: the window judges
        # what the document printed, not the ringgit figure we derive from it.
        from django.test import override_settings
        app = tie._app([tie._bill('salary_slip', {'gross_income': 'S$7,000.00',
                                                  'employer': 'Acme Pte Ltd'})])
        app.status = 'submitted'
        with override_settings(SGD_TO_MYR_RATE=3.15):
            amt, src = earner_monthly_income(app, 'father')
        self.assertEqual(src, 'salary')
        self.assertAlmostEqual(amt, 22050.0, places=2)

    def test_the_engine_reads_an_implausible_slip_as_unknown(self):
        app = tie._app([tie._bill('salary_slip', {'gross_income': '32600'})])
        self.assertEqual(earner_monthly_income(app, 'father'), (None, 'unknown'))
