"""Criteria Sprint 2 (TD-772): the other readers read the tree the gate reads.

For every live intake shape (cohorts 1, 3, 4, 5, the old model defaults, programme 7's floor 3.0
and the replay grid's edge shapes), each accessor and each switched reader gives the SAME answer
from the stored tree as the column reader gave from the columns - with the tree stored (a JSON
round trip, as the database returns it) and with ``criteria`` NULL (read from the columns). A
stored tree that says something else is followed, which is the point of the switch.
"""
import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import birth_state, criteria, criteria_read, results_route
from apps.scholarship.income_engine import amounts
from apps.scholarship.start_year import rule_on, stored_years
from apps.scholarship.tests.test_criteria import cohort
from apps.scholarship.tests.test_criteria_equivalence import COHORTS

SHAPES = dict(COHORTS, programme_7=cohort(min_stpm_pngk=3.0, income_ceiling=5860, per_capita_ceiling=1584),
              start_years_junk=cohort(allowed_start_years=['x']),
              pc_only=cohort(per_capita_ceiling=1584), gross_only=cohort(income_ceiling=5860))


def _stored(c):
    """The same cohort with its tree STORED as the database returns it (a JSON round trip)."""
    return SimpleNamespace(**dict(vars(c), criteria=json.loads(json.dumps(criteria.from_legacy(c)))))


def _both(c):
    """The columns read, and the stored read - unless `validate_tree` refuses the shape (the
    junk-only start years): such a tree is never stored, and reading one raises (TD-774)."""
    columns = ('columns', SimpleNamespace(**dict(vars(c), criteria=None)))
    if criteria.validate_tree(criteria.from_legacy(c)):
        return (columns,)
    return (columns, ('stored', _stored(c)))


class TestARefusedStoredShapeRaises(SimpleTestCase):
    def test_the_junk_start_years_shape_cannot_be_read_when_stored(self):
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'), \
                self.assertRaises(criteria.StoredTreeRefused):
            criteria_read.start_years_rule(_stored(SHAPES['start_years_junk']))


def _app(c):
    return SimpleNamespace(cohort=c, profile=SimpleNamespace(household_size=4), cohort_id=7)


