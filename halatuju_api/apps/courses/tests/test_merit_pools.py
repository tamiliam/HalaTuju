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
