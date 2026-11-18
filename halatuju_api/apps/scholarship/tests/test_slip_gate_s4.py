"""OCR-first S4 (2026-11-18): the SPM slip gate reads the DOCUMENT, not the profile.

Before S4, `_extract_slip_deterministic` refused the positional parser (``not_spm_exam``) whenever
the profile's `results_held` was not 'spm' — so an STPM, Matriculation or Diploma student's own SPM
slip always went to the model (115 of 158 AI-read slips). Now the page decides: a page that names
non-SPM results is refused; every other page goes to the parser, whose own SPM markers lock it.
The profile is recorded as a hint (``profile_held``), never a veto.

Synthetic words only (fictional names, no real slip). No Vision or model call: ``words`` is passed.
"""
from types import SimpleNamespace
from unittest import mock

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


class TestSchoolLevelAndTrialSlipsAreRefused(SimpleTestCase):
    """S4 fix round (adversarial review, MEDIUM): the same board's school-level slips and a trial
    paper carry the parser's own marker and SPM-shaped band rows, so the parser alone LOCKS them and
    maps their bands to SPM grades. Each is refused by its title, through the real gate."""
    PAGES = {
        'pt3': [('LEMBAGA PEPERIKSAAN', 150), ('PENTAKSIRAN TINGKATAN 3', 200)],
        'pt3 code': [('LEMBAGA PEPERIKSAAN', 150), ('KEPUTUSAN PT3', 200)],
        'pmr': [('LEMBAGA PEPERIKSAAN', 150), ('PENILAIAN MENENGAH RENDAH', 200)],
        'upsr': [('LEMBAGA PEPERIKSAAN', 150), ('UJIAN PENCAPAIAN SEKOLAH RENDAH', 200)],
        'trial': [('PEPERIKSAAN PERCUBAAN SIJIL PELAJARAN MALAYSIA', 200)],
        'trial english': [('SIJIL PELAJARAN MALAYSIA TRIAL EXAMINATION', 200)],
    }
    KIND = {'pt3': 'pt3', 'pt3 code': 'pt3', 'pmr': 'pmr', 'upsr': 'upsr', 'trial': 'trial',
            'trial english': 'trial'}

    def test_each_is_refused_though_the_parser_alone_would_lock_it(self):
        from apps.scholarship.academic_engine import parse_spm_slip
        for page, header in self.PAGES.items():
            words = _slip_words(header + [('CALON CONTOH BINTI REKAAN', 250)], SPM_ROWS)
            with self.subTest(page=page):
                self.assertIsNotNone(parse_spm_slip(words))     # the hazard is real
                ex, diag = _gate(dict(exam_type='spm', grades={'bm': 'A'}), words)
                self.assertIsNone(ex)
                self.assertEqual((diag['reason'], diag['exam_type'], diag['by']),
                                 ('not_spm_exam', self.KIND[page], 'document'))

    def test_the_trial_list_is_the_one_wrong_slip_uses(self):
        from apps.scholarship.wrong_slip import _NOT_A_RESULT
        self.assertTrue(_NOT_A_RESULT.search('PEPERIKSAAN PERCUBAAN SPM'))
        self.assertEqual(slip_not_spm_kind('SURAT TAWARAN SIJIL PELAJARAN MALAYSIA'), 'not_a_result')


