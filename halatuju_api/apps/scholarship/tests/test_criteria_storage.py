"""Criteria editor Sprint 2 - the stored tree (`ScholarshipCohort.criteria`).

Proves: a NULL tree keeps today's meaning (`tree_of` falls back to `from_legacy(keep_empty_spm=True)`,
the columns gate exactly); the gate (`shortlisting.evaluate`) reads the STORED tree; migration 0219's
fill and `build_criteria_trees` store `from_legacy` on NULL rows only and refuse whole;
`rescore_pending_decisions` HOLDS an already-scored decision a STORED tree would change (owner ruling
6); and the old admin form rebuilds a stored tree on save but leaves a NULL one NULL (review R1)."""
import importlib
from io import StringIO

from django.apps import apps as django_apps
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.scholarship import criteria, shortlisting
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import rescore_pending_decisions, score_application
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
    make_student,
)

MID = {'bm': 'A-', 'eng': 'B+', 'math': 'C', 'hist': 'C+', 'moral': 'D'}
STRONG = {f's{i}': 'A' for i in range(8)}
INCOME = dict(household_income=2500, household_size=5, receives_str=True)
STPM_LOW = dict(exam_type='stpm', stpm_cgpa=1.9, spm_prereq_grades=MID, results_exam_type='stpm',
                completed_qualifications=['spm', 'stpm'])


def _apply(cohort, **profile):
    student = make_student(**INCOME, **profile)
    return make_application(cohort=cohort, student=student, consent_to_contact=True, intends_tertiary_2026=True)


def _no_results(tree):
    return {**tree, 'all': [s for s in tree['all'] if s['section'] not in ('results', 'merit')]}


