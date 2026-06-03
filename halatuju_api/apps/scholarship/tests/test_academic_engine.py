"""Pure unit tests for the academic engine (Sprint 2) — read_slip + compare.

No DB: read_slip only reads ``doc.vision_fields`` (a dict), so a SimpleNamespace
stand-in is explicit and correct here; compare_academics takes plain dicts.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.academic_engine import (
    _split_band, compare_academics, parse_spm_slip, read_slip, student_slip_check,
)


def _doc(fields):
    return SimpleNamespace(vision_fields={'fields': fields, 'student_verdict': 'ok'})


def _slip_doc(results, grades, *, candidate='YESWINDRAN A/L MURALY',
              exam='SIJIL PELAJARAN MALAYSIA TAHUN 2025',
              student_verdict='ok', name_match='found'):
    """A results-slip doc stand-in for student_slip_check (no DB)."""
    return SimpleNamespace(
        doc_type='results_slip',
        vision_name_match=name_match,
        vision_fields={'fields': {'results': results, 'candidate_name': candidate, 'exam': exam},
                       'student_verdict': student_verdict},
        application=SimpleNamespace(profile=SimpleNamespace(grades=grades)),
    )


# Yeswindran's real slip (prod doc 188) — Gemini glued the SPM grade-BAND words onto
# each subject. Strip them and the 9 subjects map cleanly to the profile keys below.
YESWINDRAN_BAND_RESULTS = [
    {'subject': 'BAHASA MELAYU CEMERLANG', 'grade': 'A-'},
    {'subject': 'BAHASA INGGERIS CEMERLANG', 'grade': 'A-'},
    {'subject': 'PENDIDIKAN MORAL CEMERLANG', 'grade': 'A-'},
    {'subject': 'SEJARAH CEMERLANG TERTINGGI', 'grade': 'A+'},
    {'subject': 'MATEMATIK CEMERLANG TINGGI', 'grade': 'A'},
    {'subject': 'MATEMATIK TAMBAHAN KEPUJIAN ATAS', 'grade': 'C+'},
    {'subject': 'FIZIK KEPUJIAN TINGGI', 'grade': 'B'},
    {'subject': 'KIMIA KEPUJIAN TINGGI', 'grade': 'B'},
    {'subject': 'BIOLOGI KEPUJIAN', 'grade': 'C'},
]
ELANJELIAN_GRADES = {  # by grade key — same grades as the slip above
    'bm': 'A-', 'eng': 'A-', 'moral': 'A-', 'hist': 'A+', 'math': 'A',
    'addmath': 'C+', 'phy': 'B', 'chem': 'B', 'bio': 'C',
}


class TestSplitBand(SimpleTestCase):
    def test_strips_trailing_band_and_returns_grade(self):
        self.assertEqual(_split_band('MATEMATIK CEMERLANG TINGGI'), ('MATEMATIK', 'A'))
        self.assertEqual(_split_band('BIOLOGI KEPUJIAN'), ('BIOLOGI', 'C'))
        self.assertEqual(_split_band('SEJARAH CEMERLANG TERTINGGI'), ('SEJARAH', 'A+'))
        self.assertEqual(_split_band('MATEMATIK TAMBAHAN KEPUJIAN ATAS'),
                         ('MATEMATIK TAMBAHAN', 'C+'))

    def test_leaves_real_subjects_untouched(self):
        # "Bahasa Arab Tinggi" ends in a band MODIFIER but has no band word — keep it.
        self.assertEqual(_split_band('Bahasa Arab Tinggi'), ('Bahasa Arab Tinggi', ''))
        self.assertEqual(_split_band('Matematik'), ('Matematik', ''))
        self.assertEqual(_split_band('Pengajian Keusahawanan'), ('Pengajian Keusahawanan', ''))


class TestReadSlipBandStrip(SimpleTestCase):
    def test_band_words_stripped_from_names_and_keys(self):
        d = read_slip(_doc({'results': YESWINDRAN_BAND_RESULTS}))
        self.assertIn('MATEMATIK', d['names'])
        self.assertNotIn('MATEMATIK CEMERLANG TINGGI', d['names'])
        self.assertEqual(d['grades']['matematik'], 'A')
        self.assertEqual(d['grades']['matematik tambahan'], 'C+')

    def test_band_supplies_grade_when_letter_unread(self):
        d = read_slip(_doc({'results': [{'subject': 'MATEMATIK CEMERLANG TINGGI', 'grade': ''}]}))
        self.assertEqual(d['grades'], {'matematik': 'A'})   # derived from the band

    def test_yeswindran_slip_now_matches_elanjelian_subjects(self):
        slip = read_slip(_doc({'results': YESWINDRAN_BAND_RESULTS}))
        cmp = compare_academics(ELANJELIAN_GRADES, slip)
        self.assertEqual(cmp['slip_count'], 9)
        self.assertEqual(cmp['missing'], [])     # was "0 of 9 missing" before the fix
        self.assertTrue(cmp['complete'] and cmp['accurate'])


class TestStudentSlipCheck(SimpleTestCase):
    def test_wrong_person_slip_name_mismatch_subjects_and_results_ok(self):
        # The exact case the user tested: someone else's slip, identical grades.
        doc = _slip_doc(YESWINDRAN_BAND_RESULTS, ELANJELIAN_GRADES,
                        student_verdict='name_mismatch', name_match='not_found')
        chk = student_slip_check(doc)
        self.assertEqual(chk['name'], 'mismatch')
        self.assertEqual(chk['subjects'], 'match')
        self.assertEqual(chk['results'], 'match')
        self.assertEqual(chk['candidate_name'], 'YESWINDRAN A/L MURALY')

    def test_all_match(self):
        doc = _slip_doc(YESWINDRAN_BAND_RESULTS, ELANJELIAN_GRADES)
        chk = student_slip_check(doc)
        self.assertEqual((chk['name'], chk['subjects'], chk['results']),
                         ('match', 'match', 'match'))

    def test_missing_subject(self):
        grades = dict(ELANJELIAN_GRADES)
        grades.pop('bio')   # student didn't enter Biologi
        chk = student_slip_check(_slip_doc(YESWINDRAN_BAND_RESULTS, grades))
        self.assertEqual(chk['subjects'], 'mismatch')
        self.assertTrue(any('BIOLOGI' in m.upper() for m in chk['missing']))

    def test_grade_mismatch(self):
        grades = dict(ELANJELIAN_GRADES)
        grades['math'] = 'B+'   # typed B+, slip says A
        chk = student_slip_check(_slip_doc(YESWINDRAN_BAND_RESULTS, grades))
        self.assertEqual(chk['results'], 'mismatch')
        m = next(x for x in chk['mismatched'] if 'MATEMATIK' in x['subject'].upper())
        self.assertEqual((m['typed'], m['slip']), ('B+', 'A'))

    def test_pending_when_not_extracted_or_skipped(self):
        # review_manually = Gemini skipped (rate-limited) → genuinely pending.
        doc = _slip_doc([], ELANJELIAN_GRADES, student_verdict='review_manually')
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('pending', 'pending'))

    def test_extracted_but_empty_table_is_unreadable(self):
        # The doc 191 case: Gemini ran (name read, name_mismatch) but the subject table
        # came back EMPTY → "couldn't read", not "pending" (so the UI nudges a re-upload).
        doc = _slip_doc([], ELANJELIAN_GRADES, student_verdict='name_mismatch',
                        name_match='not_found')
        chk = student_slip_check(doc)
        self.assertEqual(chk['name'], 'mismatch')
        self.assertEqual((chk['subjects'], chk['results']), ('unreadable', 'unreadable'))

    def test_exam_year_surfaced(self):
        chk = student_slip_check(_slip_doc(YESWINDRAN_BAND_RESULTS, ELANJELIAN_GRADES))
        self.assertEqual(chk['exam_year'], '2025')
        self.assertIn('SIJIL PELAJARAN MALAYSIA', chk['exam'])


# Theresa's 8 entered subjects (grade key → grade).
THERESA_GRADES = {
    'bm': 'A-', 'eng': 'A+', 'sci': 'A+', 'srt': 'A',
    'hist': 'A', 'math': 'A', 'b_tamil': 'A', 'ekonomi': 'A',
}

# Her slip carries all 10 (the 8 above + Moral + Tamil Literature), with grades.
THERESA_SLIP_RESULTS = [
    {'subject': 'BAHASA MELAYU', 'grade': 'A-'},
    {'subject': 'BAHASA INGGERIS', 'grade': 'A+'},
    {'subject': 'PENDIDIKAN MORAL', 'grade': 'A'},
    {'subject': 'SEJARAH', 'grade': 'A'},
    {'subject': 'MATEMATIK', 'grade': 'A'},
    {'subject': 'SAINS', 'grade': 'A+'},
    {'subject': 'EKONOMI', 'grade': 'A'},
    {'subject': 'SAINS RUMAH TANGGA', 'grade': 'A'},
    {'subject': 'BAHASA TAMIL', 'grade': 'A'},
    {'subject': 'KESUSASTERAAN TAMIL', 'grade': 'A'},
]


class TestReadSlip(SimpleTestCase):
    def test_new_results_shape(self):
        d = read_slip(_doc({'results': [{'subject': 'Bahasa Melayu', 'grade': 'A-'}]}))
        self.assertEqual(d['names'], ['Bahasa Melayu'])
        self.assertEqual(d['grades'], {'bahasa melayu': 'A-'})

    def test_legacy_subjects_shape_has_names_no_grades(self):
        d = read_slip(_doc({'subjects': ['Bahasa Melayu', 'Sejarah']}))
        self.assertEqual(d['names'], ['Bahasa Melayu', 'Sejarah'])
        self.assertEqual(d['grades'], {})

    def test_empty(self):
        self.assertEqual(read_slip(_doc({})), {'names': [], 'grades': {}, 'bands': {}})


class TestBandCrossCheck(SimpleTestCase):
    """The slip prints each grade twice (letter + Malay band). The BAND is authoritative
    (distinctive text OCR reads reliably; the letter's +/- is a tiny, easily-dropped
    mark). The slip grade is the band's grade; a ±-only difference vs the typed grade is
    'uncertain' (the OCR blind spot), never a confident wrong assertion."""

    def test_band_captured_from_field(self):
        d = read_slip(_doc({'results': [{'subject': 'Matematik', 'grade': 'A', 'band': 'Cemerlang Tinggi'}]}))
        self.assertEqual(d['bands'], {'matematik': 'A'})

    def test_band_resolves_dropped_modifier_to_a_match(self):
        # The Theepicaa case: OCR dropped the "+" so the letter reads A, but the band
        # "Cemerlang Tertinggi" = A+. The band wins → the slip grade is A+, which MATCHES
        # the student's typed A+ (no flag) — not the wrong "our read shows A".
        slip = read_slip(_doc({'results': [{'subject': 'Matematik', 'grade': 'A', 'band': 'Cemerlang Tertinggi'}]}))
        cmp = compare_academics({'math': 'A+'}, slip)
        self.assertEqual((cmp['mismatched'], cmp['uncertain']), ([], []))
        self.assertTrue(cmp['accurate'])

    def test_real_mismatch_different_base_letter_flags(self):
        # A genuine difference (typed A+, slip C — base letters A vs C differ, band agrees)
        # is a CONFIDENT mismatch, not downgraded.
        slip = read_slip(_doc({'results': [{'subject': 'Matematik', 'grade': 'C', 'band': 'Kepujian'}]}))
        cmp = compare_academics({'math': 'A+'}, slip)
        self.assertEqual(len(cmp['mismatched']), 1)
        self.assertEqual(cmp['uncertain'], [])

    def test_pm_only_difference_is_uncertain_even_when_letter_band_agree(self):
        # The Fizik case: slip read A / Cemerlang Tinggi (letter+band AGREE, both A), but
        # the real grade is A+. typed A+ vs slip A differ ONLY by the '+' → the OCR's
        # blind spot → UNCERTAIN, never a confident "you typed A+ but slip says A".
        slip = read_slip(_doc({'results': [{'subject': 'Fizik', 'grade': 'A', 'band': 'Cemerlang Tinggi'}]}))
        cmp = compare_academics({'phy': 'A+'}, slip)
        self.assertEqual(cmp['mismatched'], [])
        self.assertEqual(len(cmp['uncertain']), 1)

    def test_typed_differs_from_band_by_modifier_is_uncertain(self):
        # Band "Cemerlang Tinggi" = A is the slip grade; the student typed A+. They differ
        # only by the modifier → 'uncertain' ("check by eye"), never a confident flag.
        slip = read_slip(_doc({'results': [{'subject': 'Matematik', 'grade': 'A+', 'band': 'Cemerlang Tinggi'}]}))
        cmp = compare_academics({'math': 'A+'}, slip)
        self.assertEqual(cmp['mismatched'], [])
        self.assertEqual(len(cmp['uncertain']), 1)


class TestCompareAcademics(SimpleTestCase):
    def test_theresa_missing_two_subjects(self):
        slip = read_slip(_doc({'results': THERESA_SLIP_RESULTS}))
        cmp = compare_academics(THERESA_GRADES, slip)
        self.assertEqual(cmp['slip_count'], 10)
        self.assertFalse(cmp['complete'])
        self.assertEqual(sorted(cmp['missing']),
                         ['KESUSASTERAAN TAMIL', 'PENDIDIKAN MORAL'])
        self.assertTrue(cmp['accurate'])  # the 8 she entered all match

    def test_complete_and_accurate(self):
        # Profile with all 10 → complete + accurate.
        grades = dict(THERESA_GRADES, moral='A', lit_tamil='A')
        slip = read_slip(_doc({'results': THERESA_SLIP_RESULTS}))
        cmp = compare_academics(grades, slip)
        self.assertTrue(cmp['complete'])
        self.assertTrue(cmp['accurate'])
        self.assertEqual(cmp['missing'], [])

    def test_grade_mismatch_is_caught(self):
        grades = dict(THERESA_GRADES)
        grades['math'] = 'B+'  # she typed B+, slip says A
        slip = read_slip(_doc({'results': THERESA_SLIP_RESULTS}))
        cmp = compare_academics(grades, slip)
        self.assertFalse(cmp['accurate'])
        m = next(x for x in cmp['mismatched'] if 'MATEMATIK' in x['subject'].upper())
        self.assertEqual((m['typed'], m['slip']), ('B+', 'A'))

    def test_bahasa_tamil_key_collision_matches_by_name(self):
        # Profile uses 'b_tamil'; slip name "BAHASA TAMIL" must still match.
        slip = read_slip(_doc({'results': [{'subject': 'BAHASA TAMIL', 'grade': 'A'}]}))
        cmp = compare_academics({'b_tamil': 'A'}, slip)
        self.assertTrue(cmp['complete'] and cmp['accurate'])

    def test_grade_normalisation_tolerates_spacing(self):
        slip = read_slip(_doc({'results': [{'subject': 'Matematik', 'grade': 'A -'}]}))
        cmp = compare_academics({'math': 'A-'}, slip)
        self.assertTrue(cmp['accurate'])

    def test_legacy_names_only_completeness_without_grades(self):
        slip = read_slip(_doc({'subjects': ['Bahasa Melayu', 'Pendidikan Moral']}))
        cmp = compare_academics({'bm': 'A'}, slip)
        self.assertFalse(cmp['have_grades'])
        self.assertEqual(cmp['missing'], ['Pendidikan Moral'])


# ── Deterministic positional SPM-slip parser ──────────────────────────────────

import math


def _word(text, cx, cy, h=20):
    return {'text': text, 'cx': cx, 'cy': cy, 'h': h}


def _rotate_words(words, deg):
    """Rotate a synthetic word list by ``deg`` (around the origin) and stamp the
    reading-direction angle — simulating a slip photographed sideways/skewed."""
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    return [{**w, 'cx': w['cx'] * c - w['cy'] * s, 'cy': w['cx'] * s + w['cy'] * c,
             'angle': th} for w in words]


def _slip_words(header, rows, *, first_row_y=400, row_gap=40):
    """Build a synthetic SPM-slip word list. ``header`` = list of (text, y);
    ``rows`` = list of (subject, letter, band) top-to-bottom. Subjects sit in the
    LEFT column (x~100), the grade letter at x~500, the band at x~560+ — i.e. a real
    two-column layout, so a correct parse can only come from positional pairing."""
    words = []
    for text, y in header:
        for i, tok in enumerate(text.split()):
            words.append(_word(tok, 100 + i * 45, y))
    y = first_row_y
    for subject, letter, band in rows:
        for i, tok in enumerate(subject.split()):
            words.append(_word(tok, 100 + i * 60, y))
        if letter:
            words.append(_word(letter, 500, y))
        for j, tok in enumerate(band.split()):
            words.append(_word(tok, 560 + j * 80, y))
        y += row_gap
    return words


class TestParseSpmSlip(SimpleTestCase):
    HEADER = [('SIJIL PELAJARAN MALAYSIA', 200),
              ('SHARMILA A/P SANGGAR', 250), ('060412-06-0320', 300)]
    # Sharmila's real slip — the bottom three rows are exactly what the Gemini read
    # transposed (PERTANIAN↔PERNIAGAAN↔TAMIL). A positional parse must NOT.
    SHARMILA = [
        ('BAHASA MELAYU', 'A-', 'CEMERLANG'),
        ('BAHASA INGGERIS', 'C+', 'KEPUJIAN ATAS'),
        ('PENDIDIKAN MORAL', 'A+', 'CEMERLANG TERTINGGI'),
        ('SEJARAH', 'B', 'KEPUJIAN TINGGI'),
        ('MATEMATIK', 'A-', 'CEMERLANG'),
        ('SAINS', 'B+', 'KEPUJIAN TERTINGGI'),
        ('PERTANIAN', 'A', 'CEMERLANG TINGGI'),
        ('PERNIAGAAN', 'B', 'KEPUJIAN TINGGI'),
        ('BAHASA TAMIL', 'A-', 'CEMERLANG'),
    ]

    def _parse(self, rows=None, header=None):
        return parse_spm_slip(_slip_words(header or self.HEADER, rows or self.SHARMILA))

    def test_every_row_paired_correctly(self):
        # Subjects come back as canonical SPM names (matched, not literal OCR text).
        out = self._parse()
        self.assertIsNotNone(out)
        got = {r['subject']: r['grade'] for r in out['results']}
        self.assertEqual(len(out['results']), 9)
        # The transposition victims now read their OWN row's grade.
        self.assertEqual(got['Pertanian'], 'A')
        self.assertEqual(got['Perniagaan'], 'B')
        self.assertEqual(got['Bahasa Tamil'], 'A-')

    def test_parse_is_order_independent(self):
        # Reverse the OCR word order — positional grouping must still pair by geometry.
        words = list(reversed(_slip_words(self.HEADER, self.SHARMILA)))
        got = {r['subject']: r['grade'] for r in parse_spm_slip(words)['results']}
        self.assertEqual(got['Pertanian'], 'A')
        self.assertEqual(got['Perniagaan'], 'B')
        self.assertEqual(got['Bahasa Tamil'], 'A-')

    def test_rotated_or_skewed_slip_still_parses(self):
        # Pavalaharasi's case: the slip is photographed sideways (≈90°) or skewed. The
        # parser normalises by the reading angle, so rows still pair correctly.
        upright = _slip_words(self.HEADER, self.SHARMILA)
        for deg in (90, -90, 13):   # landscape both ways + a skew
            got = {r['subject']: r['grade'] for r in parse_spm_slip(_rotate_words(upright, deg))['results']}
            self.assertEqual(got['Pertanian'], 'A', f'deg={deg}')
            self.assertEqual(got['Perniagaan'], 'B', f'deg={deg}')
            self.assertEqual(got['Bahasa Tamil'], 'A-', f'deg={deg}')

    def test_band_kept_for_cross_check(self):
        sains = next(r for r in self._parse()['results'] if r['subject'] == 'Sains')
        self.assertEqual(sains['grade'], 'B+')
        self.assertEqual(sains['band'], 'kepujian tertinggi')

    def test_subject_codes_and_noise_resolved(self):
        # Theepicaa's slip shape: subject CODES + watermark/OCR noise + an oral-test row.
        # The parser resolves each row to the subject it IS, not the literal text.
        rows = [
            ('1103 BAHASA MELAYU', 'A+', 'CEMERLANG TERTINGGI'),
            ('1119 BAHASA INGGERIS', 'A', 'CEMERLANG TINGGI'),
            ('4541 KIMIA Malaysia', 'B', 'KEPUJIAN TINGGI'),
            ('3472 MATEMATIK TAMBAHAN', 'C+', 'KEPUJIAN ATAS'),
            ('UJIAN LISAN BAHASA MELAYU', '', 'KEPUJIAN'),
        ]
        out = self._parse(rows)
        got = {r['subject']: r['grade'] for r in out['results']}
        self.assertEqual(got['Bahasa Melayu'], 'A+')        # code "1103" stripped
        self.assertEqual(got['Kimia'], 'B')                 # "Malaysia" noise ignored
        self.assertEqual(got['Matematik Tambahan'], 'C+')   # longest-match wins over "Matematik"
        # The oral-test row resolves to Bahasa Melayu and dedups against the real row.
        self.assertEqual(sum(1 for r in out['results'] if r['subject'] == 'Bahasa Melayu'), 1)

    def test_band_is_authoritative_over_letter(self):
        # The Theepicaa case: OCR read the letter as "A" but the band "Cemerlang
        # Tertinggi" = A+. The BAND wins — so a student who typed A+ matches the slip,
        # rather than being wrongly told "our read shows A".
        rows = [('BAHASA MELAYU', 'A', 'CEMERLANG TERTINGGI')] + self.SHARMILA[1:4]
        bm = next(r for r in self._parse(rows)['results'] if r['subject'] == 'Bahasa Melayu')
        self.assertEqual(bm['grade'], 'A+')   # band-derived, not the letter "A"
        self.assertEqual(bm['band'], 'cemerlang tertinggi')

    def test_split_plus_letter_reassembled(self):
        # The OCR splits "A+" into "A" "+" — the letter is reassembled (and the band
        # agrees), so the grade is A+, not A.
        rows = [('BAHASA MELAYU', 'A +', 'CEMERLANG TERTINGGI')] + self.SHARMILA[1:4]
        bm = next(r for r in self._parse(rows)['results'] if r['subject'] == 'Bahasa Melayu')
        self.assertEqual(bm['grade'], 'A+')

    def test_band_only_row_uses_band_grade(self):
        # Letter unreadable, band present → grade derived from the band.
        rows = [('BAHASA MELAYU', '', 'CEMERLANG')] + self.SHARMILA[1:4]
        bm = next(r for r in self._parse(rows)['results'] if r['subject'] == 'Bahasa Melayu')
        self.assertEqual(bm['grade'], 'A-')

    def test_tidak_hadir_is_th(self):
        rows = self.SHARMILA[:3] + [('SAINS', '', 'TIDAK HADIR')]
        sains = next(r for r in self._parse(rows)['results'] if r['subject'] == 'Sains')
        self.assertEqual(sains['grade'], 'TH')

    def test_name_and_exam_extracted(self):
        out = self._parse()
        self.assertEqual(out['candidate_name'], 'SHARMILA A/P SANGGAR')
        self.assertIn('SIJIL PELAJARAN MALAYSIA', out['exam'])

    def test_name_row_not_parsed_as_a_grade(self):
        # The "A/P" in the name must never be mistaken for an "A" grade row.
        subjects = {r['subject'] for r in self._parse()['results']}
        self.assertNotIn('SHARMILA', subjects)

    def test_non_spm_returns_none(self):
        self.assertIsNone(parse_spm_slip([_word('STPM', 100, 100), _word('SLIP', 200, 100)]))

    def test_too_few_rows_returns_none(self):
        self.assertIsNone(self._parse(self.SHARMILA[:2]))

    def test_orphan_subject_row_falls_back(self):
        # Sharmila's skewed-photo case: a subject ("Bahasa Melayu") lands on a row with
        # NO grade (its grade split onto another row). Rather than emit a wrong grade,
        # the parse bails (→ None → Gemini fallback).
        words = _slip_words(self.HEADER, self.SHARMILA[1:])   # 8 well-formed rows
        words += [_word('BAHASA', 100, 380), _word('MELAYU', 160, 380)]  # orphan subject
        self.assertIsNone(parse_spm_slip(words))
