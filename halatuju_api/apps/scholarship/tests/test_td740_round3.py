"""TD-740 review round 3 (25 Nov): pdfium decides blank codes; every indirect value is resolved.

Finding 1: a Type3 code whose glyph draws nothing passed when OUR /ToUnicode parser read it as a space, but pdfium
reads a CMap differently (a ``/Xbeginbfchar`` keyword glued to a name, a ``%beginbfchar`` comment, a space inside a
destination ``<00 20>``): pdfium's text page, and so the SPM words op, read 'LULUS' that nothing draws. pdfium's own
text page now reads every such code (`pdfium_type3.pdfium_blank`). Finding 2: a form whose /Subtype is ``9 0 R`` was
not walked (pypdf's ``get`` does not resolve), while pdfium draws it and pypdf reads it. Crafted PDFs only, fictional
words only.
"""
from django.test import SimpleTestCase

from apps.scholarship import pdfium_type3
from apps.scholarship.tests.test_ocr20_dup_keys import _words
from apps.scholarship.tests.test_td740_offpage import (
    EMPTY_D1, G, INKED, _gate_refuses, _lus, _page1_lost, _pdf, _reads, _stream, _t3)

BODY = b'BT /T3 24 Tf 72 600 Td (LULUS) Tj ET'
SPACES = b'<4C> <0020> <53> <0020> <55> <0020>'


def _t3_tu(cmap: bytes, glyph: bytes = EMPTY_D1) -> bytes:
    """Page 1 shows LULUS in a Type3 font (8) whose L, U and S glyphs are ``glyph``, with a /ToUnicode (12)
    holding ``cmap``."""
    objs = _t3(_lus(glyph), diffs=b'[76 /L 83 /S 85 /U]')
    objs[0] = objs[0][:-2] + b' /ToUnicode 12 0 R >>'
    full = (b'/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /X def /CMapType 2 def\n'
            b'1 begincodespacerange <00> <FF> endcodespacerange\n' + cmap + b'\nendcmap CMapName currentdict'
            b' /CMap defineresource pop end end')
    return _pdf(G + BODY, extra=objs + [_stream(full)], fonts=b'/T3 8 0 R ', forms=0)


class PdfiumReadsTheBlankCodes(SimpleTestCase):
    def test_review_probes(self):
        """Our parser reads a space; pdfium reads 'L', 'U', 'S' that nothing draws: refused."""
        for name, cmap in (('tu_glued_begin', b'/Xbeginbfchar ' + SPACES + b' endbfchar'),
                           ('tu_comment_begin', b'%beginbfchar\n' + SPACES + b' endbfchar'),
                           ('tu_bad_dst', b'3 beginbfchar <4C> <00 20> <53> <00 20> <55> <00 20> endbfchar')):
            with self.subTest(name):
                self.assertTrue(_page1_lost(_t3_tu(cmap)))

    def test_controls(self):
        """A real map to spaces reads as blank to both (the genuine letters' case); an inked glyph reads."""
        pdf = _t3_tu(b'3 beginbfchar ' + SPACES + b' endbfchar')
        self.assertTrue(_reads(pdf, 'GENUINE'))
        self.assertEqual(_words(pdf), ['GENUINE'])
        inked = _t3_tu(b'3 beginbfchar ' + SPACES.replace(b'0020', b'004C') + b' endbfchar', INKED)
        self.assertEqual(_words(inked), ['GENUINE', 'LLLLL'])

    def test_tiny_and_zero_boxes(self):
        """The sheet shows codes at `TEXT_PT`: a 1 x 1 box (pdfium reads it on a real page) is read there, so a
        parser-only space is refused; a zero box (the genuine space: pdfium drops it on every page) reads as blank."""
        self.assertEqual(pdfium_type3.TEXT_PT, 1000)
        glued = b'/Xbeginbfchar ' + SPACES + b' endbfchar'
        self.assertTrue(_page1_lost(_t3_tu(glued, b'600 0 0 0 1 1 d1')))
        self.assertTrue(_page1_lost(_t3_tu(glued, b'600 0 0 0 0.6 0.6 d1')))
        for glyph in (b'600 0 0 0 0 0 d1', b'600 0 0 0 0 700 d1'):
            with self.subTest(glyph=glyph):
                self.assertTrue(_reads(_t3_tu(b'3 beginbfchar ' + SPACES + b' endbfchar', glyph), 'GENUINE'))

    def test_pdfium_blank_fails_closed(self):
        font = object()
        self.assertEqual(pdfium_type3.pdfium_blank([], None), set())
        self.assertIsNone(pdfium_type3.pdfium_blank([(font, 76)], None))
        too_many = [(font, 76)] * (pdfium_type3.INK_MAX_GLYPHS + 1)
        self.assertIsNone(pdfium_type3.pdfium_blank(too_many, lambda data: [[(32, 0)]] * len(too_many)))

    def test_pdfium_blank_rules(self):
        """Per page: every character whitespace; none at all is blank (pdfium drops a degenerate box)."""
        pdf = _t3_tu(b'3 beginbfchar ' + SPACES + b' endbfchar')
        from pypdf import PdfReader
        import io
        font = PdfReader(io.BytesIO(pdf)).pages[0]['/Resources']['/Font']['/T3']
        for name, read, blank in (('space', [(32, 0)], True), ('none', [], True), ('generated_only', [(32, 1)], True),
                                  ('a_letter', [(32, 0), (76, 0)], False), ('an_error', [(32, -1)], False),
                                  ('nbsp', [(0xA0, 0)], True)):
            with self.subTest(name):
                got = pdfium_type3.pdfium_blank([(font, 76)], lambda data, r=read: [r])
                self.assertEqual(got == {(id(font), 76)}, blank)
        with self.subTest('page_count_mismatch'):
            self.assertIsNone(pdfium_type3.pdfium_blank([(font, 76)], lambda data: []))


