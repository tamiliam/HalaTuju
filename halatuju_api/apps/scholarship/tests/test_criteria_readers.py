"""Criteria editor Sprint 3b (TD-772 / TD-774) - every reader reads the intake's TREE.

Proves: the four live intake shapes (1, 3, 4, 5) read the same through every reader with the tree
NULL (today's columns) and with the tree stored; a stored tree WINS over contradicting columns in
every moved reader (the admin intake rows, the seed's report, the born-in surfaces, the income
lines); a refused stored tree fails ONE row / intake visibly (the chip, the IC-lock hold, the
rescore) and never a page or a job; and the officer income band reads the 'all' join and refuses
a household size of 0 or below."""
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.scholarship import birth_state, criteria, criteria_read, rejection_chip
from apps.scholarship.income_engine import amounts
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import rescore_pending_decisions, score_application
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.tests.test_criteria import COHORT_1, COHORT_3, COHORT_4, COHORT_5, cohort
from apps.scholarship.views_admin.gifts import _requirements_row
from apps.scholarship.views_admin.sponsors import _HELD_BY_RULES_ERROR, _held_by_birth_state_rule

LIVE = {'1': COHORT_1, '3': COHORT_3, '4': COHORT_4, '5': COHORT_5}
#: A tree that contradicts COHORT_1's columns on every reader's question.
OTHER = criteria.from_legacy(cohort(min_spm_a_count=1, min_stpm_pngk=2.2, income_ceiling=3000,
                                    per_capita_ceiling=700, allowed_birth_states=['sabah'],
                                    allowed_start_years=[2027]))
BAD = {'all': [{'section': 'nonsense'}]}


def stored(c, tree):
    return SimpleNamespace(**vars(c), criteria=tree)


def readings(c):
    return (criteria_read.column_values(c), criteria_read.income_ceilings(c), criteria_read.pngk_floor(c),
            criteria_read.birth_state_keys(c), criteria_read.start_years_rule(c),
            birth_state.stored_keys(birth_state.cohort_rule(c)), _requirements_row(c))


class TestLiveShapesReadTheSame(SimpleTestCase):
    def test_null_and_stored_trees_read_the_same_through_every_reader(self):
        for name, c in LIVE.items():
            with self.subTest(intake=name):
                self.assertEqual(readings(c), readings(stored(c, criteria.from_legacy(c))))

    def test_column_values_are_the_columns(self):
        for name, c in LIVE.items():
            with self.subTest(intake=name):
                got = criteria_read.column_values(c)
                for f in criteria_read.COLUMN_FIELDS:
                    self.assertEqual(got[f], getattr(c, f), f)
                self.assertEqual(got['allowed_birth_states'], c.allowed_birth_states)
                self.assertEqual(got['allowed_start_years'], c.allowed_start_years)


class TestAStoredTreeWins(SimpleTestCase):
    def test_every_reader_reads_the_tree_not_the_columns(self):
        c = stored(COHORT_1, OTHER)
        values = criteria_read.column_values(c)
        self.assertEqual((values['min_spm_a_count'], values['min_spm_bplus_count'], values['min_stpm_pngk'],
                          values['income_ceiling'], values['per_capita_ceiling']), (1, None, 2.2, 3000, 700))
        self.assertEqual(values['allowed_birth_states'], ['sabah'])
        self.assertEqual(values['allowed_start_years'], [2027])
        row = _requirements_row(c)
        self.assertEqual((row['min_spm_a_count'], row['income_ceiling'], row['allowed_birth_states']),
                         (1, 3000, ['sabah']))
        self.assertEqual(birth_state.stored_keys(birth_state.cohort_rule(c)), ['sabah'])
        self.assertEqual(criteria_read.income_ceilings(c)[:2], (3000, 700))


