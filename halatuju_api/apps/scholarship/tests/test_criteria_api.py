"""Criteria editor Sprint 3 - the admin API for the criteria tree (`views_admin.criteria_tree`).

Proves: GET serves the tree the gate reads (stored, else today's column meaning) on both routes;
PATCH replaces the whole tree, rewrites the old columns to say it (so the old form and every reader
agree), audits old and new, and is a true no-op (nothing saved, nothing logged, every reader the
same) for the four live intake shapes; every bad tree is a 400 and is never saved; a refused stored
tree, an unbuilt (NULL) row and a moved rule year are 409s; another tenant's intake is a 404 and a
member without `programmes.edit` a 403. Also TD-774 items 1-4: the old form refuses to rebuild a
tree its columns cannot say; a non-dict stored value is refused, never read from the columns; the
IC-hold wording; an open intake whose rules are refused is flagged (`rules_error_open`)."""
import json
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import birth_state, criteria, criteria_write
from apps.scholarship.criteria_read import column_values
from apps.scholarship.models import ScholarshipCohort
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_cohort, make_programme,
)
from apps.scholarship.tests.test_criteria import (
    COHORT_1, COHORT_3, COHORT_4, COHORT_5, PENINSULA, gc, post, results, spm,
)
from apps.scholarship.views_admin.gifts import _requirements_row
from apps.scholarship.views_admin.sponsors import _HELD_BY_RULES_ERROR

LIVE = {'1': COHORT_1, '3': COHORT_3, '4': COHORT_4, '5': COHORT_5}
LOG = 'apps.scholarship.views_admin'


def pngk(v):
    return {'test': 'min_pngk', 'value': v}


def income(mode, hh, pc):
    return {'section': 'income', mode: [{'test': 'household_income_max', 'rm': hh},
                                       {'test': 'income_per_person_under', 'rm': pc}]}


#: A tree the old columns can say exactly.
GOOD = {'all': [results('own', post(pngk(3.0))), income('any', 5000, 900)]}
#: A tree they cannot: both income lines must pass ('all').
BEYOND = {'all': [results('own', post(pngk(3.0))), income('all', 5000, 900)]}
BAD_STORED = {'all': [{'section': 'nonsense'}]}


def columns_of(c):
    return {k: v for k, v in vars(c).items() if k != 'code'}


def readers(c):
    """Every reader the brief names, read off a fresh row."""
    c = ScholarshipCohort.objects.get(pk=c.pk)
    return (column_values(c), birth_state.cohort_rule(c), criteria.tree_of(c), _requirements_row(c))


# ── The write checks, unit by unit ─────────────────────────────────────────────────────────

BAD_TREES = {
    'not a dict': [],
    'unknown top key': {**GOOD, 'extra': 1},
    'unknown section': {'all': [{'section': 'nonsense', 'any': [1]}]},
    'empty section': {'all': [{'section': 'income', 'any': []}]},
    'unknown test': {'all': [{'section': 'income', 'any': [{'test': 'wealth', 'rm': 1}]}]},
    'negative pngk': {'all': [results('own', post(pngk(-1)))]},
    'pngk a string': {'all': [results('own', post(pngk('3.0')))]},
    'pngk a bool': {'all': [results('own', post(pngk(True)))]},
    'pngk over the scale': {'all': [results('own', post(pngk(30)))]},
    'merit over the scale': {'all': [{'section': 'merit', 'all': [{'test': 'min_merit', 'value': 800}]}]},
    'unknown grade': {'all': [results('own', spm(gc(3, 'Z')))]},
    'count over the guard': {'all': [results('own', spm(gc(21, 'C')))]},
    'count a fraction': {'all': [results('own', spm(gc(2.5, 'C')))]},
    'rm not whole': {'all': [income('any', 5860.5, 900)]},
    'rm too large': {'all': [income('any', 58600000, 900)]},
    'unknown state': {'all': [{'section': 'born_in', 'any': ['atlantis']}]},
    'repeated state': {'all': [{'section': 'born_in', 'any': ['sabah', 'sabah']}]},
    'repeated section': {'all': [income('any', 5000, 900), income('any', 5000, 900)]},
    'void spm door': {'all': [results('any', post(pngk(2.0)), spm(gc(0, 'C')))]},
    'empty tree': {'all': []},
    'flag only': {'all': [], 'flag': [{'test': 'course_start_year', 'allowed': [2026]}]},
    'years out of order': {'all': GOOD['all'], 'flag': [{'test': 'course_start_year', 'allowed': [2026, 2025]}]},
    'years repeated': {'all': GOOD['all'], 'flag': [{'test': 'course_start_year', 'allowed': [2026, 2026]}]},
    'years as text': {'all': GOOD['all'], 'flag': [{'test': 'course_start_year', 'allowed': ['2026']}]},
}


