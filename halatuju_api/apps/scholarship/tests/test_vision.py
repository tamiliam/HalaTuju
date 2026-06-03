"""Pure-function tests for the IC Vision OCR helpers (S13).

These exercise the canonicalisers + matchers + text-extraction regexes — the
Google Cloud Vision call itself is never made here.
"""
from django.test import TestCase, override_settings

from apps.scholarship.vision import (
    _as_image_for_gemini, _canonical_name_tokens, _canonical_nric, _extract_address,
    _extract_name, _extract_nric, _is_card_label_line, _merge_ic_reads, _should_gemini_ic,
    extract_mykad, name_match, nric_match,
)


class _FakeProfile:
    """Minimal stand-in for a StudentProfile (no DB) — just the two fields the IC
    confidence gate / merge read."""
    def __init__(self, nric='', name=''):
        self.nric = nric
        self.name = name


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
        # The parentage-marker line is the name (A/P), even with addresses present.
        self.assertEqual(_extract_name(self.SAMPLE_OCR, '030101-14-1234'), 'PRIYA A/P KRISHNAN')

    def test_name_beats_longer_locality(self):
        # Regression: a locality line LONGER than the name must NOT win — the
        # parentage marker anchors the name. (The Harish "TAMAN SRI LAYANG" bug.)
        ocr = ("MYKAD\nMALAYSIA\n080923-06-0355\nHARISH A/L SANGGAR\n"
               "37 JALAN SRI LAYANG 3/7\nTAMAN SRI LAYANG SELATAN\n28400 MENTAKAB\nPAHANG")
        self.assertEqual(_extract_name(ocr, '080923-06-0355'), 'HARISH A/L SANGGAR')

    def test_name_ap_marker_over_long_address(self):
        ocr = ("MYKAD\nMALAYSIA\n950505-05-5050\nJANANI A/P SURESH\n"
               "NO 1 LORONG BESAR\nTAMAN MELATI INDAH PERMAI\n50000 KUALA LUMPUR")
        self.assertEqual(_extract_name(ocr, '950505-05-5050'), 'JANANI A/P SURESH')

    def test_name_without_marker_uses_line_after_nric(self):
        # Chinese name, no parentage marker → first name-line right after the NRIC.
        ocr = "MYKAD\nMALAYSIA\n900101-10-5555\nTAN AH KAU\nNO 5 JALAN BESAR\nKUALA LUMPUR"
        self.assertEqual(_extract_name(ocr, '900101-10-5555'), 'TAN AH KAU')

    def test_name_truncated_marker_appends_next_line(self):
        # The Theresa case: OCR line-breaks the surname AFTER the A/P marker, so the
        # name line ENDS with the marker and the surname is on the next line → append it.
        ocr = ("MYKAD\nMALAYSIA\n080115-05-0132\nTHERESA ARUL MARY A/P\nA.PHILIPS\n"
               "TB 456 JALAN KEJORA 4\n76460 MELAKA\nMELAKA")
        self.assertEqual(_extract_name(ocr, '080115-05-0132'),
                         'THERESA ARUL MARY A/P A.PHILIPS')

    def test_name_marker_midline_does_not_append(self):
        # A marker MID-line (full name on one line) must NOT pull in the next line.
        ocr = "MYKAD\nMALAYSIA\n030101-14-1234\nPRIYA A/P KRISHNAN\nNO 9 JALAN X\n50000 KL"
        self.assertEqual(_extract_name(ocr, '030101-14-1234'), 'PRIYA A/P KRISHNAN')

    def test_mangled_ap_marker_appends_and_normalises(self):
        # The Theepicaa case: OCR dropped the SLASH, reading "A/P" as a bare "AP" at the
        # end of the line. We must still follow to the next line AND restore the "A/P".
        ocr = ("MYKAD\nMALAYSIA\n081119-05-0548\nTHEEPICAA AP\nSELVAVINAYAGAM\n"
               "NO 3 JALAN MELOR\n08000 SUNGAI PETANI\nKEDAH")
        self.assertEqual(_extract_name(ocr, '081119-05-0548'),
                         'THEEPICAA A/P SELVAVINAYAGAM')

    def test_mangled_al_marker_appends_and_normalises(self):
        ocr = ("MYKAD\nMALAYSIA\n080923-06-0355\nHARISH AL\nSANGGAR\n"
               "37 JALAN X\n28400 MENTAKAB\nPAHANG")
        self.assertEqual(_extract_name(ocr, '080923-06-0355'), 'HARISH A/L SANGGAR')

    def test_glued_name_ending_in_al_is_left_untouched(self):
        # FAISAL / PRATAP end in "AL"/"AP" but GLUED — not a standalone marker token —
        # so they must NEVER pull in the next line. (Names <6 chars are filtered out by
        # _is_name_line before this even matters, so test with real ≥6-char names.)
        for given in ('FAISAL', 'PRATAP', 'MUHAMMAD FAISAL'):
            ocr = f"MYKAD\nMALAYSIA\n900101-10-5555\n{given}\nNO 5 JALAN BESAR\nKUALA LUMPUR"
            self.assertEqual(_extract_name(ocr, '900101-10-5555'), given)

    def test_trailing_marker_canonical_is_token_safe(self):
        # The marker detector: real + spaced + mangled forms → canonical; glued → ''.
        from apps.scholarship.vision import _trailing_marker_canonical as m
        self.assertEqual(m('THERESA A/P'), 'A/P')
        self.assertEqual(m('THERESA A / P'), 'A/P')
        self.assertEqual(m('THEEPICAA AP'), 'A/P')
        self.assertEqual(m('HARISH AL'), 'A/L')
        self.assertEqual(m('AHMAD BIN'), 'BIN')
        for glued in ('FAISAL', 'PRATAP', 'VIMAL', 'KAMAL', 'BILAL'):
            self.assertEqual(m(glued), '', f'{glued} must not read as a marker')

    def test_mangled_marker_with_no_continuation_left_as_is(self):
        # A trailing "AP" with no plausible surname line after it → no append, no crash.
        ocr = "MYKAD\nMALAYSIA\n900101-10-5555\nSITI AP\n900101-10-5555\nNO 5 JALAN\nKL"
        self.assertEqual(_extract_name(ocr, '900101-10-5555'), 'SITI AP')

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

    def test_picks_up_taman_line_above_postcode(self):
        """The taman/kampung line is all-caps with no digits (same shape as a
        Malaysian name) but must NOT be filtered out — it's part of the address.
        Regression for the 'TAMAN SEMANGAT was dropped' field-report from
        Elanjelian's real MyKad. The name is identified by parentage markers
        (A/L, A/P, BIN, BINTI, S/O, D/O, @) — addresses never have those."""
        text = """710829-02-5709
ELANJELIAN A/L VENUGOPAL
C65B JALAN SEJATI
TAMAN SEMANGAT
08000 SUNGAI PETANI
KEDAH"""
        result = _extract_address(text)
        self.assertIn('C65B JALAN SEJATI', result)
        self.assertIn('TAMAN SEMANGAT', result)
        self.assertIn('08000 SUNGAI PETANI', result)
        self.assertIn('KEDAH', result)
        self.assertNotIn('ELANJELIAN', result)
        self.assertNotIn('A/L', result)

    def test_drops_malay_name_with_binti(self):
        """Malay names with BIN/BINTI markers are correctly identified as the
        name (not the address) by the parentage-marker filter."""
        text = """030101-14-1234
NUR AISYAH BINTI ABDULLAH
NO 7 JALAN BUKIT
TAMAN BAHAGIA
40000 SHAH ALAM
SELANGOR"""
        result = _extract_address(text)
        self.assertIn('NO 7 JALAN BUKIT', result)
        self.assertIn('TAMAN BAHAGIA', result)
        self.assertNotIn('NUR AISYAH', result)
        self.assertNotIn('BINTI', result)

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


