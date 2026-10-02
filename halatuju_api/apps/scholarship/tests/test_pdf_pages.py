"""Page 1 of a PDF renders within a pixel budget (2026-10-02).

An unbounded 200 DPI raster of one scan-to-PDF with a huge page box asked for more than 2 GiB and
killed the api instance three hours running. Real PDFs, generated here, through real pypdfium2.
"""
import io

from django.test import SimpleTestCase
from PIL import Image

from apps.scholarship.pdf_pages import (
    MAX_PAGE_SIDE_PT, MAX_RASTER_SIDE_PX, RASTER_DPI, pdf_first_page_png, raster_scale,
)

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def _blank_pdf(width_pt, height_pt):
    """A minimal, valid one-page PDF whose page box is ``width_pt`` x ``height_pt`` points."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] >>" % (width_pt, height_pt),
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return out


def _png_size(png):
    return Image.open(io.BytesIO(png)).size


class TestRasterBudget(SimpleTestCase):
    def test_an_a4_page_still_renders_at_200_dpi(self):
        png = pdf_first_page_png(_blank_pdf(595, 842))
        self.assertTrue(png.startswith(_PNG_MAGIC))
        w, h = _png_size(png)
        self.assertAlmostEqual(w, 595 * RASTER_DPI / 72, delta=2)    # ~1653
        self.assertAlmostEqual(h, 842 * RASTER_DPI / 72, delta=2)    # ~2339

    def test_a_huge_page_renders_within_the_cap_and_keeps_its_shape(self):
        # 3000 x 2000 pt at 200 DPI would be 8333 x 5556 px (46 MP); the cap brings it to 4000 x 2667.
        png = pdf_first_page_png(_blank_pdf(3000, 2000))
        self.assertTrue(png.startswith(_PNG_MAGIC))
        w, h = _png_size(png)
        self.assertLessEqual(max(w, h), MAX_RASTER_SIDE_PX)
        self.assertGreaterEqual(w, MAX_RASTER_SIDE_PX - 2)
        self.assertAlmostEqual(w / h, 1.5, delta=0.01)

    def test_an_absurd_page_box_is_refused_not_rendered(self):
        with self.assertLogs('apps.scholarship.pdf_pages', level='WARNING') as logs:
            self.assertIsNone(pdf_first_page_png(_blank_pdf(MAX_PAGE_SIDE_PT + 1000, 842)))
        self.assertIn('refused', logs.output[0])

    def test_raster_scale(self):
        self.assertEqual(raster_scale(595, 842), RASTER_DPI / 72.0)
        self.assertAlmostEqual(raster_scale(8000, 100) * 8000, MAX_RASTER_SIDE_PX)
        self.assertIsNone(raster_scale(0, 842))
        self.assertIsNone(raster_scale(842, MAX_PAGE_SIDE_PT + 1))
