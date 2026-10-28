"""Third results route S2a (2026-10-25): Matriculation / Asasi / Diploma, server side.

Roadmap: docs/plans/2026-10-25-third-results-route-roadmap.md (S2a, rulings D1 D3 D5). The legacy
rows are pinned in `test_exam_questions.TABLE` (unchanged except new rows); this file pins:

1. the accessors - "highest completed" `results_held`, `is_tertiary`, `overall_cgpa`, `merit_100`,
   `spm_grades_for`;
2. the gate - `min_stpm_pngk` on the overall CGPA with a reason naming the qualification, D5
   (a private-college Diploma is ineligible), D3 (`min_merit_score` stays SPM-only);
3. every roadmap section-4 door marked S2a - submit, rescore, the cohort floor edit, the profile
   sync, the sponsor line, the AI profile input, the review claims, the admin label, the intake
   snapshot, the calculator - and pins for the doors that must NOT re-run the gate.
"""
import re
from pathlib import Path
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APITestCase

from apps.courses import exam_questions as eq
from apps.courses.models import StudentProfile
from apps.courses.serializers import ProfileUpdateSerializer
from apps.scholarship import pool, shortlisting
from apps.scholarship.emails import sponsor_cards
from apps.scholarship.models import ScholarshipCohort
from apps.scholarship.services import rescore_pending_decisions, score_application
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

SPM = {'bm': 'A', 'eng': 'A', 'math': 'A+', 'hist': 'A', 'moral': 'A'}
STPM = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'}

#: The acceptance example: Matriculation CGPA 3.50 + co-curriculum 8 -> overall 3.47, merit 86.75.
MATRIC = dict(exam_type='matric', grades=SPM, higher_cgpa=3.5, higher_koko=8,
              results_exam_type='matric', completed_qualifications=['spm', 'matric'])
DIPLOMA = dict(exam_type='diploma', grades=SPM, higher_cgpa=2.8, higher_institution_type='public',
               results_exam_type='diploma', completed_qualifications=['spm', 'diploma'])

#: Only the STPM floor is set, so the academic test is the CGPA test alone.
ONLY_CGPA = dict(min_spm_a_count=None, min_spm_bplus_count=None, min_spm_credit_count=None,
                 min_merit_score=None, income_ceiling=None, per_capita_ceiling=None)


def _p(**fields):
    return StudentProfile(supabase_user_id='third', **fields)


def _cohort(**floors):
    base = dict(min_stpm_pngk=None, min_spm_a_count=None, min_spm_bplus_count=None,
                min_spm_credit_count=None, min_merit_score=None)
    base.update(floors)
    return SimpleNamespace(**base)


class TestTheMigrationIsSafeForTheImageStillServing(SimpleTestCase):
    """Migrate-first: the image serving between the hand-applied DDL and the deploy inserts
    profiles without naming the new columns, so each NOT NULL one carries a DATABASE default
    (lessons 2026-10-19), and the nullable floats need none."""

    def test_not_null_columns_have_database_defaults(self):
        from django.db.models.fields import NOT_PROVIDED
        for name in ('completed_qualifications', 'higher_institution_type'):
            f = StudentProfile._meta.get_field(name)
            with self.subTest(field=name):
                self.assertFalse(f.null)
                self.assertIsNot(f.db_default, NOT_PROVIDED)
        for name in ('higher_cgpa', 'higher_koko'):
            self.assertTrue(StudentProfile._meta.get_field(name).null)

    def test_the_docstring_carries_the_ddl_and_the_ledger_row(self):
        import importlib
        doc = importlib.import_module('apps.courses.migrations.0084_third_results_route').__doc__
        self.assertIn('ADD COLUMN "completed_qualifications" jsonb DEFAULT \'[]\'::jsonb NOT NULL',
                      doc)
        self.assertIn('ADD COLUMN "higher_institution_type" varchar(10) DEFAULT \'\' NOT NULL', doc)
        self.assertIn("('courses', '0084_third_results_route', now())", doc)


