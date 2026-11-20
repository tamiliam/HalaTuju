"""OCR-first S5 — the SPM results-slip AI read moves off 2.5 Flash onto 3.8 Flash, safely.

SPM grades feed eligibility: refusing (a failed read) is always safe, a wrong grade is not. So the
slip schema asks for a closed grade enum with every key required, every answer is checked
(`vision.sanitize.clean_slip_grade` / `clean_slip_text`), a malformed answer is asked ONCE more on
3.8, and a second malformed answer is a failed read. A 2.5 model is never called for a slip.

The sanitiser cases follow the 26 failure shapes of the paid eval ("Aplus", stray JSON, tab and
CJK characters). Synthetic data only; every model call is mocked, nothing leaves the machine.
"""
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import vision
from apps.scholarship.academic_engine import _GRADE_TO_BAND
from apps.scholarship.read_errors import DOCUMENT_FAILED, is_ai_service_error
from apps.scholarship.vision import slip_read
from apps.scholarship.vision.sanitize import clean_slip_grade, clean_slip_text
from apps.scholarship.vision.schemas import _FIELD_SCHEMAS, SLIP_BLANK, SLIP_GRADES

_SEAM = 'apps.scholarship.vision._call_gemini_json'


def _good(grade='A', subject='MATEMATIK', band=None):
    """A good two-row answer; the second row's band (by default) is the one that says ``grade``,
    so a valid grade with its own band is never a band-vs-letter conflict (review round 3)."""
    if band is None:
        band = _GRADE_TO_BAND.get(clean_slip_grade(grade) or '', 'cemerlang tinggi').upper()
    return {'candidate_name': 'CALON CONTOH', 'exam': 'SPM 2025',
            'results': [{'subject': 'BAHASA MELAYU', 'grade': 'A+', 'band': 'CEMERLANG TERTINGGI'},
                        {'subject': subject, 'grade': grade, 'band': band}],
            'warnings': []}


def _read(*answers):
    """The slip read through the real `extract_document_fields`, the seam answering ``answers`` in
    turn; returns (result, the models each call was given)."""
    with patch(_SEAM, side_effect=list(answers)) as seam:
        out = vision.extract_document_fields('SIJIL PELAJARAN MALAYSIA', 'results_slip')
    return out, [c.kwargs.get('models') for c in seam.call_args_list]