class TestAddressCardLabelStrip(TestCase):
    """#2 — card-chrome labels ("MyKad", "WARGANEGARA", "ISLAM"…) must never leak into
    the surfaced home address. Field report: 'Address: MyKad, C65B JALAN SEJATI…'."""

    def test_is_card_label_line(self):
        self.assertTrue(_is_card_label_line('MyKad'))
        self.assertTrue(_is_card_label_line('WARGANEGARA MALAYSIA'))
        self.assertTrue(_is_card_label_line('ISLAM'))
        self.assertFalse(_is_card_label_line('C65B JALAN SEJATI'))
        self.assertFalse(_is_card_label_line('TAMAN SEMANGAT'))
        self.assertFalse(_is_card_label_line(''))

    def test_drops_mykad_label_from_address(self):
        # 'MyKad' sits in the up-walk window above the postcode and must be dropped.
        text = """710829-02-5709
ELANJELIAN A/L VENUGOPAL
MyKad
C65B JALAN SEJATI
08000 SUNGAI PETANI
KEDAH"""
        result = _extract_address(text)
        self.assertNotIn('MyKad', result)
        self.assertNotIn('MYKAD', result.upper())
        self.assertIn('C65B JALAN SEJATI', result)
        self.assertIn('08000 SUNGAI PETANI', result)
        self.assertIn('KEDAH', result)

    def test_drops_warganegara_label_from_address(self):
        text = """030101-14-1234
WARGANEGARA
NO 12 JALAN MAHKOTA
40000 SHAH ALAM
SELANGOR"""
        result = _extract_address(text)
        self.assertNotIn('WARGANEGARA', result.upper())
        self.assertIn('NO 12 JALAN MAHKOTA', result)


