"""OCR-first S4 (2026-11-18): the SPM slip gate reads the DOCUMENT, not the profile.

Before S4, `_extract_slip_deterministic` refused the positional parser (``not_spm_exam``) whenever
the profile's `results_held` was not 'spm' — so an STPM, Matriculation or Diploma student's own SPM
slip always went to the model (115 of 158 AI-read slips). Now the page decides: a page that names
non-SPM results is refused; every other page goes to the parser, whose own SPM markers lock it.
The profile is recorded as a hint (``profile_held``), never a veto.

Synthetic words only (fictional names, no real slip). No Vision or model call: ``words`` is passed.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.courses.models import StudentProfile
from apps.scholarship import vision
from apps.scholarship.tests.test_academic_engine import _slip_words
from apps.scholarship.vision.field_extraction import SLIP_READER_VERSION, slip_not_spm_kind

SPM_ROWS = [
    ('BAHASA MELAYU', 'A-', 'CEMERLANG'),
    ('BAHASA INGGERIS', 'C+', 'KEPUJIAN ATAS'),
    ('SEJARAH', 'B', 'KEPUJIAN TINGGI'),
    ('MATEMATIK', 'A-', 'CEMERLANG'),
    ('SAINS', 'B+', 'KEPUJIAN TERTINGGI'),
]
EXPECTED = {'Bahasa Melayu': 'A-', 'Bahasa Inggeris': 'C+', 'Sejarah': 'B', 'Matematik': 'A-',
            'Sains': 'B+'}


def _header(title):
    return [(title, 200), ('CALON CONTOH BINTI REKAAN', 250)]


#: Profiles that are NOT SPM-holding — each one vetoed the parser before S4.
NON_SPM_PROFILES = {
    'stpm': dict(exam_type='stpm', stpm_grades={'PA': 'A'}, stpm_cgpa=3.5, results_exam_type='stpm'),
    'matric': dict(exam_type='matric', higher_cgpa=3.5, results_exam_type='matric',
                   completed_qualifications=['spm', 'matric']),
    'diploma': dict(exam_type='diploma', higher_cgpa=2.8, results_exam_type='diploma',
                    completed_qualifications=['spm', 'diploma']),
}


def _gate(profile_fields, words):
    profile = StudentProfile(supabase_user_id='s4-gate', **profile_fields)
    doc = SimpleNamespace(application=SimpleNamespace(profile=profile), content_type='image/jpeg')
    return vision._extract_slip_deterministic(doc, b'img', words=words)


def _grades(ex):
    return {r['subject']: r['grade'] for r in ex['fields']['results']}


class TestAnSpmSlipReachesTheParserWhateverTheProfile(SimpleTestCase):
    WORDS = _slip_words(_header('SIJIL PELAJARAN MALAYSIA'), SPM_ROWS)

    def test_an_spm_profile_still_locks(self):
        ex, diag = _gate(dict(exam_type='spm', grades={'bm': 'A'}), self.WORDS)
        self.assertEqual(diag['reason'], 'ok')
        self.assertEqual(_grades(ex), EXPECTED)

    def test_a_non_spm_profile_reaches_the_parser_and_locks_the_same_grades(self):
        for held, fields in NON_SPM_PROFILES.items():
            with self.subTest(profile=held):
                ex, diag = _gate(fields, self.WORDS)
                self.assertEqual(diag, {'reason': 'ok', 'profile_held': held})   # hint recorded
                self.assertEqual(_grades(ex), EXPECTED)
                self.assertEqual(ex['parser_version'], SLIP_READER_VERSION)

    def test_the_lembaga_marker_alone_also_reaches_the_parser(self):
        words = _slip_words(_header('LEMBAGA PEPERIKSAAN'), SPM_ROWS)
        ex, diag = _gate(NON_SPM_PROFILES['stpm'], words)
        self.assertEqual(diag['reason'], 'ok')
        self.assertEqual(_grades(ex), EXPECTED)

    def test_the_parser_never_writes_the_profile(self):
        fields = NON_SPM_PROFILES['stpm']
        profile = StudentProfile(supabase_user_id='s4-gate', **fields)
        doc = SimpleNamespace(application=SimpleNamespace(profile=profile), content_type='image/jpeg')
        vision._extract_slip_deterministic(doc, b'img', words=self.WORDS)
        self.assertEqual(profile.stpm_grades, {'PA': 'A'})
        self.assertEqual(profile.stpm_cgpa, 3.5)
        self.assertFalse(profile.grades)

    def test_spm_slip_text_names_no_other_results(self):
        self.assertEqual(slip_not_spm_kind('SIJIL PELAJARAN MALAYSIA TAHUN 2024 BAHASA MELAYU A-'), '')
        self.assertEqual(slip_not_spm_kind(''), '')
        self.assertEqual(slip_not_spm_kind(None), '')


class TestANonSpmPageIsStillRefused(SimpleTestCase):
    """Refused by what the page says, under an SPM profile too (the profile never rescues it)."""
    PAGES = {
        'stpm': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA',
        'matric': 'PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN MALAYSIA',
        'spmv': 'SIJIL PELAJARAN MALAYSIA VOKASIONAL',
        'svm': 'SIJIL VOKASIONAL MALAYSIA',
        'igcse': 'CAMBRIDGE IGCSE STATEMENT OF RESULTS',
        'o_level': 'GCE O LEVEL STATEMENT OF RESULTS',
    }

    def test_each_non_spm_title_is_refused_by_the_document(self):
        for kind, title in self.PAGES.items():
            words = _slip_words(_header(title), SPM_ROWS)
            for held, fields in [('spm', dict(exam_type='spm', grades={'bm': 'A'})),
                                 ('stpm', NON_SPM_PROFILES['stpm'])]:
                with self.subTest(page=kind, profile=held):
                    ex, diag = _gate(fields, words)
                    self.assertIsNone(ex)
                    self.assertEqual(diag['reason'], 'not_spm_exam')
                    self.assertEqual(diag['exam_type'], kind)
                    self.assertEqual(diag['by'], 'document')
                    self.assertEqual(diag['profile_held'], held)
                    self.assertEqual(diag['reader'], SLIP_READER_VERSION)

    def test_titles_match_whole_words_only(self):
        # A subject or a name that merely CONTAINS the letters is not a title.
        self.assertEqual(slip_not_spm_kind('SIJIL PELAJARAN MALAYSIA PENDIDIKAN ISLAM STAMPED'), '')
        self.assertEqual(slip_not_spm_kind('SIJIL PELAJARAN MALAYSIA SVMX'), '')


class TestTheFallbacksCarryTheReaderStamp(SimpleTestCase):
    def test_no_words_and_parse_none_carry_the_stamp(self):
        _ex, diag = _gate(NON_SPM_PROFILES['diploma'], [])
        self.assertEqual(diag, {'reason': 'no_words', 'reader': SLIP_READER_VERSION})
        # SPM title but too few subject rows to lock → the model reads it, as before
        words = _slip_words(_header('SIJIL PELAJARAN MALAYSIA'), SPM_ROWS[:1])
        ex, diag = _gate(NON_SPM_PROFILES['diploma'], words)
        self.assertIsNone(ex)
        self.assertEqual(diag['reason'], 'parse_none')
        self.assertEqual(diag['reader'], SLIP_READER_VERSION)

    def test_no_image_is_unchanged(self):
        doc = SimpleNamespace(application=SimpleNamespace(profile=None), content_type='image/jpeg')
        self.assertEqual(vision._extract_slip_deterministic(doc, None), (None, {'reason': 'no_image'}))
