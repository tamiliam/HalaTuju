"""Bumi coverage Sprint C — the Islamic-studies SPM subjects reach the engines as electives.

Owner ruling 2026-10-28: they are ordinary SPM subjects, open to anyone, with no religion
question. The grades form offers them as ELECTIVES (no stream), so:
  * merit — they sit in no stream pool, so the heuristic scores them in Sec3 (the electives),
    exactly as Pendidikan Islam always has; a student who designates none is unchanged;
  * STPM entry — a requirement naming the subject's code is met by the key the form saves;
    BAHASA_ARAB_MUASIRAH_SPM ("Al-Lughah Al-'Arabiah Al-Mu'asirah") is met by `lughah_arabiah`
    AND, as before, by `bahasa_arab`, counted once;
  * the AI report prompt names each subject, never a raw key.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.courses.engine import ARTS_POOL, SCIENCE_POOL, TECHNICAL_POOL, prepare_merit_inputs
from apps.courses.stpm_engine import SPM_CODE_MAP, check_spm_prerequisites
from apps.reports.report_engine import SUBJECT_LABELS
from apps.scholarship.academic_engine import _SUBJECT_BM

ISLAMIC_KEYS = (
    'islam', 'tasawwur_islam', 'pqs', 'psi', 'usul_aldin', 'al_syariah', 'manahij',
    'lughah_arabiah', 'adab_balaghah', 'hifz_alquran', 'maharat_alquran',
    'turath_islamiah', 'turath_quran_sunnah', 'turath_bahasa_arab',
)
CORES = {'bm': 'A', 'eng': 'A', 'math': 'A', 'hist': 'A'}


def _req(*groups):
    return SimpleNamespace(spm_subject_group=list(groups))


class TheMeritEngine(SimpleTestCase):
    def test_no_islamic_subject_is_in_a_stream_pool(self):
        self.assertEqual(set(ISLAMIC_KEYS) & (ARTS_POOL | TECHNICAL_POOL | SCIENCE_POOL), set())

    def test_an_islamic_subject_is_scored_as_an_elective(self):
        # the merit engine reads history as 'history' (the profile's grades are mapped first)
        grades = {'bm': 'A', 'eng': 'A', 'math': 'A', 'history': 'A',
                  'ekonomi': 'B', 'poa': 'B', 'tasawwur_islam': 'A+'}
        _s1, sec2, sec3 = prepare_merit_inputs(grades)
        self.assertEqual(sorted(sec2), ['B', 'B'])       # the Arts pair keeps the stream weight
        self.assertEqual(sec3, ['A+'])                    # Tasawwur Islam is an elective


class TheStpmSpmPrerequisites(SimpleTestCase):
    def test_every_islamic_requirement_code_maps_to_a_form_key(self):
        form_keys = set(ISLAMIC_KEYS)
        for code in ('PENDIDIKAN_ISLAM_SPM', 'PENDIDIKAN_SYARIAH_ISLAMIAH_SPM', 'USUL_AL_DIN_SPM',
                     'PENDIDIKAN_AL_QURAN_SPM', 'AL_SYARIAH_SPM', 'TASAWWUR_ISLAM_SPM',
                     'HIFZ_AL_QURAN_SPM', 'MAHARAT_AL_QURAN_SPM', 'MANAHIJ_SPM',
                     'TURATH_DIRASAT_ISLAMIAH_SPM', 'TURATH_AL_QURAN_SPM', 'AL_ADAB_SPM',
                     'TURATH_BAHASA_ARAB_SPM'):
            with self.subTest(code=code):
                self.assertIn(SPM_CODE_MAP[code], form_keys)

    def test_tasawwur_islam_meets_its_requirement(self):
        req = _req({'subjects': ['TASAWWUR_ISLAM_SPM', 'PENDIDIKAN_ISLAM_SPM'], 'min_count': 1,
                    'min_grade': 'C'})
        self.assertTrue(check_spm_prerequisites(req, {**CORES, 'tasawwur_islam': 'B'}))
        self.assertFalse(check_spm_prerequisites(req, {**CORES, 'tasawwur_islam': 'D'}))

    def test_muasirah_is_met_by_the_subjects_own_key(self):
        req = _req({'subjects': ['BAHASA_ARAB_MUASIRAH_SPM'], 'min_count': 1, 'min_grade': 'C'})
        self.assertTrue(check_spm_prerequisites(req, {**CORES, 'lughah_arabiah': 'B'}))

    def test_muasirah_is_still_met_by_bahasa_arab(self):
        # Unchanged for every existing student: the old reading is kept.
        req = _req({'subjects': ['BAHASA_ARAB_MUASIRAH_SPM'], 'min_count': 1, 'min_grade': 'C'})
        self.assertTrue(check_spm_prerequisites(req, {**CORES, 'bahasa_arab': 'B'}))
        self.assertFalse(check_spm_prerequisites(req, CORES))

    def test_holding_both_counts_the_code_once(self):
        req = _req({'subjects': ['BAHASA_ARAB_MUASIRAH_SPM'], 'min_count': 2, 'min_grade': 'C'})
        self.assertFalse(check_spm_prerequisites(req, {**CORES, 'bahasa_arab': 'A', 'lughah_arabiah': 'A'}))

    def test_an_excluded_muasirah_excludes_both_keys(self):
        req = _req({'exclude': ['BAHASA_ARAB_MUASIRAH_SPM'], 'min_count': 5, 'min_grade': 'C'})
        self.assertFalse(check_spm_prerequisites(req, {**CORES, 'lughah_arabiah': 'A'}))
        self.assertTrue(check_spm_prerequisites(req, {**CORES, 'lughah_arabiah': 'A', 'geo': 'A'}))


class TheReportPrompt(SimpleTestCase):
    def test_every_islamic_subject_has_its_slip_name(self):
        for key in ISLAMIC_KEYS:
            with self.subTest(key=key):
                self.assertEqual(SUBJECT_LABELS[key], _SUBJECT_BM[key])


class EachSubjectCountsOncePerGroup(SimpleTestCase):
    """Owner ruling 2026-10-29: a student's subject counts at most once per SPM prerequisite group.
    The fixture lists repeat codes (AL_ADAB_SPM twice in UA6145021 / UA6145033) and map several codes
    to one key (EKONOMI_SPM + EKONOMI_ASAS_SPM -> ekonomi), which counted one grade two or three times."""

    def test_adab_balaghah_alone_fails_a_two_subject_group(self):
        req = _req({'subjects': ['AL_ADAB_SPM', 'AL_ADAB_SPM', 'BAHASA_ARAB_SPM'], 'min_count': 2,
                    'min_grade': 'C'})
        self.assertFalse(check_spm_prerequisites(req, {'math': 'C', 'adab_balaghah': 'C'}))
        self.assertTrue(check_spm_prerequisites(req, {'adab_balaghah': 'C', 'bahasa_arab': 'C'}))

    def test_ekonomi_alone_fails_the_ua6314002_group(self):
        # UA6314002 (UPSI, Ekonomi (Kewangan Islam)) — the row the STPM golden master lost.
        req = _req({'min_count': 2, 'min_grade': 'C', 'subjects': [
            'PERDAGANGAN_SPM', 'EKONOMI_ASAS_SPM', 'PRINSIP_PERAKAUNAN_SPM', 'EKONOMI_SPM',
            'PERNIAGAAN_SPM', 'BAHASA_ARAB_SPM', 'BAHASA_ARAB_SPM', 'BAHASA_ARAB_TINGGI_SPM']},
            {'min_count': 1, 'min_grade': 'C', 'subjects': ['MATH', 'ADD_MATH']})
        self.assertFalse(check_spm_prerequisites(req, {'math': 'A', 'ekonomi': 'A', 'geo': 'A'}))
        self.assertTrue(check_spm_prerequisites(req, {'math': 'A', 'ekonomi': 'A', 'poa': 'B'}))

    def test_bahasa_arab_alone_no_longer_counts_twice(self):
        req = _req({'subjects': ['BAHASA_ARAB_SPM', 'BAHASA_ARAB_SPM', 'BAHASA_ARAB_MUASIRAH_SPM'],
                    'min_count': 2, 'min_grade': 'C'})
        self.assertFalse(check_spm_prerequisites(req, {'bahasa_arab': 'A'}))
        self.assertTrue(check_spm_prerequisites(req, {'bahasa_arab': 'A', 'lughah_arabiah': 'B'}))
