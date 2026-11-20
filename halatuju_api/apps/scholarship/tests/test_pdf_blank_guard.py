"""2026-11-21: a page that draws a JPEG 2000 image but renders PURE white is a failed read (`pdfium_worker.blank_render`).

Under the Linux child's memory cap pdfium failed to decode an A4 400 dpi colour JPX scan at 1:7 (6.6 MB) and drew
nothing, with no error: the page came back mean 255, spread 0, and went to the AI read as a white page. That full-size
case was measured by hand in the Linux child (the hand-back of this change). Here a JPX codestream cut in half stands in
for it: pdfium cannot decode it either and draws the same pure-white page, so the guard is pinned in CI on every
machine. The genuine near-blank pages (a text page, an empty page, a scanned blank back page, a light watermark, a small
logo, a signature, a truly white JPX scan) must still render. Synthetic files only.
"""
import io
import zlib

from django.test import SimpleTestCase

from apps.scholarship import pdf_pages, pdfium_worker
from apps.scholarship.tests.test_ocr_visible import DRAWN, SCANNED, _stream
from apps.scholarship.tests.test_pdf_render_check import FULL_PAGE, _a4
from apps.scholarship.tests.test_pdfium_child import _fresh

HEAD = b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB /BitsPerComponent 8 '


def _noise(w, h, mean, spread, seed=0):
    import numpy as np
    from PIL import Image
    pixels = np.random.default_rng(seed).normal(mean, spread, (h, w, 3)).clip(0, 255).astype(np.uint8)
    return Image.fromarray(pixels, 'RGB')


def _jpx(im, cut=False, **kw):
    """``im`` as a /JPXDecode image XObject; ``cut``: only the first half of its codestream, which pdfium cannot
    decode and draws as nothing (the white page an out-of-memory decode gives)."""
    buf = io.BytesIO()
    im.save(buf, 'JPEG2000', **kw)
    data = buf.getvalue()
    return _stream(HEAD % im.size + b'/Filter /JPXDecode', data[:len(data) // 2] if cut else data)


def _flate(im):
    return _stream(HEAD % im.size + b'/Filter /FlateDecode', zlib.compress(im.convert('RGB').tobytes()))


def _jpeg(im):
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=85)
    return _stream(HEAD % im.size + b'/Filter /DCTDecode', buf.getvalue())


def _page(image, place=FULL_PAGE):
    """A one-page A4 PDF drawing ``image`` at ``place`` (a ``cm`` matrix)."""
    return _a4(b'q ' + place + b'/Im0 Do Q', b'/XObject << /Im0 6 0 R >>', {6: image})


def _in_form(image):
    """A one-page A4 PDF drawing ``image`` full page from inside a form XObject."""
    form = _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 595 842] /Resources << /XObject << /Im0 7 0 R >> >>',
                   b'q ' + FULL_PAGE + b'/Im0 Do Q')
    return _a4(b'q /Fm0 Do Q', b'/XObject << /Fm0 6 0 R >>', {6: form, 7: image})


def _two_pages(first, second):
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    for one in (first, second):
        writer.add_page(PdfReader(io.BytesIO(one)).pages[0])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


#: A scan whose JPX data pdfium cannot decode: 300 x 400 px of noise, 188 KB of its 376 KB codestream kept.
FAILED_SCAN = _page(_jpx(_noise(300, 400, 120, 60), cut=True))
#: A good scanned page (baseline JPEG), for a letter whose page 2 fails.
GOOD_SCAN = _page(_jpeg(_noise(300, 400, 200, 40)))


def _stats(png):
    from PIL import Image, ImageStat
    im = Image.open(io.BytesIO(png)).convert('L')
    return ImageStat.Stat(im).extrema[0]


class TheDetector(SimpleTestCase):
    def test_pure_white_is_every_pixel_255_in_every_colour_band(self):
        from PIL import Image
        white = Image.new('RGB', (40, 30), (255, 255, 255))
        self.assertTrue(pdfium_worker._pure_white(white))
        self.assertTrue(pdfium_worker._pure_white(Image.new('L', (40, 30), 255)))
        self.assertTrue(pdfium_worker._pure_white(Image.new('RGBA', (40, 30), (255, 255, 255, 0))))    # alpha ignored
        speck = white.copy()
        speck.putpixel((39, 29), (255, 254, 255))                   # one band one level off: not pure white
        self.assertFalse(pdfium_worker._pure_white(speck))

    def test_a_dense_jpx_is_found_on_the_page_or_inside_a_form(self):
        import pypdfium2 as pdfium
        image = _jpx(_noise(300, 400, 120, 60))
        for pdf in (_page(image), _in_form(image)):
            doc = pdfium.PdfDocument(pdf)
            try:
                self.assertTrue(pdfium_worker.draws_dense_jpx(doc[0]))
            finally:
                doc.close()

    def test_a_white_jpx_a_small_jpx_and_other_images_are_not_dense(self):
        import pypdfium2 as pdfium
        from PIL import Image
        for label, pdf in (('white jpx', _page(_jpx(Image.new('RGB', (900, 1200), (255, 255, 255))))),
                           ('tiled white jpx', _page(_jpx(Image.new('RGB', (900, 1200), (255, 255, 255)),
                                                          tile_size=(128, 128), num_resolutions=4))),
                           ('small jpx', _page(_jpx(_noise(60, 40, 120, 60)))),     # under the 16 KiB floor
                           ('jpeg', GOOD_SCAN), ('flate', _page(_flate(_noise(300, 400, 120, 60)))),
                           ('text', DRAWN), ('empty', SCANNED)):
            with self.subTest(label):
                doc = pdfium.PdfDocument(pdf)
                try:
                    self.assertFalse(pdfium_worker.draws_dense_jpx(doc[0]))
                finally:
                    doc.close()


