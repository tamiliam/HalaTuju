"""Cockpit verified-tick reconciliation (2026-07-15): household income + size vs the documents.
Pure logic (tolerance / all-known / accounted); the underlying earner-income + roster reads are
covered by the income-engine tests, so we mock them here and assert the reconciliation rules."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import income_engine as ie


def _app(income=None, size=None):
    return SimpleNamespace(profile=SimpleNamespace(household_income=income, household_size=size))


class TestHouseholdIncomeReconciliation(SimpleTestCase):
    def test_matches_within_tolerance(self):
        app = _app(income=7000, size=5)
        with mock.patch.object(ie, 'effective_working_members', return_value=['father', 'mother']), \
             mock.patch.object(ie, 'earner_monthly_income', side_effect=[(3600.0, 'salary'), (3400.0, 'salary')]):
            r = ie.household_income_reconciliation(app)
        self.assertEqual(r['documented_total'], 7000.0)
        self.assertTrue(r['all_known'])
        self.assertTrue(r['matches'])

    def test_137_over_tolerance_no_match(self):
        # #137: father 4,500 + mother 3,374.73 = 7,874.73 vs stated 7,000 (+12.5%) → beyond the
        # ±10% / RM700 band → NOT a match (the owner: it should not tick).
        app = _app(income=7000, size=5)
        with mock.patch.object(ie, 'effective_working_members', return_value=['father', 'mother']), \
             mock.patch.object(ie, 'earner_monthly_income', side_effect=[(4500.0, 'salary'), (3374.73, 'salary')]):
            r = ie.household_income_reconciliation(app)
        self.assertEqual(r['documented_total'], 7874.73)
        self.assertTrue(r['all_known'])
        self.assertFalse(r['matches'])

    def test_unknown_earner_income_is_not_all_known(self):
        app = _app(income=5000, size=4)
        with mock.patch.object(ie, 'effective_working_members', return_value=['father', 'mother']), \
             mock.patch.object(ie, 'earner_monthly_income', side_effect=[(3000.0, 'salary'), (None, 'unknown')]):
            r = ie.household_income_reconciliation(app)
        self.assertFalse(r['all_known'])
        self.assertIsNone(r['documented_total'])
        self.assertFalse(r['matches'])

    def test_no_working_members(self):
        app = _app(income=5000, size=4)
        with mock.patch.object(ie, 'effective_working_members', return_value=[]):
            r = ie.household_income_reconciliation(app)
        self.assertIsNone(r['documented_total'])
        self.assertFalse(r['matches'])

    def test_small_income_uses_flat_grace(self):
        # 900 documented vs 1000 stated: 10% = 100, but the RM300 floor grace applies → match.
        app = _app(income=1000, size=3)
        with mock.patch.object(ie, 'effective_working_members', return_value=['father']), \
             mock.patch.object(ie, 'earner_monthly_income', side_effect=[(900.0, 'salary')]):
            r = ie.household_income_reconciliation(app)
        self.assertTrue(r['matches'])


class TestHouseholdSizeAccounted(SimpleTestCase):
    def test_accounted_when_exact_and_no_gaps(self):
        app = _app(income=7000, size=5)
        with mock.patch.object(ie, '_described_household_count', return_value=5), \
             mock.patch.object(ie, 'household_status_gaps', return_value=[]):
            r = ie.household_size_accounted(app)
        self.assertTrue(r['accounted'])
        self.assertFalse(r['overcount'])

    def test_not_accounted_when_status_gap(self):
        app = _app(income=7000, size=5)
        with mock.patch.object(ie, '_described_household_count', return_value=5), \
             mock.patch.object(ie, 'household_status_gaps', return_value=[{'member': 'father', 'need': 'status'}]):
            r = ie.household_size_accounted(app)
        self.assertFalse(r['accounted'])

    def test_undercount_is_benign(self):
        # Household larger than the itemised roster (grandparents, unlisted relatives) → no tick,
        # but NOT an over-count flag either.
        app = _app(income=7000, size=6)
        with mock.patch.object(ie, '_described_household_count', return_value=4), \
             mock.patch.object(ie, 'household_status_gaps', return_value=[]):
            r = ie.household_size_accounted(app)
        self.assertFalse(r['accounted'])
        self.assertFalse(r['overcount'])

    def test_overcount_flagged(self):
        app = _app(income=7000, size=3)
        with mock.patch.object(ie, '_described_household_count', return_value=5), \
             mock.patch.object(ie, 'household_status_gaps', return_value=[]):
            r = ie.household_size_accounted(app)
        self.assertFalse(r['accounted'])
        self.assertTrue(r['overcount'])