class TestResultsHeldIsTheHighestCompleted(SimpleTestCase):
    def test_a_completed_third_route_is_held(self):
        self.assertEqual(eq.results_held(_p(**MATRIC)), 'matric')
        self.assertEqual(eq.results_held(_p(**DIPLOMA)), 'diploma')

    def test_a_tertiary_completion_beats_a_later_spm_completion(self):
        """#153's shape GOING FORWARD: SPM form completed last, STPM completed too -> STPM."""
        p = _p(exam_type='spm', grades=SPM, stpm_grades=STPM, stpm_cgpa=3.92,
               results_exam_type='spm', completed_qualifications=['spm', 'stpm'])
        self.assertEqual(eq.results_held(p), 'stpm')

    def test_D1_the_legacy_shape_is_NOT_promoted(self):
        """#153 TODAY: recorded SPM, STPM data on file, no completed list -> SPM, as before."""
        p = _p(exam_type='spm', grades=SPM, stpm_grades=STPM, stpm_cgpa=3.92,
               results_exam_type='spm')
        self.assertEqual(eq.results_held(p), 'spm')

    def test_presence_of_data_never_promotes_15(self):
        # Only SPM was COMPLETED; the STPM grades were typed into the course guide.
        p = _p(exam_type='stpm', grades=SPM, stpm_grades=STPM, stpm_cgpa=4.0,
               results_exam_type='spm', completed_qualifications=['spm'])
        self.assertEqual(eq.results_held(p), 'spm')
        # and a third-route CGPA with no completed third-route form does not promote either
        p = _p(exam_type='spm', grades=SPM, higher_cgpa=3.9, higher_koko=9,
               results_exam_type='spm', completed_qualifications=['spm'])
        self.assertEqual(eq.results_held(p), 'spm')

    def test_between_two_tertiary_completions_the_last_form_wins_else_a_fixed_order(self):
        both = dict(grades=SPM, stpm_grades=STPM, stpm_cgpa=3.5, higher_cgpa=3.5, higher_koko=8,
                    completed_qualifications=['spm', 'stpm', 'matric'])
        self.assertEqual(eq.results_held(_p(results_exam_type='matric', **both)), 'matric')
        self.assertEqual(eq.results_held(_p(results_exam_type='stpm', **both)), 'stpm')
        self.assertEqual(eq.results_held(_p(results_exam_type='spm', **both)), 'stpm')

    def test_the_recorded_completion_counts_as_completed(self):
        p = _p(exam_type='stpm', grades=SPM, stpm_cgpa=3.5, results_exam_type='stpm',
               completed_qualifications=['spm'])
        self.assertEqual(eq.results_held(p), 'stpm')

    def test_the_third_card_tapped_with_no_results_reads_spm(self):
        """Step 2's correction for the third route: declared Matriculation, SPM grades only."""
        self.assertEqual(eq.results_held(_p(exam_type='matric', grades=SPM)), 'spm')
        # with nothing at all on file the declaration stands (as declared STPM does today)
        self.assertEqual(eq.results_held(_p(exam_type='diploma')), 'diploma')

    def test_a_garbage_completed_list_falls_back_to_the_old_rule(self):
        for junk in ('stpm', {'stpm': 1}, ['phd', 7, None], None):
            with self.subTest(junk=repr(junk)):
                p = _p(exam_type='stpm', grades=SPM, completed_qualifications=junk)
                self.assertEqual(eq.results_held(p), 'spm')    # the Form Six explorer rule
        self.assertEqual(eq.completed_qualifications(_p(completed_qualifications=[' MATRIC ',
                                                                                   'matric'])),
                         ['matric'])


class TestIsTertiary(SimpleTestCase):
    def test_the_one_stpm_equivalent_test(self):
        for held in ('stpm', 'matric', 'asasi', 'diploma', ' STPM '):
            self.assertTrue(eq.is_tertiary(held), held)
        for held in ('spm', '', None, 'poly', 'phd'):
            self.assertFalse(eq.is_tertiary(held), held)


class TestOverallCgpaAndMerit(SimpleTestCase):
    def test_the_acceptance_example(self):
        p = _p(**MATRIC)
        self.assertEqual(eq.overall_cgpa(p), 3.47)
        self.assertEqual(eq.merit_100(p), 86.75)

    def test_asasi_uses_the_same_weighting(self):
        p = _p(**{**MATRIC, 'exam_type': 'asasi', 'results_exam_type': 'asasi',
                  'completed_qualifications': ['spm', 'asasi']})
        self.assertEqual(eq.overall_cgpa(p), 3.47)

    def test_a_diploma_is_its_cgpa_as_is_and_ignores_any_koko(self):
        self.assertEqual(eq.overall_cgpa(_p(**DIPLOMA)), 2.8)
        self.assertEqual(eq.overall_cgpa(_p(**{**DIPLOMA, 'higher_koko': 10})), 2.8)
        self.assertEqual(eq.merit_100(_p(**DIPLOMA)), 70.0)

    def test_co_curriculum_is_capped_at_10_like_the_stpm_calculator(self):
        self.assertEqual(eq.overall_cgpa(_p(**{**MATRIC, 'higher_koko': 14})), 3.55)

    def test_nothing_usable_is_absent_never_zero(self):
        for bad in (dict(higher_cgpa=None), dict(higher_cgpa=0), dict(higher_cgpa=4.5),
                    dict(higher_koko=None), dict(higher_koko=-1)):
            with self.subTest(bad=repr(bad)):
                p = _p(**{**MATRIC, **bad})
                self.assertIsNone(eq.overall_cgpa(p))
                self.assertIsNone(eq.merit_100(p))

    def test_stpm_is_unchanged_from_S1(self):
        p = _p(exam_type='stpm', stpm_grades=STPM, stpm_cgpa=3.7)
        self.assertEqual(eq.overall_cgpa(p), 3.7)
        self.assertEqual(eq.merit_100(p), 92.5)

    def test_spm_has_no_overall_cgpa(self):
        self.assertIsNone(eq.overall_cgpa(_p(exam_type='spm', grades=SPM)))
        self.assertIsNone(eq.overall_cgpa(None))

    def test_the_formula_is_the_stpm_calculators_own(self):
        # 0.9 x CGPA + 0.1 x (koko / 10 x 4), as the owner wrote it, at 2 decimals
        for cgpa, koko in ((3.5, 8), (2.0, 0), (4.0, 10), (3.33, 7.5)):
            self.assertAlmostEqual(eq.overall_from(cgpa, koko),
                                   round(0.9 * cgpa + 0.1 * (koko / 10 * 4), 2), places=9)


