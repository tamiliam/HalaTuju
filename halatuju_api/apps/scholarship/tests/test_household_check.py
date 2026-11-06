"""Cockpit verified-tick reconciliation (2026-07-15): household income + size vs the documents.
Pure logic (tolerance / all-known / accounted); the underlying earner-income + roster reads are
covered by the income-engine tests, so we mock them here and assert the reconciliation rules."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.scholarship import income_engine as ie
from apps.scholarship.tests.package_patch import patch_engine


def _app(income=None, size=None):
    return SimpleNamespace(profile=SimpleNamespace(household_income=income, household_size=size))


class TestHouseholdIncomeReconciliation(SimpleTestCase):
    @staticmethod
    def _recon(app, members, incomes, *, genuine=True, has_doc=True):
        """Run the reconciliation with the earner set + per-member incomes mocked; genuineness
        defaults to genuine (fail-open). ``genuine`` may be a list (one per member); ``has_doc``
        (request #54) whether each member has an income document on file."""
        g = dict(side_effect=genuine) if isinstance(genuine, list) else dict(return_value=genuine)
        return patch_engine(ie, '_income_earning_members', return_value=members), \
            patch_engine(ie, 'earner_monthly_income', side_effect=[(a, 's') for a in incomes]), \
            patch_engine(ie, '_member_income_genuine', **g), \
            patch_engine(ie, '_member_has_income_doc', return_value=has_doc)

    def test_matches_within_tolerance(self):
        app = _app(income=7000, size=5)
        m1, m2, m3, m4 = self._recon(app, ['father', 'mother'], [3600.0, 3400.0])
        with m1, m2, m3, m4:
            r = ie.household_income_reconciliation(app)
        self.assertEqual(r['documented_total'], 7000.0)
        self.assertTrue(r['all_known'])
        self.assertTrue(r['genuine'])
        self.assertTrue(r['matches'])

    def test_137_over_tolerance_no_match(self):
        # #137: father 4,500 + mother 3,374.73 = 7,874.73 vs stated 7,000 (+12.5%) → beyond the
        # ±10% / RM700 band → NOT a match (the owner: it should not tick).
        app = _app(income=7000, size=5)
        m1, m2, m3, m4 = self._recon(app, ['father', 'mother'], [4500.0, 3374.73])
        with m1, m2, m3, m4:
            r = ie.household_income_reconciliation(app)
        self.assertEqual(r['documented_total'], 7874.73)
        self.assertFalse(r['matches'])

    def test_str_route_sibling_earner_is_summed(self):
        # #117-style: STR route, no salary-route working members, but a working sister with a
        # genuine payslip → she's summed, so the household gets a documented income.
        app = _app(income=3000, size=6)
        m1, m2, m3, m4 = self._recon(app, ['sister'], [3000.0])
        with m1, m2, m3, m4:
            r = ie.household_income_reconciliation(app)
        self.assertEqual(r['documented_total'], 3000.0)
        self.assertTrue(r['matches'])

    def test_suspect_income_doc_is_not_confident(self):
        # #117 real: the sister's slip is genuineness-SUSPECT → no verified tick (documented=None).
        app = _app(income=3000, size=6)
        m1, m2, m3, m4 = self._recon(app, ['sister'], [3000.0], genuine=False)
        with m1, m2, m3, m4:
            r = ie.household_income_reconciliation(app)
        self.assertFalse(r['genuine'])
        self.assertIsNone(r['documented_total'])
        self.assertFalse(r['matches'])

    def test_unknown_earner_income_is_not_all_known(self):
        app = _app(income=5000, size=4)
        m1, m2, m3, m4 = self._recon(app, ['father', 'mother'], [3000.0, None])
        with m1, m2, m3, m4:
            r = ie.household_income_reconciliation(app)
        self.assertFalse(r['all_known'])
        self.assertIsNone(r['documented_total'])
        self.assertFalse(r['matches'])

    def test_no_earning_members(self):
        app = _app(income=5000, size=4)
        m1, m2, m3, m4 = self._recon(app, [], [])
        with m1, m2, m3, m4:
            r = ie.household_income_reconciliation(app)
        self.assertIsNone(r['documented_total'])
        self.assertFalse(r['matches'])

    def test_small_income_uses_flat_grace(self):
        # 900 documented vs 1000 stated: 10% = 100, but the RM300 floor grace applies → match.
        app = _app(income=1000, size=3)
        m1, m2, m3, m4 = self._recon(app, ['father'], [900.0])
        with m1, m2, m3, m4:
            r = ie.household_income_reconciliation(app)
        self.assertTrue(r['matches'])


    # ── Request #54: the additive fields the cockpit's amber note reads ──────────────────────
    def test_54_confident_match_has_nothing_unchecked(self):
        m = self._recon(_app(income=7000), ['father', 'mother'], [3600.0, 3400.0])
        with m[0], m[1], m[2], m[3]:
            r = ie.household_income_reconciliation(_app(income=7000))
        self.assertTrue(r['matches'])
        self.assertEqual(r['read_total'], 7000.0)
        self.assertEqual(r['unchecked'], [])
        self.assertTrue(r['has_documents'])

    def test_54_confident_outside_tolerance_serves_the_documents_figure(self):
        m = self._recon(_app(income=4000), ['father'], [5100.0])
        with m[0], m[1], m[2], m[3]:
            r = ie.household_income_reconciliation(_app(income=4000))
        self.assertFalse(r['matches'])
        self.assertEqual(r['documented_total'], 5100.0)
        self.assertEqual(r['read_total'], 5100.0)
        self.assertEqual(r['unchecked'], [])

    def test_54_one_earner_unverified_names_them_and_keeps_the_read_total(self):
        m = self._recon(_app(income=4000), ['father', 'mother'], [3100.0, 2000.0],
                        genuine=[False, True])
        with m[0], m[1], m[2], m[3]:
            r = ie.household_income_reconciliation(_app(income=4000))
        self.assertIsNone(r['documented_total'])
        self.assertFalse(r['matches'])
        self.assertEqual(r['read_total'], 5100.0)
        self.assertEqual(r['unchecked'], [{'member': 'father', 'reason': 'unverified'}])

    def test_54_one_earner_unread(self):
        m = self._recon(_app(income=4000), ['father', 'mother'], [None, 2000.0])
        with m[0], m[1], m[2], m[3]:
            r = ie.household_income_reconciliation(_app(income=4000))
        self.assertIsNone(r['documented_total'])
        self.assertEqual(r['read_total'], 2000.0)
        self.assertEqual(r['unchecked'], [{'member': 'father', 'reason': 'unread'}])

    def test_54_no_income_documents_at_all(self):
        m = self._recon(_app(income=4000), ['father'], [None], has_doc=False)
        with m[0], m[1], m[2], m[3]:
            r = ie.household_income_reconciliation(_app(income=4000))
        self.assertFalse(r['has_documents'])
        self.assertEqual(r['read_total'], 0.0)

    def test_54_no_earners(self):
        m = self._recon(_app(income=4000), [], [])
        with m[0], m[1], m[2], m[3]:
            r = ie.household_income_reconciliation(_app(income=4000))
        self.assertIsNone(r['read_total'])
        self.assertEqual(r['unchecked'], [])
        self.assertFalse(r['has_documents'])


class TestHouseholdSizeAccounted(SimpleTestCase):
    def test_accounted_when_exact_and_no_gaps(self):
        app = _app(income=7000, size=5)
        with patch_engine(ie, '_described_household_count', return_value=5), \
             patch_engine(ie, 'household_status_gaps', return_value=[]):
            r = ie.household_size_accounted(app)
        self.assertTrue(r['accounted'])
        self.assertFalse(r['overcount'])

    def test_not_accounted_when_status_gap(self):
        app = _app(income=7000, size=5)
        with patch_engine(ie, '_described_household_count', return_value=5), \
             patch_engine(ie, 'household_status_gaps', return_value=[{'member': 'father', 'need': 'status'}]):
            r = ie.household_size_accounted(app)
        self.assertFalse(r['accounted'])

    def test_undercount_is_benign(self):
        # Household larger than the itemised roster (grandparents, unlisted relatives) → no tick,
        # but NOT an over-count flag either.
        app = _app(income=7000, size=6)
        with patch_engine(ie, '_described_household_count', return_value=4), \
             patch_engine(ie, 'household_status_gaps', return_value=[]):
            r = ie.household_size_accounted(app)
        self.assertFalse(r['accounted'])
        self.assertFalse(r['overcount'])

    def test_overcount_flagged(self):
        app = _app(income=7000, size=3)
        with patch_engine(ie, '_described_household_count', return_value=5), \
             patch_engine(ie, 'household_status_gaps', return_value=[]):
            r = ie.household_size_accounted(app)
        self.assertFalse(r['accounted'])
        self.assertTrue(r['overcount'])


class TestMemberHasIncomeDoc(TestCase):
    """Request #54: `has_documents` reads the real document cluster (salary route, tagged docs)."""

    def test_reads_the_tagged_salary_slip(self):
        from apps.scholarship.models import ApplicantDocument
        from apps.scholarship.tests.factories import make_application
        app = make_application('submitted', income_route='salary')
        self.assertFalse(ie._member_has_income_doc(app, 'father'))
        ApplicantDocument.objects.create(application=app, doc_type='salary_slip',
                                         household_member='father',
                                         storage_path=f'{app.id}/salary_slip/father')
        self.assertTrue(ie._member_has_income_doc(app, 'father'))
        self.assertFalse(ie._member_has_income_doc(app, 'mother'))
