"""Tests for PDF document intake (document-intake hardening).

The digital-PDF path is exercised end-to-end with a REAL generated text PDF (no
Vision call). The scanned-PDF → Vision path and the image path mock the Vision
client only (mirrors the project's "never call Vision in tests" rule).
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.services import _ic_identity_blockers, _is_ic_decode_error
from apps.scholarship.views import _is_allowed_upload
from apps.scholarship.vision import (
    _is_pdf, _pdf_first_page_png, _pdf_text_layer, extract_mykad, extract_text,
)

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def _make_text_pdf(text='HELLO GRED A'):
    """A minimal, valid one-page PDF with a real text layer (correct xref)."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    ]
    stream = b"BT /F1 24 Tf 36 100 Td (" + text.encode() + b") Tj ET"
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += b"trailer\n<< /Size " + str(len(objs) + 1).encode() + b" /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    return out


class TestPdfHelpers(SimpleTestCase):
    def test_is_pdf(self):
        self.assertTrue(_is_pdf('application/pdf', b''))
        self.assertTrue(_is_pdf('', b'%PDF-1.7 ...'))
        self.assertTrue(_is_pdf('application/pdf; charset=binary', b'x'))
        self.assertFalse(_is_pdf('image/jpeg', b'\xff\xd8\xff'))
        self.assertFalse(_is_pdf('', b'\xff\xd8\xff'))

    def test_text_layer_reads_digital_pdf(self):
        self.assertIn('GRED A', _pdf_text_layer(_make_text_pdf('RESULT GRED A')))

    def test_text_layer_empty_on_garbage(self):
        self.assertEqual(_pdf_text_layer(b'not a pdf'), '')

    def test_rasterise_returns_png(self):
        img = _pdf_first_page_png(_make_text_pdf())
        self.assertIsNotNone(img)
        self.assertTrue(img.startswith(_PNG_MAGIC))


class TestExtractDispatch(SimpleTestCase):
    def test_digital_pdf_uses_text_layer_no_vision(self):
        # Realistic length (> _MIN_PDF_TEXT) so it's treated as a digital PDF.
        with patch('apps.scholarship.vision._vision_document_text') as seam:
            out = extract_text(_make_text_pdf('SIJIL PELAJARAN MALAYSIA 2025 GRED A'), 'application/pdf')
        self.assertIsNone(out['error'])
        self.assertIn('GRED A', out['text'])
        seam.assert_not_called()  # digital PDF → no billable Vision call

    @patch('apps.scholarship.vision._pdf_first_page_png', return_value=b'FAKEPNG')
    @patch('apps.scholarship.vision._pdf_text_layer', return_value='')
    @patch('apps.scholarship.vision._vision_document_text',
           return_value={'text': 'OCR FROM SCAN', 'error': None})
    def test_scanned_pdf_rasterises_to_vision(self, seam, _t, _r):
        out = extract_text(b'%PDF- scanned', 'application/pdf')
        self.assertEqual(out['text'], 'OCR FROM SCAN')
        seam.assert_called_once_with(b'FAKEPNG')  # the rasterised page reached Vision

    @patch('apps.scholarship.vision._vision_document_text',
           return_value={'text': 'IMG TEXT', 'error': None})
    def test_image_path_unchanged(self, seam):
        out = extract_text(b'\xff\xd8\xff imagebytes', 'image/jpeg')
        self.assertEqual(out['text'], 'IMG TEXT')
        seam.assert_called_once()

    @patch('apps.scholarship.vision._pdf_first_page_png', return_value=b'FAKEPNG')
    @patch('apps.scholarship.vision._vision_document_text',
           return_value={'text': 'WARGANEGARA\n880101-10-1234\nALI BIN ABU', 'error': None})
    def test_mykad_pdf_rasterises_and_parses(self, seam, _r):
        out = extract_mykad(b'%PDF- scanned ic', 'application/pdf')
        self.assertEqual(out['nric'], '880101-10-1234')
        self.assertIsNone(out['error'])
        seam.assert_called_once_with(b'FAKEPNG')

    @patch('apps.scholarship.vision._pdf_first_page_png', return_value=None)
    @patch('apps.scholarship.vision._pdf_text_layer', return_value='')
    def test_unrasterisable_pdf_is_bad_image_data(self, _t, _r):
        self.assertEqual(extract_text(b'%PDF-', 'application/pdf')['error'], 'Bad image data.')