class TestSpmGradesFor(SimpleTestCase):
    def test_an_spm_holder_reads_grades_only(self):
        p = _p(exam_type='spm', grades={'bm': 'A'}, spm_prereq_grades={'eng': 'B'})
        self.assertEqual(eq.spm_grades_for(p), {'bm': 'A'})

    def test_a_tertiary_holder_reads_both_with_grades_winning(self):
        p = _p(exam_type='stpm', stpm_cgpa=3.5, grades={'bm': 'A'},
               spm_prereq_grades={'bm': 'C', 'eng': 'B'})
        self.assertEqual(eq.spm_grades_for(p), {'bm': 'A', 'eng': 'B'})
        self.assertEqual(eq.spm_grades_for(None), {})


class TestTheGate(SimpleTestCase):
    def test_matric_347_passes_the_20_and_29_floors(self):
        p = _p(**MATRIC)
        self.assertEqual(shortlisting._academic_ok(p, _cohort(min_stpm_pngk=2.0)), (True, ''))
        self.assertEqual(shortlisting._academic_ok(p, _cohort(min_stpm_pngk=2.9)), (True, ''))

    def test_the_reason_names_the_qualification(self):
        p = _p(**{**MATRIC, 'higher_cgpa': 3.0, 'higher_koko': 0})        # 2.70
        self.assertEqual(shortlisting._academic_ok(p, _cohort(min_stpm_pngk=2.9)),
                         (False, 'Matriculation CGPA 2.70 below 2.90'))

    def test_the_spm_bars_do_not_apply_D3(self):
        """`min_merit_score` and the A-counts are SPM tests; the CGPA floor is the tertiary bar."""
        # With the floor SET (amended 2026-10-27, D16c: a blank floor makes the intake SPM-only,
        # pinned in test_spm_only_intake_gate).
        p = _p(**MATRIC)
        self.assertEqual(shortlisting._academic_ok(p, _cohort(min_stpm_pngk=2.0, min_merit_score=99,
                                                              min_spm_a_count=10)), (True, ''))

    def test_no_floor_set_passes(self):
        self.assertEqual(shortlisting._academic_ok(_p(**DIPLOMA), _cohort()), (True, ''))

    def test_a_missing_cgpa_fails_with_a_plain_reason(self):
        self.assertEqual(shortlisting._academic_ok(_p(exam_type='asasi'),
                                                   _cohort(min_stpm_pngk=2.0)),
                         (False, 'Asasi CGPA not provided'))
        p = _p(**{**MATRIC, 'higher_koko': None})
        self.assertEqual(shortlisting._academic_ok(p, _cohort(min_stpm_pngk=2.0)),
                         (False, 'Matriculation co-curriculum score not provided'))

    def test_stpm_reason_is_unchanged(self):
        p = _p(exam_type='stpm', stpm_grades=STPM, stpm_cgpa=3.5)
        self.assertEqual(shortlisting._academic_ok(p, _cohort(min_stpm_pngk=3.6)),
                         (False, 'PNGK 3.5 below 3.6'))


class TestTheGateThroughEvaluate(TestCase):
    """`evaluate` on real applications: merit vs ineligible (D5)."""

    def _result(self, profile_fields, **floors):
        cohort = make_cohort(**{**ONLY_CGPA, 'min_stpm_pngk': 2.9, **floors})
        app = make_application(cohort=cohort, student=make_student(**profile_fields))
        return shortlisting.evaluate(app, cohort)

    def test_matric_347_is_shortlisted(self):
        self.assertEqual(self._result(MATRIC).verdict, 'shortlisted')

    def test_diploma_280_vs_the_flagship_29_is_rejected_on_merit(self):
        r = self._result(DIPLOMA)
        self.assertEqual((r.verdict, r.category), ('rejected', 'merit'))
        self.assertEqual(r.reason, 'academic floor: Diploma CGPA 2.80 below 2.90')

    def test_a_private_college_diploma_is_ineligible_D5(self):
        r = self._result({**DIPLOMA, 'higher_cgpa': 3.9, 'higher_institution_type': 'private'},
                         min_stpm_pngk=None)
        self.assertEqual((r.verdict, r.category), ('rejected', 'ineligible'))
        self.assertEqual(r.reason, 'Diploma from a private college: only diplomas from public '
                                   'institutions count for this programme')

    def test_a_diploma_with_no_institution_stated_fails_closed_D5(self):
        r = self._result({**DIPLOMA, 'higher_cgpa': 3.9, 'higher_institution_type': ''})
        self.assertEqual((r.verdict, r.category), ('rejected', 'ineligible'))
        self.assertIn('not stated', r.reason)

    def test_D5_reads_only_a_held_diploma(self):
        # a Matriculation holder never states an institution type, and is not asked to
        self.assertEqual(self._result({**MATRIC, 'higher_institution_type': ''}).verdict,
                         'shortlisted')
        # an SPM holder with a stray private-diploma field is untouched
        r = self._result(dict(exam_type='spm', grades=SPM, higher_institution_type='private'))
        self.assertNotEqual(r.category, 'ineligible')


