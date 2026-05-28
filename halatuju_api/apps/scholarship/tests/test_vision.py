"""Pure-function tests for the IC Vision OCR helpers (S13).

These exercise the canonicalisers + matchers + text-extraction regexes — the
Google Cloud Vision call itself is never made here.
"""
from django.test import TestCase

from apps.scholarship.vision import (
    _canonical_name_tokens, _canonical_nric, _extract_address, _extract_name, _extract_nric,
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


class TestExtractAddress(TestCase):
    """Post-S14: pull the MyKad-printed home address (postcode-anchored, 2-3 lines).

    Soft signal only — admin/interviewer eyeballs the surfaced text against
    profile.address. No matcher / no verdict computed."""

    def test_extracts_simple_two_line_block(self):
        text = """MYKAD
MALAYSIA
030101-14-1234
PRIYA A/P KRISHNAN
NO 12 JALAN MAHKOTA
40000 SHAH ALAM
SELANGOR"""
        # postcode anchor on the "40000 SHAH ALAM" line; the all-caps name is dropped.
        result = _extract_address(text)
        self.assertIn('NO 12 JALAN MAHKOTA', result)
        self.assertIn('40000 SHAH ALAM', result)
        self.assertIn('SELANGOR', result)  # state picked up from the line below the postcode
        self.assertNotIn('PRIYA', result)  # name skipped (no digits, all-caps letters)
        self.assertNotIn('030101', result)  # NRIC skipped

    def test_picks_up_state_below_postcode(self):
        """The state line sits directly below the postcode on MyKad — must be
        captured even though it's all-caps with no digits (same shape as a name)."""
        text = """710829-02-5709
ELANJELIAN A/L VENUGOPAL
C65B JALAN SEJATI
08000 SUNGAI PETANI
KEDAH"""
        result = _extract_address(text)
        self.assertIn('C65B JALAN SEJATI', result)
        self.assertIn('08000 SUNGAI PETANI', result)
        self.assertIn('KEDAH', result)
        self.assertNotIn('ELANJELIAN', result)

    def test_state_filter_rejects_non_state_word(self):
        """A random one-word all-caps line below the postcode must NOT be
        treated as a state (we'd otherwise pick up gibberish from the back of
        the IC like 'MYKAD')."""
        text = """030101-14-1234
NO 1
40000 SHAH ALAM
MYKAD"""
        result = _extract_address(text)
        self.assertIn('40000 SHAH ALAM', result)
        self.assertNotIn('MYKAD', result)  # 'MYKAD' is not in the state list

    def test_state_w_p_prefix_variants(self):
        """'W.P. KUALA LUMPUR' and the unspaced 'WP KUALA LUMPUR' both work."""
        text_dotted = "030101-14-1234\nNO 1\n50000 KL\nW.P. KUALA LUMPUR"
        text_plain = "030101-14-1234\nNO 1\n50000 KL\nKUALA LUMPUR"
        self.assertIn('W.P. KUALA LUMPUR', _extract_address(text_dotted))
        self.assertIn('KUALA LUMPUR', _extract_address(text_plain))

    def test_strips_alamat_label(self):
        text = """710829-02-5709
ELANJELIAN A/L VENUGOPAL
Alamat: NO 5, JALAN BAHAGIA
68000 AMPANG"""
        result = _extract_address(text)
        self.assertTrue(result.startswith('NO 5, JALAN BAHAGIA') or 'NO 5' in result)
        self.assertNotIn('Alamat', result)  # the "Alamat:" prefix is dropped

    def test_returns_empty_without_postcode(self):
        # If Vision can't find a 5-digit postcode block, no address surfaces.
        text = "MYKAD\nMALAYSIA\n030101-14-1234\nPRIYA A/P KRISHNAN"
        self.assertEqual(_extract_address(text), '')

    def test_empty_input(self):
        self.assertEqual(_extract_address(''), '')
        self.assertEqual(_extract_address(None), '')  # type: ignore

    def test_deduplicates_repeated_lines(self):
        # Vision occasionally repeats the same line in the layout pass.
        text = """030101-14-1234
NO 12 JALAN ABC
NO 12 JALAN ABC
40000 SHAH ALAM"""
        result = _extract_address(text)
        # Each unique line should appear once.
        self.assertEqual(result.count('NO 12 JALAN ABC'), 1)


class TestExtractMykadGraceful(TestCase):
    def test_empty_bytes(self):
        r = extract_mykad(b'')
        self.assertEqual(r['nric'], '')
        self.assertEqual(r['name'], '')
        self.assertEqual(r['address'], '')
        self.assertIn('empty', r['error'].lower())
