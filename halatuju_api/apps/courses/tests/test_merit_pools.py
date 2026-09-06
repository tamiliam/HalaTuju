"""
Tests for the SPM merit stream pools (Sec2 = 30% weight).

Guards the fix from Sprint S18: when the Arts and Technical stream dropdowns
were expanded to the full official SPM subject list, the backend pools in
engine.py had to be expanded in lockstep — otherwise a newly-selectable stream
subject would silently drop from the 30% Sec2 weight to the 10% Sec3 weight.

`prepare_merit_inputs(grades)` returns (sec1, sec2, sec3) as lists of grade
strings. Sec2 is the best 2 grades from the student's detected primary stream
pool, so we assert which grades land there.
"""
from django.test import SimpleTestCase

from apps.courses.engine import (
    prepare_merit_inputs,
    calculate_merit_score,
    SCIENCE_POOL,
    ARTS_POOL,
    TECHNICAL_POOL,
)

CORES = {'bm': 'A', 'eng': 'A', 'math': 'A', 'history': 'A'}


class TestMeritPoolMembership(SimpleTestCase):
    """The backend pools must mirror SPM_STREAM_POOLS in subjects.ts."""

    def test_arts_pool_full_official_list(self):
        self.assertEqual(len(ARTS_POOL), 38)
        for key in ('tarian', 'lakonan', 'seni_halus_2d', 'bahasa_punjabi',
                    'bible_knowledge', 'music', 'lit_tamil', 'reka_bentuk_grafik'):
            self.assertIn(key, ARTS_POOL)

    def test_technical_pool_full_official_list(self):
        self.assertEqual(len(TECHNICAL_POOL), 16)
        for key in ('kelestarian', 'pertanian', 'srt', 'sports_sci', 'addsci'):
            self.assertIn(key, TECHNICAL_POOL)

    def test_sciences_in_both_science_and_technical(self):
        for key in ('phy', 'chem', 'bio', 'addmath'):
            self.assertIn(key, SCIENCE_POOL)
            self.assertIn(key, TECHNICAL_POOL)

    def test_no_islamic_subjects_in_pools(self):
        islamic = {'pqs', 'psi', 'tasawwur_islam', 'usul_aldin', 'al_syariah',
                   'manahij', 'hifz_alquran', 'maharat_alquran', 'islam'}
        self.assertEqual(islamic & (ARTS_POOL | TECHNICAL_POOL | SCIENCE_POOL), set())


class TestMeritStreamWeighting(SimpleTestCase):
    """Stream subjects must land in Sec2 (30%), not Sec3 (10%)."""

    def test_arts_performance_subjects_land_in_sec2(self):
        # Dance (A+) and Acting (A) are the student's two best arts subjects.
        grades = {**CORES, 'tarian': 'A+', 'lakonan': 'A', 'geo': 'B'}
        _sec1, sec2, _sec3 = prepare_merit_inputs(grades)
        # Best 2 from the arts pool by grade points → A+ then A.
        self.assertEqual(sorted(sec2), sorted(['A+', 'A']))

    def test_addmath_counts_as_stream_for_technical_student(self):
        # A technical student's Additional Maths (A+) must now count toward the
        # 30% stream weight, not drop to the 10% elective bucket.
        grades = {**CORES, 'eng_civil': 'A', 'eng_mech': 'B', 'addmath': 'A+'}
        _sec1, sec2, _sec3 = prepare_merit_inputs(grades)
        self.assertIn('A+', sec2)  # addmath's grade reached Sec2

    def test_pure_science_student_unchanged(self):
        # Regression: a science student still scores the same (sciences win the
        # science/technical tie by ordering, best-2 identical either way).
        grades = {**CORES, 'phy': 'A+', 'chem': 'A', 'bio': 'B', 'addmath': 'A'}
        _sec1, sec2, _sec3 = prepare_merit_inputs(grades)
        self.assertEqual(sorted(sec2), sorted(['A+', 'A']))


