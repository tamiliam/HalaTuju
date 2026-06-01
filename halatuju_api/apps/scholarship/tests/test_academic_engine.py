"""Pure unit tests for the academic engine (Sprint 2) — read_slip + compare.

No DB: read_slip only reads ``doc.vision_fields`` (a dict), so a SimpleNamespace
stand-in is explicit and correct here; compare_academics takes plain dicts.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.academic_engine import compare_academics, read_slip


def _doc(fields):
    return SimpleNamespace(vision_fields={'fields': fields, 'student_verdict': 'ok'})


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
