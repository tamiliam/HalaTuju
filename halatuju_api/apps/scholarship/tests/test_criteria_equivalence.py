"""Criteria editor Sprints 1-2 - the old columns gate and the tree agree, except where the owner ruled.

Many synthetic students (every results route, still studying, missing results, weak and strong
SPM grades, every income edge, three birth states) against many intake shapes (the live ones,
the model defaults, blank floors, merit-only, per-person-only, a zero floor, a floor beside a
merit-only SPM bar, a floor beside every bar at 0; a diploma with no institution stated and an
application with no profile). For each pair:
`shortlisting.evaluate_columns(app, cohort)` vs `criteria.evaluate(app, from_legacy(cohort))`. The
ONLY allowed difference is the owner's class (b) (2026-11-25: intake 5's CGPA trap switched off) and
its reason-only twin (b2), classified by the replay command's own `classify_replay`, so the test and
the live replay judge alike. Sprint 2 (owner ruling B, 2026-11-26): results are judged 'own', so a
post-SPM holder below the floor on intakes 3 and 4 is still refused - Sprint 1's classes a1 / a2 are
gone. Finished Matric / Asasi / Diploma holders with a blank CGPA are in the grid too."""
import itertools
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.courses.models import StudentProfile
from apps.scholarship import criteria, shortlisting
from apps.scholarship.management.commands.replay_criteria import (
    CLASS_B, CLASS_B2, EXPECTED, classify_replay)
from apps.scholarship.tests.test_criteria import COHORT_1, COHORT_3, COHORT_4, COHORT_5, DEFAULTS, cohort

STRONG = {'bm': 'A+', 'eng': 'A', 'math': 'A', 'hist': 'A-', 'moral': 'B+', 'sci': 'B', 'geo': 'C'}
MID = {'bm': 'A-', 'eng': 'B+', 'math': 'C', 'hist': 'C+', 'moral': 'D'}
WEAK = {'bm': 'C', 'eng': 'D', 'math': 'E', 'hist': 'G'}

_DONE = {'stpm': dict(results_exam_type='stpm', completed_qualifications=['spm', 'stpm'])}
for _k in ('matric', 'asasi', 'diploma'):
    _DONE[_k] = dict(results_exam_type=_k, completed_qualifications=['spm', _k])

RESULTS = {
    'spm_strong': dict(exam_type='spm', grades=STRONG),
    'spm_mid': dict(exam_type='spm', grades=MID),
    'spm_weak': dict(exam_type='spm', grades=WEAK),
    'spm_none': dict(exam_type='spm', grades={}),
    'blank': dict(exam_type='', grades={}),
    'stpm_35': dict(exam_type='stpm', stpm_cgpa=3.5, spm_prereq_grades=MID, **_DONE['stpm']),
    'stpm_29': dict(exam_type='stpm', stpm_cgpa=2.9, spm_prereq_grades=STRONG, **_DONE['stpm']),
    'stpm_25_weak': dict(exam_type='stpm', stpm_cgpa=2.5, spm_prereq_grades=WEAK, **_DONE['stpm']),
    'stpm_19_mid': dict(exam_type='stpm', stpm_cgpa=1.9, spm_prereq_grades=MID, **_DONE['stpm']),
    'stpm_none_noprereq': dict(exam_type='stpm', stpm_cgpa=None, stpm_grades={'pa': 'B'}, **_DONE['stpm']),
    'matric_ok': dict(exam_type='matric', higher_cgpa=3.4, higher_koko=8, spm_prereq_grades=MID, **_DONE['matric']),
    'matric_nokoko': dict(exam_type='matric', higher_cgpa=3.4, spm_prereq_grades=MID, **_DONE['matric']),
    'asasi_low': dict(exam_type='asasi', higher_cgpa=1.8, higher_koko=5, spm_prereq_grades=STRONG, **_DONE['asasi']),
    'dip_pub_29': dict(exam_type='diploma', higher_cgpa=2.9, higher_institution_type='public',
                       spm_prereq_grades={}, **_DONE['diploma']),
    'dip_pub_bad': dict(exam_type='diploma', higher_cgpa=7.0, higher_institution_type='public',
                        spm_prereq_grades=WEAK, **_DONE['diploma']),
    'dip_private': dict(exam_type='diploma', higher_cgpa=3.9, higher_institution_type='private', **_DONE['diploma']),
    'dip_unstated': dict(exam_type='diploma', higher_cgpa=3.9, higher_institution_type='',
                         spm_prereq_grades=STRONG, **_DONE['diploma']),
    'stpm_10_nospm': dict(exam_type='stpm', stpm_cgpa=1.0, spm_prereq_grades={}, **_DONE['stpm']),
    'stpm_10_strong': dict(exam_type='stpm', stpm_cgpa=1.0, spm_prereq_grades=STRONG, coq_score=10.0,
                           **_DONE['stpm']),
    # Sprint 2 carry-over: FINISHED third-route results with the CGPA left blank.
    'matric_nocgpa': dict(exam_type='matric', higher_cgpa=None, higher_koko=8, spm_prereq_grades=STRONG,
                          **_DONE['matric']),
    'asasi_nocgpa': dict(exam_type='asasi', higher_cgpa=None, higher_koko=5, spm_prereq_grades=MID,
                         **_DONE['asasi']),
    'dip_nocgpa': dict(exam_type='diploma', higher_cgpa=None, higher_institution_type='public',
                       spm_prereq_grades=STRONG, **_DONE['diploma']),
    'no_profile': None,
    'still_stpm': dict(exam_type='stpm', grades=MID),
    'still_matric': dict(exam_type='matric', grades=STRONG),
}
INCOME = {
    'str': dict(receives_str=True, household_income=None),
    'none': dict(household_income=None, household_size=4),
    'zero': dict(household_income=0, household_size=4),
    'b40': dict(household_income=5860, household_size=2),
    'big_family': dict(household_income=7000, household_size=6),
    'pc_edge': dict(household_income=7920, household_size=5),
    'no_size': dict(household_income=7000, household_size=None),
    'rich': dict(household_income=20000, household_size=3),
}
NRICS = ('050101-10-1234', '050101-12-1234', '050101-82-1234')

