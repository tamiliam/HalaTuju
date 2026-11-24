"""Criteria editor Sprint 1 - today's gate and the tree agree, except where the owner ruled.

Many synthetic students (every results route, still studying, missing results, weak and strong
SPM grades, every income edge, three birth states) against many intake shapes (the live ones,
the model defaults, blank floors, merit-only, per-person-only, a zero floor). For each pair:
`shortlisting.evaluate(app, cohort)` vs `criteria.evaluate(app, from_legacy(cohort))`. The ONLY
allowed differences are the owner's two classes (2026-11-25), classified by the replay command's
own `classify`, so the test and the live replay judge alike."""
import itertools
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.courses.models import StudentProfile
from apps.scholarship import criteria, shortlisting
from apps.scholarship.management.commands.replay_criteria import CLASS_A1, CLASS_A2, CLASS_B, classify
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
    'all_bars': cohort(min_spm_a_count=1, min_spm_bplus_count=3, min_spm_credit_count=5, min_merit_score=50.0,
                       min_stpm_pngk=2.5, allowed_birth_states=['selangor', 'sabah'], income_ceiling=5860),
}


def _app(results, income, nric, **gates):
    profile = StudentProfile(supabase_user_id='eq', nric=nric, **RESULTS[results], **INCOME[income])
    return SimpleNamespace(profile=profile, consent_to_contact=True, intends_tertiary_2026=True,
                           upu_status='', **gates)


def _run(**opts):
    found = {}
    for (cname, c), r, i, n in itertools.product(COHORTS.items(), RESULTS, INCOME, NRICS):
        a = _app(r, i, n)
        tree = criteria.from_legacy(c, **opts)
        cls = classify(a, c, shortlisting.evaluate(a, c), criteria.evaluate(a, tree), tree)
        found.setdefault(cls, []).append((cname, r, i, n))
    return found


class TestEquivalence(SimpleTestCase):
    def test_from_legacy_differs_only_by_the_owner_classes(self):
        found = _run()
        self.assertEqual(set(found) - {'same', CLASS_A1, CLASS_A2, CLASS_B}, set(),
                         {k: v[:5] for k, v in found.items() if k != 'same'})
        self.assertGreater(len(found['same']), 4000)
        # (a1) below the floor, meets today's SPM bars; (a2) CGPA missing (here: no co-curriculum).
        self.assertIn(('cohort_3', 'stpm_19_mid', 'b40', '050101-12-1234'), found[CLASS_A1])
        self.assertIn(('cohort_4', 'asasi_low', 'str', '050101-10-1234'), found[CLASS_A1])
        self.assertIn(('cohort_4', 'matric_nokoko', 'b40', '050101-10-1234'), found[CLASS_A2])
        # (b) only where a floor stands with no SPM bar - intake 5 among these shapes - and only
        # for students with no final post-SPM result.
        b = found[CLASS_B]
        self.assertEqual({c for c, *_ in b}, {'cohort_5'})
        self.assertTrue({r for _, r, _, _ in b} <= {'spm_strong', 'spm_mid', 'spm_weak', 'spm_none', 'blank',
                                                     'still_stpm', 'still_matric'})
        # Intake 5 has no SPM group, so its post-SPM holders below the floor are NOT loosened.
        self.assertFalse([x for x in found[CLASS_A1] + found.get(CLASS_A2, []) if x[0] == 'cohort_5'])

    def test_plain_keeps_the_spm_group_and_never_shows_class_b(self):
        found = _run(keep_empty_spm=True)
        self.assertEqual(set(found) - {'same', CLASS_A1, CLASS_A2}, set(),
                         {k: v[:5] for k, v in found.items() if k != 'same'})
        self.assertIn(('cohort_5', 'asasi_low', 'str', '050101-10-1234'), found[CLASS_A1])

    def test_the_hard_gates_agree(self):
        for gates in (dict(consent_to_contact=False), dict(intends_tertiary_2026=False), dict(upu_status='ipts')):
            for cname, c in COHORTS.items():
                a = _app('stpm_19_mid', 'b40', NRICS[0])
                for k, v in gates.items():
                    setattr(a, k, v)
                self.assertEqual(shortlisting.evaluate(a, c), criteria.evaluate(a, criteria.from_legacy(c)))