class TestTheScoringDoors(TestCase):
    """Roadmap section 4: submit -> score, rescore pending, the cohort floor edit."""

    def _scored(self, profile_fields, floor):
        cohort = make_cohort(**{**ONLY_CGPA, 'min_stpm_pngk': floor})
        app = make_application(cohort=cohort, student=make_student(**profile_fields))
        score_application(app)
        app.refresh_from_db()
        return app

    def test_submit_scores_the_third_route_on_its_overall_cgpa(self):
        app = self._scored(MATRIC, 2.9)
        self.assertEqual(app.verdict, 'shortlisted')
        app = self._scored(DIPLOMA, 2.9)
        self.assertEqual((app.verdict, app.rejection_category), ('rejected', 'merit'))
        self.assertEqual(app.shortlist_reason, 'academic floor: Diploma CGPA 2.80 below 2.90')

    def test_a_floor_edited_after_submit_is_applied_by_the_rescore(self):
        app = self._scored(MATRIC, 2.9)
        self.assertEqual(app.verdict, 'shortlisted')
        ScholarshipCohort.objects.filter(pk=app.cohort_id).update(min_stpm_pngk=3.5)
        out = rescore_pending_decisions()
        app.refresh_from_db()
        self.assertEqual((app.verdict, app.rejection_category), ('rejected', 'merit'))
        self.assertEqual(app.shortlist_reason,
                         'academic floor: Matriculation CGPA 3.47 below 3.50')
        self.assertIn(app.id, [row['id'] for row in out['changed']])

    def test_the_profile_is_read_live_at_rescore(self):
        """Profile edit after submit (results form re-completed) reaches the next rescore."""
        app = self._scored(DIPLOMA, 2.9)
        self.assertEqual(app.verdict, 'rejected')
        StudentProfile.objects.filter(pk=app.profile_id).update(higher_cgpa=3.1)
        rescore_pending_decisions()
        app.refresh_from_db()
        self.assertEqual(app.verdict, 'shortlisted')


_API = Path(__file__).resolve().parents[3]


class TestTheGateIsNotReRunElsewhere(SimpleTestCase):
    """QC accept/reject, reopen and its cancel, revert to pool, award and award revert read
    `results_held` / merit for DISPLAY only and never re-run the gate. Pinned by source: the
    engine has exactly one caller, `services/intake.py`."""

    def test_evaluate_has_one_caller(self):
        callers = []
        for path in (_API / 'apps').rglob('*.py'):
            rel = path.relative_to(_API).as_posix()
            if '/tests/' in rel or '/migrations/' in rel or rel.endswith('shortlisting.py'):
                continue
            src = path.read_text(encoding='utf-8')
            # a CALL with an argument (prose mentions read "evaluate()"); `page.evaluate(` is
            # Playwright's, in a scraper
            if re.search(r'(?<![\w.])evaluate\(\s*\w|shortlisting\.evaluate\(\s*\w|'
                         r'_academic_ok\(\s*\w', src):
                callers.append(rel)
        # STPM CGPA sprint C2: the backfill PREVIEW asks the gate before/after for the owner's list
        # and writes no verdict — a declared read-only caller, not a re-run.
        self.assertEqual(sorted(callers), ['apps/scholarship/management/commands/backfill_stpm_cgpa.py',
                                           'apps/scholarship/services/intake.py'])