COHORTS = {
    'cohort_1': COHORT_1, 'cohort_3': COHORT_3, 'cohort_4': COHORT_4, 'cohort_5': COHORT_5,
    'defaults': DEFAULTS, 'nothing': cohort(),
    'blank_floor_merit_only': cohort(min_merit_score=60.0, income_ceiling=5860),
    'blank_floor_credit': cohort(min_spm_credit_count=5, per_capita_ceiling=1584),
    'floor_zero': cohort(min_stpm_pngk=0.0, min_spm_a_count=2),
    'bplus_only': cohort(min_spm_bplus_count=3, min_stpm_pngk=2.5, income_ceiling=4000, per_capita_ceiling=1000),
    # review round 2 (F1/F4): a floor beside a merit-only SPM bar, the same with credit 0, and a
    # floor beside every bar at 0 (no bar can fail -> no SPM group).
    'floor_merit_only': cohort(min_stpm_pngk=3.0, min_merit_score=80.0),
    'floor_credit0_merit': cohort(min_stpm_pngk=3.0, min_spm_credit_count=0, min_merit_score=80.0),
    'floor_merit_low': cohort(min_stpm_pngk=3.0, min_merit_score=40.0),
    'floor_all_zero': cohort(min_stpm_pngk=2.0, min_spm_a_count=0, min_spm_bplus_count=0,
                             min_spm_credit_count=0, min_merit_score=0),
    'all_bars': cohort(min_spm_a_count=1, min_spm_bplus_count=3, min_spm_credit_count=5, min_merit_score=50.0,
                       min_stpm_pngk=2.5, allowed_birth_states=['selangor', 'sabah'], income_ceiling=5860),
}


def _app(results, income, nric, **gates):
    profile = (None if RESULTS[results] is None
               else StudentProfile(supabase_user_id='eq', nric=nric, **RESULTS[results], **INCOME[income]))
    return SimpleNamespace(profile=profile, consent_to_contact=True, intends_tertiary_2026=True,
                           upu_status='', **gates)


_CACHE = {}


def _run(**opts):
    key = tuple(sorted(opts.items()))
    if key not in _CACHE:
        _CACHE[key] = _grid(**opts)
    return _CACHE[key]


def _grid(**opts):
    found = {}
    for (cname, c), r, i, n in itertools.product(COHORTS.items(), RESULTS, INCOME, NRICS):
        a = _app(r, i, n)
        tree = criteria.from_legacy(c, **opts)
        cls = classify_replay(a, c, shortlisting.evaluate_columns(a, c), criteria.evaluate(a, tree), tree)
        found.setdefault(cls, []).append((cname, r, i, n))
    return found


