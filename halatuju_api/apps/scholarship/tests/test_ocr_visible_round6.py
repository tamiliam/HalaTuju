"""S-visible fix round 6: whitelists, not blacklists — optional content, what pdfium loads with a page, string
length, and one lock around pdfium (fix round 8: the lock gave way to a pdfium child process, `pdfium_run`).

Each hostile shape is the Vision route in under 3 seconds; each real-corpus shape keeps its free text layer.
Fictional words only.
"""
import threading
import time
import zlib
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import pdf_pages, spm_cert_parse
from apps.scholarship.tests.test_ocr_visible import DRAWN, SPM_TEXT, _raw_layer, _show, _stream
from apps.scholarship.tests.test_ocr_visible_paths import ALL_ON, FONT_RES, MARKED, SECRET, _doc, _oc_doc, _xobj

TEXT = _show(SPM_TEXT)


def _reads(pdf):
    pdf_pages._layer_memo_clear()
    return 'SIJIL' in pdf_pages.pdf_text_layer(pdf)


def _configs_doc(content, configs, objs=None, extra=b'/Properties << /MC0 6 0 R >>'):
    """An /OCProperties whose /D is all ON, plus /Configs (pdfium may take a /View one)."""
    catalog = (b'<< /Type /Catalog /Pages 2 0 R /OCProperties << /OCGs [6 0 R] /D ' + ALL_ON
               + b' /Configs [' + configs + b'] >> >>')
    return _oc_doc(content, ALL_ON, {1: catalog, **(objs or {})}, extra)


class TheOptionalContentWhitelist(SimpleTestCase):
    def test_a_view_configuration_that_switches_the_layer_off(self):
        for configs in (b'<< /Intent /View /BaseState /OFF >>', b'<< /Intent /View /OFF [6 0 R] >>',
                        b'<< /OFF [6 0 R] >>'):
            with self.subTest(configs=configs):
                pdf = _configs_doc(MARKED, configs)
                self.assertIn(b'/Configs', pdf)
                self.assertIn('DISAHKAN', _raw_layer(pdf))
                pdf_pages._layer_memo_clear()
                self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_a_form_with_an_oc_entry_under_configs(self):
        form = _xobj(b'/Subtype /Form /OC 6 0 R', _show(SECRET.decode()))
        pdf = _configs_doc(b'/Fm1 Do', b'<< /Intent /View /OFF [6 0 R] >>', {7: form}, b'/XObject << /Fm1 7 0 R >>')
        self.assertIn('DISAHKAN', _raw_layer(pdf))
        pdf_pages._layer_memo_clear()
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_any_shape_outside_the_whitelist_hides_oc_marked_text(self):
        for default, ocg in ((b'<< /ON [6 0 R] /Locked [6 0 R] >>', None), (b'<< /ON [6 0 R] /Intent /View >>', None),
                             (b'<< /BaseState /Unchanged >>', None), (b'<< /ON [6 0 R] /OFF [7 0 R] >>', None),
                             (ALL_ON, b'<< /Type /OCG /Name (L) /Intent /View >>')):
            with self.subTest(default=default, ocg=ocg):
                objs = {6: ocg} if ocg else {}
                self.assertFalse(_reads(_oc_doc(MARKED, default, objs)))

    def test_the_corpus_shape_of_a_plain_layer_that_is_on_keeps_the_layer(self):
        # a real genuine document draws its text in a plain /OCG: /D holds /ON, an empty /OFF and /Order
        for default in (b'<< /ON [6 0 R] /OFF [] /Order [6 0 R] >>', b'<< /BaseState /ON /RBGroups [] >>'):
            with self.subTest(default=default):
                self.assertTrue(_reads(_oc_doc(MARKED, default)))


# ── What pdfium loads with a page ────────────────────────────────────────────────────────────────────────
def _flate(head, data):
    return _stream(head + b' /Filter /FlateDecode', zlib.compress(data))


