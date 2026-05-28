"""Pure-function tests for the IC Vision OCR helpers (S13).

These exercise the canonicalisers + matchers + text-extraction regexes — the
Google Cloud Vision call itself is never made here.
"""
from django.test import TestCase

from apps.scholarship.vision import (
    _canonical_name_tokens, _canonical_nric, _extract_name, _extract_nric,
    extract_mykad, name_match, nric_match,
)


class TestNricMatch(TestCase):
    def test_canonical_strips_hyphens_and_spaces(self):
        self.assertEqual(_canonical_nric('030101-14-1234'), '030101141234')
        self.assertEqual(_canonical_nric('030101 14 1234'), '030101141234')
        self.assertEqual(_canonical_nric(' 030101-14-1234 '), '030101141234')

    def test_match_canonical(self):
        self.assertTrue(nric_match('030101-14-1234', '030101141234'))
        self.assertTrue(nric_match('030101141234', '030101-14-1234'))
        self.assertTrue(nric_match('030101 14 1234', '030101-14-1234'))

    def test_mismatch(self):
        self.assertFalse(nric_match('030101-14-1234', '030101-14-9999'))

    def test_empty_returns_false(self):
        self.assertFalse(nric_match('', '030101-14-1234'))
        self.assertFalse(nric_match('030101-14-1234', ''))
        self.assertFalse(nric_match('', ''))


class TestNameMatch(TestCase):
    def test_canonical_tokens_strip_parentage_markers(self):
        self.assertEqual(
            _canonical_name_tokens('Priya A/P Krishnan'),
            {'priya', 'krishnan'},
        )
        self.assertEqual(
            _canonical_name_tokens('Ahmad bin Yusoff'),
            {'ahmad', 'yusoff'},
        )
        self.assertEqual(
            _canonical_name_tokens('Nurul Binti Hassan'),  # case-insensitive
            {'nurul', 'hassan'},
        )

    def test_match_exact(self):
        self.assertEqual(name_match('Priya Krishnan', 'priya krishnan'), 'match')
        # parentage tokens absorbed
        self.assertEqual(name_match('AHMAD BIN YUSOFF', 'Ahmad Yusoff'), 'match')

    def test_partial_when_one_is_subset(self):
        # IC has a middle name the profile omits
        self.assertEqual(
            name_match('PRIYA D/O DEVI KRISHNAN', 'Priya Krishnan'),
            'partial',
        )
        # the other direction also reads as partial
        self.assertEqual(
            name_match('Priya Krishnan', 'Priya Devi Krishnan'),
            'partial',
        )

    def test_mismatch_when_disjoint(self):
        self.assertEqual(name_match('Priya Krishnan', 'Ahmad Yusoff'), 'mismatch')

    def test_empty_returns_mismatch(self):
        self.assertEqual(name_match('', 'Priya'), 'mismatch')
        self.assertEqual(name_match('Priya', ''), 'mismatch')
        self.assertEqual(name_match('', ''), 'mismatch')


class TestTextExtraction(TestCase):
    SAMPLE_OCR = """MYKAD
MALAYSIA
030101-14-1234
PRIYA A/P KRISHNAN
NO 12 JALAN MAHKOTA
40000 SHAH ALAM"""

    def test_extracts_nric(self):
        self.assertEqual(_extract_nric(self.SAMPLE_OCR), '030101-14-1234')

    def test_nric_handles_spaces(self):
        self.assertEqual(_extract_nric('030101 14 1234'), '030101 14 1234')

    def test_extracts_name(self):
        # Longest all-caps non-numeric line that isn't the NRIC line.
        self.assertEqual(_extract_name(self.SAMPLE_OCR, '030101-14-1234'), 'PRIYA A/P KRISHNAN')

    def test_no_text_returns_empty(self):
        self.assertEqual(_extract_nric(''), '')
        self.assertEqual(_extract_name(''), '')


class TestExtractMykadGraceful(TestCase):
    def test_empty_bytes(self):
        r = extract_mykad(b'')
        self.assertEqual(r['nric'], '')
        self.assertEqual(r['name'], '')
        self.assertIn('empty', r['error'].lower())