class TestExplicitStreamSubjects(SimpleTestCase):
    """TD-063: when the student's stream picks are passed, the engine trusts
    them and ignores the pools. Falls back to the heuristic when absent."""

    def test_none_falls_back_to_heuristic(self):
        # No explicit picks → identical to the legacy heuristic path.
        grades = {**CORES, 'phy': 'A+', 'chem': 'A', 'bio': 'B', 'addmath': 'A'}
        self.assertEqual(
            prepare_merit_inputs(grades, stream_subjects=None),
            prepare_merit_inputs(grades),
        )

    def test_empty_list_falls_back_to_heuristic(self):
        grades = {**CORES, 'ekonomi': 'A', 'poa': 'B', 'geo': 'A'}
        self.assertEqual(
            prepare_merit_inputs(grades, stream_subjects=[]),
            prepare_merit_inputs(grades),
        )

    def test_full_aliran_list_matches_heuristic(self):
        # SAFETY PROPERTY: passing the full list of stream subjects the student
        # studied yields the same Sec2/Sec3 as the heuristic (best-2 of pool).
        grades = {**CORES, 'phy': 'C', 'chem': 'C', 'bio': 'A', 'addmath': 'A'}
        _s1, sec2_explicit, sec3_explicit = prepare_merit_inputs(
            grades, stream_subjects=['phy', 'chem', 'bio', 'addmath'])
        _s1b, sec2_heur, sec3_heur = prepare_merit_inputs(grades)
        self.assertEqual(sorted(sec2_explicit), sorted(sec2_heur))
        self.assertEqual(sorted(sec3_explicit), sorted(sec3_heur))
        self.assertEqual(sorted(sec2_explicit), sorted(['A', 'A']))  # best 2

    def test_cross_stream_student_scored_on_their_real_stream(self):
        # Heuristic mis-guesses the stream for a cross-stream student; the
        # explicit pick scores their actual (stronger) stream subjects.
        grades = {**CORES, 'phy': 'A', 'chem': 'B', 'ekonomi': 'A', 'poa': 'A'}
        _s1, sec2_heur, _s3 = prepare_merit_inputs(grades)  # guesses sci/tech
        _s1b, sec2_explicit, _s3b = prepare_merit_inputs(
            grades, stream_subjects=['ekonomi', 'poa'])
        self.assertEqual(sorted(sec2_explicit), sorted(['A', 'A']))
        # The student's real stream (two A's) differs from the mis-guess (A + B).
        self.assertNotEqual(sorted(sec2_heur), sorted(sec2_explicit))

    def test_designated_subject_absent_from_pools_still_counts_as_stream(self):
        # The S18 bug class, now impossible for labelled data: a stream subject
        # missing from the back-end pools is still scored at the 30% weight when
        # the student explicitly designates it.
        grades = {**CORES, 'phy': 'A', 'not_in_any_pool': 'A+', 'geo': 'C'}
        _s1, sec2, _s3 = prepare_merit_inputs(
            grades, stream_subjects=['phy', 'not_in_any_pool'])
        self.assertEqual(sorted(sec2), sorted(['A+', 'A']))

    def test_core_subjects_ignored_in_explicit_list(self):
        # A defensive list that accidentally includes a core subject must not
        # pull it into Sec2 (core is always Sec1).
        grades = {**CORES, 'phy': 'A', 'chem': 'B'}
        _s1, sec2, _s3 = prepare_merit_inputs(
            grades, stream_subjects=['math', 'phy', 'chem'])
        self.assertEqual(sorted(sec2), sorted(['A', 'B']))  # math excluded