def _type3(names, codes, proc, shared=False, font_extra=b'', encoding=b'/Type /Encoding'):
    """Page 1 shows ``codes`` character codes of a Type3 font whose /Differences name ``names`` glyphs (all one
    glyph when ``shared``), each glyph procedure ``proc`` (one compressed stream object per name)."""
    procs = b' '.join(b'/g%d %d 0 R' % (i, 7 + (0 if shared else i)) for i in range(names))
    diff = b' '.join(b'%d /g%d' % (c, 0 if shared else c % names) for c in range(codes))
    font = (b'<< /Type /Font /Subtype /Type3 /FontBBox [0 0 1000 1000] /FontMatrix [0.001 0 0 0.001 0 0] '
            b'/CharProcs << ' + procs + b' >> /Encoding << ' + encoding + b' /Differences [' + diff + b'] >> '
            b'/FirstChar 0 /LastChar %d /Widths [' % (codes - 1) + b'500 ' * codes + b'] ' + font_extra + b'>>')
    stream = _flate(b'<<', proc)
    objs = {6: font, **{7 + i: stream for i in range(1 if shared else names)}}
    shown = b'BT /T3 12 Tf 20 100 Td <' + b''.join(b'%02x' % c for c in range(codes)) + b'> Tj ET '
    return _doc(shown + TEXT, objs, page_res=b'/Resources << /Font << /F1 3 0 R /T3 6 0 R >> >>', filtered=True)


GLYPH = b'500 0 0 0 10 10 d1 0 0 m 10 0 l 10 10 l h f'
BOMB_GLYPH = b'500 0 0 0 10 10 d1 ' + b'0 0 m 1 1 l ' * 233_000 + b'h f'          # 2.8 MB


def _with(res, content, objs):
    return _doc(content + b' ' + TEXT, objs, page_res=b'/Resources << ' + FONT_RES + b' ' + res + b' >>', filtered=True)


