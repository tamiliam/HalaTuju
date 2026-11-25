"""TD-740 review round 4 (25 Nov): edge (j) closed - a blank code is tested in a spread run, never alone.

r3 drew each Type3 code ALONE on pdfium's text sheet and took "pdfium reads nothing" as blank. pdfium drops a text
object only when the WHOLE object's box is degenerate: an 'L' whose glyph has a zero-size d1 box and no ink read
nothing alone, but ``(LULUS) Tj`` (even ``(LL) Tj``) on the real page read 'LULUS' through a /ToUnicode our parser
reads as spaces. The sheet now shows each code `RUN` times, spread by character spacing, and a code is blank only
when pdfium reads at least one character of its own and only whitespace (and pypdf reads whitespace). Crafted PDFs
only, fictional words only.
"""
import io

from django.test import SimpleTestCase
from pypdf import PdfReader

from apps.scholarship import pdfium_type3
from apps.scholarship.tests.test_ocr20_dup_keys import _words
from apps.scholarship.tests.test_td740_offpage import G, _lus, _page1_lost, _pdf, _reads, _stream, _t3

BODY = b'BT /T3 24 Tf 72 600 Td (LULUS) Tj ET'
SHEAR = b'BT /T3 24 Tf 1 0 1 1 72 600 Tm (LULUS) Tj ET'
#: The review's CMap: pdfium reads the bytes ('L', 'U', 'S'), our parser and pypdf read spaces.
BAD = b'3 beginbfchar <4C> <00 20> <53> <00 20> <55> <00 20> endbfchar'
SPACE = b'3 beginbfchar <4C> <0020> <53> <0020> <55> <0020> endbfchar'
Z = b'600 0 0 0 0 700 d1'          # zero wide, 700 high
H = b'600 0 0 0 500 0 d1'          # 500 wide, zero high
ZZ = b'600 0 0 0 0 0 d1'           # an empty box
FM = b'[0.001 0 0 0.001 0 0]'


def _t3_tu(cmap: bytes, glyph: bytes, body: bytes = BODY, fm: bytes = FM, width: int = 600) -> bytes:
    """Page 1 shows ``body`` in a Type3 font (8) whose L, U and S glyphs are ``glyph`` (no ink), with a /ToUnicode
    (12) holding ``cmap``, the /FontMatrix ``fm`` and every width ``width``."""
    objs = _t3(_lus(glyph), diffs=b'[76 /L 83 /S 85 /U]')
    objs[0] = objs[0][:-2] + b' /ToUnicode 12 0 R >>'
    objs[0] = objs[0].replace(b'/FontMatrix ' + FM, b'/FontMatrix ' + fm)
    objs[0] = objs[0].replace(b'/Widths [' + b'600 ' * 59, b'/Widths [' + b'%d ' % width * 59)
    full = (b'/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /X def /CMapType 2 def\n'
            b'1 begincodespacerange <00> <FF> endcodespacerange\n' + cmap + b'\nendcmap CMapName currentdict'
            b' /CMap defineresource pop end end')
    return _pdf(G + body, extra=objs + [_stream(full)], fonts=b'/T3 8 0 R ', forms=0)