class TestTheSponsorLine(TestCase):
    def test_the_pool_band_names_the_qualification(self):
        self.assertEqual(pool.academic_band(_p(**MATRIC)), 'Matriculation · CGPA 3.47')
        self.assertEqual(pool.academic_band(_p(**DIPLOMA)), 'Diploma · CGPA 2.80')
        self.assertEqual(pool.academic_band(_p(exam_type='asasi')), 'Asasi')

    def test_spm_and_stpm_bands_are_unchanged(self):
        self.assertEqual(pool.academic_band(_p(exam_type='stpm', stpm_grades=STPM,
                                               stpm_cgpa=3.5)), 'STPM · PNGK 3.5')
        self.assertEqual(pool.academic_band(_p(exam_type='spm', grades=SPM)), 'SPM · 5 As')

    def test_the_sponsor_email_reads_the_cgpa_not_the_letters_of_the_name(self):
        self.assertEqual(sponsor_cards._acad_score('Matriculation · CGPA 2.10'), 2.1)
        self.assertEqual(sponsor_cards._acad_score('Asasi · CGPA 2.00'), 2.0)
        # unchanged for SPM / STPM
        self.assertEqual(sponsor_cards._acad_score('SPM · 7 As'), 7.0)
        self.assertEqual(sponsor_cards._acad_score('STPM · PNGK 3.5'), 3.5)
        self.assertEqual(sponsor_cards._acad_score('STPM'), 0.0)
        self.assertEqual(sponsor_cards._acad_score(''), 0.0)


class TestTheReadersOnAMatricHolder(TestCase):
    def setUp(self):
        self.student = make_student(**MATRIC)
        self.app = make_application('submitted', student=self.student)

    def test_the_ai_profile_input_names_the_qualification_and_cgpa(self):
        from apps.scholarship import profile_engine
        prompt = profile_engine._build_prompt(self.app)
        self.assertIn('Qualification: Matriculation (STPM-equivalent), overall CGPA 3.47 ', prompt)
        self.assertIn('Merit score (out of 100): 86.75', prompt)
        # NO bump in S2a (review round 1): no live profile's input moved while the route was
        # shut. S2b opens the route and bumps it (superseding the S2a pin of '2026-10-25.1').
        # STPM CGPA sprint C2 (2026-10-28) bumps it again: the STPM PNGK and merit inputs moved.
        self.assertEqual(profile_engine.PROMPT_VERSION, '2026-10-28.1')

    def test_the_ai_profile_input_is_unchanged_for_spm(self):
        from apps.scholarship import profile_engine
        app = make_application('submitted', student=make_student(exam_type='spm', grades=SPM))
        self.assertIn('Qualification: spm ', profile_engine._build_prompt(app))

    def test_the_facts_ledger_claims_the_held_qualification(self):
        from unittest import mock
        from apps.scholarship import submission_review
        with mock.patch.object(submission_review, '_verdict_map', return_value={}):
            rows = submission_review.build_facts_ledger(self.app)
        self.assertEqual([r['value'] for r in rows if r['claim'] == 'qualification'], ['matric'])

    def test_the_admin_list_and_detail_serve_the_route(self):
        from apps.scholarship.serializers_admin import (AdminApplicationDetailSerializer,
                                                        AdminApplicationListSerializer)
        for ser in (AdminApplicationListSerializer, AdminApplicationDetailSerializer):
            data = ser(self.app).data
            with self.subTest(ser=ser.__name__):
                self.assertEqual(data['qualification'], 'matric')
                self.assertEqual(data['merit_score'], 86.75)
                self.assertEqual(data['overall_cgpa'], 3.47)
        detail = AdminApplicationDetailSerializer(self.app).data
        self.assertEqual((detail['higher_cgpa'], detail['higher_koko'],
                          detail['higher_institution_type']), (3.5, 8.0, ''))

    def test_the_intake_snapshot_carries_the_third_route(self):
        from apps.scholarship.services.profile_sync import build_intake_snapshot
        snap = build_intake_snapshot(self.student, {})['profile']
        self.assertEqual((snap['higher_cgpa'], snap['higher_koko'],
                          snap['higher_institution_type'], snap['completed_qualifications'],
                          snap['results_held']), (3.5, 8.0, '', ['spm', 'matric'], 'matric'))

    def test_the_student_payload_serves_the_held_route(self):
        from apps.scholarship.serializers import ApplicationReadSerializer
        self.assertEqual(ApplicationReadSerializer(self.app).data['exam_type'], 'matric')