class TestWriteProblems(SimpleTestCase):
    def test_good_trees_pass(self):
        for tree in (GOOD, BEYOND, *(criteria.from_legacy(c) for c in LIVE.values())):
            with self.subTest(tree=tree):
                self.assertEqual(criteria_write.write_problems(tree), [])

    def test_every_bad_class_is_refused(self):
        for name, tree in BAD_TREES.items():
            with self.subTest(case=name):
                self.assertTrue(criteria_write.write_problems(tree))

    def test_non_finite_numbers_are_refused(self):
        for v in (float('inf'), float('nan')):
            with self.subTest(v=v):
                self.assertTrue(criteria_write.write_problems({'all': [results('own', post(pngk(v)))]}))

    def test_the_boundaries_pass(self):
        edge = {'all': [results('own', post(pngk(4.0)), spm(gc(20, 'A+'))),
                        {'section': 'merit', 'all': [{'test': 'min_merit', 'value': 100}]},
                        income('any', 100_000, 0)]}
        self.assertEqual(criteria_write.write_problems(edge), [])

    def test_columns_and_beyond(self):
        self.assertFalse(criteria_write.says_more_than_columns(GOOD))
        self.assertTrue(criteria_write.says_more_than_columns(BEYOND))
        cols = criteria_write.columns_for(GOOD)
        self.assertEqual((cols['min_stpm_pngk'], cols['income_ceiling'], cols['per_capita_ceiling']),
                         (3.0, 5000, 900))
        for c in LIVE.values():
            self.assertFalse(criteria_write.says_more_than_columns(criteria.from_legacy(c)))


class TestANonDictStoredValueIsRefused(SimpleTestCase):
    """TD-774 item 2: a hand-edited list, string or number is a stored tree that is refused,
    never quietly read from the columns. Only NULL reads the columns."""

    def test_tree_of_refuses_every_non_dict(self):
        for value in ([], ['x'], 'x', 5, 1.5, True):
            with self.subTest(value=value), self.assertLogs('apps.scholarship.criteria', 'ERROR'):
                with self.assertRaises(criteria.StoredTreeRefused):
                    criteria.tree_of(SimpleNamespace(**vars(COHORT_4), criteria=value, id=1))

    def test_null_reads_the_columns(self):
        c = SimpleNamespace(**vars(COHORT_4), criteria=None)
        self.assertEqual(criteria.tree_of(c), criteria.from_legacy(c, keep_empty_spm=True))


class TestTheIcHoldWording(SimpleTestCase):
    def test_item_3(self):
        # TD-774 item 3: a technical correction, never "re-save the rules" from blank boxes.
        self.assertIn('needs a technical correction', _HELD_BY_RULES_ERROR)
        self.assertNotIn('save', _HELD_BY_RULES_ERROR.lower())


# ── The endpoints ──────────────────────────────────────────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.admin = make_admin('org_admin', owning_org=cls.programme.organisation)

    def setUp(self):
        self.client = authed_client(self.admin)

    def _cohort(self, shape=COHORT_4, stored=True, **kw):
        c = make_cohort(programme=self.programme, is_open=False, **{**columns_of(shape), **kw})
        if stored:
            ScholarshipCohort.objects.filter(pk=c.pk).update(criteria=criteria.from_legacy(c))
            c.refresh_from_db()
        return c

    def _url(self, c):
        return f'/api/v1/admin/scholarship/intake-years/{c.id}/criteria/'

    def _rule_url(self, p=None):
        return f'/api/v1/admin/scholarship/programmes/{(p or self.programme).id}/criteria/'

    def _send(self, url, c, body):
        """PATCH ``body`` with the digest of ``c``'s stored tree as it is NOW (the screen's GET)."""
        digest = criteria_write.digest(ScholarshipCohort.objects.get(pk=c.pk).criteria)
        return self.client.patch(url, {**body, 'digest': digest}, format='json')

    def _old_form(self, c, body):
        return self.client.patch(f'/api/v1/admin/scholarship/intake-years/{c.id}/', body, format='json')