class BlankCodesAreReadInARun(SimpleTestCase):
    def test_review_probes(self):
        """Review round 4's bad cases: pdfium's page read 'LULUS' (or 'LL') that nothing draws; now refused."""
        for name, pdf in (('z_id_bad', _t3_tu(BAD, Z)), ('h_id_bad', _t3_tu(BAD, H)),
                          ('z_shear_bad', _t3_tu(BAD, Z, SHEAR)), ('h_shear_bad', _t3_tu(BAD, H, SHEAR)),
                          ('zz_shear_bad', _t3_tu(BAD, ZZ, SHEAR)), ('zz_id_bad', _t3_tu(BAD, ZZ)),
                          ('z_id_bad_two', _t3_tu(BAD, Z, b'BT /T3 24 Tf 72 600 Td (LL) Tj ET'))):
            with self.subTest(name):
                self.assertTrue(_page1_lost(pdf))

    def test_a_genuine_zero_box_space_still_reads(self):
        """A zero-box glyph a real /ToUnicode maps to a space (the genuine letters' case): pdfium reads one space
        in the run, so the page reads."""
        for glyph in (Z, H, ZZ):
            with self.subTest(glyph=glyph):
                pdf = _t3_tu(SPACE, glyph)
                self.assertTrue(_reads(pdf, 'GENUINE'))
                self.assertEqual(_words(pdf), ['GENUINE'])

    def test_a_zero_width_glyph_is_still_spread(self):
        """/Widths 0: the character spacing alone spreads the run, so pdfium still reads the 'L's (refused) and
        the genuine space (passes)."""
        for glyph in (Z, ZZ):
            with self.subTest(glyph=glyph):
                self.assertTrue(_page1_lost(_t3_tu(BAD, glyph, width=0)))
                self.assertTrue(_reads(_t3_tu(SPACE, glyph, width=0), 'GENUINE'))

    def test_odd_font_matrices_and_widths_never_pass_the_bad_map(self):
        """A negative, zero, rotated or huge /FontMatrix with zero or Tc-sized widths: refused, whatever the run."""
        for fm in (b'[-0.001 0 0 0.001 0 0]', b'[-0.001 0 0 -0.001 0 0]', b'[0 0.001 -0.001 0 0 0]',
                   b'[0 0 0 0 0 0]', b'[1 0 0 1 0 0]'):
            for width in (0, pdfium_type3.RUN_TC):
                with self.subTest(fm=fm, width=width):
                    self.assertTrue(_page1_lost(_t3_tu(BAD, Z, fm=fm, width=width)))

    def test_a_run_that_collapses_is_refused(self):
        """A /FontMatrix of -0.001 with widths of exactly `RUN_TC` cancels the spacing: the run's box is degenerate
        and pdfium reads nothing. Nothing read is not blank, so even the genuine-looking space map is refused (the
        STRICT rule: when unsure, refuse)."""
        pdf = _t3_tu(SPACE, ZZ, fm=b'[-0.001 0 0 0.001 0 0]', width=pdfium_type3.RUN_TC)
        self.assertTrue(_page1_lost(pdf))

    def test_horizontal_scaling_on_the_page_does_not_matter(self):
        """Tz on the real page cannot hide the bad map: the sheet reads the code in its own text state."""
        for tz in (b'0 Tz ', b'-100 Tz ', b'1 Tz '):
            with self.subTest(tz=tz):
                self.assertTrue(_page1_lost(_t3_tu(BAD, Z, b'BT /T3 24 Tf ' + tz + b'72 600 Td (LULUS) Tj ET')))


class TheSheetAndTheRule(SimpleTestCase):
    def _font(self):
        return PdfReader(io.BytesIO(_t3_tu(SPACE, ZZ))).pages[0]['/Resources']['/Font']['/T3']

    def test_text_sheet_shows_a_spread_run(self):
        self.assertEqual((pdfium_type3.TEXT_PT, pdfium_type3.RUN, pdfium_type3.RUN_TC), (1000, 3, 500))
        page = PdfReader(io.BytesIO(pdfium_type3.text_sheet([(self._font(), 76)]))).pages[0]
        self.assertEqual(page.get_contents().get_data(), b'BT /G0 1000 Tf 500 Tc 2000 2000 Td <4c4c4c> Tj ET')

    def test_nothing_read_is_not_blank(self):
        font = self._font()
        for name, read, blank in (('space', [(32, 0)], True), ('spaces', [(32, 0), (32, 1), (32, 0)], True),
                                  ('none', [], False), ('generated_only', [(32, 1)], False),
                                  ('letters', [(76, 0)] * 3, False), ('an_error', [(32, 0), (32, -1)], False)):
            with self.subTest(name):
                got = pdfium_type3.pdfium_blank([(font, 76)], lambda data, r=read: [r])
                self.assertEqual(got == {(id(font), 76)}, blank)
