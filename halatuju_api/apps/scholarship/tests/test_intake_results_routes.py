"""TD-773: the intake endpoint says which results routes a round lets through (`results_routes`).

The apply page's Step 3 reads it to show two notes: a warning to an SPM-only holder on a round that
needs post-SPM results, and a hint to a post-SPM holder on a round that judges each student on their
own results. It is read from the tree the gate reads (`criteria.tree_of`), never from intake
numbers, and it is display only: the field is added beside the answer and nothing else moves."""
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from apps.scholarship import criteria, criteria_read
from apps.scholarship.tests.factories import make_cohort
from apps.scholarship.tests.test_criteria import COHORT_1, COHORT_3, COHORT_4, COHORT_5, cohort

PNGK = {'route': 'post_spm', 'all': [{'test': 'min_pngk', 'value': 2.5}]}
SPM = {'route': 'spm', 'all': [{'test': 'grade_count', 'at_least': 3, 'grade_or_better': 'C'}]}


def stored(c, tree):
    return SimpleNamespace(**vars(c), criteria=tree)


def results(mode, *groups):
    return {'all': [{'section': 'results', mode: list(groups)}]}


class TestResultsRoutesReadsTheTree(SimpleTestCase):
    def test_the_live_shapes_read_from_their_columns(self):
        # Intake 1: SPM grade bars, no PNGK floor (D16c: everyone on the SPM grades).
        self.assertEqual(criteria_read.results_routes(COHORT_1), 'spm')
        # Intakes 3 and 4: a PNGK floor beside SPM bars, 'own' - each on their own results.
        self.assertEqual(criteria_read.results_routes(COHORT_3), 'both')
        self.assertEqual(criteria_read.results_routes(COHORT_4), 'both')
        # Intake 5 with its tree still NULL: the gate reads the CGPA trap left ON (an SPM group with
        # no test beside the floor), so SPM holders still pass - the note must say what the gate does.
        self.assertEqual(criteria_read.results_routes(COHORT_5), 'both')

    def test_intake_5_once_its_tree_is_stored_needs_post_spm_results(self):
        # The stored tree switches the SPM group off (owner ruling 2026-11-25).
        self.assertEqual(criteria_read.results_routes(stored(COHORT_5, criteria.from_legacy(COHORT_5))),
                         'post_spm')

    def test_a_stored_tree_wins_over_its_columns(self):
        self.assertEqual(criteria_read.results_routes(stored(COHORT_1, results('own', PNGK))), 'post_spm')
        self.assertEqual(criteria_read.results_routes(stored(COHORT_5, results('own', SPM))), 'spm')

    def test_each_join_of_both_groups(self):
        cases = {'own': 'both', 'any': 'either', 'all': 'post_spm'}
        for mode, want in cases.items():
            with self.subTest(mode=mode):
                tree = results(mode, PNGK, SPM)
                self.assertEqual(criteria.validate_tree(tree), [])
                self.assertEqual(criteria_read.results_routes(stored(COHORT_1, tree)), want)

    def test_one_group_alone_reads_the_same_under_every_join(self):
        for mode in ('own', 'any', 'all'):
            with self.subTest(mode=mode):
                self.assertEqual(criteria_read.results_routes(stored(COHORT_1, results(mode, PNGK))), 'post_spm')
                self.assertEqual(criteria_read.results_routes(stored(COHORT_1, results(mode, SPM))), 'spm')

    def test_no_results_group_reads_none(self):
        self.assertIsNone(criteria_read.results_routes(cohort()))                  # no academic column at all
        self.assertIsNone(criteria_read.results_routes(stored(COHORT_3, {'all': []})))   # stored "nothing checked"
        income_only = {'all': [{'section': 'income', 'any': [{'test': 'household_income_max', 'rm': 5000}]}]}
        self.assertIsNone(criteria_read.results_routes(stored(COHORT_3, income_only)))

    def test_no_intake_reads_none(self):
        self.assertIsNone(criteria_read.results_routes(None))

    def test_a_refused_stored_tree_reads_none_and_is_still_logged(self):
        with self.assertLogs('apps.scholarship.criteria', level='ERROR'):
            self.assertIsNone(criteria_read.results_routes(stored(COHORT_1, {'all': [{'section': 'nonsense'}]})))


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestIntakeEndpointCarriesTheRoutes(TestCase):
    def setUp(self):
        self.client = APIClient()

    def get(self, code=''):
        qs = f'?programme={code}' if code else ''
        return self.client.get(f'/api/v1/scholarship/intake/{qs}').json()

    def test_an_open_round_carries_its_routes(self):
        c = make_cohort(is_open=True, is_active=True)          # the factory's A-, B+ and PNGK bars
        body = self.get(c.programme.code)
        self.assertTrue(body['open'])
        self.assertEqual(body['results_routes'], 'both')

    def test_a_stored_post_spm_tree_reads_post_spm(self):
        c = make_cohort(is_open=True, is_active=True, criteria=results('own', PNGK))
        self.assertEqual(self.get(c.programme.code)['results_routes'], 'post_spm')

    def test_a_round_with_no_results_rule_reads_null(self):
        c = make_cohort(is_open=True, is_active=True, min_spm_a_count=None, min_spm_bplus_count=None,
                        min_stpm_pngk=None)
        self.assertIsNone(self.get(c.programme.code)['results_routes'])

    def test_a_closed_round_reads_null(self):
        c = make_cohort(is_open=False, is_active=True)
        body = self.get(c.programme.code)
        self.assertFalse(body['open'])
        self.assertIsNone(body['results_routes'])

    def test_two_open_rounds_and_no_code_name_no_routes(self):
        make_cohort(is_open=True, is_active=True)
        make_cohort(is_open=True, is_active=True)
        body = self.get()
        self.assertEqual(len(body['choices']), 2)
        self.assertIsNone(body['results_routes'])

    def test_a_refused_stored_tree_still_answers_the_page(self):
        c = make_cohort(is_open=True, is_active=True, criteria={'all': [{'section': 'nonsense'}]})
        with self.assertLogs('apps.scholarship.criteria', level='ERROR'):
            body = self.get(c.programme.code)
        self.assertTrue(body['open'])
        self.assertIsNone(body['results_routes'])