@override_settings(THIRD_ROUTE_OPEN=True)
class TestTheProfileSync(TestCase):
    """The sync serializer accepts and guards the new fields (the one writer) - with the route
    OPEN, as S2b will run it. The shut door is `TestTheDoorIsShutUntilS2b`."""

    _n = 0

    def _profile(self, **fields):
        type(self)._n += 1
        return StudentProfile.objects.create(supabase_user_id=f'tr-{self._n}', name='A Student',
                                             **fields)

    def _save(self, profile, data):
        s = ProfileUpdateSerializer(profile, data=data, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        return s.save()

    def test_a_completed_third_route_form_lands(self):
        saved = self._save(self._profile(), {
            'exam_type': 'matric', 'grades': SPM, 'higher_cgpa': 3.5, 'higher_koko': 8,
            'muet_band': 4, 'results_exam_type': 'matric',
            'completed_qualifications': ['spm', 'matric']})
        self.assertEqual((saved.exam_type, saved.results_exam_type, saved.higher_cgpa,
                          saved.higher_koko, saved.completed_qualifications),
                         ('matric', 'matric', 3.5, 8.0, ['spm', 'matric']))
        self.assertEqual(eq.results_held(saved), 'matric')

    def test_an_unbacked_third_route_claim_is_dropped(self):
        saved = self._save(self._profile(grades=SPM), {
            'results_exam_type': 'diploma', 'completed_qualifications': ['spm', 'diploma']})
        self.assertEqual(saved.results_exam_type, '')
        self.assertEqual(saved.completed_qualifications, ['spm'])

    def test_an_unbacked_stpm_or_spm_entry_is_dropped_too(self):
        saved = self._save(self._profile(), {'completed_qualifications': ['spm', 'stpm']})
        self.assertEqual(saved.completed_qualifications, [])
        saved = self._save(self._profile(spm_prereq_grades={'bm': 'A'}, stpm_cgpa=3.4),
                           {'completed_qualifications': ['spm', 'stpm']})
        self.assertEqual(saved.completed_qualifications, ['spm', 'stpm'])

    def test_one_third_route_kind_at_a_time_the_recorded_one_wins(self):
        saved = self._save(self._profile(higher_cgpa=3.0), {
            'results_exam_type': 'asasi', 'completed_qualifications': ['matric', 'asasi']})
        self.assertEqual(saved.completed_qualifications, ['asasi'])
        saved = self._save(self._profile(higher_cgpa=3.0), {
            'completed_qualifications': ['matric', 'diploma', 'phd', 'MATRIC']})
        self.assertEqual(saved.completed_qualifications, ['diploma'])

    def test_out_of_range_values_are_refused(self):
        for bad in ({'higher_cgpa': 4.5}, {'higher_cgpa': -1}, {'higher_koko': 11},
                    {'higher_institution_type': 'abroad'}, {'completed_qualifications': 'spm'},
                    {'exam_type': 'phd'}):
            with self.subTest(bad=repr(bad)):
                s = ProfileUpdateSerializer(self._profile(), data=bad, partial=True)
                self.assertFalse(s.is_valid())

    def test_the_profile_payload_serves_the_new_fields(self):
        from apps.courses.views import ProfileView
        p = self._profile(**DIPLOMA)
        request = RequestFactory().get('/api/v1/profile/')
        request.user_id = p.supabase_user_id
        data = ProfileView().get(request).data
        self.assertEqual((data['higher_cgpa'], data['higher_koko'],
                          data['higher_institution_type'], data['completed_qualifications'],
                          data['results_held'], data['overall_cgpa']),
                         (2.8, None, 'public', ['spm', 'diploma'], 'diploma', 2.8))


class TestTheCgpaCalculator(APITestCase):
    URL = '/api/v1/calculate/cgpa/'

    def test_matric_raw_cgpa_and_koko(self):
        r = self.client.post(self.URL, {'kind': 'matric', 'higher_cgpa': 3.5, 'koko_score': 8},
                             format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['cgpa'], r.data['academic_cgpa'], r.data['merit_percent']),
                         (3.47, 3.5, 86.75))

    def test_diploma_is_as_is(self):
        r = self.client.post(self.URL, {'kind': 'diploma', 'higher_cgpa': 2.8, 'koko_score': 9},
                             format='json')
        self.assertEqual((r.data['cgpa'], r.data['merit_percent']), (2.8, 70.0))

    def test_bad_third_route_input_is_a_400(self):
        for body in ({'kind': 'matric', 'higher_cgpa': 5}, {'kind': 'phd', 'higher_cgpa': 3},
                     {'kind': 'matric', 'higher_cgpa': 3.0}, {'kind': 'asasi', 'higher_cgpa': 'x',
                                                              'koko_score': 5}):
            with self.subTest(body=repr(body)):
                self.assertEqual(self.client.post(self.URL, body, format='json').status_code, 400)

    def test_the_stpm_branch_answers_the_pngk_and_the_merit_apart(self):
        """Superseded 2026-10-28 (STPM CGPA sprint C2, owner ruling: CGPA and merit are different).
        This pinned the old plain-average answer (cgpa 3.42 / merit 85.5 for PA + two); the STPM
        branch now answers the PNGK and, separately, overall_from(PNGK, koko) / 4 x 100. PA + two has
        no PNGK. The third-route branch above is untouched."""
        r = self.client.post(self.URL, {'stpm_grades': {'PA': 'A', 'MATH_T': 'B+', 'PHYSICS': 'B'},
                                        'koko_score': 8}, format='json')
        self.assertEqual((r.data['cgpa'], r.data['merit_percent']), (None, None))
        r = self.client.post(self.URL, {'stpm_grades': {'PA': 'A', 'MATH_T': 'B+', 'PHYSICS': 'B',
                                                        'CHEMISTRY': 'B'}, 'koko_score': 8}, format='json')
        # (4 + 3.33 + 3 + 3) / 4 = 3.3325 -> 3.33; 0.9 x 3.33 + 0.04 x 8 = 3.317 -> 3.32 -> 83.0
        self.assertEqual((r.data['cgpa'], r.data['overall'], r.data['merit_percent']), (3.33, 3.32, 83.0))