class TestGetOneIntake(_Base):
    def test_a_stored_tree_is_served(self):
        c = self._cohort(COHORT_3)
        r = self.client.get(self._url(c))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {
            'intake': {'id': c.id, 'code': c.code, 'name': c.name, 'year': c.year, 'is_open': False},
            'stored': True, 'criteria': criteria.from_legacy(c), 'rules_error': False,
            'beyond_columns': False, 'digest': criteria_write.digest(c.criteria)})

    def test_a_null_row_serves_todays_column_meaning(self):
        c = self._cohort(COHORT_5, stored=False)
        r = self.client.get(self._url(c))
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['stored'], r.data['beyond_columns']), (False, False))
        self.assertEqual(r.data['criteria'], criteria.from_legacy(c, keep_empty_spm=True))

    def test_a_refused_stored_tree_is_served_as_an_error_never_a_guess(self):
        c = self._cohort()
        for value in (BAD_STORED, [], 'x', 5):
            with self.subTest(value=value):
                ScholarshipCohort.objects.filter(pk=c.pk).update(criteria=value)
                r = self.client.get(self._url(c))
                self.assertEqual(r.status_code, 200)
                self.assertEqual((r.data['stored'], r.data['criteria'], r.data['rules_error']),
                                 (True, None, True))
                self.assertTrue(r.data['problems'])

    def test_a_tree_beyond_the_columns_says_so(self):
        c = self._cohort()
        ScholarshipCohort.objects.filter(pk=c.pk).update(criteria=BEYOND)
        r = self.client.get(self._url(c))
        self.assertEqual((r.data['criteria'], r.data['beyond_columns']), (BEYOND, True))