class TestEquivalence(SimpleTestCase):
    def test_from_legacy_differs_only_by_the_owner_classes(self):
        found = _run()
        self.assertEqual(set(found) - EXPECTED, set(), {k: v[:5] for k, v in found.items() if k != 'same'})
        self.assertGreater(len(found['same']), 4000)
        # Owner ruling B: below the floor, or CGPA missing, on intakes 3 and 4 - still refused,
        # however strong the SPM grades (no SPM door for a post-SPM holder).
        for x in (('cohort_3', 'stpm_19_mid', 'b40', '050101-12-1234'), ('cohort_4', 'asasi_low', 'str', '050101-10-1234'),
                  ('cohort_4', 'matric_nokoko', 'b40', '050101-10-1234'), ('cohort_4', 'matric_nocgpa', 'b40', NRICS[0]),
                  ('cohort_3', 'dip_nocgpa', 'b40', '050101-12-1234')):
            self.assertIn(x, found['same'])
        # (b) only where a floor stands with no SPM bar that can fail - intake 5 and the every-bar-0
        # shape - and only for students with no final post-SPM result. (b2) is the same shape where
        # today already refuses on a 0 bar (no SPM grades / no merit): verdict kept, reason moves.
        spm_only = {'spm_strong', 'spm_mid', 'spm_weak', 'spm_none', 'blank', 'still_stpm', 'still_matric',
                    'no_profile'}
        for cls, cohorts in ((CLASS_B, {'cohort_5', 'floor_all_zero'}), (CLASS_B2, {'floor_all_zero'})):
            self.assertEqual({c for c, *_ in found[cls]}, cohorts)
            self.assertTrue({r for _, r, _, _ in found[cls]} <= spm_only)
        # Every live cohort other than intake 5 agrees exactly with its columns.
        for cname in ('cohort_1', 'cohort_3', 'cohort_4', 'defaults'):
            self.assertFalse([x for k, v in found.items() if k != 'same' for x in v if x[0] == cname], cname)

    def test_every_tree_validates(self):
        for cname, c in COHORTS.items():
            with self.subTest(cohort=cname):
                self.assertEqual(criteria.validate_tree(criteria.from_legacy(c)), [])

    def test_a_floor_beside_a_merit_only_bar_is_not_void(self):
        # F1: STPM PNGK 1.0 with no SPM grades used to pass through the merit-only SPM door.
        for cname in ('floor_merit_only', 'floor_credit0_merit', 'floor_merit_low'):
            c = COHORTS[cname]
            for r in ('stpm_10_nospm', 'stpm_10_strong'):
                a = _app(r, 'b40', NRICS[0])
                with self.subTest(cohort=cname, results=r):
                    got = criteria.evaluate(a, criteria.from_legacy(c))
                    self.assertEqual((got.verdict, got.category), ('rejected', 'merit'))
                    self.assertEqual(got, shortlisting.evaluate_columns(a, c))

    def test_a_floor_beside_every_bar_at_zero_has_no_spm_group(self):
        groups = criteria.from_legacy(COHORTS['floor_all_zero'])['all'][0]['own']
        self.assertEqual([g['route'] for g in groups], ['post_spm'])

    def test_diploma_unstated_and_no_profile_agree(self):
        found = _run()
        odd = [(k, x) for k, v in found.items() if k != 'same' for x in v if x[1] in ('dip_unstated', 'no_profile')]
        # no profile reads as an SPM student: only the every-bar-0 shape moves its reason (b2)
        self.assertEqual({(k, x[0], x[1]) for k, x in odd}, {(CLASS_B2, 'floor_all_zero', 'no_profile')})
        a = _app('dip_unstated', 'b40', NRICS[0])
        self.assertTrue(criteria.evaluate(a, criteria.from_legacy(COHORT_4)).reason
                        .startswith('Diploma institution not stated'))

    def test_plain_is_todays_gate_exactly(self):
        # --plain leaves the trap on (an SPM group that cannot fail beside a floor). Under 'own' a
        # post-SPM holder never uses that group, so the plain tree is today's gate, byte for byte.
        found = _run(keep_empty_spm=True)
        self.assertEqual(set(found), {'same'}, {k: v[:5] for k, v in found.items() if k != 'same'})

    def test_the_hard_gates_agree(self):
        for gates in (dict(consent_to_contact=False), dict(intends_tertiary_2026=False), dict(upu_status='ipts')):
            for cname, c in COHORTS.items():
                a = _app('stpm_19_mid', 'b40', NRICS[0])
                for k, v in gates.items():
                    setattr(a, k, v)
                self.assertEqual(shortlisting.evaluate_columns(a, c), criteria.evaluate(a, criteria.from_legacy(c)))