class TestTheGateReadsTheStoredTree(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(min_stpm_pngk=2.0, min_spm_credit_count=3, min_spm_a_count=0,
                                 min_spm_bplus_count=0, min_merit_score=0, income_ceiling=5860,
                                 per_capita_ceiling=None)
        cls.low = _apply(cls.cohort, **STPM_LOW)

    def test_null_means_the_columns(self):
        self.assertIsNone(self.cohort.criteria)
        self.assertEqual(criteria.tree_of(self.cohort), criteria.from_legacy(self.cohort, keep_empty_spm=True))
        self.assertEqual(shortlisting.evaluate(self.low, self.cohort),
                         shortlisting.evaluate_columns(self.low, self.cohort))
        self.assertEqual(shortlisting.evaluate(self.low, self.cohort).verdict, 'rejected')

    def test_a_stored_tree_is_what_decides(self):
        self.cohort.criteria = _no_results(criteria.from_legacy(self.cohort))
        got = shortlisting.evaluate(self.low, self.cohort)
        self.assertEqual(got, criteria.evaluate(self.low, self.cohort.criteria))
        self.assertNotEqual(got.verdict, 'rejected')
        self.assertEqual(shortlisting.evaluate_columns(self.low, self.cohort).verdict, 'rejected')

    def test_a_stored_empty_tree_is_never_replaced(self):
        self.cohort.criteria = {'all': []}
        self.assertEqual(criteria.tree_of(self.cohort), {'all': []})

    def test_a_refused_stored_tree_is_an_error_never_the_columns(self):
        """TD-774: a stored tree `validate_tree` refuses is logged and raised - the gate never
        quietly judges the intake on its columns instead."""
        for bad in ({'all': [{'section': 'born_in', 'any': ['Sabah']}]},      # wrong-case state
                    {'all': [{'section': 'nonsense', 'any': [1]}]},           # unknown section
                    {'all': 'x'}):                                            # malformed
            with self.subTest(tree=bad):
                self.cohort.criteria = bad
                with self.assertLogs('apps.scholarship.criteria', 'ERROR') as logs, \
                        self.assertRaises(criteria.StoredTreeRefused) as caught:
                    criteria.tree_of(self.cohort)
                self.assertEqual((caught.exception.cohort_id, caught.exception.code),
                                 (self.cohort.id, self.cohort.code))
                self.assertIn(f'intake {self.cohort.id}', logs.output[0])
                with self.assertRaises(criteria.StoredTreeRefused):
                    shortlisting.evaluate(self.low, self.cohort)


class TestTheFill(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = make_cohort(code='fill-a', min_stpm_pngk=2.0, min_spm_credit_count=3)
        cls.b = make_cohort(code='fill-b', min_stpm_pngk=3.0, min_spm_a_count=None, min_spm_bplus_count=None)
        cls.kept = make_cohort(code='fill-kept')
        ScholarshipCohort.objects.filter(pk=cls.kept.pk).update(criteria={'all': []})

    def _trees(self):
        return dict(ScholarshipCohort.objects.values_list('code', 'criteria'))

    def _expect_filled(self):
        trees = self._trees()
        for c in (self.a, self.b):
            self.assertEqual(trees[c.code], criteria.from_legacy(ScholarshipCohort.objects.get(pk=c.pk)))
        self.assertEqual(trees['fill-kept'], {'all': []})

    def test_the_migration_fill_stores_from_legacy_on_null_rows_only(self):
        mig = importlib.import_module('apps.scholarship.migrations.0219_cohort_criteria')
        mig._fill(django_apps, None)
        self._expect_filled()

    def test_the_command_is_a_dry_run_unless_told(self):
        out = StringIO()
        call_command('build_criteria_trees', stdout=out)
        self.assertIn(f'would store: {self.a.id} fill-a', out.getvalue())
        self.assertNotIn('fill-kept', out.getvalue())
        self.assertIsNone(self._trees()['fill-a'])
        out = StringIO()
        call_command('build_criteria_trees', '--apply', stdout=out)
        self.assertIn(f'stored: {self.b.id} fill-b', out.getvalue())
        self._expect_filled()
        out = StringIO()
        call_command('build_criteria_trees', '--apply', stdout=out)
        self.assertIn('stored 0 tree(s)', out.getvalue())

    def test_apply_locks_the_rows_and_a_dry_run_does_not(self):
        """TD-774: --apply reads the intakes with select_for_update (inside its transaction), so an
        admin requirement save cannot commit new columns between the read and the write."""
        from unittest import mock

        from django.db.models.query import QuerySet
        real = QuerySet.select_for_update
        with mock.patch.object(QuerySet, 'select_for_update', autospec=True,
                               side_effect=lambda qs, *a, **k: real(qs, *a, **k)) as locked:
            call_command('build_criteria_trees', stdout=StringIO())
            self.assertEqual(locked.call_count, 0)
            call_command('build_criteria_trees', '--apply', stdout=StringIO())
            self.assertEqual(locked.call_count, 1)
            self.assertIs(locked.call_args[0][0].model, ScholarshipCohort)
        self._expect_filled()

    def test_one_refused_tree_refuses_the_whole_fill(self):
        bad = make_cohort(code='fill-bad', allowed_birth_states=['Sabah'])
        with self.assertRaisesMessage(CommandError, f'{bad.id} fill-bad'):
            call_command('build_criteria_trees', '--apply', stdout=StringIO())
        self.assertIsNone(self._trees()['fill-a'])
        with self.assertRaises(ValueError):
            importlib.import_module('apps.scholarship.migrations.0219_cohort_criteria')._fill(django_apps, None)


class TestRescoreHoldsWhatTheTreeWouldChange(TestCase):
    """Owner ruling 6: existing decisions must not change by the switch to the tree."""

    @classmethod
    def setUpTestData(cls):
        # intake 5's shape: a PNGK floor and no SPM bar (the CGPA trap, switched off by the STORED
        # tree - what `build_criteria_trees --apply` writes; a NULL row keeps today's meaning)
        cls.degree = make_cohort(code='deg-shape', min_stpm_pngk=3.0, min_spm_a_count=None,
                                 min_spm_bplus_count=None, income_ceiling=5860, per_capita_ceiling=1584)
        ScholarshipCohort.objects.filter(pk=cls.degree.pk).update(criteria=criteria.from_legacy(cls.degree))
        cls.degree.refresh_from_db()

    def test_a_null_tree_changes_nothing_before_the_apply(self):
        # Adversarial review R1: the deploy must not switch intake 5. With criteria NULL the gate is
        # today's gate, so rescoring holds and changes nothing.
        ScholarshipCohort.objects.filter(pk=self.degree.pk).update(criteria=None)
        self.degree.refresh_from_db()
        app = _apply(self.degree, exam_type='spm', grades=STRONG)
        self.assertEqual(shortlisting.evaluate(app, self.degree), shortlisting.evaluate_columns(app, self.degree))
        self.assertEqual(shortlisting.evaluate(app, self.degree).verdict, 'shortlisted')
        score_application(app)
        result = rescore_pending_decisions()
        self.assertEqual((result['held'], result['changed']), ([], []))

    def test_an_already_scored_class_b_decision_is_held_and_untouched(self):
        app = _apply(self.degree, exam_type='spm', grades=STRONG)
        old = shortlisting.evaluate_columns(app, self.degree)
        new = shortlisting.evaluate(app, self.degree)
        self.assertNotEqual(old.verdict, new.verdict)
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            verdict=old.verdict, bucket=old.bucket, shortlist_reason=old.reason)
        result = rescore_pending_decisions()
        self.assertEqual(result['held'], [app.id])
        self.assertEqual(result['changed'], [])
        app.refresh_from_db()
        self.assertEqual((app.verdict, app.shortlist_reason), (old.verdict, old.reason))
        out = StringIO()
        call_command('rescore_pending_decisions', stdout=out)
        self.assertIn(f'HELD (stored decision kept; the criteria tree would decide differently): 1 → [{app.id}]',
                      out.getvalue())

    def test_an_unscored_or_fresh_scoring_uses_the_tree(self):
        app = _apply(self.degree, exam_type='spm', grades=STRONG)
        new = shortlisting.evaluate(app, self.degree)
        result = rescore_pending_decisions()
        self.assertEqual(result['held'], [])
        app.refresh_from_db()
        self.assertEqual(app.verdict, new.verdict)
        fresh = _apply(self.degree, exam_type='spm', grades=STRONG)
        self.assertEqual(score_application(fresh).verdict, new.verdict)

    def test_a_decision_both_engines_agree_on_is_rescored_as_before(self):
        app = _apply(self.degree, exam_type='stpm', stpm_cgpa=3.5, spm_prereq_grades=MID,
                     results_exam_type='stpm', completed_qualifications=['spm', 'stpm'])
        score_application(app)
        app.refresh_from_db()
        result = rescore_pending_decisions()
        self.assertEqual((result['held'], result['changed']), ([], []))
        self.assertEqual(result['rescored'], 1)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheOldFormRebuildsTheTree(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.admin = make_admin('org_admin', owning_org=cls.programme.organisation)

    def setUp(self):
        self.client = authed_client(self.admin)

    def _year(self, c):
        return f'/api/v1/admin/scholarship/intake-years/{c.id}/'

    def test_create_leaves_the_tree_null_so_the_boxes_keep_todays_meaning(self):
        # Adversarial review R1: the old form never turns a NULL row into a stored tree (that would
        # switch the CGPA trap off on intake 5's shape without the --apply yes).
        r = self.client.post(f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/',
                             {'code': 'form-new', 'name': 'form-new', 'year': 2027, 'min_stpm_pngk': 2.5,
                              'min_spm_a_count': None, 'min_spm_bplus_count': None},
                             format='json')
        self.assertEqual(r.status_code, 201)
        c = ScholarshipCohort.objects.get(code='form-new')
        self.assertIsNone(c.criteria)
        self.assertEqual(criteria.tree_of(c), criteria.from_legacy(c, keep_empty_spm=True))

    def test_a_requirement_change_on_a_null_row_leaves_it_null(self):
        c = make_cohort(programme=self.programme, is_active=True, is_open=False, code='form-null',
                        min_stpm_pngk=2.0, min_spm_a_count=None, min_spm_bplus_count=None)
        r = self.client.patch(self._year(c), {'min_stpm_pngk': 3.0}, format='json')
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.min_stpm_pngk, 3.0)
        self.assertIsNone(c.criteria)
        groups = criteria.tree_of(c)['all'][0]['own']
        self.assertEqual([g['route'] for g in groups], ['post_spm', 'spm'])   # the trap stays on
        self.assertEqual(groups[0]['all'][0]['value'], 3.0)

    def test_a_requirement_change_rebuilds_and_a_name_change_does_not(self):
        c = make_cohort(programme=self.programme, is_active=True, is_open=False, code='form-old',
                        min_stpm_pngk=2.0)
        ScholarshipCohort.objects.filter(pk=c.pk).update(criteria={'all': []})
        r = self.client.patch(self._year(c), {'name': 'Renamed'}, format='json')
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.criteria, {'all': []})
        r = self.client.patch(self._year(c), {'min_stpm_pngk': 2.75}, format='json')
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.criteria, criteria.from_legacy(c))
        self.assertEqual(criteria.tree_of(c)['all'][0]['own'][0]['all'][0]['value'], 2.75)
