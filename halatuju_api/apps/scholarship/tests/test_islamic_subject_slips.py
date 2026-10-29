"""Bumi coverage Sprint C — the Islamic-studies SPM subjects on a results slip / certificate.

BrightPath request #48: a student's slip lists TASAWWUR ISLAM, the grades form could not offer it,
so the slip check said "Not entered yet" and the coach looped the student back to "Adjust my
grades". The form now offers the subject (subjects.ts); these tests hold the BACKEND half: every
one of the 13 subjects, printed as the slip prints it, reads as the subject the student entered.

The printed names are the Lembaga Peperiksaan subject names (codes 5226-5228, 5301-5305,
5401-5405), as the MOHE Syarat text spells them too. Two spellings differ only by an apostrophe
("SYARI'AH" / "SYARIAH", "MU'ASIRAH" / "MUASIRAH"); both must read as one subject.
Synthetic rows only — no real name, IC or grade.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.academic_engine import (
    _SUBJECT_BM, _norm_lower_alnum, compare_academics, parse_spm_slip, read_slip,
    student_slip_check,
)
from apps.scholarship.tests.test_academic_engine import _slip_words
from apps.scholarship.tests.test_certificate_parser import SUBJECTS, cert, read

#: key → how the slip prints it (upper case, as Lembaga Peperiksaan does).
PRINTED = {
    'tasawwur_islam': 'TASAWWUR ISLAM',
    'pqs': 'PENDIDIKAN AL-QURAN DAN AL-SUNNAH',
    'psi': 'PENDIDIKAN SYARIAH ISLAMIAH',
    'usul_aldin': 'USUL AL-DIN',
    'al_syariah': 'AL-SYARIAH',
    'manahij': "MANAHIJ AL-'ULUM AL-ISLAMIAH",
    'lughah_arabiah': "AL-LUGHAH AL-'ARABIAH AL-MU'ASIRAH",
    'adab_balaghah': 'AL-ADAB WA AL-BALAGHAH',
    'hifz_alquran': 'HIFZ AL-QURAN',
    'maharat_alquran': 'MAHARAT AL-QURAN',
    'turath_islamiah': 'TURATH DIRASAT ISLAMIAH',
    'turath_quran_sunnah': 'TURATH AL-QURAN DAN AL-SUNNAH',
    'turath_bahasa_arab': 'TURATH BAHASA ARAB',
}
#: The same subjects as the MOHE Syarat text spells them (another real source, other apostrophes).
MOHE_SPELLING = {
    'psi': "Pendidikan Syari'ah Islamiah",
    'lughah_arabiah': "Al-lughah Al-arabiah Al-mu'asirah",
    'hifz_alquran': 'Hifz Al Quran',
    'maharat_alquran': 'Maharat Al Quran',
    'manahij': "Manahij Al-'ulum Al-islamiah",
}
CORE_ROWS = [('BAHASA MELAYU', 'A-', 'CEMERLANG'), ('BAHASA INGGERIS', 'B', 'KEPUJIAN TINGGI'),
             ('SEJARAH', 'A', 'CEMERLANG TINGGI'), ('MATEMATIK', 'C+', 'KEPUJIAN ATAS')]
CORE_GRADES = {'bm': 'A-', 'eng': 'B', 'hist': 'A', 'math': 'C+'}
HEADER = [('SIJIL PELAJARAN MALAYSIA', 200), ('NUR AISYAH BINTI AHMAD', 250)]


def _gemini_doc(results, grades):
    """A slip read by the Gemini fallback: the subject names come back as PRINTED, not matched."""
    return SimpleNamespace(
        doc_type='results_slip', vision_name_match='found',
        vision_fields={'fields': {'results': results, 'candidate_name': 'NUR AISYAH BINTI AHMAD',
                                  'exam': 'SIJIL PELAJARAN MALAYSIA TAHUN 2025'},
                       'student_verdict': 'ok'},
        application=SimpleNamespace(profile=SimpleNamespace(grades=grades), cohort=None))


class TheThirteenSubjectsHaveSlipNames(SimpleTestCase):
    def test_every_printed_name_normalises_to_the_engine_name(self):
        for key, printed in PRINTED.items():
            with self.subTest(key=key):
                self.assertEqual(_norm_lower_alnum(printed), _norm_lower_alnum(_SUBJECT_BM[key]))

    def test_the_mohe_spelling_reads_the_same(self):
        for key, spelt in MOHE_SPELLING.items():
            with self.subTest(key=key):
                self.assertEqual(_norm_lower_alnum(spelt), _norm_lower_alnum(_SUBJECT_BM[key]))

    def test_an_apostrophe_is_dropped_not_spaced(self):
        self.assertEqual(_norm_lower_alnum("SYARI'AH"), 'syariah')
        self.assertEqual(_norm_lower_alnum('MU’ASIRAH'), 'muasirah')


class TheExactSlipReader(SimpleTestCase):
    """`parse_spm_slip` — the deterministic positional read of an SPM slip."""

    def test_every_subject_row_resolves_to_its_engine_name(self):
        for key, printed in PRINTED.items():
            with self.subTest(key=key):
                rows = CORE_ROWS + [(printed, 'A', 'CEMERLANG TINGGI')]
                out = parse_spm_slip(_slip_words(HEADER, rows))
                got = {r['subject']: r['grade'] for r in out['results']}
                self.assertEqual(got.get(_SUBJECT_BM[key]), 'A', got)

    def test_turath_bahasa_arab_is_not_read_as_bahasa_arab(self):
        out = parse_spm_slip(_slip_words(HEADER, CORE_ROWS + [('TURATH BAHASA ARAB', 'B', 'KEPUJIAN TINGGI')]))
        self.assertIn('Turath Bahasa Arab', [r['subject'] for r in out['results']])
        self.assertNotIn('Bahasa Arab', [r['subject'] for r in out['results']])


class TheSlipCheck(SimpleTestCase):
    """`student_slip_check` — what the student sees ("Not entered yet") and the coach reads."""

    def test_request_48_tasawwur_islam_entered_is_a_match(self):
        results = [{'subject': 'BAHASA MELAYU', 'grade': 'A-'}, {'subject': 'SEJARAH', 'grade': 'A'},
                   {'subject': 'TASAWWUR ISLAM', 'grade': 'B+'}]
        chk = student_slip_check(_gemini_doc(results, {'bm': 'A-', 'hist': 'A', 'tasawwur_islam': 'B+'}))
        self.assertEqual(chk['subjects'], 'match')
        self.assertEqual(chk['results'], 'match')
        self.assertEqual(chk['missing'], [])

    def test_request_48_before_the_fix_it_was_missing(self):
        # The shape #48 saw: the slip has it, the profile cannot (the form did not offer it).
        results = [{'subject': 'BAHASA MELAYU', 'grade': 'A-'}, {'subject': 'TASAWWUR ISLAM', 'grade': 'B+'}]
        chk = student_slip_check(_gemini_doc(results, {'bm': 'A-'}))
        self.assertEqual(chk['subjects'], 'mismatch')
        self.assertEqual(chk['missing'], ['TASAWWUR ISLAM'])

    def test_every_subject_as_printed_matches_the_entered_key(self):
        results = [{'subject': p, 'grade': 'A'} for p in PRINTED.values()]
        cmp = compare_academics({k: 'A' for k in PRINTED}, read_slip(_gemini_doc(results, {})))
        self.assertEqual(cmp['missing'], [])
        self.assertEqual(cmp['mismatched'], [])
        self.assertTrue(cmp['complete'])

    def test_the_other_apostrophe_spelling_also_matches(self):
        results = [{'subject': s, 'grade': 'B'} for s in MOHE_SPELLING.values()]
        cmp = compare_academics({k: 'B' for k in MOHE_SPELLING}, read_slip(_gemini_doc(results, {})))
        self.assertEqual(cmp['missing'], [])


class TheCertificateReader(SimpleTestCase):
    """`spm_cert_parse` — a line in the subject column must BE a known subject, word for word.
    A hyphenated word ("AL-DIN") is split before the comparison (it read as one word before)."""

    def test_each_subject_reads_on_a_certificate(self):
        for key, printed in PRINTED.items():
            with self.subTest(key=key):
                subjects = SUBJECTS[:4] + [(printed, 'B (KEPUJIAN TINGGI)')]
                r = read(cert(subjects))
                self.assertIsNotNone(r)
                self.assertEqual(r['results'][4]['subject'], _SUBJECT_BM[key])
                self.assertEqual(r['results'][4]['grade'], 'B')

    def test_an_unknown_hyphenated_line_still_falls_back(self):
        self.assertIsNone(read(cert(SUBJECTS[:4] + [('AL-KLINGON', 'B (KEPUJIAN TINGGI)')])))


# ── Sprint C review: stored reads, and looser printing ────────────────────────────────────────
#: Subject strings exactly as they sit in live stored reads (18 of 2,313 carry an Islamic subject;
#: queried by the lead 2026-10-29) → the key the student enters. Stored reads are never re-read.
LIVE_STORED = [
    ('Pendidikan Al-Quran & Al-Sunnah', 'pqs'),
    ("MANAHIJ AL-'ULUM AL-ISLAMIAH", 'manahij'),
    ("AL-LUGHAH AL-ARABIAH AL-MU'ASIRAH", 'lughah_arabiah'),
    ('5302 MAHARAT AL - QURAN B + KEPUJIAN TERTINGGI', 'maharat_alquran'),
    ('5301 HIFZ AL - QURAN B + KEPUJIAN TERTINGGI', 'hifz_alquran'),
    ('TASAWWUR ISLAM B + ( KEPUJIAN TERTINGGI )', 'tasawwur_islam'),
    ('5228 PENDIDIKAN SYARIAH ISLAMIAH B + KEPUJIAN TERTINGGI', 'psi'),
    ('AL-SYARIAH', 'al_syariah'),
    ('USUL AL-DIN', 'usul_aldin'),
    ('Pendidikan Syariah Islamiah', 'psi'),
    ('Maharat Al-Quran', 'maharat_alquran'),
    ('Hifz Al-Quran', 'hifz_alquran'),
    ('Tasawwur Islam', 'tasawwur_islam'),
]
#: The names before Sprint C (what a read stored before MODEL_VERSION 1.18.0 may hold).
OLD_NAMES = [('Manahij', 'manahij'), ('Lughah Arabiah', 'lughah_arabiah'),
             ('Adab & Balaghah', 'adab_balaghah'), ('Turath Islamiah', 'turath_islamiah'),
             ('Turath Quran & Sunnah', 'turath_quran_sunnah'),
             ('Pendidikan Al-Quran & Al-Sunnah', 'pqs')]


class TheStoredReads(SimpleTestCase):
    def _missing(self, stored, key):
        slip = read_slip(_gemini_doc([{'subject': stored, 'grade': 'B+'}], {}))
        return compare_academics({key: 'B+'}, slip)

    def test_every_live_stored_string_matches_its_key(self):
        for stored, key in LIVE_STORED:
            with self.subTest(stored=stored):
                cmp = self._missing(stored, key)
                self.assertEqual(cmp['missing'], [])
                self.assertEqual(cmp['mismatched'], [])

    def test_every_old_short_name_still_matches(self):
        for old, key in OLD_NAMES:
            with self.subTest(old=old):
                self.assertEqual(self._missing(old, key)['missing'], [])

    def test_a_cell_with_another_word_is_not_folded_into_a_subject(self):
        # "UJIAN LISAN BAHASA MELAYU" is the oral test, not Bahasa Melayu: it must stay its own row.
        cmp = self._missing('UJIAN LISAN BAHASA MELAYU', 'bm')
        self.assertEqual(cmp['missing'], ['UJIAN LISAN BAHASA MELAYU'])

    def test_the_missing_list_still_shows_the_printed_text(self):
        cmp = self._missing('5302 MAHARAT AL - QURAN B + KEPUJIAN TERTINGGI', 'bm')
        self.assertEqual(len(cmp['missing']), 1)
        self.assertTrue(cmp['missing'][0].startswith('5302 MAHARAT'))


class TheLooserPrinting(SimpleTestCase):
    def test_apostrophe_forms_and_a_lone_apostrophe(self):
        for printed in ("MU'ASIRAH", 'MU’ASIRAH', 'MU‘ASIRAH', 'MUʼASIRAH',
                        'MUʻASIRAH', 'MU´ASIRAH', 'MU′ASIRAH', 'MU`ASIRAH',
                        "MU ' ASIRAH", 'MUASIRAH'):
            with self.subTest(printed=printed):
                self.assertEqual(_norm_lower_alnum(printed), 'muasirah')

    def test_ampersand_reads_as_dan_and_a_spaced_hyphen_as_a_hyphen(self):
        self.assertEqual(_norm_lower_alnum('Al-Quran & Al-Sunnah'), _norm_lower_alnum('AL-QURAN DAN AL-SUNNAH'))
        self.assertEqual(_norm_lower_alnum('HIFZ AL - QURAN'), _norm_lower_alnum('Hifz Al-Quran'))

    def test_no_two_subjects_share_a_name_or_a_word_set(self):
        from apps.scholarship.academic_engine import _KNOWN_SUBJECTS
        norms = {}
        for name in set(_SUBJECT_BM.values()):
            norms.setdefault(_norm_lower_alnum(name), set()).add(name)
        self.assertEqual([v for v in norms.values() if len(v) > 1], [])
        sets = {}
        for name, words in _KNOWN_SUBJECTS:
            sets.setdefault(words, set()).add(name)
        self.assertEqual([v for v in sets.values() if len(v) > 1], [])

    def test_the_exact_slip_reader_takes_the_loose_forms(self):
        for printed, key in (('HIFZ AL - QURAN', 'hifz_alquran'),
                             ("AL-LUGHAH AL-'ARABIAH AL-MU ' ASIRAH", 'lughah_arabiah'),
                             ('PENDIDIKAN AL-QURAN & AL-SUNNAH', 'pqs')):
            with self.subTest(printed=printed):
                out = parse_spm_slip(_slip_words(HEADER, CORE_ROWS + [(printed, 'A', 'CEMERLANG TINGGI')]))
                self.assertIn(_SUBJECT_BM[key], [r['subject'] for r in out['results']])

    def test_the_certificate_reader_takes_the_loose_forms_and_old_names(self):
        for printed, key in (('HIFZ AL - QURAN', 'hifz_alquran'),
                             ("MANAHIJ AL - 'ULUM AL - ISLAMIAH", 'manahij'),
                             ("AL-LUGHAH AL-'ARABIAH AL-MU ' ASIRAH", 'lughah_arabiah'),
                             ('PENDIDIKAN AL-QURAN & AL-SUNNAH', 'pqs'),
                             ('MANAHIJ', 'manahij')):
            with self.subTest(printed=printed):
                r = read(cert(SUBJECTS[:4] + [(printed, 'B (KEPUJIAN TINGGI)')]))
                self.assertIsNotNone(r)
                self.assertEqual(r['results'][4]['subject'], _SUBJECT_BM[key])
