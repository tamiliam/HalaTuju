"""Criteria editor Sprints 1-2 - the read-only replay command (`replay_criteria`).

Proves: the owner-ruled class (b) is found and named, and intakes 3 / 4's shape now agrees exactly
(owner ruling B); the STORED tree is what is compared, and a stored tree that is not its columns'
tree needs a look; the output carries application ids and class names only (no name, NRIC, email,
grade or income); and the run writes nothing - no INSERT / UPDATE / DELETE is sent and no row changes."""
from io import StringIO

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.courses.models import StudentProfile
from apps.scholarship import criteria
from apps.scholarship.management.commands.replay_criteria import CLASS_B, STORED_DIFFERS
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

MID = {'bm': 'A-', 'eng': 'B+', 'math': 'C', 'hist': 'C+', 'moral': 'D'}
STRONG = {f's{i}': 'A' for i in range(8)}
INCOME = dict(household_income=2500, household_size=5, receives_str=True)


def _apply(cohort, **profile):
    student = make_student(**INCOME, **profile)
    return make_application(cohort=cohort, student=student, consent_to_contact=True, intends_tertiary_2026=True)


class TestReplayCommand(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Intakes 3 / 4 shape: a PNGK floor beside an SPM credit bar.
        cls.loose = make_cohort(min_stpm_pngk=2.0, min_spm_credit_count=3, min_spm_a_count=0,
                                min_spm_bplus_count=0, min_merit_score=0, income_ceiling=5860,
                                per_capita_ceiling=None)
        cls.below_floor = _apply(cls.loose, exam_type='stpm', stpm_cgpa=1.9, spm_prereq_grades=MID,
                                 results_exam_type='stpm', completed_qualifications=['spm', 'stpm'],
                                 contact_email='hidden@example.test')
        cls.spm_ok = _apply(cls.loose, exam_type='spm', grades=STRONG)
        # The degree intake's shape: a floor and no SPM bar, so no SPM group (the CGPA trap).
        cls.degree = make_cohort(code='deg-shape', min_stpm_pngk=3.0, min_spm_a_count=None,
                                 min_spm_bplus_count=None, income_ceiling=5860, per_capita_ceiling=1584)
        cls.spm_only = _apply(cls.degree, exam_type='spm', grades=STRONG)

    def _run(self, *args):
        out = StringIO()
        call_command('replay_criteria', *args, stdout=out)
        return out.getvalue()

    def test_finds_and_names_the_owner_class(self):
        out = self._run()
        # owner ruling B: the post-SPM holder below the floor is refused by both engines
        self.assertIn(f'cohort {self.loose.id} ({self.loose.code}): tree=columns; total=2; same=2', out)
        self.assertIn(f'  {CLASS_B}: pending (submitted, undecided)=1, decided=0 [submitted=1]\n'
                      f'    pending: {self.spm_only.id}\n', out)
        self.assertIn('start_year_flag_differs=0', out)
        self.assertIn('RESULT: only expected classes', out)

    def test_a_decided_application_is_counted_apart(self):
        decided = _apply(self.degree, exam_type='spm', grades=STRONG)
        ScholarshipApplication.objects.filter(pk=decided.pk).update(status='rejected')
        out = self._run('--cohort', 'deg-shape')
        self.assertIn(f'  {CLASS_B}: pending (submitted, undecided)=1, decided=1 [rejected=1, submitted=1]', out)
        self.assertIn(f'    decided: {decided.id}', out)

    def test_an_unknown_intake_code_is_an_error(self):
        with self.assertRaisesMessage(CommandError, 'unknown intake code(s): no-such-intake'):
            self._run('--cohort', 'deg-shape', '--cohort', 'no-such-intake')

    def test_plain_keeps_the_degree_spm_group(self):
        out = self._run('--plain', '--cohort', 'deg-shape')
        self.assertNotIn(CLASS_B, out)
        self.assertNotIn(self.loose.code, out)
        self.assertIn('total=1; same=1', out)

    def test_plain_never_passes_a_post_spm_holder_through_the_spm_group(self):
        # --plain leaves the trap on (an SPM group that cannot fail beside the floor); under 'own'
        # a post-SPM holder below the floor is still judged on the floor alone.
        _apply(self.degree, exam_type='stpm', stpm_cgpa=1.0, spm_prereq_grades=MID,
               results_exam_type='stpm', completed_qualifications=['spm', 'stpm'])
        out = self._run('--plain', '--cohort', 'deg-shape')
        self.assertIn('total=2; same=2', out)
        self.assertIn('RESULT: only expected classes', out)

    def test_the_stored_tree_is_compared_and_one_off_its_columns_needs_a_look(self):
        ScholarshipCohort.objects.filter(pk=self.loose.pk).update(criteria=criteria.from_legacy(self.loose))
        out = self._run('--cohort', self.loose.code)
        self.assertIn('tree=stored; total=2; same=2', out)
        self.assertNotIn(STORED_DIFFERS, out)
        self.assertIn('stored_trees_differ=0', out)
        # a stored tree that is NOT the columns' (here: the results section taken away) is what the
        # gate reads, so the replay judges with it - and says it needs a look.
        tree = criteria.from_legacy(self.loose)
        tree['all'] = [sec for sec in tree['all'] if sec['section'] not in ('results', 'merit')]
        ScholarshipCohort.objects.filter(pk=self.loose.pk).update(criteria=tree)
        out = self._run('--cohort', self.loose.code)
        self.assertIn(f'tree=stored; total=2; same=1, unexpected=1\n  {STORED_DIFFERS}\n', out)
        self.assertIn(f'    pending: {self.below_floor.id}', out)
        self.assertIn('stored_trees_differ=1', out)
        self.assertIn('RESULT: 2 need a look', out)

    def test_a_floor_beside_a_merit_only_bar_is_not_an_open_door(self):
        c = make_cohort(code='merit-door', min_stpm_pngk=3.0, min_spm_a_count=None, min_spm_bplus_count=None,
                        min_merit_score=80, income_ceiling=5860, per_capita_ceiling=None)
        _apply(c, exam_type='stpm', stpm_cgpa=1.0, spm_prereq_grades={}, results_exam_type='stpm',
               completed_qualifications=['spm', 'stpm'])
        out = self._run('--cohort', 'merit-door')
        self.assertIn('total=1; same=1', out)
        self.assertIn('RESULT: only expected classes', out)

    def test_a_tree_validate_refuses_is_listed_by_id_and_code(self):
        bad = make_cohort(code='bad-tree', min_stpm_pngk=None, min_spm_a_count=None, min_spm_bplus_count=None)
        ScholarshipCohort.objects.filter(pk=bad.pk).update(allowed_birth_states=['Sabah'])
        out = self._run('--cohort', 'bad-tree')
        self.assertIn(f'cohort {bad.id} (bad-tree): tree=columns; total=0; no applications\n'
                      '  TREE REFUSED by validate: born_in must be any: [distinct state keys]\n', out)
        self.assertIn('trees_refused=1', out)
        self.assertIn('RESULT: 1 need a look', out)
        self.assertNotIn('Sabah', out)
        self.assertIn('trees_refused=0', self._run('--cohort', 'deg-shape'))

    def test_prints_no_personal_data(self):
        out = self._run()
        for app in (self.below_floor, self.spm_only, self.spm_ok):
            p = app.profile
            for secret in (p.nric, p.name, p.contact_email, '2500', 'A-', 'B+', '1.9'):
                if secret:
                    self.assertNotIn(str(secret), out)

    def test_writes_nothing(self):
        before = {m: list(m.objects.order_by('pk').values()) for m in
                  (ScholarshipApplication, StudentProfile, ScholarshipCohort)}
        with CaptureQueriesContext(connection) as ctx:
            self._run()
        writes = [q['sql'] for q in ctx.captured_queries
                  if q['sql'].lstrip().split(' ', 1)[0].upper() in {'INSERT', 'UPDATE', 'DELETE'}]
        self.assertEqual(writes, [])
        after = {m: list(m.objects.order_by('pk').values()) for m in before}
        self.assertEqual(before, after)
        if connection.vendor == 'postgresql':
            self.assertTrue(any('SET TRANSACTION READ ONLY' in q['sql'] for q in ctx.captured_queries))
