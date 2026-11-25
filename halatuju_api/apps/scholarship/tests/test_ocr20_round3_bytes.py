"""OCR-20 review round 3 part 1 (25 Nov): content-stream bytes pypdf and pdfium tokenise differently
(`pdf_content_bytes`). Each probe drew one thing in pdfium and read another to the gate; each now loses its exact
read (page 1 not drawn, no text). The controls are genuine-looking shapes that must keep it. Fictional words only.
"""
from django.test import SimpleTestCase

from apps.scholarship import pdf_content_bytes as cb
from apps.scholarship import pdf_pages
from apps.scholarship.tests.test_ocr20_dup_keys import _words

FONT = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
G = b'BT /F1 24 Tf 72 700 Td (GENUINE) Tj ET\n'
L = b'BT /F1 24 Tf 72 600 Td (LULUS) Tj ET\n'


def _stream(data: bytes) -> bytes:
    return b'<< /Length %d >>\nstream\n' % len(data) + data + b'\nendstream'


def _pdf(*streams: bytes) -> bytes:
    """One page; one content stream, or a /Contents array of several (objects 5, 6, ...)."""
    out, off = bytearray(b'%PDF-1.4\n'), []
    refs = b' '.join(b'%d 0 R' % (5 + k) for k in range(len(streams)))
    contents = refs if len(streams) == 1 else b'[' + refs + b']'
    bodies = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
              b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >>'
              b' /Contents ' + contents + b' >>', FONT] + [_stream(s) for s in streams]
    for n, body in enumerate(bodies, 1):
        off.append(len(out))
        out += b'%d 0 obj\n' % n + body + b'\nendobj\n'
    x, size = len(out), len(bodies) + 1
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size + b''.join(b'%010d 00000 n \n' % o for o in off)
    return bytes(out + b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, x))


def _read(pdf: bytes) -> tuple:
    """(first_page_drawn, pdf_text_layer collapsed, pdf_page_texts collapsed)."""
    pdf_pages._layer_memo_clear()
    drawn = pdf_pages.first_page_drawn(pdf)
    pdf_pages._layer_memo_clear()
    layer = ' '.join(pdf_pages.pdf_text_layer(pdf).split())
    pdf_pages._layer_memo_clear()
    pages = [' '.join(t.split()) for t in pdf_pages.pdf_page_texts(pdf, 1)]
    pdf_pages._layer_memo_clear()
    return drawn, layer, pages


#: The round-3 probes (scratchpad ocr20/r3, p1 and p2) and the shapes found next to them while fixing.
PROBES = {
    'H1_p1a_comment_across_streams': (G + b'% note', L),
    'H1_string_open_across_streams': (b'BT /F1 24 Tf 72 700 Td (GEN', b'UINE) Tj ET'),
    'H1_split_dict_end': (b'/Span << /ActualText (X) >', b'> BDC ' + L + b'EMC'),
    'H2_p1b_x80_after_Tj': (b'BT /F1 24 Tf 72 700 Td (TIDAK) Tj\x80 72 650 Td (LAYAK) Tj ET',),
    'H2_p1b2_xff_after_Tj': (b'BT /F1 24 Tf 72 700 Td (TIDAK) Tj\xff 72 650 Td (LAYAK) Tj ET',),
    'H2_p2b_cm_x80_offpage': (G + b'q 1 0 0 1 5000 5000 cm\x80 ' + L + b'Q\n',),
    'H2_p2a_Tr3_x80': (G + b'BT 3 Tr\x80 /F1 24 Tf 72 600 Td (LULUS) Tj ET\n',),
    'H2_nul_after_Tj_unknown_word': (b'BT /F1 24 Tf 72 700 Td (TIDAK) Tj\x00 72 650 Td (LAYAK) Tj ET',),
    'H2_unknown_operator': (G + b'1 0 0 1 9000 9000 zz ' + L,),
    'H3_p1f_BI_x80': (G + b'q 10 0 0 10 300 300 cm BI\x80 /W 1 /H 1 /BPC 8 /CS /G ID ' + L + b'EI Q\n',),
    'M1_p1d_octal_777': (b'BT /F1 24 Tf 72 700 Td (A\\777B) Tj ET',),
    'M1_unknown_escape_digit': (b'BT /F1 24 Tf 72 700 Td (RM\\9) Tj ET',),
    'M1_unknown_escape_letter': (b'BT /F1 24 Tf 72 700 Td (A\\qB) Tj ET',),
    'M2_p1e_bs_lf_lf': (b'BT /F1 24 Tf 72 700 Td (TIDAK\\\n\nLAYAK) Tj ET',),
    'M2_bs_lf_cr': (b'BT /F1 24 Tf 72 700 Td (TIDAK\\\n\rLAYAK) Tj ET',),
    'M2_bs_cr_cr': (b'BT /F1 24 Tf 72 700 Td (TIDAK\\\r\rLAYAK) Tj ET',),
}