class TestPatchOneIntake(_Base):
    def test_a_no_op_patch_changes_nothing_for_every_live_shape(self):
        for name, shape in LIVE.items():
            with self.subTest(intake=name):
                c = self._cohort(shape)
                before = readers(c)
                with self.assertNoLogs(LOG, 'INFO'):
                    r = self._send(self._url(c), c, {'criteria': criteria.from_legacy(c)})
                self.assertEqual(r.status_code, 200, r.data)
                self.assertIs(r.data['changed'], False)
                self.assertEqual(readers(c), before)

    def test_a_save_rewrites_the_columns_and_audits_old_and_new(self):
        c = self._cohort(COHORT_4)
        old = c.criteria
        with self.assertLogs(LOG, 'INFO') as logs:
            r = self._send(self._url(c), c, {'criteria': GOOD})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['changed'], r.data['criteria'], r.data['beyond_columns']), (True, GOOD, False))
        c.refresh_from_db()
        self.assertEqual(c.criteria, GOOD)
        self.assertEqual((c.min_stpm_pngk, c.min_spm_credit_count, c.income_ceiling, c.per_capita_ceiling),
                         (3.0, None, 5000, 900))
        self.assertEqual(criteria.from_legacy(c), GOOD)   # the old form reads the same rules
        self.assertEqual(column_values(c), criteria_write.columns_for(GOOD))
        updated, tree_set = logs.output
        self.assertIn(f'AUDIT intake_year_updated cohort={c.code} fields=', updated)
        self.assertIn('criteria', updated)
        self.assertIn(f'AUDIT intake_year_criteria_set cohort={c.code} '
                      f'old={json.dumps(old, sort_keys=True, separators=(",", ":"))} '
                      f'new={json.dumps(GOOD, sort_keys=True, separators=(",", ":"))} by=', tree_set)
        # ...and the old form keeps working on the saved tree.
        r = self._old_form(c, {'income_ceiling': 6000})
        self.assertEqual(r.status_code, 200, r.data)
        c.refresh_from_db()
        self.assertEqual(c.criteria, criteria.from_legacy(c))

    def test_born_in_and_start_years_reach_their_columns(self):
        c = self._cohort(COHORT_1)
        tree = {'all': [*GOOD['all'], {'section': 'born_in', 'any': ['sabah', 'wp_labuan']}],
                'flag': [{'test': 'course_start_year', 'allowed': [2025, 2026]}]}
        r = self._send(self._url(c), c, {'criteria': tree})
        self.assertEqual(r.status_code, 200, r.data)
        c.refresh_from_db()
        self.assertEqual((c.allowed_birth_states, c.allowed_start_years), (['sabah', 'wp_labuan'], [2025, 2026]))
        self.assertEqual(birth_state.stored_keys(birth_state.cohort_rule(c)), ['sabah', 'wp_labuan'])

    def test_a_tree_beyond_the_columns_saves_whole_and_the_old_form_then_refuses(self):
        c = self._cohort()
        r = self._send(self._url(c), c, {'criteria': BEYOND})
        self.assertEqual((r.status_code, r.data['beyond_columns']), (200, True))
        c.refresh_from_db()
        self.assertEqual(c.criteria, BEYOND)
        with self.assertLogs(LOG, 'ERROR'):
            r = self._old_form(c, {'income_ceiling': 6000})
        self.assertEqual((r.status_code, r.data['code']), (409, 'rules_beyond_columns'))
        c.refresh_from_db()
        self.assertEqual((c.criteria, c.income_ceiling), (BEYOND, 5000))
        self.assertEqual(self._old_form(c, {'name': 'Renamed'}).status_code, 200)

    def test_every_bad_tree_is_a_400_and_never_saved(self):
        c = self._cohort()
        before = (c.criteria, column_values(c))
        for name, tree in BAD_TREES.items():
            with self.subTest(case=name):
                r = self._send(self._url(c), c, {'criteria': tree})
                self.assertEqual((r.status_code, r.data['code']), (400, 'bad_criteria'))
                self.assertTrue(r.data['problems'])
                c.refresh_from_db()
                self.assertEqual((c.criteria, column_values(c)), before)

    def test_an_infinite_number_is_a_400(self):
        c = self._cohort()
        body = ('{"criteria": {"all": [{"section": "results", "own": [{"route": "post_spm", '
                '"all": [{"test": "min_pngk", "value": 1e999}]}]}]}, '
                f'"digest": "{criteria_write.digest(c.criteria)}"}}')
        r = self.client.patch(self._url(c), body, content_type='application/json')
        self.assertEqual(r.status_code, 400)
        c.refresh_from_db()
        self.assertEqual(c.criteria, criteria.from_legacy(c))

    def test_bad_bodies(self):
        c = self._cohort()
        d = criteria_write.digest(c.criteria)
        for body, code in (([1, 2], 'criteria_required'), ({}, 'criteria_required'),
                           ({'digest': d}, 'criteria_required'),
                           ({'tree': GOOD}, 'unknown_field'),
                           ({'criteria': GOOD, 'min_stpm_pngk': 2.0}, 'unknown_field'),
                           ({'criteria': GOOD}, 'digest_required'),
                           ({'criteria': GOOD, 'digest': ''}, 'digest_required'),
                           ({'criteria': GOOD, 'digest': 5}, 'digest_required'),
                           ({'criteria': None, 'digest': d}, 'bad_criteria')):
            with self.subTest(body=body):
                r = self.client.patch(self._url(c), body, format='json')
                self.assertEqual((r.status_code, r.data['code']), (400, code))
        r = self.client.patch(self._url(c), {'tree': 1, 'zz': 2}, format='json')
        self.assertEqual(r.data['fields'], ['tree', 'zz'])

    def test_a_refused_stored_tree_is_a_409_and_audited(self):
        c = self._cohort()
        for value in (BAD_STORED, [], 'x', 5):
            with self.subTest(value=value):
                ScholarshipCohort.objects.filter(pk=c.pk).update(criteria=value)
                with self.assertLogs(LOG, 'ERROR') as logs:
                    r = self._send(self._url(c), c, {'criteria': GOOD})
                self.assertEqual((r.status_code, r.data['code']), (409, 'rules_error'))
                self.assertIn('intake_year_rules_error_refused', logs.output[0])
                self.assertIn('action=criteria', logs.output[0])
                c.refresh_from_db()
                self.assertEqual(c.criteria, value)

    def test_a_null_row_is_a_409_until_the_build(self):
        c = self._cohort(stored=False)
        r = self._send(self._url(c), c, {'criteria': GOOD})
        self.assertEqual((r.status_code, r.data['code']), (409, 'criteria_not_built'))
        c.refresh_from_db()
        self.assertIsNone(c.criteria)


