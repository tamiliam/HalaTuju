"""Criteria fix round 3 (review R2, blocker 1 and should-fix 2): a new intake year created WITH
its criteria tree (`AdminIntakeYearListView.post`, body key ``criteria``).

Proves: the tree is checked by the criteria PATCH's own check (`criteria_tree.tree_refusal`), and
a refused tree saves no year and writes no audit line; the year, the tree, the columns that say it
and the audit lines are one write (a failure after the save leaves no year); after the create the
stored tree is the one sent and the columns are `criteria_write.columns_for` of it; a tree the
columns cannot say (an 'all' income join, a grade count at A+, A, B or C+) is stored whole; a tree
sent with requirement keys is refused, never reconciled; the org fence holds; a create without a
tree is today's behaviour."""
import json
from unittest import mock

from django.test import TestCase, override_settings

from apps.scholarship import criteria, criteria_write
from apps.scholarship.criteria_read import column_values
from apps.scholarship.models import ScholarshipCohort
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_programme,
)
from apps.scholarship.tests.test_criteria import gc, post, results, spm
from apps.scholarship.tests.test_criteria_api import BAD_TREES, BEYOND, GOOD, LOG

COLUMN_KEYS = ('min_spm_a_count', 'min_spm_bplus_count', 'min_spm_credit_count', 'min_stpm_pngk',
               'min_merit_score', 'income_ceiling', 'per_capita_ceiling')