class TestIncomeHeadroom(SimpleTestCase):
    def band(self, pc, size, ceilings):
        app = SimpleNamespace(cohort=None, profile=SimpleNamespace(household_size=size))
        with mock.patch.object(amounts, 'income_per_capita', return_value=(pc, True)), \
                mock.patch.object(criteria_read, 'income_ceilings', return_value=ceilings):
            return amounts.income_headroom(app, [])

    def test_a_size_of_zero_or_below_is_unknown(self):
        for size in (0, -2):
            with self.subTest(size=size):
                self.assertEqual(self.band(500, size, (5860, 1000, 'any'))[0], 'unknown')

    def test_all_is_over_when_either_line_fails(self):
        # gross 4800 passes the household line; RM1,200 a head does not pass RM1,000
        self.assertEqual(self.band(1200, 4, (5860, 1000, 'all'))[0], 'over')
        self.assertNotEqual(self.band(1200, 4, (5860, 1000, 'any'))[0], 'over')
        # gross 7000 fails the household line; RM700 a head passes RM1,000
        self.assertEqual(self.band(700, 10, (5860, 1000, 'all'))[0], 'over')

    def test_all_grades_on_the_stricter_line(self):
        band, ctx = self.band(500, 4, (5860, 1000, 'all'))
        self.assertEqual(band, 'probable')            # binding line min(5860, 4000): room 2000 >= 1000
        self.assertEqual((ctx['breach_room'], ctx['per_capita_ceiling']), (2000, 1000))
        band, ctx = self.band(900, 4, (5860, 2000, 'all'))
        self.assertEqual(ctx['per_capita_ceiling'], 1465)   # 5860 / 4 is stricter than 2000
        self.assertEqual(band, 'probable')            # room 5860 - 3600 = 2260 >= 1465

    def test_all_thin_margin(self):
        band, ctx = self.band(1300, 4, (5860, 1400, 'all'))
        self.assertEqual(ctx['breach_room'], 5600 - 5200)
        self.assertEqual(band, 'unsure')


def _apply(c):
    student = make_student(household_income=2500, household_size=5, receives_str=True, exam_type='spm',
                           grades={f's{i}': 'A' for i in range(8)})
    return make_application(cohort=c, student=student, consent_to_contact=True, intends_tertiary_2026=True)


class TestARefusedTreeFailsOneRowOrIntake(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.good = make_cohort(code='good-intake', income_ceiling=5860, per_capita_ceiling=1584)
        cls.bad = make_cohort(code='bad-intake', income_ceiling=5860, per_capita_ceiling=1584,
                              allowed_birth_states=['sabah'])

    def _break(self):
        ScholarshipCohort.objects.filter(pk=self.bad.pk).update(criteria=BAD)

    def test_the_chip_says_rules_error_for_that_row_only(self):
        ok, broken = _apply(self.good), _apply(self.bad)
        self._break()
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            self.assertEqual(rejection_chip.chip(ScholarshipApplication.objects.get(pk=broken.pk)), 'rules_error')
        self.assertEqual(rejection_chip.chip(ScholarshipApplication.objects.get(pk=ok.pk)), '')
        self.assertIn('rules_error', rejection_chip.CHIPS)

    def test_the_ic_lock_is_held_with_a_reason(self):
        app = _apply(self.bad)
        ScholarshipApplication.objects.filter(pk=app.pk).update(status='recommended')
        self.assertNotEqual(_held_by_birth_state_rule(app.profile), _HELD_BY_RULES_ERROR)
        self._break()
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            self.assertEqual(_held_by_birth_state_rule(app.profile), _HELD_BY_RULES_ERROR)

    def test_rescore_skips_the_refused_intake_whole_and_carries_on(self):
        ok, broken = _apply(self.good), _apply(self.bad)
        score_application(ok)
        score_application(broken)
        ScholarshipApplication.objects.filter(pk=broken.pk).update(verdict='', shortlist_reason='kept')
        self._break()
        with self.assertLogs('apps.scholarship', 'ERROR') as logs:
            result = rescore_pending_decisions()
        self.assertIn('bad-intake', '\n'.join(logs.output))
        self.assertEqual(result['refused_intakes'], [{'id': self.bad.id, 'code': 'bad-intake'}])
        self.assertEqual(result['rescored'], 1)
        broken.refresh_from_db()
        self.assertEqual((broken.verdict, broken.shortlist_reason), ('', 'kept'))   # untouched
        out, err = StringIO(), StringIO()
        with self.assertLogs('apps.scholarship', 'ERROR'):
            call_command('rescore_pending_decisions', stdout=out, stderr=err)
        self.assertIn('bad-intake', err.getvalue())


class TestTheSeedReportsTheTree(TestCase):
    def test_a_new_seed_stores_its_tree_and_an_existing_row_reports_its_tree(self):
        call_command('seed_b40_2026_cohort', stdout=StringIO())
        c = ScholarshipCohort.objects.get(code='b40-2026')
        self.assertEqual(c.criteria, criteria.from_legacy(c))
        ScholarshipCohort.objects.filter(pk=c.pk).update(criteria=OTHER)
        out = StringIO()
        call_command('seed_b40_2026_cohort', stdout=out)
        self.assertIn('min_spm_a_count=1,', out.getvalue())
        self.assertIn('per_capita_ceiling=RM700', out.getvalue())