def _form_indirect(glyph: bytes, subtype_ref=True, font_in_form=True) -> bytes:
    """Page 1 draws /X1 (8), a form whose /Subtype is ``9 0 R`` (the name /Form); the Type3 font (10) is named in
    the form's resources (``font_in_form``) or the page's."""
    sub = b'/Subtype 9 0 R' if subtype_ref else b'/Subtype /Form'
    res = b' /Resources << /Font << /T3 10 0 R >> >>' if font_in_form else b''
    form = _stream(BODY, b'<< /Type /XObject ' + sub + b' /BBox [-10000 -10000 10000 10000]' + res)
    return _pdf(G + b'/X1 Do', extra=[form, b'/Form'] + _t3(_lus(glyph), at=10),
                fonts=b'' if font_in_form else b'/T3 10 0 R ', forms=1)


class IndirectValuesAreResolved(SimpleTestCase):
    def test_review_probes_form_subtype(self):
        for name, pdf in (('ctl_form_direct_empty', _form_indirect(EMPTY_D1, subtype_ref=False)),
                          ('form_subtype_ref_empty', _form_indirect(EMPTY_D1)),
                          ('form_subtype_ref_pagefont_empty', _form_indirect(EMPTY_D1, font_in_form=False))):
            with self.subTest(name):
                self.assertTrue(_page1_lost(pdf))
        self.assertTrue(_reads(_form_indirect(INKED), 'GENUINE LULUS'))

    def test_font_subtype(self):
        """A Type3 font whose /Subtype is ``12 0 R``: `_is_t3` resolves it (so `shown_ok` and `page_flags` judge
        it), and the pdfium load whitelist (`pdf_pdfium_load._font`, unresolved) refuses the whole file."""
        import io
        from pypdf import PdfReader
        for glyph, words in ((EMPTY_D1, []), (INKED, ['GENUINE', 'LULUS'])):
            objs = _t3(_lus(glyph), diffs=b'[76 /L 83 /S 85 /U]')
            objs[0] = objs[0].replace(b'/Subtype /Type3', b'/Subtype 12 0 R')
            pdf = _pdf(G + BODY, extra=objs + [b'/Type3'], fonts=b'/T3 8 0 R ', forms=0)
            with self.subTest(glyph=glyph):
                self.assertTrue(pdfium_type3._is_t3(PdfReader(io.BytesIO(pdf)).pages[0]['/Resources']['/Font']['/T3']))
                self.assertTrue(pdfium_type3.page_flags(pdf, 0)[2] or pdfium_type3.page_flags(pdf, 0)[3])
                self.assertTrue(_gate_refuses(pdf))
                self.assertEqual(_words(pdf), words)   # the words op: the page refused, or all drawn

    def test_form_resources_and_groups(self):
        """The form's /Resources and its /Font group by reference; the page's /XObject group by reference."""
        form = _stream(BODY, b'<< /Type /XObject /Subtype /Form /BBox [-10000 -10000 10000 10000] /Resources 9 0 R')
        self.assertTrue(_page1_lost(_pdf(G + b'/X1 Do', extra=[form, b'<< /Font 14 0 R >>'] + _t3(_lus(EMPTY_D1), at=10)
                                         + [b'<< /T3 10 0 R >>'], forms=1)))

    def test_font_matrix_items(self):
        """/FontMatrix items by reference: resolved (before, a float() of a reference refused a genuine glyph)."""
        for glyph, lost in ((INKED, False), (EMPTY_D1, True)):
            objs = _t3(_lus(glyph), diffs=b'[76 /L 83 /S 85 /U]')
            objs[0] = objs[0].replace(b'/FontMatrix [0.001 0 0 0.001 0 0]', b'/FontMatrix [12 0 R 0 0 12 0 R 0 0]')
            pdf = _pdf(G + BODY, extra=objs + [b'0.001'], fonts=b'/T3 8 0 R ', forms=0)
            with self.subTest(lost=lost):
                self.assertEqual(_page1_lost(pdf), lost)

    def test_encoding_and_charprocs_by_reference(self):
        objs = _t3(_lus(EMPTY_D1), diffs=b'12 0 R')
        objs[0] = objs[0].replace(b'/CharProcs << ', b'/CharProcs 13 0 R /X << ')
        objs[0] = objs[0].replace(b'/Encoding << /Type /Encoding /Differences 12 0 R >>', b'/Encoding 14 0 R')
        extra = objs + [b'[76 /L 83 /S 85 /U]', b'<< /L 9 0 R /U 10 0 R /S 11 0 R >>',
                        b'<< /Type /Encoding /Differences 12 0 R >>']
        self.assertTrue(_page1_lost(_pdf(G + BODY, extra=extra, fonts=b'/T3 8 0 R ', forms=0)))

    def test_page_flags_pattern_type(self):
        """A tiling pattern whose /PatternType is ``13 0 R`` (the number 1): its resources are walked."""
        pat = _stream(b'', b'<< /Type /Pattern /PatternType 13 0 R /PaintType 1 /TilingType 1 /BBox [0 0 10 10]'
                           b' /XStep 10 /YStep 10 /Resources << /Font << /T3 8 0 R >> >>')
        objs = _t3(_lus(INKED), diffs=b'[76 /L 83 /S 85 /U]')
        pdf = _pdf(G, extra=objs + [pat, b'1'], forms=0)
        pdf = pdf.replace(b'/Font << /F1 4 0 R >>', b'/Font << /F1 4 0 R >> /Pattern << /P1 12 0 R >>', 1)
        from apps.scholarship.tests.test_td740_offpage import _fix_xref
        self.assertTrue(pdfium_type3.page_flags(_fix_xref(pdf), 0)[3])

    def test_a_parent_form_whose_resources_are_null(self):
        """/Resources by reference to null with a /Parent: two resource views, refused like a missing one."""
        form = _stream(b'BT /F1 24 Tf 72 300 Td (LULUS) Tj ET', b'<< /Type /XObject /Subtype /Form'
                       b' /BBox [-10000 -10000 10000 10000] /Resources 9 0 R /Parent 10 0 R')
        pdf = _pdf(G + b'/X1 Do', extra=[form, b'null', b'<< /Resources << /Font << /F1 4 0 R >> >> >>'], forms=1)
        self.assertTrue(pdfium_type3.page_flags(pdf, 0)[0])

    def test_val(self):
        from pypdf.generic import DictionaryObject, NameObject
        self.assertIsNone(pdfium_type3._val(None, '/Subtype'))
        self.assertIsNone(pdfium_type3._val(DictionaryObject(), '/Subtype'))
        d = DictionaryObject({NameObject('/Subtype'): NameObject('/Form')})
        self.assertEqual(pdfium_type3._val(d, '/Subtype'), '/Form')