class TheRound3ProbesLoseTheExactRead(SimpleTestCase):
    def test_every_probe_is_not_drawn_and_has_no_text(self):
        for name, streams in PROBES.items():
            with self.subTest(name):
                self.assertEqual(_read(_pdf(*streams)), (False, '', ['']))

    def test_pdfium_draws_what_the_gate_would_have_read_differently(self):
        """The disagreement is real: pdfium drew TIDAK where pypdf read only LAYAK (probe p1b)."""
        self.assertIn('TIDAK', _words(_pdf(*PROBES['H2_p1b_x80_after_Tj'])))


class GenuineShapesKeepTheExactRead(SimpleTestCase):
    def test_controls(self):
        cases = {
            'x80_and_xff_inside_a_string': ((b'BT /F1 24 Tf 72 700 Td (A\x80B\xffC) Tj ET',), 'A\x80B\xffC'),
            'contents_array_streams_end_in_lf': ((G + b'% note\n', L), 'GENUINE LULUS'),
            'contents_array_no_lf_between_operators': ((G.strip(), L.strip()), 'GENUINE LULUS'),
            'backslash_cr_lf': ((b'BT /F1 24 Tf 72 700 Td (TIDAK\\\r\nLAYAK) Tj ET',), 'TIDAKLAYAK'),
            'backslash_cr_and_lf_alone': ((b'BT /F1 24 Tf 72 700 Td (TI\\\rDAK\\\nLAYAK) Tj ET',), 'TIDAKLAYAK'),
            'standard_escapes': ((b'BT /F1 24 Tf 72 700 Td (A\\(B\\)C\\\\D\\/E\\101) Tj ET',), 'A(B)C\\D/EA'),
            'nested_parens_and_percent_in_string': ((b'BT /F1 24 Tf 72 700 Td (50% (x) <y>) Tj ET',), '50% (x) <y>'),
            'hex_string_with_white_space': ((b'BT /F1 24 Tf 72 700 Td <4C 55\n4C55 53> Tj ET',), 'LULUS'),
            'comment_with_high_bytes': ((b'%\x80\xff\x0b\n' + G,), 'GENUINE'),
            'colour_operators_variable_arity': ((b'/DeviceRGB cs 0 0 0 sc ' + G,), 'GENUINE'),
            'bi_word_ending_a_string': ((b'BT /F1 24 Tf 72 700 Td (SPM BI) Tj ET',), 'SPM BI'),
        }
        for name, (streams, text) in cases.items():
            with self.subTest(name):
                self.assertEqual(_read(_pdf(*streams)), (True, text, [text]))


class TheScan(SimpleTestCase):
    def test_scan_raises_on_bytes_and_escapes(self):
        for data in (b'Tj\x80', b'/F\xff 1 Tf', b'1\x0b2 Td', b'<41\x8042> Tj', b'(\\400)', b'(\\8)',
                     b'(a\\\n\n)', b'(a\\\r\r)', b'(a\\\n\r)'):
            with self.subTest(data):
                with self.assertRaises(ValueError):
                    cb._scan(data)

    def test_scan_tells_an_open_comment_string_or_hex(self):
        self.assertFalse(cb._scan(b'ET % note'))
        self.assertFalse(cb._scan(b'(GEN'))
        self.assertFalse(cb._scan(b'(a (b) \\)'))
        self.assertFalse(cb._scan(b'<41'))
        self.assertTrue(cb._scan(b'ET % note\n'))
        self.assertTrue(cb._scan(b'<< /A (x) >> BDC (a\\\r\n) Tj <4142> Tj'))
        self.assertTrue(cb._scan(b'(\\377\\0\\12a)'))

    def test_inline_image_word_ends_on_pdfium_white_space(self):
        for data in (b' BI\x80/W', b' BI\xff', b'Q BI\n', b'\x80BI '):
            with self.subTest(data):
                self.assertTrue(cb.INLINE_IMAGE.search(data))
        self.assertFalse(cb.INLINE_IMAGE.search(b' BIG '))
        self.assertFalse(cb.INLINE_IMAGE.search(b'(SPM BI) Tj'))     # a subject in a string (3 genuine fixtures)

    def test_unknown_operator(self):
        self.assertTrue(cb.unknown_operator([([], b'Tj\x80')]))
        self.assertTrue(cb.unknown_operator([([], b'endobj')]))
        self.assertFalse(cb.unknown_operator([([], b'BX'), ([1], b'sc'), ([], b'EX'), ([], b'INLINE IMAGE')]))