class APageThatRendersWhite(SimpleTestCase):
    """Through the real pdfium child: the failed decode is no image, logged with the reason."""

    def setUp(self):
        _fresh()
        self.addCleanup(_fresh)

    def test_page_one_is_no_page_on_every_render_path(self):
        with self.assertLogs('apps.scholarship.pdf_pages', 'WARNING') as logs:
            self.assertEqual(pdf_pages.pdf_page_pngs(FAILED_SCAN, 3), [])
            self.assertIsNone(pdf_pages.pdf_first_page_png(FAILED_SCAN))
            self.assertIsNone(pdf_pages.pdf_pages_png(FAILED_SCAN))
        said = '\n'.join(logs.output)
        self.assertIn('stopped on page 1: ' + pdfium_worker.BLANK_STOP, said)
        self.assertIn('stacked rasterise stopped: ' + pdfium_worker.BLANK_STOP, said)

    def test_the_same_from_inside_a_form(self):
        self.assertEqual(pdf_pages.pdf_page_pngs(_in_form(_jpx(_noise(300, 400, 120, 60), cut=True)), 3), [])

    def test_a_failed_page_two_keeps_page_one_and_the_stack_is_not_made(self):
        letter = _two_pages(GOOD_SCAN, FAILED_SCAN)
        pngs = pdf_pages.pdf_page_pngs(letter, 3)
        self.assertEqual(len(pngs), 1)
        self.assertLess(_stats(pngs[0])[0], 255)                    # page 1, the good scan
        self.assertIsNone(pdf_pages.pdf_pages_png(letter))


class GenuineNearBlankPages(SimpleTestCase):
    """Pages that are (nearly) blank on purpose still render, on every path."""

    def setUp(self):
        _fresh()
        self.addCleanup(_fresh)

    def _renders(self, pdf, white):
        _fresh()
        pngs = pdf_pages.pdf_page_pngs(pdf, 3)
        self.assertEqual(len(pngs), 1)
        self.assertEqual(pngs[0], pdf_pages.pdf_first_page_png(pdf))
        self.assertIsNotNone(pdf_pages.pdf_pages_png(pdf))
        self.assertEqual(_stats(pngs[0]) == (255, 255), white)

    def test_a_text_page_and_an_empty_page(self):
        self._renders(DRAWN, white=False)
        self._renders(SCANNED, white=True)                          # white, but draws no image

    def test_a_scanned_blank_back_page_with_scanner_noise(self):
        for label, encode in (('jpx', _jpx), ('jpeg', _jpeg)):
            with self.subTest(label):
                self._renders(_page(encode(_noise(600, 840, 250, 3))), white=False)

    def test_a_light_watermark_a_small_logo_and_a_signature_alone(self):
        from PIL import Image, ImageDraw
        watermark = Image.new('RGB', (500, 500), (255, 255, 255))
        ImageDraw.Draw(watermark).ellipse((50, 50, 450, 450), outline=(236, 236, 240), width=30)
        logo = Image.new('RGB', (160, 160), (255, 255, 255))
        ImageDraw.Draw(logo).rectangle((20, 20, 140, 140), fill=(30, 70, 160))
        signature = Image.new('RGB', (400, 120), (255, 255, 255))
        ImageDraw.Draw(signature).line([(10, 90), (90, 20), (170, 100), (260, 30), (390, 80)], fill=(20, 20, 60), width=4)
        for label, image, place in (('watermark', watermark, b'400 0 0 400 97 221 cm '),
                                    ('logo', logo, b'60 0 0 60 40 760 cm '),
                                    ('signature', signature, b'150 0 0 45 380 90 cm ')):
            for encoding, encode in (('jpx', _jpx), ('flate', _flate)):
                with self.subTest(label, encoding=encoding):
                    self._renders(_page(encode(image), place), white=False)

    def test_a_truly_white_jpx_scan_renders_white_and_is_kept(self):
        # a scanner's background removal can make a blank back page exactly white; its codestream is tiny
        from PIL import Image
        self._renders(_page(_jpx(Image.new('RGB', (900, 1270), (255, 255, 255)))), white=True)