class TheSlipSchema(SimpleTestCase):
    def setUp(self):
        self.schema = _FIELD_SCHEMAS['results_slip']
        self.row = self.schema['properties']['results']['items']

    def test_the_grade_set_is_the_academic_engines(self):
        from apps.scholarship.academic_engine import _GRADE_TOKENS
        self.assertEqual(set(SLIP_GRADES), set(_GRADE_TOKENS))

    def test_each_grade_is_an_enum_of_the_grades_plus_the_blank_word(self):
        """Fix round 4: Gemini refused '' in the enum (400 on all 98 paid calls); the blank word
        stands in for it and is never empty."""
        grade = self.row['properties']['grade']
        self.assertEqual(grade['type'], 'string')
        self.assertEqual(grade['enum'], ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G', 'TH', 'BLANK'])
        self.assertNotIn('', grade['enum'])
        self.assertNotIn(SLIP_BLANK, SLIP_GRADES)

    def test_the_prompt_asks_for_the_blank_word_not_an_empty_grade(self):
        hint = vision._DOC_HINTS['results_slip']
        self.assertIn('the word BLANK', hint)
        self.assertNotIn('leave it empty', hint)

    def test_every_row_key_is_required(self):
        self.assertEqual(sorted(self.row['required']), ['band', 'grade', 'subject'])

    def test_the_subject_list_is_required(self):
        self.assertIn('results', self.schema['required'])
        self.assertEqual(self.schema['properties']['results']['type'], 'array')

    def test_other_schemas_gain_no_required_list(self):
        self.assertNotIn('required', _FIELD_SCHEMAS['salary_slip'])

    def test_the_sdk_takes_the_slip_schema(self):
        from google.genai import types
        types.GenerateContentConfig(response_mime_type='application/json', response_schema=self.schema)


class TheGradeCleanUp(SimpleTestCase):
    """Known harmless variants map onto the one spelling; anything else is refused (None)."""

    def test_known_variants_map(self):
        cases = {'A+': 'A+', 'Aplus': 'A+', 'APLUS': 'A+', 'A plus': 'A+', 'a+': 'A+',
                 'A\t': 'A', '\tB+ ': 'B+', ' C + ': 'C+', 'A +': 'A+', 'A　': 'A',
                 'Ａ＋': 'A+', 'Ｂ': 'B', 'ＴＨ': 'TH', 'A−': 'A-',
                 'A–': 'A-', 'A minus': 'A-', 'Cplus': 'C+',
                 'th': 'TH', 'TH': 'TH', 'G': 'G', 'E': 'E', 'D': 'D', '': '', '   ': '', '\t': ''}
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(clean_slip_grade(raw), want)

    def test_the_blank_word_is_a_blank_cell_never_a_grade(self):
        """Fix round 4: the schema's 'BLANK' comes back as '' and never reaches stored data."""
        for raw in ('BLANK', 'blank', ' Blank\t', 'ＢＬＡＮＫ'):
            with self.subTest(raw=raw):
                self.assertEqual(clean_slip_grade(raw), '')
        for raw in ('BLANKS', 'BLANK+', 'A BLANK', 'BLAN', 'BLANK\n'):
            with self.subTest(refused=raw):
                self.assertIsNone(clean_slip_grade(raw))
        data = {'candidate_name': 'X', 'exam': 'SPM',
                'results': [{'subject': 'SEJARAH', 'grade': 'BLANK', 'band': 'KEPUJIAN'},
                            {'subject': 'SAINS', 'grade': 'A', 'band': 'CEMERLANG TINGGI'}]}
        out, _ = _read(data)
        self.assertEqual(out['error'], '')
        self.assertEqual([r['grade'] for r in out['fields']['results']], ['', 'A'])
        self.assertNotIn('BLANK', json.dumps(out))

    def test_every_grade_survives_unchanged(self):
        for g in SLIP_GRADES:
            with self.subTest(grade=g):
                self.assertEqual(clean_slip_grade(g), g)

    def test_anything_else_is_refused_never_guessed(self):
        for raw in ('A+}', '"A+"', '{"grade": "A"}', 'A十', '优', 'A++', '1A', 'F', 'B-', 'Bminus',
                    'Gplus', 'Eplus', 'A+B', 'AA', 'PLUS', 'A*', 'Cemerlang', 'A,', None, 5, ['A']):
            with self.subTest(raw=raw):
                self.assertIsNone(clean_slip_grade(raw))

    def test_control_and_format_characters_are_refused_not_stripped(self):
        """Review round 1: only plain space and tab (and NFKC's spaces) are folded; a newline,
        NUL, DEL, NEL, a zero-width mark or a line separator means the cell is not a clean grade."""
        for raw in ('A\n', 'A\r', 'A\x00', 'A\x7f', 'A\x85', 'A​+', 'A‎', '﻿A',
                    'A⁠', 'A ', 'B ', 'A '):
            with self.subTest(raw=repr(raw)):
                self.assertIsNone(clean_slip_grade(raw))


class TheTextCleanUp(SimpleTestCase):
    def test_spacing_and_full_width_are_folded(self):
        self.assertEqual(clean_slip_text('BAHASA\tMELAYU'), 'BAHASA MELAYU')
        self.assertEqual(clean_slip_text('  SEJARAH  \n'), 'SEJARAH')
        self.assertEqual(clean_slip_text('ＭＡＴＥ'), 'MATE')
        self.assertEqual(clean_slip_text('PENDIDIKAN MORAL (ELEKTIF)'), 'PENDIDIKAN MORAL (ELEKTIF)')
        self.assertEqual(clean_slip_text(None), '')

    def test_stray_json_cjk_and_control_characters_are_refused(self):
        for raw in ('MATEMATIK"}', '{"subject": "SAINS"}', 'SEJARAH]', 'SAINS 数学',
                    'FIZIK\x00', 'KIMIA\\', 5):
            with self.subTest(raw=raw):
                self.assertIsNone(clean_slip_text(raw))


class TheAnswerCheck(SimpleTestCase):
    def test_a_good_answer_is_cleaned(self):
        data = _good(grade='Aplus', subject='MATEMATIK\tTAMBAHAN')
        cleaned, problems = slip_read.check_slip_answer(data)
        self.assertEqual(problems, [])
        self.assertEqual(cleaned['results'][1], {'subject': 'MATEMATIK TAMBAHAN', 'grade': 'A+',
                                                 'band': 'CEMERLANG TERTINGGI'})

    def test_an_answer_with_no_rows_is_a_bad_answer(self):
        cleaned, problems = slip_read.check_slip_answer({'candidate_name': '', 'exam': '', 'results': []})
        self.assertIsNone(cleaned)
        self.assertTrue(problems)
        blank_rows = {'results': [{'subject': '', 'grade': '', 'band': ''}]}
        self.assertIsNone(slip_read.check_slip_answer(blank_rows)[0])

    def test_rows_with_no_grade_and_no_band_anywhere_are_a_bad_answer(self):
        data = {'candidate_name': 'X', 'exam': 'SPM',
                'results': [{'subject': 'SEJARAH', 'grade': '', 'band': ''},
                            {'subject': 'SAINS', 'grade': '', 'band': ''}]}
        cleaned, problems = slip_read.check_slip_answer(data)
        self.assertIsNone(cleaned)
        self.assertIn('no grade or band read on any row', problems)
        data['results'][1]['band'] = 'LULUS'               # one row read: a good answer
        self.assertEqual(slip_read.check_slip_answer(data)[1], [])

    def test_one_subject_with_two_different_grades_is_a_bad_answer(self):
        for second in ({'subject': 'MATEMATIK', 'grade': 'B', 'band': 'KEPUJIAN TINGGI'},
                       {'subject': 'matematik', 'grade': 'A', 'band': 'CEMERLANG TINGI'}):
            data = _good()
            data['results'].append(second)
            with self.subTest(second=second):
                cleaned, problems = slip_read.check_slip_answer(data)
                self.assertIsNone(cleaned)
                self.assertTrue(any('same subject' in p for p in problems))

    def test_an_exact_duplicate_row_is_kept_once(self):
        data = _good()
        data['results'].append({'subject': 'MATEMATIK', 'grade': 'A', 'band': 'CEMERLANG TINGGI'})
        cleaned, problems = slip_read.check_slip_answer(data)
        self.assertEqual(problems, [])
        self.assertEqual([r['subject'] for r in cleaned['results']], ['BAHASA MELAYU', 'MATEMATIK'])

    def test_an_english_and_a_malay_row_of_one_subject_are_checked_together(self):
        """Review round 2: the duplicate check uses the comparison's own key (`_compare_key` after
        the band-word split), so English and Malay names of one subject cannot carry two grades."""
        for first, second in (
                ({'subject': 'MATHEMATICS', 'grade': 'A-', 'band': 'CEMERLANG'},
                 {'subject': 'MATEMATIK', 'grade': 'D', 'band': 'LULUS ATAS'}),
                ({'subject': 'PHYSICS CEMERLANG TINGGI', 'grade': 'A', 'band': ''},
                 {'subject': '4531 FIZIK', 'grade': 'C', 'band': 'KEPUJIAN'}),
                ({'subject': 'ADDITIONAL MATHEMATICS', 'grade': 'B', 'band': 'KEPUJIAN TINGGI'},
                 {'subject': 'Matematik Tambahan', 'grade': 'A', 'band': 'CEMERLANG TINGGI'})):
            data = {'candidate_name': 'CALON CONTOH', 'exam': 'SPM', 'results': [first, second]}
            with self.subTest(first=first, second=second):
                cleaned, problems = slip_read.check_slip_answer(data)
                self.assertIsNone(cleaned)
                self.assertTrue(any('same subject' in p for p in problems))

    def test_an_english_and_a_malay_row_that_agree_are_kept_once(self):
        data = {'candidate_name': 'CALON CONTOH', 'exam': 'SPM',
                'results': [{'subject': 'MATHEMATICS', 'grade': 'A', 'band': 'CEMERLANG TINGGI'},
                            {'subject': 'MATEMATIK', 'grade': 'A', 'band': 'CEMERLANG TINGGI'},
                            {'subject': 'SAINS', 'grade': 'B', 'band': 'KEPUJIAN TINGGI'}]}
        cleaned, problems = slip_read.check_slip_answer(data)
        self.assertEqual(problems, [])
        self.assertEqual([r['subject'] for r in cleaned['results']], ['MATHEMATICS', 'SAINS'])

    def test_a_duplicate_whose_band_differs_only_in_case_or_spacing_is_kept_once(self):
        """Review round 2: the bands match case- and space-insensitively."""
        for band in ('Cemerlang', 'cemerlang', ' CEMERLANG\t', 'CEMERLANG'):
            data = {'candidate_name': 'X', 'exam': 'SPM',
                    'results': [{'subject': 'SEJARAH', 'grade': 'A-', 'band': band},
                                {'subject': 'SEJARAH', 'grade': 'A-', 'band': 'CEMERLANG'}]}
            with self.subTest(band=band):
                cleaned, problems = slip_read.check_slip_answer(data)
                self.assertEqual(problems, [])
                self.assertEqual(len(cleaned['results']), 1)

    def test_a_duplicate_with_one_blank_band_is_kept_once_with_the_band(self):
        for rows in ([('A-', ''), ('A-', 'CEMERLANG')], [('A-', 'CEMERLANG'), ('A-', '')]):
            data = {'candidate_name': 'X', 'exam': 'SPM',
                    'results': [{'subject': 'SEJARAH', 'grade': g, 'band': b} for g, b in rows]}
            with self.subTest(rows=rows):
                cleaned, problems = slip_read.check_slip_answer(data)
                self.assertEqual(problems, [])
                self.assertEqual(cleaned['results'], [{'subject': 'SEJARAH', 'grade': 'A-',
                                                       'band': 'CEMERLANG'}])

    def test_a_real_conflict_is_still_a_bad_answer(self):
        for second in (('B', 'CEMERLANG'), ('A-', 'KEPUJIAN'), ('', 'CEMERLANG'), ('B', ''),
                       ('A-', 'CEMERLANG TINGI')):
            data = {'candidate_name': 'X', 'exam': 'SPM',
                    'results': [{'subject': 'SEJARAH', 'grade': 'A-', 'band': 'CEMERLANG'},
                                {'subject': 'SEJARAH', 'grade': second[0], 'band': second[1]}]}
            with self.subTest(second=second):
                self.assertIsNone(slip_read.check_slip_answer(data)[0])

    def _check(self, *rows):
        return slip_read.check_slip_answer(
            {'candidate_name': 'X', 'exam': 'SPM',
             'results': [{'subject': s, 'grade': g, 'band': b} for s, g, b in rows]})

    def test_a_band_that_says_another_grade_than_its_letter_is_a_bad_answer(self):
        """Review round 3: `read_slip` lets the band win over the letter, so ('SEJARAH', 'A',
        'KEPUJIAN') would be stored as a confident C. A band contradicting its letter is refused."""
        for row in (('SEJARAH', 'A', 'KEPUJIAN'), ('SEJARAH', 'A+', 'CEMERLANG TINGGI'),
                    ('SEJARAH', 'C', 'kepujian  atas'), ('SEJARAH', 'G', 'TIDAK HADIR'),
                    ('SEJARAH KEPUJIAN', 'A', ''),                 # band words glued to the subject
                    ('SEJARAH CEMERLANG TINGGI', 'A', 'GAGAL'),    # glued band vs band field
                    ('SEJARAH CEMERLANG TINGGI', '', 'GAGAL')):    # two bands, two grades
            with self.subTest(row=row):
                cleaned, problems = self._check(row)
                self.assertIsNone(cleaned)
                self.assertTrue(any('band says a different grade' in p for p in problems))

    def test_a_grade_named_inside_the_subject_must_be_the_letter(self):
        """Review round 4 (MEDIUM): band words or a lone grade INSIDE the subject (not trailing,
        so `_split_band` never sees them) that are not the row's letter are a bad answer."""
        for row in (('SEJARAH C', 'A', ''), ('SEJARAH (C)', 'A', 'CEMERLANG TINGGI'),
                    ('SEJARAH C+ ELEKTIF', 'A', ''), ('SEJARAH KEPUJIAN (ELEKTIF)', 'A', ''),
                    ('SEJARAH CEMERLANG TINGGI (ELEKTIF)', 'A+', ''), ('SEJARAH GAGAL MORAL', 'A', ''),
                    ('SEJARAH TIDAK HADIR', 'A', ''), ('SEJARAH, LULUS ATAS', 'E', ''),
                    ('SEJARAH Aplus', 'A', ''), ('SEJARAH C-', 'C', ''), ('SEJARAH F', 'A', ''),
                    ('SEJARAH C', '', ''), ('SEJARAH C', '', 'KEPUJIAN TINGGI'),
                    ('SEJARAH A KEPUJIAN', 'A', '')):
            with self.subTest(row=row):
                cleaned, problems = self._check(row, ('SAINS', 'A', 'CEMERLANG TINGGI'))
                self.assertIsNone(cleaned)
                self.assertTrue(any('subject names a grade' in p or 'band says' in p for p in problems))

    def test_a_grade_named_in_the_subject_that_is_the_letter_is_kept(self):
        for row in (('SEJARAH C', 'C', 'KEPUJIAN'), ('SEJARAH (A-)', 'A-', ''),
                    ('SEJARAH KEPUJIAN TINGGI (ELEKTIF)', 'B', ''), ('SEJARAH TIDAK HADIR', 'TH', '')):
            with self.subTest(row=row):
                self.assertEqual(self._check(row)[1], [])

    def test_real_subject_names_name_no_grade(self):
        for subject in ('BAHASA MELAYU', 'BAHASA ARAB TINGGI', 'PENDIDIKAN AL-QURAN DAN AL-SUNNAH',
                        'PENDIDIKAN MORAL (ELEKTIF)', 'MATEMATIK TAMBAHAN', 'BAHASA TAMIL',
                        'ENGLISH FOR SCIENCE AND TECHNOLOGY', 'PRINSIP PERAKAUNAN', 'SAINS - TAMBAHAN',
                        'Pendidikan Seni Visual', 'TASAWWUR ISLAM', 'GRAFIK KOMUNIKASI TEKNIKAL'):
            with self.subTest(subject=subject):
                self.assertEqual(slip_read._grades_named_in(subject), set())
                self.assertEqual(self._check((subject, 'B', 'KEPUJIAN TINGGI'))[1], [])

    def test_the_blocker_duplicates_are_refused_never_filled(self):
        """Review round 3 blocker: a blank band was filled from a duplicate whose band says another
        grade, so these stored a C and a G for an A."""
        for rows in ([('SEJARAH', 'A', ''), ('SEJARAH', 'A', 'KEPUJIAN')],
                     [('SEJARAH CEMERLANG TINGGI', 'A', ''), ('SEJARAH', 'A', 'GAGAL')],
                     [('SEJARAH', 'A', 'KEPUJIAN'), ('SEJARAH', 'A', '')]):
            with self.subTest(rows=rows):
                cleaned, problems = self._check(*rows)
                self.assertIsNone(cleaned)
                self.assertTrue(problems)

    def test_a_duplicate_band_is_filled_only_when_it_says_the_kept_letter(self):
        cleaned, problems = self._check(('SEJARAH', 'A', ''), ('SEJARAH', 'A', 'CEMERLANG TINGGI'))
        self.assertEqual(problems, [])
        self.assertEqual(cleaned['results'], [{'subject': 'SEJARAH', 'grade': 'A', 'band': 'CEMERLANG TINGGI'}])
        cleaned, problems = self._check(('SEJARAH CEMERLANG TINGGI', 'A', ''), ('SEJARAH', 'A', 'CEMERLANG TINGGI'))
        self.assertEqual(problems, [])
        self.assertEqual(len(cleaned['results']), 1)
        # No letter to keep: a band from a duplicate is never filled in.
        self.assertIsNone(self._check(('SEJARAH', '', ''), ('SEJARAH', '', 'KEPUJIAN'))[0])
        # An unknown band text beside a blank one is not a band that says the letter.
        self.assertIsNone(self._check(('SEJARAH', 'A', 'CEMERLANG TINGI'), ('SEJARAH', 'A', 'CEMERLANG TINGGI'))[0])

    def test_every_spm_grade_with_its_own_band_is_a_good_answer(self):
        """Every grade of the academic engine's map, with the band that says it (field or glued)."""
        from apps.scholarship.academic_engine import _BAND_TO_GRADE
        self.assertEqual(sorted(_BAND_TO_GRADE.values()), sorted(SLIP_GRADES))
        for band, grade in _BAND_TO_GRADE.items():
            for row in (('SEJARAH', grade, band.upper()), ('SEJARAH', grade, band),
                        ('SEJARAH', '', band.upper())):
                with self.subTest(row=row):
                    cleaned, problems = self._check(row)
                    self.assertEqual(problems, [])
                    self.assertEqual(cleaned['results'][0]['grade'], row[1])
            if grade != 'TH':                              # "tidak hadir" is never glued (`_BAND_RE`)
                with self.subTest(glued=band):
                    self.assertEqual(self._check((f'SEJARAH {band.upper()}', grade, ''))[1], [])

    def test_only_the_known_keys_are_kept(self):
        data = {**_good(), 'notes': 'extra', 'extra_id': 'X1'}
        data['results'][0] = {**data['results'][0], 'confidence': 0.9, 'code': '1103'}
        cleaned, _ = slip_read.check_slip_answer(data)
        self.assertEqual(sorted(cleaned), ['candidate_name', 'exam', 'results', 'warnings'])
        for row in cleaned['results']:
            self.assertEqual(sorted(row), ['band', 'grade', 'subject'])
        out, _ = _read(data)
        self.assertNotIn('notes', out['fields'])
        self.assertNotIn('extra_id', out['fields'])

    def test_a_blank_row_is_dropped(self):
        data = _good()
        data['results'].append({'subject': '', 'grade': '', 'band': ''})
        cleaned, problems = slip_read.check_slip_answer(data)
        self.assertEqual((len(cleaned['results']), problems), (2, []))

    def test_malformed_answers_are_refused(self):
        bad = {
            'not an object': ['results'],
            'no results': {'candidate_name': 'X'},
            'results not a list': {'results': 'A+ A A'},
            'row not an object': {'results': ['MATEMATIK A']},
            'row with no grade key': {'results': [{'subject': 'SAINS', 'band': 'LULUS'}]},
            'grade outside the set': _good(grade='A+}'),
            'CJK grade': _good(grade='A十'),
            'stray JSON subject': _good(subject='SAINS"},{'),
            'CJK band': _good(band='优秀'),
            'a grade with no subject': _good(subject=''),
            'name not text': {**_good(), 'candidate_name': {'x': 1}},
        }
        for why, data in bad.items():
            with self.subTest(why=why):
                cleaned, problems = slip_read.check_slip_answer(data)
                self.assertIsNone(cleaned)
                self.assertTrue(problems)


class TheRetry(SimpleTestCase):
    def test_a_good_first_answer_is_one_call(self):
        out, models = _read(_good())
        self.assertEqual(out['error'], '')
        self.assertEqual(out['slip_calls'], 1)
        self.assertEqual(len(models), 1)

    def test_a_malformed_first_answer_gets_one_retry_which_can_answer(self):
        out, models = _read(_good(grade='A+}'), _good(grade='Aplus'))
        self.assertEqual(out['error'], '')
        self.assertEqual(out['slip_calls'], 2)
        self.assertEqual(out['fields']['results'][1]['grade'], 'A+')
        self.assertEqual(len(models), 2)

    def test_malformed_twice_is_a_failed_read_never_a_grade(self):
        out, models = _read(_good(grade='A十'), _good(grade='Aplus}'))
        self.assertEqual(len(models), 2)                      # one retry only, never a third call
        self.assertEqual(out['fields'], {})
        self.assertTrue(out['error'].startswith(DOCUMENT_FAILED))
        self.assertIn(slip_read.MALFORMED_SLIP, out['error'])
        self.assertFalse(is_ai_service_error(out['error']))   # stored 'unreadable', not deferred

    def test_the_failed_read_names_the_model_once(self):
        unparseable = {'_error': f'{DOCUMENT_FAILED}: gemini-3.8-flash: UNPARSEABLE_RESPONSE'}
        for answers in ((unparseable, unparseable), (_good(grade='A十'), unparseable)):
            with self.subTest(answers=answers):
                out, _ = _read(*answers)
                self.assertEqual(out['error'].count('gemini-3.8-flash'), 1)
                self.assertIn('try 1:', out['error'])
                self.assertIn('try 2:', out['error'])

    def test_a_bad_answer_of_any_new_kind_gets_one_retry_then_is_unreadable(self):
        dup = _good()
        dup['results'].append({'subject': 'MATEMATIK', 'grade': 'C', 'band': ''})
        for bad in (dup, {'candidate_name': 'X', 'exam': 'SPM', 'results': []}):
            with self.subTest(bad=bad):
                out, models = _read(bad, bad)
                self.assertEqual(len(models), 2)
                self.assertTrue(out['error'].startswith(DOCUMENT_FAILED))
                self.assertFalse(is_ai_service_error(out['error']))

    def test_an_unparseable_answer_is_retried_once(self):
        unparseable = {'_error': f'{DOCUMENT_FAILED}: gemini-3.8-flash: UNPARSEABLE_RESPONSE'}
        out, models = _read(unparseable, _good())
        self.assertEqual((out['error'], out['slip_calls'], len(models)), ('', 2, 2))
        out, models = _read(unparseable, unparseable)
        self.assertEqual(len(models), 2)
        self.assertTrue(out['error'].startswith(DOCUMENT_FAILED))

    def test_a_service_error_is_not_retried_and_stays_a_service_error(self):
        from apps.scholarship.gemini import cascade_failure
        down = {'_error': cascade_failure([('gemini-3.8-flash', '503 UNAVAILABLE')])}
        out, models = _read(down)
        self.assertEqual(len(models), 1)
        self.assertTrue(is_ai_service_error(out['error']))    # 'review_manually', never 'unreadable'

    def test_the_answer_keeps_the_existing_clean_up(self):
        data = _good()
        data['warnings'] = ['The name is partly faint.']
        out, _ = _read(data)
        self.assertEqual(out['warnings'], ['The name is partly faint.'])
        self.assertNotIn('warnings', out['fields'])


class TwoPointFiveIsNeverCalled(SimpleTestCase):
    def test_every_slip_call_is_on_3_8_only(self):
        _, models = _read(_good(grade='bad'), _good(grade='bad'))
        self.assertEqual(models, [['gemini-3.8-flash'], ['gemini-3.8-flash']])

    def test_the_image_read_too(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (40, 40), 'white').save(buf, format='PNG')
        with patch(_SEAM, side_effect=[_good()]) as seam:
            vision.extract_document_fields('', 'results_slip', image=buf.getvalue(), content_type='image/png')
        self.assertEqual(seam.call_args.kwargs['models'], ['gemini-3.8-flash'])

    def test_with_no_3_8_model_the_read_refuses_rather_than_fall_back(self):
        with patch('apps.scholarship.profile_engine.MODEL_CASCADE', ['gemini-2.5-flash', 'gemini-2.5-flash-lite']), \
                patch(_SEAM) as seam:
            out = vision.extract_document_fields('SIJIL PELAJARAN MALAYSIA', 'results_slip')
        seam.assert_not_called()
        self.assertEqual(out['fields'], {})
        self.assertTrue(is_ai_service_error(out['error']))

    def test_a_2_5_model_list_is_refused(self):
        calls = []
        out = slip_read.read_slip_checked(lambda models: calls.append(models) or _good(),
                                          models=['gemini-3.8-flash', 'gemini-2.5-flash'])
        self.assertEqual(calls, [])
        self.assertTrue(out['error'])

    def test_only_3_8_models_may_read_an_allow_list(self):
        """Review round 1: a model that is merely 'not 2.5' is refused, never let through."""
        with patch('apps.scholarship.profile_engine.MODEL_CASCADE',
                   ['gemini-4.0-pro', 'gemini-3.8-flash', 'gemini-2.5-flash', 'other-model']):
            self.assertEqual(slip_read.slip_read_models(), ['gemini-3.8-flash'])
        for models in (['gemini-4.0-pro'], ['gemini-3.8-flash', 'gemini-3.9-flash'], ['gpt-x'], []):
            calls = []
            with self.subTest(models=models):
                out = slip_read.read_slip_checked(lambda m: calls.append(m) or _good(), models=models)
                self.assertEqual(calls, [])
                self.assertTrue(is_ai_service_error(out['error']))   # 'review_manually'

    def test_the_allow_list_is_3_8_flash_exactly_never_a_look_alike(self):
        """Review round 2: a bare 'gemini-3.8' prefix let look-alike and Lite names through."""
        for name in ('gemini-3.8-flash', 'gemini-3.8-flash-preview-11-2026', 'gemini-3.8-flash-001'):
            with self.subTest(allowed=name):
                self.assertTrue(slip_read.is_slip_model(name))
        for name in ('gemini-3.80', 'gemini-3.81-pro', 'gemini-3.8', 'gemini-3.8-flash-lite',
                     'gemini-3.8-flash-lite-preview', 'gemini-3.8-pro', 'gemini-3.8-flashy',
                     'gemini-3.8-flash-preview-lite', 'models/gemini-3.8-flash', '', None):
            with self.subTest(refused=name):
                self.assertFalse(slip_read.is_slip_model(name))
        # Review round 3: matched on the lowercased name as a whole; every other variant refused.
        for name in ('GEMINI-3.8-FLASH', 'Gemini-3.8-Flash-Preview', 'gemini-3.8-flash-preview-05-20'):
            with self.subTest(allowed=name):
                self.assertTrue(slip_read.is_slip_model(name))
        for name in ('gemini-3.8-flash-LITE', 'gemini-3.8-flash-8b', 'gemini-3.8-flash-image',
                     'gemini-3.8-flash-tts', 'gemini-3.8-flash-thinking-exp', 'gemini-3.8-flash-preview-tts',
                     'gemini-3.8-flash-preview-image', 'gemini-3.8-flash-exp', 'gemini-3.8-flash-latest',
                     'gemini-3.8-flash-0001', 'gemini-3.8-flash\n', ' gemini-3.8-flash',
                     'gemini-3.8-flash-٠٠١', 'gemini-3x8-flash'):
            with self.subTest(refused=name):
                self.assertFalse(slip_read.is_slip_model(name))
        for models in (['gemini-3.8-flash-image'], ['gemini-3.8-flash-tts']):
            calls = []
            with self.subTest(models=models):
                out = slip_read.read_slip_checked(lambda m: calls.append(m) or _good(), models=models)
                self.assertEqual(calls, [])
                self.assertTrue(is_ai_service_error(out['error']))
        with patch('apps.scholarship.profile_engine.MODEL_CASCADE',
                   ['gemini-3.8-flash-lite', 'gemini-3.80', 'gemini-2.5-flash']):
            self.assertEqual(slip_read.slip_read_models(), [])
        for models in (['gemini-3.8-flash-lite'], ['gemini-3.81-pro'], ['gemini-3.8']):
            calls = []
            with self.subTest(models=models):
                out = slip_read.read_slip_checked(lambda m: calls.append(m) or _good(), models=models)
                self.assertEqual(calls, [])
                self.assertTrue(is_ai_service_error(out['error']))   # 'review_manually'

    def test_a_dated_preview_is_month_day_or_month_year_exactly(self):
        """Review round 4 (LOW-4): the date was looser than the docs ("-preview-11-202")."""
        for name in ('gemini-3.8-flash-preview-05-20', 'gemini-3.8-flash-preview-11-2026',
                     'gemini-3.8-flash-preview-12-31', 'gemini-3.8-flash-preview'):
            with self.subTest(allowed=name):
                self.assertTrue(slip_read.is_slip_model(name))
        for name in ('gemini-3.8-flash-preview-11-202', 'gemini-3.8-flash-preview-13-20',
                     'gemini-3.8-flash-preview-00-20', 'gemini-3.8-flash-preview-05-32',
                     'gemini-3.8-flash-preview-05-00', 'gemini-3.8-flash-preview-11-1999',
                     'gemini-3.8-flash-preview-5-20', 'gemini-3.8-flash-preview-05'):
            with self.subTest(refused=name):
                self.assertFalse(slip_read.is_slip_model(name))

    def test_nothing_is_pinned_to_2_5(self):
        self.assertEqual(vision.PINNED_25_DOC_TYPES, frozenset())
        self.assertEqual(vision.doc_read_cascade('results_slip'), slip_read.slip_read_models())
        self.assertFalse([m for m in vision.doc_read_cascade('results_slip') if '2.5' in m])

    def test_the_answer_json_round_trips(self):
        out, _ = _read(json.loads(json.dumps(_good())))
        self.assertEqual(out['fields']['exam'], 'SPM 2025')