class TestAllowlist(SimpleTestCase):
    def test_images_and_pdf_allowed(self):
        self.assertTrue(_is_allowed_upload('image/jpeg', 'ic.jpg'))
        self.assertTrue(_is_allowed_upload('application/pdf', 'ic.pdf'))
        self.assertTrue(_is_allowed_upload('', 'scan.PDF'))          # by extension
        self.assertTrue(_is_allowed_upload('image/png', ''))

    def test_video_and_junk_rejected(self):
        self.assertFalse(_is_allowed_upload('video/mp4', 'clip.mp4'))
        self.assertFalse(_is_allowed_upload('application/octet-stream', 'thing.exe'))
        self.assertFalse(_is_allowed_upload('', ''))


class TestDecodeErrorClassification(SimpleTestCase):
    def test_decode_errors(self):
        for e in ('Bad image data.', 'empty image', 'could not fetch image'):
            self.assertTrue(_is_ic_decode_error(e), e)

    def test_service_errors(self):
        for e in ('Vision API quota exceeded', 'AI module not installed', 'connection reset'):
            self.assertFalse(_is_ic_decode_error(e), e)


class TestIcUnreadableRemap(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app_with_ic(self, vision_error):
        p = StudentProfile.objects.create(supabase_user_id=f'pdf-{vision_error}',
                                          name='ALI', nric='880101-10-1234')
        app = ScholarshipApplication.objects.create(cohort=self.cohort, profile=p, status='shortlisted')
        ApplicantDocument.objects.create(application=app, doc_type='ic', storage_path='x',
                                         vision_error=vision_error, vision_run_at=timezone.now())
        return app

    def test_bad_image_data_is_unreadable_not_service_down(self):
        # The TD-080 fix: a PDF/video IC ("Bad image data.") tells the student to
        # re-upload, instead of a false "service unavailable".
        self.assertEqual(_ic_identity_blockers(self._app_with_ic('Bad image data.')), ['ic_unreadable'])

    def test_genuine_service_error_stays_service_down(self):
        self.assertEqual(_ic_identity_blockers(self._app_with_ic('Vision API quota exceeded')),
                         ['ic_service_down'])

    def _app_with_read_ic(self, *, vnric, vname, pnric, pname):
        p = StudentProfile.objects.create(supabase_user_id=f'gate-{vnric}',
                                          name=pname, nric=pnric)
        app = ScholarshipApplication.objects.create(cohort=self.cohort, profile=p, status='shortlisted')
        ApplicantDocument.objects.create(application=app, doc_type='ic', storage_path='x',
                                         vision_nric=vnric, vision_name=vname, vision_run_at=timezone.now())
        return app

    def test_name_mismatch_does_not_block_when_nric_matches(self):
        # Harish case: NRIC verified, but the name OCR'd as a locality. The NRIC is
        # the hard key, so the name mismatch must NOT block consent.
        app = self._app_with_read_ic(vnric='080923-06-0355', vname='TAMAN SRI LAYANG',
                                     pnric='080923-06-0355', pname='Harish Rish')
        self.assertNotIn('ic_name_mismatch', _ic_identity_blockers(app))

    def test_name_mismatch_blocks_when_nric_also_fails(self):
        # No NRIC verification → a disjoint name still blocks (genuine wrong-IC risk).
        app = self._app_with_read_ic(vnric='111111-11-1111', vname='SOMEONE ELSE',
                                     pnric='080923-06-0355', pname='Harish Rish')
        blockers = _ic_identity_blockers(app)
        self.assertIn('ic_nric_mismatch', blockers)
        self.assertIn('ic_name_mismatch', blockers)
