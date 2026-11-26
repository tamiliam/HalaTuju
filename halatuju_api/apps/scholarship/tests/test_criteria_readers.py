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
from django.test import SimpleTestCase, TestCase, override_settings

from apps.courses.profile_claim import NRIC_LOCKED, handle_claim, ic_held_by_birth_state_rule

from apps.scholarship import birth_state, criteria, criteria_read, rejection_chip
from apps.scholarship.income_engine import amounts
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import rescore_pending_decisions, score_application
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
    make_student, no_rules,
)
from apps.scholarship.tests.test_criteria import COHORT_1, COHORT_3, COHORT_4, COHORT_5, cohort
from apps.scholarship.views_admin.gifts import REQUIREMENT_FIELDS, _requirements_row
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


SABAH_IC, SELANGOR_IC = '080505-12-1234', '080505-10-1234'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestARefusedTreeNeverBreaksTheRulesTab(TestCase):
    """Sprint 3b review, finding 1: one refused intake must not 500 the gift's intake list (the
    only screen where it can be fixed), nor the finish view after `finished_at` is saved."""

    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.admin = make_admin('org_admin', owning_org=cls.programme.organisation)
        cls.good = make_cohort(programme=cls.programme, code='rt-good', is_open=False,
                               income_ceiling=5860)
        cls.bad = make_cohort(programme=cls.programme, code='rt-bad', is_open=False)
        ScholarshipCohort.objects.filter(pk=cls.bad.pk).update(criteria=BAD)

    def setUp(self):
        self.client = authed_client(self.admin)

    def _flagged(self, reqs):
        self.assertIs(reqs['rules_error'], True)
        for f in (*REQUIREMENT_FIELDS, 'allowed_birth_states', 'allowed_start_years'):
            self.assertIsNone(reqs[f], f)

    def test_the_list_serves_every_year_and_flags_the_refused_one(self):
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            r = self.client.get(f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/')
        self.assertEqual(r.status_code, 200)
        rows = {y['code']: y['requirements'] for y in r.data['years']}
        self._flagged(rows['rt-bad'])
        self.assertNotIn('rules_error', rows['rt-good'])
        self.assertEqual(rows['rt-good']['income_ceiling'], 5860)

    def test_finishing_a_refused_intake_answers_with_its_row(self):
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            r = self.client.post(f'/api/v1/admin/scholarship/intake-years/{self.bad.id}/finish/',
                                 {'confirm': 'rt-bad'}, format='json')
        self.assertEqual(r.status_code, 200)
        self._flagged(r.data['requirements'])
        self.assertIsNotNone(r.data['finished_at'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestARefusedTreeNeverBreaksTheStudentsProfile(TestCase):
    """Sprint 3b review, finding 2: the IC hold FAILS CLOSED (held, as the admin break-glass), and
    the own-IC audit records the intake as `rule_unreadable` instead of raising after the save."""

    def _on_bad(self, stage):
        student = make_student(nric=SABAH_IC)
        app = make_application(stage, student=student,
                               cohort=make_cohort(allowed_birth_states=['sabah']))
        student.refresh_from_db()
        student.nric_verified = False
        student.save(update_fields=['nric_verified'])
        ScholarshipCohort.objects.filter(pk=app.cohort_id).update(criteria=BAD)
        return app, student

    def test_the_ic_hold_fails_closed(self):
        app, student = self._on_bad('recommended')
        uid = student.supabase_user_id
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            self.assertIs(ic_held_by_birth_state_rule(student), True)
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            self.assertEqual(handle_claim(uid, uid, {'nric': SELANGOR_IC}), (NRIC_LOCKED, 403))
        student.refresh_from_db()
        self.assertEqual(student.nric, SABAH_IC)
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            r = authed_client(uid).get('/api/v1/profile/')
        self.assertEqual(r.status_code, 200)
        self.assertIs(r.json()['nric_locked'], True)

    def test_the_audit_line_records_the_intake_as_rule_unreadable(self):
        app, student = self._on_bad('shortlisted')
        uid = student.supabase_user_id
        with self.assertLogs('apps.courses.profile_claim', 'INFO') as logs, \
                self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            self.assertEqual(handle_claim(uid, uid, {'nric': SELANGOR_IC}), ({'status': 'created'}, 200))
        line = next(m for m in logs.output if 'AUDIT nric_self_change' in m)
        self.assertIn(f'rule_fails=none rule_unreadable={app.id}', line)
        student.refresh_from_db()
        self.assertEqual(student.nric, SELANGOR_IC)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestCreateNeedsEveryRequirementKey(TestCase):
    """Sprint 3b review, finding 3 (owner rule: a blank or missing value never silently becomes a
    permissive default): a create that leaves a requirement key OUT is refused, naming the keys;
    an explicit null is still "no rule"."""

    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.admin = make_admin('org_admin', owning_org=cls.programme.organisation)

    def _create(self, code, **body):
        return authed_client(self.admin).post(
            f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/',
            {'code': code, 'name': code, 'year': 2027, **body}, format='json')

    def test_a_partial_or_empty_body_is_refused_naming_the_missing_keys(self):
        r = self._create('ck-partial', income_ceiling=5860, per_capita_ceiling=1584)
        self.assertEqual((r.status_code, r.data['code']), (400, 'missing_requirement'))
        self.assertEqual(set(r.data['fields']),
                         set(REQUIREMENT_FIELDS) - {'income_ceiling', 'per_capita_ceiling'}
                         | {'allowed_birth_states', 'allowed_start_years'})
        r = self._create('ck-empty')
        self.assertEqual((r.status_code, r.data['code']), (400, 'missing_requirement'))
        self.assertEqual(len(r.data['fields']), len(REQUIREMENT_FIELDS) + 2)
        self.assertFalse(ScholarshipCohort.objects.filter(code__in=('ck-partial', 'ck-empty')).exists())

    def test_a_full_body_with_explicit_nulls_creates_with_no_rule_for_those(self):
        r = self._create('ck-full', **no_rules(income_ceiling=5860, min_stpm_pngk=2.5))
        self.assertEqual(r.status_code, 201, r.data)
        c = ScholarshipCohort.objects.get(code='ck-full')
        self.assertEqual((c.min_spm_a_count, c.min_spm_bplus_count, c.per_capita_ceiling), (None, None, None))
        self.assertEqual(c.criteria, criteria.from_legacy(c))
        self.assertEqual(criteria_read.income_ceilings(c)[:2], (5860, None))
        self.assertIsNone(r.data['requirements']['per_capita_ceiling'])
        self.assertNotIn('rules_error', r.data['requirements'])