BIG = b'\x00' * 10_000_000
CLOSED = {   # each pdfium would parse on load (or might); none of the 533 real PDFs uses the shape
    'sampled function': _with(b'/Shading << /Sh0 6 0 R >>', b'q /Sh0 sh Q', {
        6: b'<< /ShadingType 2 /ColorSpace /DeviceGray /Coords [0 0 1 0] /Function 7 0 R >>',
        7: _flate(b'<< /FunctionType 0 /Domain [0 1] /Range [0 1] /Size [2] /BitsPerSample 8', b'\x00\xff')}),
    'mesh shading': _with(b'/Shading << /Sh0 6 0 R >>', b'q /Sh0 sh Q', {
        6: _flate(b'<< /ShadingType 4 /ColorSpace /DeviceGray /BitsPerCoordinate 8 /BitsPerComponent 8 '
                  b'/BitsPerFlag 8 /Decode [0 1 0 1 0 1]', b'\x00' * 9)}),
    'font program past the stream cap': _doc(b'BT /F2 12 Tf 20 100 Td (AB) Tj ET ' + TEXT, {
        6: b'<< /Type /Font /Subtype /TrueType /BaseFont /X /FirstChar 65 /LastChar 66 /Widths [500 500] '
           b'/FontDescriptor 7 0 R >>',
        7: b'<< /Type /FontDescriptor /FontName /X /Flags 32 /FontBBox [0 0 1 1] /ItalicAngle 0 /Ascent 1 '
           b'/Descent 0 /CapHeight 1 /StemV 1 /FontFile2 8 0 R >>',
        8: _flate(b'<<', BIG)}, page_res=b'/Resources << /Font << /F1 3 0 R /F2 6 0 R >> >>', filtered=True),
    'font program not flate': _doc(b'BT /F2 12 Tf 20 100 Td (AB) Tj ET ' + TEXT, {
        6: b'<< /Type /Font /Subtype /TrueType /BaseFont /X /FirstChar 65 /LastChar 66 /Widths [500 500] '
           b'/FontDescriptor 7 0 R >>',
        7: b'<< /Type /FontDescriptor /FontName /X /Flags 32 /FontBBox [0 0 1 1] /ItalicAngle 0 /Ascent 1 '
           b'/Descent 0 /CapHeight 1 /StemV 1 /FontFile2 8 0 R >>',
        8: _stream(b'<< /Filter /ASCIIHexDecode', b'00>')}, page_res=b'/Resources << /Font << /F1 3 0 R /F2 6 0 R >> >>'),
    'embedded encoding CMap': _doc(b'BT /F2 12 Tf 20 100 Td <0041> Tj ET ' + TEXT, {
        6: b'<< /Type /Font /Subtype /Type0 /BaseFont /X /Encoding 7 0 R /DescendantFonts [8 0 R] >>',
        7: _stream(b'<< /Type /CMap /CMapName /X', b'begincmap endcmap'),
        8: b'<< /Type /Font /Subtype /CIDFontType2 /BaseFont /X /CIDSystemInfo << /Registry (A) /Ordering (B) '
           b'/Supplement 0 >> >>'}, page_res=b'/Resources << /Font << /F1 3 0 R /F2 6 0 R >> >>'),
    'ICC profile past the stream cap': _with(b'/ColorSpace << /CS0 6 0 R >>', b'/CS0 cs 0.5 0.5 0.5 sc 0 0 9 9 re f', {
        6: b'[/ICCBased 7 0 R]', 7: _flate(b'<< /N 3', BIG)}),
    'separation colour space': _with(b'/ColorSpace << /CS0 6 0 R >>', b'/CS0 cs 1 sc 0 0 9 9 re f', {
        6: b'[/Separation /Spot /DeviceGray << /FunctionType 2 /Domain [0 1] /C0 [1] /C1 [0] /N 1 >>]'}),
    'tiling cell past the stream cap': _with(b'/Pattern << /P0 6 0 R >>', b'/Pattern cs /P0 scn 0 0 300 200 re f', {
        6: _flate(b'<< /PatternType 1 /PaintType 1 /TilingType 1 /BBox [0 0 10 10] /XStep 10 /YStep 10 '
                  b'/Resources << >>', b'0 0 m 1 1 l S ' * 700_000)}),
    'soft mask past the stream cap': _with(b'/ExtGState << /GS0 6 0 R >>', b'/GS0 gs 0 0 300 200 re f', {
        6: b'<< /Type /ExtGState /SMask << /Type /Mask /S /Luminosity /G 7 0 R >> >>',
        7: _flate(b'<< /Type /XObject /Subtype /Form /BBox [0 0 300 200]', b'0 0 m 1 1 l S ' * 700_000)}),
    'graphics state with a transfer function': _with(b'/ExtGState << /GS0 6 0 R >>', b'/GS0 gs', {
        6: b'<< /Type /ExtGState /TR /Identity >>'}),
    'an inline image in a form the walk never reads': _with(b'/XObject << /Fm0 6 0 R >>', b'', {
        6: _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 1 1]', b'BI /W 1 /H 1 /BPC 8 /CS /G ID \x00 EI')}),
    'a glyph that calls a form': _type3(1, 1, GLYPH + b' /Fm0 Do'),
    'a glyph that shows text': _type3(1, 1, GLYPH + b' BT (A) Tj ET'),
    'a Type3 font with its own resources': _type3(1, 1, GLYPH, font_extra=b'/Resources << >> '),
    'a Type3 font with a base encoding': _type3(1, 1, GLYPH, encoding=b'/BaseEncoding /WinAnsiEncoding'),
}


class WhatPdfiumLoadsWithAPage(SimpleTestCase):
    def _hostile(self, pdf):
        """pypdf extracts the page (it never runs a glyph); the load check hides it before pdfium loads it."""
        with patch('apps.scholarship.pdfium_run.ask') as opened:
            t0 = time.perf_counter()
            self.assertFalse(_reads(pdf))
            self.assertEqual(''.join(pdf_pages.pdf_page_texts(pdf, 3)), '')
            self.assertFalse(pdf_pages.first_page_drawn(pdf))
            self.assertLess(time.perf_counter() - t0, 3.0)
        self.assertEqual(opened.call_count, 0)                   # no pdfium child loaded it

    def test_the_type3_glyph_bomb(self):
        # 120 glyph procedures of 2.8 MB each in a 670 KB file: pdfium took 13.5 s to load the page
        pdf = _type3(120, 120, BOMB_GLYPH)
        self.assertLess(len(pdf), 1_000_000)
        self._hostile(pdf)

    def test_one_glyph_named_by_256_codes_is_parsed_256_times(self):
        # a 10 KB file: pdfium parses the one 2.8 MB procedure for each code (9.7 s), so it is charged per code
        pdf = _type3(1, 256, BOMB_GLYPH, shared=True)
        self.assertLess(len(pdf), 20_000)
        self._hostile(pdf)

    def test_each_shape_outside_the_whitelist_is_hidden(self):
        for name, pdf in CLOSED.items():
            with self.subTest(name=name):
                self._hostile(pdf)

    def test_the_whitelisted_shapes_keep_the_layer(self):
        # the corpus's shapes: a small Type3 font, an ICC profile, an axial shading of exponential functions,
        # a soft mask, a huge image (pdfium decodes it only to paint: not charged)
        kept = {
            'type3': _type3(4, 40, GLYPH),
            'icc': _with(b'/ColorSpace << /CS0 6 0 R >>', b'/CS0 cs 0.5 0.5 0.5 sc 0 0 9 9 re f', {
                6: b'[/ICCBased 7 0 R]', 7: _flate(b'<< /N 3', b'\x00' * 3_144)}),
            'shading': _with(b'/Shading << /Sh0 6 0 R >>', b'q /Sh0 sh Q', {
                6: b'<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [0 0 1 0] /Function << /FunctionType 3 '
                   b'/Domain [0 1] /Bounds [] /Encode [0 1] /Functions [<< /FunctionType 2 /Domain [0 1] /N 1 >>] >> >>'}),
            'soft mask': _with(b'/ExtGState << /GS0 6 0 R >>', b'/GS0 gs 0 0 300 200 re f', {
                6: b'<< /Type /ExtGState /ca 0.5 /SMask << /Type /Mask /S /Luminosity /G 7 0 R >> >>',
                7: _flate(b'<< /Type /XObject /Subtype /Form /BBox [0 0 300 200]', b'0 0 m 1 1 l S')}),
            'image': _with(b'/XObject << /Im0 6 0 R >>', b'q 300 0 0 200 0 0 cm /Im0 Do Q', {
                6: _flate(b'<< /Type /XObject /Subtype /Image /Width 20000 /Height 20000 /ColorSpace /DeviceGray '
                          b'/BitsPerComponent 8', b'\x00' * 1_000)}),
        }
        for name, pdf in kept.items():
            with self.subTest(name=name):
                self.assertTrue(_reads(pdf))

    def test_load_check_charges_a_glyph_per_code(self):
        import io
        from pypdf import PdfReader
        from apps.scholarship.pdf_pdfium_load import MAX_LOAD_BYTES, load_check
        reader = PdfReader(io.BytesIO(_type3(1, 256, GLYPH, shared=True)))
        state = {}
        load_check(reader.pages[0], reader, state)
        self.assertEqual(list(state['sizes'].values()), [len(GLYPH)])
        self.assertEqual(MAX_LOAD_BYTES - state['bytes'], 256 * len(GLYPH))


class TheStringLength(SimpleTestCase):
    """pdfium keeps a string's first 32,767 bytes; pypdf all of it. Corpus max: 1,893."""

    def test_a_string_past_32767_bytes_is_hidden(self):
        # spaced, so no run of 1,024 bare bytes (a cap of its own) is what refuses them
        for show in (b'(' + b'A ' * 16_384 + b') Tj', b'<' + b'41 ' * 32_768 + b'> Tj'):
            with self.subTest(show=show[:3]):
                self.assertFalse(_reads(_doc(b'BT /F1 12 Tf 20 150 Td ' + show + b' ET ' + TEXT, filtered=True)))

    def test_a_string_under_the_cap_keeps_the_layer(self):
        # the cap is on the RAW string (never shorter than its decoded bytes): 32,000 bytes pass
        for show in (b'(' + b'A ' * 16_000 + b') Tj', b'<' + b'41 ' * 10_000 + b'> Tj'):
            with self.subTest(show=show[:3]):
                self.assertTrue(_reads(_doc(b'BT /F1 12 Tf 20 150 Td ' + show + b' ET ' + TEXT, filtered=True)))


class PdfiumOnlyInTheChild(SimpleTestCase):
    """Fix round 8: the web process never opens a PDF with pdfium; only `pdfium_worker` (a child) does."""

    def test_no_request_path_module_opens_or_imports_pdfium(self):
        from pathlib import Path
        root = Path(pdf_pages.__file__).resolve().parents[1]           # apps/
        offenders = [str(p.relative_to(root)) for p in root.rglob('*.py')
                     if any(k in p.read_text(encoding='utf-8', errors='replace')
                            for k in ('PdfDocument(', 'import pypdfium2', 'from pypdfium2'))
                     and p.name not in ('pdfium_worker.py', 'capture_ocr.py') and 'tests' not in p.parts]
        self.assertEqual(offenders, [])

    def test_threads_reading_at_once_get_the_same_answers(self):
        from apps.scholarship import pdfium_run
        calls = {'count': lambda: pdf_pages.pdf_page_count(DRAWN), 'r1': lambda: pdf_pages.pdf_first_page_png(DRAWN),
                 'words': lambda: spm_cert_parse._pdf_words(DRAWN)}
        alone = {}
        for k, f in calls.items():
            pdfium_run.memo_clear()
            alone[k] = f()
        pdfium_run.memo_clear()
        got, threads = [], [threading.Thread(target=lambda k=k: got.append((k, calls[k]()))) for k in list(calls) * 2]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(got), 6)
        for k, v in got:
            self.assertEqual(v, alone[k], k)