class TestTheTrialAndOfferWordsAreReadInTheTitleZoneOnly(SimpleTestCase):
    """S4 review 2 (LOW): `_NOT_A_RESULT` reads the title zone only — as `wrong_slip` reads it in the
    exam title alone — so a footer, a portal menu or a scanner's "trial version" stamp never refuses a
    real SPM slip, while a slip whose TITLE is a trial or an offer still is."""
    FOOTERS = ('PORTAL PENDAFTARAN PELAJAR', 'SEMAK TAWARAN UPU', 'OFFER LETTER DOWNLOAD',
               'TRIAL VERSION SCANNER APP', 'REGISTRATION', 'LAPOR DIRI', 'PERCUBAAN')

    def test_a_footer_word_never_refuses_a_real_slip(self):
        for footer in self.FOOTERS:
            words = _slip_words(_header('SIJIL PELAJARAN MALAYSIA') + [(footer, 900)], SPM_ROWS)
            with self.subTest(footer=footer):
                ex, diag = _gate(NON_SPM_PROFILES['stpm'], words)
                self.assertEqual(diag['reason'], 'ok')
                self.assertEqual(_grades(ex), EXPECTED)

    def test_a_footer_word_in_the_ocr_text_never_refuses_it_before_the_word_boxes(self):
        body = '\n'.join(f'{s} {g} {b}' for s, g, b in SPM_ROWS)
        words = _slip_words(_header('SIJIL PELAJARAN MALAYSIA'), SPM_ROWS)
        for footer in self.FOOTERS:
            text = f'LEMBAGA PEPERIKSAAN\nSIJIL PELAJARAN MALAYSIA\nCALON CONTOH\n{body}\n{footer}'
            with self.subTest(footer=footer):
                self.assertEqual(slip_not_spm_kind(text), '')
                doc = SimpleNamespace(application=SimpleNamespace(
                    profile=StudentProfile(supabase_user_id='s4-gate', **NON_SPM_PROFILES['stpm'])),
                    content_type='image/jpeg')
                with mock.patch('apps.scholarship.vision._vision_words',
                                return_value={'words': words, 'error': None}):
                    ex, diag = vision._extract_slip_deterministic(doc, b'img', text=text)
                self.assertEqual(diag['reason'], 'ok')
                self.assertEqual(_grades(ex), EXPECTED)

    def test_a_trial_or_offer_title_is_still_refused(self):
        for header, kind in (([('PEPERIKSAAN PERCUBAAN', 150), ('SIJIL PELAJARAN MALAYSIA', 200)], 'trial'),
                             ([('SURAT TAWARAN', 150), ('SIJIL PELAJARAN MALAYSIA', 200)], 'not_a_result'),
                             ([('SIJIL PELAJARAN MALAYSIA', 150), ('TRIAL EXAMINATION 2024', 200)], 'trial')):
            words = _slip_words(header + [('CALON CONTOH BINTI REKAAN', 250)], SPM_ROWS)
            with self.subTest(kind=kind, title=header[0][0]):
                ex, diag = _gate(dict(exam_type='spm', grades={'bm': 'A'}), words)
                self.assertIsNone(ex)
                self.assertEqual((diag['reason'], diag['exam_type']), ('not_spm_exam', kind))

    def test_the_text_title_zone_stops_at_the_first_subject(self):
        self.assertEqual(slip_not_spm_kind('SIJIL PELAJARAN MALAYSIA BAHASA MELAYU A- TRIAL VERSION'), '')
        self.assertEqual(slip_not_spm_kind('PEPERIKSAAN PERCUBAAN SPM BAHASA MELAYU A-'), 'trial')
        nine = '\n'.join(['SIJIL PELAJARAN MALAYSIA'] + ['CALON CONTOH'] * 8 + ['TAWARAN'])
        self.assertEqual(slip_not_spm_kind(nine), '')                      # past the first 8 lines


class TestTheTextCheckReadsPageOneOfADigitalPdf(SimpleTestCase):
    """S4 review 2 (LOW): a digital PDF's OCR text is its WHOLE text layer, but the word boxes read
    page 1 only — so the text check reads page 1's layer too."""
    PAGE1 = 'SIJIL PELAJARAN MALAYSIA\nCALON CONTOH'
    PAGE2 = 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA\nPEPERIKSAAN PERCUBAAN'
    WORDS = _slip_words(_header('SIJIL PELAJARAN MALAYSIA'), SPM_ROWS)

    def _run(self, text, layers):
        doc = SimpleNamespace(application=SimpleNamespace(
            profile=StudentProfile(supabase_user_id='s4-gate', **NON_SPM_PROFILES['stpm'])),
            content_type='application/pdf')
        with mock.patch('apps.scholarship.offer_exact.pdf_layers', return_value=layers), \
                mock.patch('apps.scholarship.vision._vision_words',
                           return_value={'words': self.WORDS, 'error': None}) as vw:
            ex, diag = vision._extract_slip_deterministic(doc, b'%PDF-1.4', text=text)
        return ex, diag, vw

    def test_page_two_of_the_layer_never_refuses_page_one(self):
        layer = f'{self.PAGE1}\n{self.PAGE2}'
        ex, diag, vw = self._run(layer, (layer, self.PAGE1))
        vw.assert_called_once()
        self.assertEqual(diag['reason'], 'ok')
        self.assertEqual(_grades(ex), EXPECTED)

    def test_page_one_of_the_layer_is_still_checked(self):
        layer = f'{self.PAGE2}\n{self.PAGE1}'
        ex, diag, vw = self._run(layer, (layer, self.PAGE2))
        vw.assert_not_called()
        self.assertIsNone(ex)
        self.assertEqual((diag['reason'], diag['exam_type'], diag['source']), ('not_spm_exam', 'trial', 'ocr_text'))

    def test_a_scanned_page_one_leaves_it_to_the_word_boxes(self):
        layer = self.PAGE2
        ex, diag, vw = self._run(layer, (layer, ''))
        vw.assert_called_once()
        self.assertEqual(diag['reason'], 'ok')

    def test_text_that_is_not_the_layer_is_vision_page_one_and_kept(self):
        ex, diag, vw = self._run(self.PAGE2, ('SOME OTHER LAYER', 'SOME OTHER LAYER'))
        vw.assert_not_called()
        self.assertEqual(diag['exam_type'], 'trial')


