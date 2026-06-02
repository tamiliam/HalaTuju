"""Pure unit tests for the academic engine (Sprint 2) — read_slip + compare.

No DB: read_slip only reads ``doc.vision_fields`` (a dict), so a SimpleNamespace
stand-in is explicit and correct here; compare_academics takes plain dicts.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.academic_engine import (
    _split_band, compare_academics, read_slip, student_slip_check,
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
        self.assertEqual(read_slip(_doc({})), {'names': [], 'grades': {}})


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