class TestTheRuleYearRoute(_Base):
    def test_no_year_is_a_404(self):
        p = make_programme(organisation=self.programme.organisation)
        r = self.client.get(self._rule_url(p))
        self.assertEqual((r.status_code, r.data['code']), (404, 'no_intake_year'))

    def test_the_open_year_else_the_newest(self):
        old = self._cohort(year=2026, code='rule-2026')
        new = self._cohort(year=2027, code='rule-2027')
        self.assertEqual(self.client.get(self._rule_url()).data['intake']['id'], new.id)
        ScholarshipCohort.objects.filter(pk=old.pk).update(is_open=True)
        r = self.client.get(self._rule_url())
        self.assertEqual((r.data['intake']['id'], r.data['intake']['is_open']), (old.id, True))

    def test_patch_names_the_year_it_means(self):
        old = self._cohort(year=2026, code='rule-a')
        new = self._cohort(year=2027, code='rule-b')
        for body in ({'criteria': GOOD}, {'criteria': GOOD, 'intake_id': str(new.id)},
                     {'criteria': GOOD, 'intake_id': True}):
            with self.subTest(body=body):
                r = self._send(self._rule_url(), new, body)
                self.assertEqual((r.status_code, r.data['code']), (400, 'intake_id_required'))
        r = self._send(self._rule_url(), old, {'criteria': GOOD, 'intake_id': old.id})
        self.assertEqual((r.status_code, r.data['code'], r.data['intake_id']), (409, 'rule_year_changed', new.id))
        r = self._send(self._rule_url(), new, {'criteria': GOOD, 'intake_id': new.id})
        self.assertEqual((r.status_code, r.data['changed']), (200, True))
        new.refresh_from_db(); old.refresh_from_db()
        self.assertEqual(new.criteria, GOOD)
        self.assertEqual(old.criteria, criteria.from_legacy(old))

    def test_a_no_op_patch_on_the_rule_year(self):
        c = self._cohort(COHORT_5)
        before = readers(c)
        r = self._send(self._rule_url(), c, {'criteria': criteria.from_legacy(c), 'intake_id': c.id})
        self.assertEqual((r.status_code, r.data['changed']), (200, False))
        self.assertEqual(readers(c), before)

    def test_a_bad_tree_is_a_400_before_the_year_check(self):
        c = self._cohort()
        r = self._send(self._rule_url(), c, {'criteria': {'all': []}, 'intake_id': c.id + 999})
        self.assertEqual((r.status_code, r.data['code']), (400, 'bad_criteria'))


class TestWhoMay(_Base):
    def test_a_member_without_programmes_edit_gets_403(self):
        c = self._cohort()
        member = authed_client(make_admin('reviewer', owning_org=self.programme.organisation))
        for url in (self._url(c), self._rule_url()):
            with self.subTest(url=url):
                self.assertEqual(member.get(url).status_code, 403)
                self.assertEqual(member.patch(url, {'criteria': GOOD}, format='json').status_code, 403)
        c.refresh_from_db()
        self.assertEqual(c.criteria, criteria.from_legacy(c))

    def test_another_tenants_intake_is_a_404_whatever_the_body(self):
        other = make_programme()
        c = make_cohort(programme=other, **columns_of(COHORT_4))
        for url in (self._url(c), self._rule_url(other)):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.patch(url, [1], format='json').status_code, 404)
                self.assertEqual(self.client.patch(url, {'criteria': GOOD}, format='json').status_code, 404)