class TestIcGeminiFallbackHelpers(TestCase):
    """#5 — the IC Gemini second opinion: pure confidence-gate + merge + image-prep."""

    # ── _should_gemini_ic ────────────────────────────────────────────────────
    def test_no_escalation_on_clean_matching_read(self):
        result = {'nric': '030101-14-1234', 'name': 'PRIYA A/P KRISHNAN', 'address': 'X'}
        self.assertFalse(_should_gemini_ic(result, _FakeProfile('030101-14-1234', 'Priya Krishnan')))

    def test_escalates_when_nric_missing(self):
        self.assertTrue(_should_gemini_ic({'nric': '', 'name': 'X Y'}, _FakeProfile()))

    def test_escalates_when_name_missing(self):
        self.assertTrue(_should_gemini_ic({'nric': '030101-14-1234', 'name': ''}, _FakeProfile()))

    def test_escalates_on_nric_mismatch_vs_profile(self):
        # A single misread digit (…1234 vs …1239) → likely OCR error → second opinion.
        result = {'nric': '030101-14-1239', 'name': 'PRIYA A/P KRISHNAN'}
        self.assertTrue(_should_gemini_ic(result, _FakeProfile('030101-14-1234', 'Priya Krishnan')))

    def test_escalates_on_name_mismatch_vs_profile(self):
        result = {'nric': '030101-14-1234', 'name': 'SOMEONE ELSE'}
        self.assertTrue(_should_gemini_ic(result, _FakeProfile('030101-14-1234', 'Priya Krishnan')))

    def test_no_escalation_without_profile_when_fields_present(self):
        # Nothing to compare against, but both core fields read → stay free.
        result = {'nric': '030101-14-1234', 'name': 'PRIYA A/P KRISHNAN'}
        self.assertFalse(_should_gemini_ic(result, None))

    @override_settings(IC_GEMINI_FALLBACK_ENABLED=False)
    def test_knob_off_never_escalates(self):
        self.assertFalse(_should_gemini_ic({'nric': '', 'name': ''}, _FakeProfile()))

    # ── _merge_ic_reads ──────────────────────────────────────────────────────
    def test_merge_fills_empty_core_fields(self):
        det = {'nric': '', 'name': '', 'address': '', 'error': None}
        g = {'nric': '030101-14-1234', 'name': 'PRIYA A/P KRISHNAN', 'address': 'NO 1, KL'}
        out = _merge_ic_reads(det, g, _FakeProfile())
        self.assertEqual(out['nric'], '030101-14-1234')
        self.assertEqual(out['name'], 'PRIYA A/P KRISHNAN')
        self.assertEqual(out['address'], 'NO 1, KL')

    def test_merge_recovers_misread_nric_when_gemini_matches_profile(self):
        det = {'nric': '030101-14-1239', 'name': 'PRIYA A/P KRISHNAN', 'address': '', 'error': None}
        g = {'nric': '030101-14-1234', 'name': 'PRIYA A/P KRISHNAN', 'address': ''}
        out = _merge_ic_reads(det, g, _FakeProfile('030101-14-1234', 'Priya Krishnan'))
        self.assertEqual(out['nric'], '030101-14-1234')   # gemini wins — it matches profile

    def test_merge_keeps_confident_det_nric_when_gemini_disagrees(self):
        det = {'nric': '030101-14-1234', 'name': 'PRIYA A/P KRISHNAN', 'address': '', 'error': None}
        g = {'nric': '999999-99-9999', 'name': 'PRIYA A/P KRISHNAN', 'address': ''}
        out = _merge_ic_reads(det, g, _FakeProfile('030101-14-1234', 'Priya Krishnan'))
        self.assertEqual(out['nric'], '030101-14-1234')   # det already matched → not overridden

    def test_merge_address_always_prefers_gemini_clean_value(self):
        det = {'nric': '030101-14-1234', 'name': 'X', 'address': 'MyKad, NO 1', 'error': None}
        g = {'nric': '', 'name': '', 'address': 'NO 1, JALAN BERSIH, 50000 KL'}
        out = _merge_ic_reads(det, g, _FakeProfile())
        self.assertEqual(out['address'], 'NO 1, JALAN BERSIH, 50000 KL')

    # ── _as_image_for_gemini ─────────────────────────────────────────────────
    def test_image_passthrough_with_mime(self):
        img, mime = _as_image_for_gemini(b'\xff\xd8\xff', 'image/jpeg')
        self.assertEqual(img, b'\xff\xd8\xff')
        self.assertEqual(mime, 'image/jpeg')

    def test_image_defaults_mime_when_unknown(self):
        _img, mime = _as_image_for_gemini(b'rawbytes', '')
        self.assertEqual(mime, 'image/jpeg')

    def test_empty_returns_none(self):
        img, mime = _as_image_for_gemini(b'', 'image/png')
        self.assertIsNone(img)
        self.assertEqual(mime, '')


class TestExtractMykadGraceful(TestCase):
    def test_empty_bytes(self):
        r = extract_mykad(b'')
        self.assertEqual(r['nric'], '')
        self.assertEqual(r['name'], '')
        self.assertEqual(r['address'], '')
        self.assertIn('empty', r['error'].lower())
