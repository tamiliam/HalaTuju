"""S-visible fix round 7: a page's render cost is bounded BEFORE pdfium renders it (under the one pdfium lock).

Each hostile page below stalled a pdfium render for seconds to minutes; each must now be refused in under 3 s,
land on the upload's existing "cannot read" path, and a real-shaped phone-photo PDF must still render.
"""
import io
import time
import zlib
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import pdf_pages, pdf_render_check, vision
from apps.scholarship.read_errors import is_ic_decode_error
from apps.scholarship.tests.test_ocr_visible import _stream
from apps.scholarship.tests.test_ocr_visible_paths import _doc

A4 = b'/MediaBox [0 0 595 842] '
FULL_PAGE = b'595 0 0 842 0 0 cm '


def _a4(content, res=b'', objs=None, box=A4):
    return _doc(content, objs, page_res=b'/Resources << ' + res + b' >>', filtered=True).replace(
        b'/MediaBox [0 0 300 200] ', box)


def _image(w, h, extra=b'', data=b'\x00' * 64, cs=b'/DeviceRGB'):
    """An image XObject. The check reads only its dictionary, so a hostile one needs no real pixel data."""
    return _stream(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace ' % (w, h) + cs
                   + b' /BitsPerComponent 8 /Filter /FlateDecode ' + extra, zlib.compress(data))


def _jpeg(w, h):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (w, h), (200, 190, 170)).save(buf, format='JPEG', quality=70)
    return _stream(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB '
                   b'/BitsPerComponent 8 /Filter /DCTDecode' % (w, h), buf.getvalue())


def _tiling(bbox, step, matrix=b'1 0 0 1 0 0'):
    return _stream(b'<< /PatternType 1 /PaintType 1 /TilingType 1 /BBox [0 0 %d %d] /XStep %s /YStep %s '
                   % (bbox, bbox, step, step) + b'/Matrix [' + matrix + b'] /Resources << >>', b'0 0 1 1 re f')


def _pattern_fill(pattern):
    return _a4(b'/Pattern cs /P0 scn 0 0 595 842 re f', b'/Pattern << /P0 6 0 R >>', {6: pattern})


def _type3(glyph_ops):
    """A Type 3 font (round 6's load shape: no /Resources, /Differences only) whose one glyph draws a path."""
    curves = b'0 0 m ' + b'1000 1000 0 1000 1000 0 c ' * glyph_ops + b'f'
    return {6: b'<< /Type /Font /Subtype /Type3 /FontBBox [0 0 1000 1000] /FontMatrix [0.001 0 0 0.001 0 0] '
               b'/CharProcs << /a 7 0 R >> /Encoding << /Type /Encoding /Differences [87 /a] >> /FirstChar 87 '
               b'/LastChar 87 /Widths [1000] >>',
            7: _stream(b'<<', b'1000 0 0 0 1000 1000 d1 ' + curves)}


#: A scanner app's PDF: an A4 photo of the page (3000 x 4000 JPEG) drawn full page, its OCR text invisible.
PHOTO = _a4(b'q ' + FULL_PAGE + b'/Im0 Do Q BT /F1 12 Tf 3 Tr 20 150 Td (CONTOH) Tj ET',
            b'/XObject << /Im0 6 0 R >> /Font << /F1 3 0 R >>', {6: _jpeg(3000, 4000)})

HOSTILE = {
    'a 20,000 x 20,000 image': _a4(FULL_PAGE + b'/Im0 Do', b'/XObject << /Im0 6 0 R >>', {6: _image(20000, 20000)}),
    'a huge tiling cell': _pattern_fill(_tiling(5000, b'5000')),
    'a tiny tiling step': _pattern_fill(_tiling(1, b'0.01')),
    'a huge image soft mask': _a4(FULL_PAGE + b'/Im0 Do', b'/XObject << /Im0 6 0 R >>',
                                  {6: _image(100, 100, b'/SMask 7 0 R'),
                                   7: _image(20000, 20000, cs=b'/DeviceGray')}),
    'a soft mask repainted by every fill': _a4(b'/G0 gs ' + b'0 0 595 842 re f\n' * 60,
                                               b'/ExtGState << /G0 << /SMask << /S /Luminosity /G 6 0 R >> >> >>',
                                               {6: _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 595 842] '
                                                           b'/Group << /S /Transparency >>',
                                                           b'0 0 595 842 re f\n' * 60)}),
    'a huge 1-bit image (small in bytes, not in pixels)': _a4(
        FULL_PAGE + b'/Im0 Do', b'/XObject << /Im0 6 0 R >>',
        {6: _image(20000, 20000).replace(b'/ColorSpace /DeviceRGB /BitsPerComponent 8',
                                         b'/ImageMask true /BitsPerComponent 1')}),
    'blended fills over the blend cap': _a4(b'/G0 gs 0.5 g ' + b'0 0 595 842 re f\n' * 20,
                                            b'/ExtGState << /G0 << /BM /Multiply >> >>'),
    'Type 3 glyphs over the glyph cap': _a4(b'BT /T3 12 Tf 0 400 Td (' + b'W' * 5000 + b') Tj ET',
                                            b'/Font << /T3 6 0 R >>', _type3(180)),
    'a shading outside the whitelist': _a4(b'/Sh0 sh', b'/Shading << /Sh0 << /ShadingType 3 /ColorSpace /DeviceGray '
                                           b'/Coords [0 0 0 300 400 600] /Function << /FunctionType 2 /Domain [0 1] '
                                           b'/N 1 >> >> >>'),
    'many medium images over the page cap': _a4(FULL_PAGE + b'/Im0 Do\n' * 12, b'/XObject << /Im0 6 0 R >>',
                                                {6: _image(3000, 3000)}),
    'full-page fills over the paint cap': _a4(b'0 0 595 842 re f\n' * 20000),
    'wide strokes over the paint cap': _a4(b'800 w ' + b'0 421 m 595 421 l S\n' * 20000),
    'small-image draws over the paint cap': _a4(FULL_PAGE + b'/Im0 Do\n' * 2000, b'/XObject << /Im0 6 0 R >>',
                                                {6: _image(100, 100)}),
    'a scale bomb (a page box past the render bounds)': _a4(b'0 0 1 1 re f', box=b'/MediaBox [0 0 1 1000000] '),
    'a scale bomb (a form scaled a million times)': _a4(b'1000000 0 0 1000000 0 0 cm /Fm0 Do',
                                                        b'/XObject << /Fm0 6 0 R >>',
                                                        {6: _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 1 1]',
                                                                    b'0 0 1 1 re f\n' * 200)}),
    'an inline image': _a4(b'q 10 0 0 10 0 0 cm BI /W 1 /H 1 /CS /G /BPC 8 ID \x00\nEI Q\n'),
    'an image filter outside the whitelist': _a4(FULL_PAGE + b'/Im0 Do', b'/XObject << /Im0 6 0 R >>',
                                                 {6: _image(10, 10).replace(b'/FlateDecode', b'/ASCIIHexDecode')}),
}