class TestAccessorsMatchTheColumns(SimpleTestCase):
    def test_every_accessor_equals_its_column_reader_for_every_shape(self):
        for name, c in SHAPES.items():
            for how, read in _both(c):
                with self.subTest(shape=name, read=how):
                    self.assertEqual(criteria_read.pngk_floor(read), c.min_stpm_pngk)
                    self.assertEqual(criteria_read.asks_post_spm_results(read), c.min_stpm_pngk is not None)
                    gross, pc, mode = criteria_read.income_ceilings(read)
                    self.assertEqual((gross, pc), (c.income_ceiling, c.per_capita_ceiling))
                    self.assertEqual(mode, 'any' if (gross is not None or pc is not None) else None)
                    self.assertEqual(criteria_read.birth_state_keys(read), birth_state.stored_keys(c.allowed_birth_states))
                    years = c.allowed_start_years
                    self.assertEqual(criteria_read.start_years_rule(read),
                                     stored_years(years) if rule_on(years) else None)

    def test_the_switched_readers_answer_as_before(self):
        for name, c in SHAPES.items():
            for how, read in _both(c):
                with self.subTest(shape=name, read=how):
                    self.assertEqual(results_route.gift_asks_higher(_app(read)), c.min_stpm_pngk is not None)
                    self.assertEqual(amounts.income_test_configured(_app(read)),
                                     bool(c.income_ceiling or c.per_capita_ceiling))
                    for nric in ('050101-10-1234', '050101-12-1234', '050101-82-1234'):
                        self.assertEqual(birth_state.meets_rule(nric, birth_state.cohort_rule(read)),
                                         birth_state.meets_rule(nric, c.allowed_birth_states))

    def test_income_headroom_is_unchanged_at_and_around_each_line(self):
        """Every band and figure as the column reader gave them, with TD-771's ruling applied
        (26 Nov): per-person exactly ON its line is not met, so with the household line also
        failed the band is 'over', as the gate refuses it."""
        for name in ('cohort_1', 'cohort_3', 'cohort_4', 'cohort_5', 'defaults', 'programme_7',
                     'pc_only', 'gross_only', 'nothing'):
            c = SHAPES[name]
            for pc_value in (500, 899, 900, 1000, 1180, 1465, 1584, 1585, 2000, None):
                with mock.patch.object(amounts, 'income_per_capita', return_value=(pc_value, True)):
                    want = self._column_headroom(c, pc_value)
                    for how, read in _both(c):
                        with self.subTest(shape=name, pc=pc_value, read=how):
                            self.assertEqual(amounts.income_headroom(_app(read), []), want)

    @staticmethod
    def _column_headroom(c, pc):
        """The pre-switch income_headroom on the columns, with TD-771's 'over' = both lines fail."""
        gross_ceiling, pc_ceiling, size = c.income_ceiling, c.per_capita_ceiling, 4
        if pc is None or not pc_ceiling:
            return 'unknown', {'all_known': True}
        gross = pc * size
        ceiling = max([x for x in (gross_ceiling, pc_ceiling * size) if x])
        room = ceiling - gross
        ctx = {'gross': int(round(gross)), 'per_capita': int(round(pc)), 'size': size,
               'breach_room': int(round(room)), 'all_known': True,
               'gross_ceiling': int(gross_ceiling or 0), 'per_capita_ceiling': int(pc_ceiling)}
        household_ok = gross_ceiling is not None and gross <= gross_ceiling
        if not household_ok and not pc < pc_ceiling:
            return 'over', ctx
        return ('unsure' if room < amounts._HEADROOM_THIN_RM else 'probable'), ctx

    def test_the_fingerprint_intake_values_are_unchanged(self):
        """`verdict_context.intake_values` hashes the same values under the same keys, so no
        fingerprint taken before the switch-over moves (a moved one would read as new evidence)."""
        from apps.scholarship import verdict_context
        for name, c in SHAPES.items():
            years = c.allowed_start_years
            want = {'year': 2026, 'income_ceiling': c.income_ceiling, 'per_capita_ceiling': c.per_capita_ceiling,
                    'min_stpm_pngk': c.min_stpm_pngk, 'cohort_id': 7,
                    'allowed_start_years': stored_years(years) if rule_on(years) else None}
            for how, read in _both(c):
                with self.subTest(shape=name, read=how):
                    app = _app(SimpleNamespace(**dict(vars(read), year=2026)))
                    got = verdict_context.intake_values(app)
                    self.assertEqual(verdict_context.canonical_json(got), verdict_context.canonical_json(want))


class TestTheStoredTreeIsFollowed(SimpleTestCase):
    def test_a_stored_tree_wins_over_the_columns(self):
        c = SimpleNamespace(**dict(vars(SHAPES['cohort_1']), criteria={'all': [
            {'section': 'results', 'own': [{'route': 'post_spm', 'all': [{'test': 'min_pngk', 'value': 3.5}]}]},
            {'section': 'income', 'any': [{'test': 'household_income_max', 'rm': 4000}]},
            {'section': 'born_in', 'any': ['sabah']}],
            'flag': [{'test': 'course_start_year', 'allowed': [2026]}]}))
        self.assertEqual(criteria_read.pngk_floor(c), 3.5)
        self.assertTrue(results_route.gift_asks_higher(_app(c)))
        self.assertEqual(criteria_read.income_ceilings(c), (4000, None, 'any'))
        self.assertEqual(birth_state.cohort_rule(c), ['sabah'])
        self.assertEqual(criteria_read.start_years_rule(c), [2026])

    def test_a_stored_nothing_checked_tree_switches_every_reader_off(self):
        c = SimpleNamespace(**dict(vars(SHAPES['cohort_5']), criteria={'all': []}))
        self.assertFalse(results_route.gift_asks_higher(_app(c)))
        self.assertFalse(amounts.income_test_configured(_app(c)))
        self.assertEqual(birth_state.cohort_rule(c), [])
        self.assertIsNone(criteria_read.start_years_rule(c))

    def test_no_cohort_and_a_stub_read_as_before(self):
        self.assertEqual(criteria_read.income_ceilings(None), (None, None, None))
        self.assertEqual(criteria_read.birth_state_keys(None), [])
        self.assertTrue(results_route.gift_asks_higher(SimpleNamespace(cohort=SimpleNamespace())))
        # a test double answers every attribute: it is read from its columns, never as a tree
        self.assertEqual(criteria.tree_of(SimpleNamespace(**dict(vars(SHAPES['nothing']), criteria=mock.Mock()))),
                         {'all': []})
