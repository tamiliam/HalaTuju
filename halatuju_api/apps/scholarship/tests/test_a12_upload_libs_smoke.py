"""A1.2 smoke: the bumped upload libraries (Pillow, pillow-heif, pypdf) on a real HEIC, a real
multi-page PDF and a real JPEG, through the app's own helpers.

Everything is generated in memory and the storage / fetch edges are mocked. No Gemini, no Vision, no
network: this proves the libraries still decode and render, not what the models would read.
"""
import io

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from PIL import Image

from apps.scholarship.imaging import convert_heic_to_jpeg, is_heic
from apps.scholarship.pdf_pages import (
    pdf_first_page_png, pdf_page_count, pdf_page_pngs, pdf_page_texts, pdf_text_layer,
)

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def _text_pdf(pages):
    """A valid PDF with one text line per page (real text layer), built by hand."""
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>"}
    kids = []
    next_id = 4
    for text in pages:
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        kids.append(b"%d 0 R" % page_id)
        stream = b"BT /F1 24 Tf 72 700 Td (%s) Tj ET" % text.encode()
        objs[page_id] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                         b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % content_id)
        objs[content_id] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
    objs[2] = b"<< /Type /Pages /Kids [" + b" ".join(kids) + b"] /Count %d >>" % len(pages)
    objs[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    out = b"%PDF-1.4\n"
    offsets = {}
    for i in sorted(objs):
        offsets[i] = len(out)
        out += b"%d 0 obj\n" % i + objs[i] + b"\nendobj\n"
    xref = len(out)
    size = max(objs) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    out += b"".join(b"%010d 00000 n \n" % offsets[i] for i in range(1, size))
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (size, xref)
    return out


def _jpeg_bytes():
    buf = io.BytesIO()
    Image.new('RGB', (64, 48), (200, 30, 30)).save(buf, format='JPEG')
    return buf.getvalue()


class TestPdfLibsSmoke(SimpleTestCase):
    def setUp(self):
        self.pdf = _text_pdf(['Page one KEPUTUSAN', 'Page two SPM', 'Page three AKHIR'])

    def test_multi_page_pdf_counts_renders_and_reads_text(self):
        self.assertEqual(pdf_page_count(self.pdf), 3)
        pngs = pdf_page_pngs(self.pdf, 5)
        self.assertEqual(len(pngs), 3)
        self.assertTrue(all(p.startswith(_PNG_MAGIC) for p in pngs))
        self.assertTrue(pdf_first_page_png(self.pdf).startswith(_PNG_MAGIC))
        texts = pdf_page_texts(self.pdf, 5)
        self.assertEqual(len(texts), 3)
        self.assertIn('KEPUTUSAN', texts[0])
        self.assertIn('AKHIR', pdf_text_layer(self.pdf))

    def test_a_garbage_pdf_degrades_to_nothing(self):
        junk = b'%PDF-1.4 not really'
        self.assertEqual(pdf_text_layer(junk), '')
        self.assertEqual(pdf_page_pngs(junk, 3), [])


class TestJpegSmoke(SimpleTestCase):
    def test_jpeg_is_not_heic_and_decodes(self):
        doc = SimpleNamespace(content_type='image/jpeg', original_filename='a.jpg')
        self.assertFalse(is_heic(doc))
        img = Image.open(io.BytesIO(_jpeg_bytes()))
        self.assertEqual(img.size, (64, 48))
        self.assertEqual(img.convert('RGB').getpixel((0, 0))[0] > 150, True)


class TestRealHeicConversion(TestCase):
    """A real HEIC, encoded by pillow-heif itself, converted by the app's own helper."""

    def test_real_heic_converts_to_a_real_jpeg(self):
        import pillow_heif
        from apps.scholarship.models import ApplicantDocument
        from apps.scholarship.tests.factories import make_application

        pillow_heif.register_heif_opener()
        buf = io.BytesIO()
        Image.new('RGB', (80, 60), (10, 120, 200)).save(buf, format='HEIF')
        heic = buf.getvalue()

        app = make_application('submitted')
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='photo', storage_path='x/photo/a12',
            original_filename='IMG_9.HEIC', content_type='image/heic', size=len(heic))

        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=heic), \
                patch('apps.scholarship.storage.upload_object', return_value=True) as up:
            self.assertTrue(convert_heic_to_jpeg(doc))

        jpeg = up.call_args[0][1]
        self.assertTrue(jpeg.startswith(b'\xff\xd8'))
        self.assertEqual(Image.open(io.BytesIO(jpeg)).size, (80, 60))
        doc.refresh_from_db()
        self.assertEqual(doc.content_type, 'image/jpeg')
        self.assertTrue(doc.original_filename.endswith('.jpg'))
