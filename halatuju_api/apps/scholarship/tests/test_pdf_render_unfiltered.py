"""The render pre-filter reads a page whose content stream has no filter (2026-11-21).

pypdf drops /Length from a stream's dictionary, so a content stream with no /Filter is an EMPTY (falsy) dictionary.
`page_cost` tested it by truthiness and skipped the whole page walk: no image, JPX, JBIG2 or other cap applied (an
adversarial review's probe passed the gate and was killed by the Linux child's 20 s limit). Present since
c1d93982e7. Synthetic PDFs only: the JPX images are headers built in the test, never encoded.
"""
from django.test import SimpleTestCase

from apps.scholarship import pdf_pages, pdf_render_check
from apps.scholarship.tests.test_ocr_visible_paths import _doc
from apps.scholarship.tests.test_pdf_render_check import A4, FULL_PAGE, _jpeg
from apps.scholarship.tests.test_pdf_render_jpx import _codestream, _jbig2, _jpx


def _unfiltered_a4(content, res=b'', objs=None):
    """An A4 page whose ONE content stream is stored as is: its dictionary holds only /Length."""
    pdf = _doc(content, objs, page_res=b'/Resources << ' + res + b' >>', filtered=False)
    return pdf.replace(b'/MediaBox [0 0 300 200] ', A4)


def _drawing(img, objs=None):
    """An unfiltered A4 page drawing the image object 6 full page."""
    return _unfiltered_a4(b'q ' + FULL_PAGE + b'/Im0 Do Q', b'/XObject << /Im0 6 0 R >>', {6: img, **(objs or {})})


def _verdict(pdf):
    return pdf_render_check.render_refusal(pdf, lambda n: range(min(n, 30)))[1]


class AnUnfilteredContentStream(SimpleTestCase):
    def test_the_content_stream_really_is_an_empty_dictionary_to_pypdf(self):
        """The shape the hole needed: if pypdf ever keeps /Length, these tests still pass, but say why."""
        reader = pdf_pages._open_pdf(_unfiltered_a4(b'0 0 10 10 re f'))
        self.assertEqual(dict(reader.pages[0]['/Contents'].get_object()), {})

    def test_a_large_jpx_image_is_refused_by_the_jpx_work_cap(self):
        """The review's probe, one page: a 4890 x 4890 16-bit grey codestream (work 47.8 million) under a
        1600 x 2260 dictionary."""
        img = _jpx(1600, 2260, _codestream(4890, 4890, 1, 16, 0), cs=b'/DeviceGray')
        self.assertEqual(_verdict(_drawing(img)), 'OverBudget: past the render jpx_work cap')

    def test_a_jbig2_image_is_refused_by_the_whitelist(self):
        self.assertEqual(_verdict(_drawing(_jbig2(800, 600))),
                         "Refused: an image filter outside the whitelist ('/JBIG2Decode')")

    def test_a_page_past_the_paint_cap_is_refused(self):
        """Not only images: 20,000 full-page fills are charged from an unfiltered stream too."""
        self.assertEqual(_verdict(_unfiltered_a4(b'0 0 595 842 re f\n' * 20_000)),
                         'OverBudget: past the render paint_px cap')

    def test_a_genuine_letter_with_an_unfiltered_stream_passes_and_is_charged(self):
        """A photo of the letter (1240 x 1754 JPEG, 150 DPI A4) under its text: it passes, its cost is the
        walk's (it was all zero when the walk was skipped), and pdfium renders it."""
        content = b'q ' + FULL_PAGE + b'/Im0 Do Q BT /F1 12 Tf 72 760 Td (SURAT TAWARAN) Tj ET'
        pdf = _unfiltered_a4(content, b'/XObject << /Im0 6 0 R >> /Font << /F1 3 0 R >>', {6: _jpeg(1240, 1754)})
        self.assertIsNone(_verdict(pdf))
        reader = pdf_pages._open_pdf(pdf)
        cost = pdf_render_check.page_cost(reader.pages[0], reader)
        self.assertEqual(cost['image_bytes'], 1240 * 1754 * 3)
        self.assertEqual(cost['ops'], 9)
        self.assertTrue(pdf_pages.pdf_first_page_png(pdf).startswith(b'\x89PNG'))