class TestTitleEdges(SimpleTestCase):
    """S4 fix round (LOW): the vocational title in brackets, and whole-word short codes."""

    def test_the_bracketed_vocational_titles_are_refused(self):
        for text in ('SIJIL PELAJARAN MALAYSIA (VOKASIONAL) TAHUN 2024', 'SIJIL PELAJARAN MALAYSIA ( VOKASIONAL )',
                     'KEPUTUSAN SPM(V) 2024', 'KEPUTUSAN SPM (V) 2024', 'KEPUTUSAN SPMV'):
            with self.subTest(text=text):
                self.assertEqual(slip_not_spm_kind(text), 'spmv')

    def test_the_bracketed_vocational_page_is_refused_through_the_gate(self):
        words = _slip_words(_header('SIJIL PELAJARAN MALAYSIA (VOKASIONAL)'), SPM_ROWS)
        ex, diag = _gate(dict(exam_type='spm', grades={'bm': 'A'}), words)
        self.assertIsNone(ex)
        self.assertEqual(diag['exam_type'], 'spmv')

    def test_a_code_glued_to_a_letter_or_digit_is_not_a_title(self):
        for text in ('SIJIL PELAJARAN MALAYSIA UEC1234', 'SIJIL PELAJARAN MALAYSIA STAM2',
                     'SIJIL PELAJARAN MALAYSIA 2PMR', 'SMK DIPLOMAT', 'SIJIL PELAJARAN MALAYSIA STAMPED',
                     'SIJIL PELAJARAN MALAYSIA SVMX'):
            with self.subTest(text=text):
                self.assertEqual(slip_not_spm_kind(text), '')

    def test_a_standalone_code_is_still_a_title(self):
        for text, kind in (('UEC 2023', 'uec'), ('STAM 2024', 'stam'), ('SVM', 'svm'), ('PMR 2010', 'pmr'),
                           ('UPSR', 'upsr'), ('PT3', 'pt3')):
            with self.subTest(text=text):
                self.assertEqual(slip_not_spm_kind(text), kind)


class TestTheTextIsCheckedBeforeWordBoxesAreBought(SimpleTestCase):
    """S4 fix round (LOW): the OCR text the caller holds is checked first, so a misfiled non-SPM page
    costs no Vision words call."""

    def _doc(self):
        profile = StudentProfile(supabase_user_id='s4-gate', **NON_SPM_PROFILES['stpm'])
        return SimpleNamespace(application=SimpleNamespace(profile=profile), content_type='image/jpeg')

    def test_a_non_spm_text_is_refused_without_a_vision_call(self):
        with mock.patch('apps.scholarship.vision._vision_words',
                        side_effect=AssertionError('no Vision call for a refused page')) as vw:
            ex, diag = vision._extract_slip_deterministic(
                self._doc(), b'img', text='SIJIL TINGGI PERSEKOLAHAN MALAYSIA KEPUTUSAN')
        vw.assert_not_called()
        self.assertIsNone(ex)
        self.assertEqual(diag, {'reason': 'not_spm_exam', 'exam_type': 'stpm', 'by': 'document',
                                'source': 'ocr_text', 'profile_held': 'stpm', 'reader': SLIP_READER_VERSION})

    def test_an_spm_text_buys_the_word_boxes_and_locks(self):
        words = _slip_words(_header('SIJIL PELAJARAN MALAYSIA'), SPM_ROWS)
        with mock.patch('apps.scholarship.vision._vision_words',
                        return_value={'words': words, 'error': None}) as vw:
            ex, diag = vision._extract_slip_deterministic(self._doc(), b'img',
                                                          text='SIJIL PELAJARAN MALAYSIA TAHUN 2024')
        vw.assert_called_once()
        self.assertEqual(diag['reason'], 'ok')
        self.assertEqual(_grades(ex), EXPECTED)


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