class TestTheOldFormAndItems1And4(_Base):
    def test_item_1_a_tree_the_columns_cannot_say_is_not_rebuilt(self):
        c = self._cohort()
        ScholarshipCohort.objects.filter(pk=c.pk).update(criteria={'all': []})
        with self.assertLogs(LOG, 'ERROR'):
            r = self._old_form(c, {'min_stpm_pngk': 2.75})
        self.assertEqual((r.status_code, r.data['code']), (409, 'rules_beyond_columns'))
        c.refresh_from_db()
        self.assertEqual((c.criteria, c.min_stpm_pngk), ({'all': []}, 2.0))

    def test_item_2_a_non_dict_stored_value_blocks_the_old_form_and_opening(self):
        c = self._cohort()
        for value in ([], 'x', 5):
            with self.subTest(value=value):
                ScholarshipCohort.objects.filter(pk=c.pk).update(criteria=value)
                with self.assertLogs(LOG, 'ERROR'):
                    r = self._old_form(c, {'min_stpm_pngk': 2.75})
                self.assertEqual((r.status_code, r.data['code']), (409, 'rules_error'))
                with self.assertLogs(LOG, 'ERROR'):
                    r = self._old_form(c, {'is_open': True})
                self.assertEqual((r.status_code, r.data['code']), (409, 'rules_error'))
                c.refresh_from_db()
                self.assertEqual((c.criteria, c.is_open, c.min_stpm_pngk), (value, False, 2.0))

    def test_item_4_an_open_intake_with_refused_rules_is_flagged_and_can_close(self):
        bad = self._cohort(code='flag-bad')
        good = self._cohort(code='flag-good', year=2025)
        ScholarshipCohort.objects.filter(pk=bad.pk).update(criteria=BAD_STORED, is_open=True)
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            r = self.client.get(f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/')
        rows = {y['code']: y for y in r.data['years']}
        self.assertIs(rows['flag-bad']['rules_error_open'], True)
        self.assertIs(rows['flag-good']['rules_error_open'], False)
        with self.assertLogs('apps.scholarship.criteria', 'ERROR'):
            r = self._old_form(bad, {'is_open': False})
        self.assertEqual(r.status_code, 200)
        self.assertIs(r.data['rules_error_open'], False)
        self.assertIs(r.data['requirements']['rules_error'], True)   # still refused, now closed
        ScholarshipCohort.objects.filter(pk=good.pk).update(is_open=True)
        r = self.client.get(f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/')
        self.assertIs({y['code']: y for y in r.data['years']}['flag-good']['rules_error_open'], False)


# ── Review R1 (Sprint 3) fixes, one regression each ────────────────────────────────────────

def merit(*tests):
    return {'section': 'merit', 'all': list(tests)}


#: The reviewer's blocker: a post-SPM group with no floor beside an SPM group.
NO_FLOOR = {'all': [results('own', post(), spm(gc(5, 'A-')))]}


class TestReviewR1WriteChecks(SimpleTestCase):
    def test_blocker_1_a_post_spm_group_with_no_floor_is_refused(self):
        self.assertEqual(criteria_write.write_problems(NO_FLOOR), [criteria_write.NO_PNGK_FLOOR])
        self.assertIn(criteria_write.NO_PNGK_FLOOR, criteria_write.write_problems(
            {'all': [results('any', post(), spm(gc(5, 'A-')))]}))

    def test_blocker_1_a_post_spm_merit_needs_a_floor(self):
        for tree in ({'all': [results('own', spm(gc(5, 'A-'))), merit({'test': 'min_merit', 'value': 60})]},
                     {'all': [merit({'test': 'min_merit', 'value': 60})]},
                     {'all': [income('any', 5000, 900), merit({'test': 'min_upu_merit', 'value': 70},
                                                               {'test': 'min_merit', 'value': 60})]}):
            with self.subTest(tree=tree):
                self.assertIn(criteria_write.MERIT_NEEDS_FLOOR, criteria_write.write_problems(tree))
        ok = {'all': [results('own', post(pngk(2.5)), spm(gc(5, 'A-'))), merit({'test': 'min_merit', 'value': 60})]}
        self.assertEqual(criteria_write.write_problems(ok), [])

    def test_blocker_1_every_live_shape_still_passes(self):
        for name, c in LIVE.items():
            with self.subTest(intake=name):
                self.assertEqual(criteria_write.write_problems(criteria.from_legacy(c)), [])
                self.assertEqual(criteria_write.empty_problems(criteria.from_legacy(c)), [])

    def test_should_fix_2_a_results_section_with_no_rule_is_refused_without_a_merit(self):
        for tree in ({'all': [results('own', spm())]}, {'all': [results('any', spm()), income('any', 5000, 900)]}):
            with self.subTest(tree=tree):
                self.assertEqual(criteria_write.write_problems(tree), [criteria_write.NO_RESULTS_RULE])
        # from_legacy's own shape: no grade bar, a merit (an SPM group with no rule beside it)
        with_merit = {'all': [results('own', spm()), merit({'test': 'min_upu_merit', 'value': 70})]}
        self.assertEqual(criteria_write.write_problems(with_merit), [])
        c = SimpleNamespace(**{**vars(COHORT_1), 'min_spm_a_count': None, 'min_spm_bplus_count': None,
                               'min_merit_score': 70})
        self.assertEqual(criteria.from_legacy(c)['all'][:2], with_merit['all'])

    def test_minor_6_order_alone_is_not_beyond_the_columns(self):
        c3 = criteria.from_legacy(COHORT_3)
        shuffled = json.loads(json.dumps(c3))
        shuffled['all'].reverse()
        for s in shuffled['all']:
            mode = next(k for k in s if k != 'section')
            s[mode].reverse()
            if s['section'] == 'results':
                for g in s[mode]:
                    g['all'].reverse()
        shuffled['flag'] = []
        self.assertNotEqual(shuffled, c3)
        self.assertEqual(criteria_write.write_problems(shuffled), [])
        self.assertTrue(criteria_write.same_tree(shuffled, c3))
        self.assertFalse(criteria_write.says_more_than_columns(shuffled))
        self.assertTrue(criteria_write.says_more_than_columns(BEYOND))
        self.assertFalse(criteria_write.same_tree(c3, criteria.from_legacy(COHORT_4)))

    def test_should_fix_5_the_digest_is_exact(self):
        self.assertEqual(criteria_write.digest(GOOD), criteria_write.digest(json.loads(json.dumps(GOOD))))
        self.assertNotEqual(criteria_write.digest(GOOD), criteria_write.digest(BEYOND))
        self.assertNotEqual(criteria_write.digest(None), criteria_write.digest({'all': []}))
        self.assertEqual(len(criteria_write.digest(None)), 64)


class TestReviewR1Endpoints(_Base):
    def test_blocker_1_the_reviewers_tree_is_a_400_and_never_saved(self):
        c = self._cohort()
        r = self._send(self._url(c), c, {'criteria': NO_FLOOR})
        self.assertEqual((r.status_code, r.data['code'], r.data['problems']),
                         (400, 'bad_criteria', [criteria_write.NO_PNGK_FLOOR]))
        c.refresh_from_db()
        self.assertEqual(c.criteria, criteria.from_legacy(c))

    def test_should_fix_2_the_old_form_cannot_clear_every_rule(self):
        c = self._cohort(COHORT_4)
        before = c.criteria
        clear = {f: None for f in ('min_spm_a_count', 'min_spm_bplus_count', 'min_spm_credit_count',
                                   'min_stpm_pngk', 'min_merit_score', 'income_ceiling', 'per_capita_ceiling')}
        r = self._old_form(c, {**clear, 'allowed_birth_states': [], 'allowed_start_years': []})
        self.assertEqual((r.status_code, r.data['code'], r.data['problems']),
                         (400, 'bad_criteria', [criteria_write.EMPTY_TREE]))
        c.refresh_from_db()
        self.assertEqual((c.criteria, c.min_stpm_pngk), (before, 2.0))

    def test_should_fix_2_a_new_year_with_every_box_blank_is_refused(self):
        body = {'code': 'blank-2027', 'name': 'Blank', 'year': 2027,
                'min_spm_a_count': None, 'min_spm_bplus_count': None, 'min_spm_credit_count': None,
                'min_stpm_pngk': None, 'min_merit_score': None, 'income_ceiling': None,
                'per_capita_ceiling': None, 'allowed_birth_states': [], 'allowed_start_years': []}
        r = self.client.post(f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/', body,
                             format='json')
        self.assertEqual((r.status_code, r.data['code'], r.data['problems']),
                         (400, 'bad_criteria', [criteria_write.EMPTY_TREE]))
        self.assertFalse(ScholarshipCohort.objects.filter(code='blank-2027').exists())

    def test_should_fix_5_get_and_patch_serve_the_digest(self):
        c = self._cohort()
        for url in (self._url(c), self._rule_url()):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).data['digest'], criteria_write.digest(c.criteria))
        r = self._send(self._url(c), c, {'criteria': GOOD})
        self.assertEqual((r.status_code, r.data['digest']), (200, criteria_write.digest(GOOD)))

    def test_should_fix_5_a_stale_digest_is_a_409_and_nothing_is_saved(self):
        c = self._cohort()
        seen = self.client.get(self._url(c)).data['digest']
        self.assertEqual(self._old_form(c, {'income_ceiling': 6000}).status_code, 200)   # someone else
        for url, extra in ((self._url(c), {}), (self._rule_url(), {'intake_id': c.id})):
            with self.subTest(url=url):
                r = self.client.patch(url, {'criteria': GOOD, 'digest': seen, **extra}, format='json')
                self.assertEqual((r.status_code, r.data['code']), (409, 'criteria_changed'))
                c.refresh_from_db()
                self.assertEqual((c.criteria, c.income_ceiling), (criteria.from_legacy(c), 6000))
        r = self.client.patch(self._url(c), {'criteria': GOOD, 'digest': criteria_write.digest(c.criteria)},
                              format='json')
        self.assertEqual(r.status_code, 200)

    def test_should_fix_5_the_digest_is_required_on_both_routes(self):
        c = self._cohort()
        for url, extra in ((self._url(c), {}), (self._rule_url(), {'intake_id': c.id})):
            with self.subTest(url=url):
                r = self.client.patch(url, {'criteria': GOOD, **extra}, format='json')
                self.assertEqual((r.status_code, r.data['code']), (400, 'digest_required'))

    def test_minor_6_a_reordered_tree_leaves_the_old_form_working(self):
        c = self._cohort(COHORT_4)
        tree = {'all': list(reversed(c.criteria['all']))}
        r = self._send(self._url(c), c, {'criteria': tree})
        self.assertEqual((r.status_code, r.data['beyond_columns']), (200, False))
        r = self._old_form(c, {'income_ceiling': 6000})
        self.assertEqual(r.status_code, 200, r.data)

    def test_minor_7_the_rule_year_is_chosen_under_the_lock(self):
        from unittest import mock

        from django.db.models.query import QuerySet

        from apps.scholarship.views_admin.criteria_tree import rule_year
        c = self._cohort()
        real = QuerySet.select_for_update
        with mock.patch.object(QuerySet, 'select_for_update', autospec=True,
                               side_effect=lambda qs, *a, **k: real(qs, *a, **k)) as locked:
            self.assertEqual(rule_year(self.programme), c)
            self.assertEqual(locked.call_count, 0)
            self.assertEqual(rule_year(self.programme, lock=True), c)
            self.assertEqual(locked.call_count, 1)
            self.assertIn('programme_id', str(locked.call_args[0][0].query))
            r = self._send(self._rule_url(), c, {'criteria': GOOD, 'intake_id': c.id})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(locked.call_count, 2)


class TestReviewR1Fingerprint(SimpleTestCase):
    def test_should_fix_3_the_income_join_moves_the_fingerprint(self):
        from apps.scholarship import verdict_context

        def values(tree):
            cohort = SimpleNamespace(**{**vars(COHORT_4), 'year': 2026}, criteria=tree, id=1)
            return verdict_context.intake_values(SimpleNamespace(cohort_id=1, cohort=cohort))
        anyj, allj = values(GOOD), values(BEYOND)
        self.assertNotIn('income_mode', anyj)
        self.assertEqual(allj['income_mode'], 'all')
        self.assertEqual({k: v for k, v in allj.items() if k != 'income_mode'}, anyj)