class TheRenderCheck(SimpleTestCase):
    def test_each_hostile_page_is_refused_fast(self):
        for name, pdf in HOSTILE.items():
            with self.subTest(name):
                start = time.perf_counter()
                png = pdf_pages.pdf_first_page_png(pdf)
                self.assertIsNone(png)
                self.assertLess(time.perf_counter() - start, 3.0)
                self.assertEqual(pdf_pages.pdf_page_pngs(pdf, 3), [])
                self.assertIsNone(pdf_pages.pdf_pages_png(pdf))

    def test_a_real_shaped_photo_pdf_still_renders(self):
        self.assertIsNone(pdf_render_check.render_refusal(PHOTO, lambda n: [0])[1])
        png = pdf_pages.pdf_first_page_png(PHOTO)
        self.assertTrue(png and png.startswith(b'\x89PNG'))
        self.assertEqual(len(pdf_pages.pdf_page_pngs(PHOTO, 3)), 1)
        self.assertIsNotNone(pdf_pages.pdf_pages_png(PHOTO))

    def test_each_hostile_page_is_refused_by_the_render_check(self):
        """Refused by THIS check (not by a parse error on the way), so each case pins the cap it names."""
        for name, pdf in HOSTILE.items():
            with self.subTest(name):
                self.assertIsNotNone(pdf_render_check.render_refusal(pdf, lambda n: [0])[1])
                with patch.object(pdf_render_check, 'page_cost'):
                    if name not in ('a scale bomb (a page box past the render bounds)', 'an inline image'):
                        self.assertIsNone(pdf_render_check.render_refusal(pdf, lambda n: [0])[1])

    def test_real_shaped_type3_text_and_a_few_blended_paints_still_render(self):
        for pdf in (_a4(b'BT /T3 12 Tf 0 400 Td (' + b'W' * 200 + b') Tj ET', b'/Font << /T3 6 0 R >>', _type3(40)),
                    _a4(b'/G0 gs 0.5 g 0 0 595 842 re f', b'/ExtGState << /G0 << /BM /Multiply >> >>')):
            self.assertIsNone(pdf_render_check.render_refusal(pdf, lambda n: [0])[1])
            self.assertTrue(pdf_pages.pdf_first_page_png(pdf))

    def test_the_render_path_runs_the_pdfium_load_check(self):
        with patch('apps.scholarship.pdf_pdfium_load.load_check', side_effect=ValueError('outside')) as load:
            self.assertIsNone(pdf_pages.pdf_first_page_png(PHOTO))
        load.assert_called()

    def test_a_page_count_pdfium_reads_differently_is_refused(self):
        with patch.object(pdf_render_check, 'render_refusal', return_value=(2, None)):
            self.assertIsNone(pdf_pages.pdf_first_page_png(PHOTO))

    def test_a_refused_page_lands_on_the_cannot_read_path(self):
        pdf = HOSTILE['a 20,000 x 20,000 image']
        with patch.object(vision, '_vision_document_text', side_effect=AssertionError('no Vision call')):
            self.assertEqual(vision.extract_text(pdf, 'application/pdf'), {'text': '', 'error': 'Bad image data.'})
            ic = vision.extract_mykad(pdf, 'application/pdf')
        self.assertEqual(ic['error'], 'Bad image data.')
        self.assertTrue(is_ic_decode_error(ic['error']))
        self.assertEqual(vision._vision_words(pdf, 'application/pdf')['error'], 'no image')