class TestExplicitStreamToppedUpToTwo(SimpleTestCase):
    """Sec2 is scored out of TWO subjects. A designation that yields only one
    used to leave the other half scoring a subject the student never sat, at
    G = 0 — silently costing 7-15 merit points on 15 live profiles.

    The cause is upstream: the grades page pre-fills the four SCIENCE stream
    slots for everyone and saves whichever slots still name a subject, GRADED
    OR NOT. A student who clears three, grades one, and types their real
    subjects into the ELECTIVE list ships exactly one usable stream subject.
    """

    def test_one_designated_subject_is_topped_up(self):
        # Only Add Maths is designated; the best remaining non-core subject
        # joins it rather than the second Sec2 slot scoring zero.
        grades = {**CORES, 'addmath': 'A-', 'poa': 'A', 'ekonomi': 'B'}
        _s1, sec2, sec3 = prepare_merit_inputs(grades, stream_subjects=['addmath'])
        self.assertEqual(len(sec2), 2)
        self.assertEqual(sorted(sec2), sorted(['A', 'A-']))  # addmath + poa
        self.assertEqual(sec3, ['B'])                        # ekonomi drops down

    def test_a_designated_subject_with_no_grade_is_topped_up(self):
        # The #105 shape: Biology sits in the saved stream list but was never
        # sat, so the designation resolves to Add Maths alone.
        grades = {**CORES, 'addmath': 'A-', 'poa': 'A', 'ekonomi': 'A'}
        _s1, sec2, _s3 = prepare_merit_inputs(
            grades, stream_subjects=['bio', 'addmath'])
        self.assertEqual(len(sec2), 2)
        self.assertEqual(sorted(sec2), sorted(['A', 'A-']))

    def test_topping_up_never_lowers_the_merit_score(self):
        # Sec2 weights a point at 5/6 against Sec3's 5/18, so promoting a
        # subject out of Sec3 always gains more than its replacement loses.
        grades = {**CORES, 'addmath': 'A-', 'poa': 'A', 'ekonomi': 'A',
                  'sci': 'A', 'moral': 'A'}
        one_only = calculate_merit_score(
            [CORES['bm'], CORES['eng'], CORES['math'], CORES['history']],
            ['A-'],                       # what the old code produced
            ['A', 'A'], coq_score=0)
        s1, sec2, sec3 = prepare_merit_inputs(grades, stream_subjects=['addmath'])
        topped = calculate_merit_score(s1, sec2, sec3, coq_score=0)
        self.assertGreater(topped['final_merit'], one_only['final_merit'])

    def test_application_105_scores_as_the_ten_As_it_holds(self):
        # Production application #105: ten subjects, every one at A- or better,
        # reading 69.4 because 'bio' — never sat — held a Sec2 slot.
        grades = {'bm': 'A-', 'eng': 'A', 'poa': 'A', 'sci': 'A', 'history': 'A',
                  'math': 'A', 'moral': 'A', 'addmath': 'A-', 'b_tamil': 'A-',
                  'ekonomi': 'A'}
        s1, sec2, sec3 = prepare_merit_inputs(
            grades, stream_subjects=['bio', 'addmath'])
        merit = round(calculate_merit_score(s1, sec2, sec3, 7.49)['final_merit'], 1)
        self.assertEqual(merit, 84.4)   # was 69.4

    def test_two_designated_subjects_are_left_alone(self):
        # The top-up must touch NOTHING when the student named two or more —
        # their own picks stay Sec2 even when a stronger subject sits outside.
        grades = {**CORES, 'phy': 'C', 'chem': 'C', 'ekonomi': 'A+'}
        _s1, sec2, sec3 = prepare_merit_inputs(
            grades, stream_subjects=['phy', 'chem'])
        self.assertEqual(sorted(sec2), sorted(['C', 'C']))
        self.assertEqual(sec3, ['A+'])

    def test_all_designated_subjects_ungraded_still_falls_back(self):
        # Nothing designated survives → the legacy pool heuristic, unchanged.
        grades = {**CORES, 'ekonomi': 'A', 'poa': 'B'}
        self.assertEqual(
            prepare_merit_inputs(grades, stream_subjects=['bio']),
            prepare_merit_inputs(grades),
        )

    def test_a_lone_designation_with_nothing_to_top_up_from(self):
        # A student with only one non-core subject keeps a one-item Sec2 —
        # there is nothing to promote, and the top-up must not invent one.
        grades = {**CORES, 'addmath': 'A'}
        _s1, sec2, sec3 = prepare_merit_inputs(grades, stream_subjects=['addmath'])
        self.assertEqual(sec2, ['A'])
        self.assertEqual(sec3, [])