class TestTheDoorIsShutUntilS2b(TestCase):
    """Review round 1: with no form and no document check yet, an SPM applicant could PUT
    `results_exam_type='asasi'` + a 4.00 CGPA and leave the SPM rules. `THIRD_ROUTE_OPEN` (default
    off) shuts the door at the one writer, PUT /profile/ and the sync alike."""

    def setUp(self):
        self.p = StudentProfile.objects.create(supabase_user_id='door', name='A Student',
                                               exam_type='spm', grades=SPM)

    def _put(self, data):
        from apps.courses.views import ProfileView
        request = RequestFactory().put('/api/v1/profile/')
        request.user_id, request.data = self.p.supabase_user_id, data
        return ProfileView().put(request)

    def test_the_switch_is_off_by_default(self):
        from django.conf import settings
        self.assertFalse(settings.THIRD_ROUTE_OPEN)

    def test_the_escape_the_review_found_is_refused(self):
        r = self._put({'results_exam_type': 'asasi', 'higher_cgpa': 4, 'higher_koko': 10})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error'], ['third_route_closed'])
        self.p.refresh_from_db()
        self.assertEqual((self.p.results_exam_type, self.p.higher_cgpa), ('', None))
        self.assertEqual(eq.results_held(self.p), 'spm')

    def test_every_third_route_write_is_refused_while_shut(self):
        for bad in ({'exam_type': 'matric'}, {'results_exam_type': 'diploma'},
                    {'higher_cgpa': 3.0}, {'higher_koko': 5},
                    {'higher_institution_type': 'public'},
                    # S2b narrowed this from ['spm']: only a list NAMING a third-route kind is the
                    # escape; an SPM / STPM list is what every SPM / STPM sync now sends.
                    {'completed_qualifications': ['spm', 'matric']}):
            with self.subTest(bad=repr(bad)):
                s = ProfileUpdateSerializer(self.p, data=bad, partial=True)
                self.assertFalse(s.is_valid())
                self.assertIn('error', s.errors)

    def test_harmless_and_legacy_writes_still_pass_while_shut(self):
        s = ProfileUpdateSerializer(self.p, data={
            'exam_type': 'stpm', 'stpm_cgpa': 3.4, 'results_exam_type': 'stpm',
            'higher_cgpa': None, 'higher_institution_type': '', 'completed_qualifications': []},
            partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        saved = s.save()
        self.assertEqual((saved.results_exam_type, saved.completed_qualifications), ('stpm', []))

    def test_an_spm_or_stpm_completed_list_passes_while_shut_S2b(self):
        """S2b: the web sends the WHOLE completed list with every SPM / STPM sync. Shut must still
        let those through, or a web release that beat the switch would 400 every SPM student's
        onboarding sync (grades lost). Only a list naming a third-route kind is refused."""
        for ok in (['spm'], ['spm', 'stpm']):
            with self.subTest(ok=','.join(ok)):
                s = ProfileUpdateSerializer(self.p, data={
                    'exam_type': 'spm', 'results_exam_type': 'spm', 'completed_qualifications': ok},
                    partial=True)
                self.assertTrue(s.is_valid(), s.errors)
        saved = s.save()
        self.assertEqual(eq.results_held(saved), 'spm')

    @override_settings(THIRD_ROUTE_OPEN=True)
    def test_open_the_same_write_lands(self):
        r = self._put({'exam_type': 'asasi', 'results_exam_type': 'asasi', 'higher_cgpa': 3.2,
                       'higher_koko': 7, 'completed_qualifications': ['spm', 'asasi']})
        self.assertEqual(r.status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(eq.results_held(self.p), 'asasi')


@override_settings(THIRD_ROUTE_OPEN=True)
class TestTheListStaysInStep(TestCase):
    """Review round 1, scenario 2: `completed_qualifications` is reconciled on EVERY write."""

    _n = 0

    def _profile(self, **fields):
        type(self)._n += 1
        return StudentProfile.objects.create(supabase_user_id=f'step-{self._n}', name='A Student',
                                             **fields)

    def _save(self, profile, data):
        s = ProfileUpdateSerializer(profile, data=data, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        return s.save()

    def test_2a_clearing_the_cgpa_prunes_its_entry(self):
        p = self._profile(**MATRIC)
        saved = self._save(p, {'higher_cgpa': None})          # the list is not even sent
        self.assertEqual(saved.completed_qualifications, ['spm'])
        self.assertEqual(saved.results_exam_type, '')         # its marker goes with it
        self.assertEqual(eq.results_held(saved), 'spm')
        # she ranks on the SPM results she still holds, never on a vanished CGPA
        self.assertEqual(eq.merit_100(saved), eq.merit_100(_p(exam_type='spm', grades=SPM)))

    def test_2b_only_the_recorded_third_route_kind_is_kept(self):
        p = self._profile(**MATRIC)
        saved = self._save(p, {'exam_type': 'diploma', 'results_exam_type': 'diploma',
                               'higher_cgpa': 3.1, 'higher_institution_type': 'public'})
        self.assertEqual(saved.completed_qualifications, ['spm', 'diploma'])
        self.assertEqual(eq.results_held(saved), 'diploma')
        saved = self._save(saved, {'completed_qualifications': ['spm', 'matric', 'diploma']})
        self.assertEqual(saved.completed_qualifications, ['spm', 'diploma'])

    def test_2c_a_legacy_stpm_holder_is_never_demoted_by_a_list_that_omits_stpm(self):
        p = self._profile(exam_type='stpm', grades=SPM, stpm_grades=STPM, stpm_cgpa=3.5)
        self.assertEqual(eq.results_held(p), 'stpm')           # today, recorded blank
        saved = self._save(p, {'completed_qualifications': ['spm']})
        self.assertEqual(saved.completed_qualifications, ['spm', 'stpm'])
        self.assertEqual(eq.results_held(saved), 'stpm')
        # and once her STPM data is gone, 'stpm' is pruned like any other stale entry
        saved = self._save(saved, {'stpm_grades': {}, 'stpm_cgpa': None})
        self.assertEqual(saved.completed_qualifications, ['spm'])

    def test_a_blank_list_stays_blank_D1(self):
        p = self._profile(exam_type='spm', grades=SPM, stpm_grades=STPM, stpm_cgpa=3.92,
                          results_exam_type='spm')
        saved = self._save(p, {'muet_band': 4})
        self.assertEqual(saved.completed_qualifications, [])
        self.assertEqual(eq.results_held(saved), 'spm')


@override_settings(THIRD_ROUTE_OPEN=True)
class TestAStaleSyncNeverDemotes(TestCase):
    """S2b adversarial review (HIGH): a sign-in from a stale browser sends the results set it last
    saw — e.g. `results_exam_type='spm'`, `['spm']`, `exam_type='spm'`. The guard is built from the
    STORED profile: a profile holding tertiary results that are still on file stays where it was.
    Only clearing the results themselves demotes. (The review's probe table.)"""

    _n = 0
    STALE = {'exam_type': 'spm', 'results_exam_type': 'spm', 'completed_qualifications': ['spm']}

    def _profile(self, **fields):
        type(self)._n += 1
        return StudentProfile.objects.create(supabase_user_id=f'stale-{self._n}', name='A Student',
                                             **fields)

    def _sync(self, profile, data):
        s = ProfileUpdateSerializer(profile, data=data, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        return s.save()

    def test_the_probe_table(self):
        rows = [
            ('legacy STPM (recorded blank)', dict(exam_type='stpm', grades=SPM, stpm_grades=STPM,
                                                  stpm_cgpa=3.5), 'stpm'),
            ('legacy STPM (recorded stpm)', dict(exam_type='stpm', grades=SPM, stpm_grades=STPM,
                                                 stpm_cgpa=3.5, results_exam_type='stpm'), 'stpm'),
            ("['spm','stpm'] list", dict(exam_type='stpm', grades=SPM, stpm_grades=STPM,
                                         stpm_cgpa=3.5, results_exam_type='stpm',
                                         completed_qualifications=['spm', 'stpm']), 'stpm'),
            ('Matriculation', MATRIC, 'matric'),
            ('Diploma', DIPLOMA, 'diploma'),
        ]
        for label, fields, held in rows:
            with self.subTest(row=label):
                p = self._profile(**fields)
                self.assertEqual(eq.results_held(p), held)
                saved = self._sync(p, dict(self.STALE))
                self.assertEqual(eq.results_held(saved), held)

    def test_clearing_the_results_still_demotes(self):
        p = self._profile(**MATRIC)
        saved = self._sync(p, {**self.STALE, 'higher_cgpa': None})
        self.assertEqual(eq.results_held(saved), 'spm')
        p = self._profile(exam_type='stpm', grades=SPM, stpm_grades=STPM, stpm_cgpa=3.5,
                          results_exam_type='stpm')
        saved = self._sync(p, {**self.STALE, 'stpm_grades': {}, 'stpm_cgpa': None})
        self.assertEqual(eq.results_held(saved), 'spm')

    def test_an_spm_holder_and_a_lateral_move_are_untouched(self):
        p = self._profile(exam_type='spm', grades=SPM, results_exam_type='spm')
        saved = self._sync(p, dict(self.STALE))
        self.assertEqual(eq.results_held(saved), 'spm')
        p = self._profile(**MATRIC)            # Matriculation -> a completed public Diploma form
        saved = self._sync(p, {'exam_type': 'diploma', 'results_exam_type': 'diploma',
                               'higher_cgpa': 3.1, 'higher_koko': None,
                               'higher_institution_type': 'public',
                               'completed_qualifications': ['spm', 'diploma']})
        self.assertEqual(eq.results_held(saved), 'diploma')