def compact(tree):
    return json.dumps(tree, sort_keys=True, separators=(',', ':'))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestCreateWithATree(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.admin = make_admin('org_admin', owning_org=cls.programme.organisation)

    def setUp(self):
        self.client = authed_client(self.admin)

    def _create(self, tree=None, programme=None, code='new-2027', **extra):
        body = {'code': code, 'name': 'Intake 2027', 'year': 2027, **extra}
        if tree is not None:
            body['criteria'] = tree
        return self.client.post(
            f'/api/v1/admin/scholarship/programmes/{(programme or self.programme).id}/years/',
            body, format='json')

    def _nothing_saved(self, code='new-2027'):
        self.assertFalse(ScholarshipCohort.objects.filter(code=code).exists())

    def test_a_refused_tree_saves_no_year_and_no_audit_line(self):
        for name, tree in {**BAD_TREES, 'empty': {'all': []}, 'null': None}.items():
            with self.subTest(tree=name):
                body = {'code': 'new-2027', 'name': 'Intake 2027', 'year': 2027, 'criteria': tree}
                with self.assertNoLogs(LOG, 'INFO'):
                    r = self.client.post(
                        f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/',
                        body, format='json')
                self.assertEqual((r.status_code, r.data['code']), (400, 'bad_criteria'), r.data)
                self.assertTrue(r.data['problems'])
                self._nothing_saved()

    def test_the_refusal_is_the_patchs_own(self):
        # The same problems, word for word, as the criteria PATCH gives for the same tree.
        tree = BAD_TREES[next(iter(BAD_TREES))]
        r = self._create(tree)
        self.assertEqual(r.data['problems'], criteria_write.write_problems(tree))

    def test_after_create_the_tree_and_the_columns_match(self):
        with self.assertLogs(LOG, 'INFO') as logs:
            r = self._create(GOOD)
        self.assertEqual(r.status_code, 201, r.data)
        c = ScholarshipCohort.objects.get(code='new-2027')
        self.assertEqual(c.criteria, GOOD)
        self.assertEqual(column_values(c), criteria_write.columns_for(GOOD))
        self.assertEqual((c.min_stpm_pngk, c.income_ceiling, c.per_capita_ceiling), (3.0, 5000, 900))
        self.assertEqual(criteria.from_legacy(c), GOOD)       # the old form reads the same rules
        self.assertEqual((c.is_open, c.programme_id, c.owning_organisation_id),
                         (False, self.programme.id, self.programme.organisation_id))
        created, tree_set = logs.output
        self.assertIn('AUDIT intake_year_created cohort=new-2027 programme=', created)
        self.assertIn(f'AUDIT intake_year_criteria_set cohort=new-2027 old=null new={compact(GOOD)} by=',
                      tree_set)
        # The row served back says the columns the tree wrote.
        self.assertEqual(r.data['requirements']['income_ceiling'], 5000)

    def test_a_tree_the_columns_cannot_say_is_stored_whole(self):
        r = self._create(BEYOND)
        self.assertEqual(r.status_code, 201, r.data)
        c = ScholarshipCohort.objects.get(code='new-2027')
        self.assertEqual(c.criteria, BEYOND)
        self.assertEqual(column_values(c), criteria_write.columns_for(BEYOND))
        got = self.client.get(f'/api/v1/admin/scholarship/intake-years/{c.id}/criteria/')
        self.assertEqual((got.data['criteria'], got.data['beyond_columns']), (BEYOND, True))

    def test_should_fix_2_grade_rules_only_at_a_plus_a_b_or_c_plus_now_save(self):
        for grade in ('A+', 'A', 'B', 'C+'):
            with self.subTest(grade=grade):
                code = 'g-' + grade.replace('+', 'p').lower()
                tree = {'all': [results('own', spm(gc(5, grade)))]}
                # The root of should-fix 2: said in the columns alone, this rule is lost, the year
                # would check nothing, and the old create refuses it as an empty tree.
                old = self._create(code=code, **criteria_write.columns_for(tree))
                self.assertEqual((old.status_code, old.data['code']), (400, 'bad_criteria'))
                r = self._create(tree, code=code)
                self.assertEqual(r.status_code, 201, r.data)
                c = ScholarshipCohort.objects.get(code=code)
                self.assertEqual(c.criteria, tree)
                self.assertEqual(column_values(c), criteria_write.columns_for(tree))

    def test_a_post_spm_floor_with_an_spm_grade_rule(self):
        tree = {'all': [results('own', post({'test': 'min_pngk', 'value': 3.0}), spm(gc(5, 'A')))]}
        r = self._create(tree)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(ScholarshipCohort.objects.get(code='new-2027').criteria, tree)

    def test_a_tree_with_requirement_keys_is_refused_whole(self):
        with self.assertNoLogs(LOG, 'INFO'):
            r = self._create(GOOD, income_ceiling=9000, allowed_birth_states=[])
        self.assertEqual((r.status_code, r.data['code']), (400, 'criteria_with_requirements'))
        self.assertEqual(r.data['fields'], ['income_ceiling', 'allowed_birth_states'])
        self._nothing_saved()

    def test_the_other_refusals_still_come_first_and_save_nothing(self):
        r = self._create(GOOD, code='Bad Code')
        self.assertEqual(r.data['code'], 'bad_code')
        r = self._create(GOOD, opens_on='2027-02-01', closes_on='2027-01-01')
        self.assertEqual(r.data['code'], 'window_backwards')
        self._nothing_saved()

    def test_a_failure_after_the_save_leaves_no_year(self):
        with mock.patch('apps.scholarship.views_admin.criteria_tree.audit_tree_set',
                        side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self._create(GOOD)
        self._nothing_saved()

    def test_another_tenants_gift_is_a_404_and_saves_nothing(self):
        other = make_programme()
        r = self._create(GOOD, programme=other)
        self.assertEqual(r.status_code, 404)
        self._nothing_saved()

    def test_without_a_tree_the_create_is_todays(self):
        r = self._create()
        self.assertEqual((r.status_code, r.data['code']), (400, 'missing_requirement'))
        cols = {**{k: None for k in COLUMN_KEYS}, 'min_stpm_pngk': 2.5,
                'allowed_birth_states': [], 'allowed_start_years': []}
        r = self._create(**cols)
        self.assertEqual(r.status_code, 201, r.data)
        c = ScholarshipCohort.objects.get(code='new-2027')
        self.assertEqual(c.criteria, criteria.from_legacy(c))
