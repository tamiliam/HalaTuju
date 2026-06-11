"""HEIC → JPEG conversion (apps.scholarship.imaging)."""
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.scholarship.imaging import convert_heic_to_jpeg, is_heic
from apps.scholarship.models import (ApplicantDocument, ScholarshipApplication,
                                     ScholarshipCohort)
from apps.courses.models import StudentProfile


class TestIsHeic(TestCase):
    def test_detects_by_content_type_and_extension(self):
        self.assertTrue(is_heic(SimpleNamespace(content_type='image/heic', original_filename='x')))
        self.assertTrue(is_heic(SimpleNamespace(content_type='image/heif', original_filename='x')))
        self.assertTrue(is_heic(SimpleNamespace(content_type='', original_filename='IMG_1.HEIC')))
        self.assertFalse(is_heic(SimpleNamespace(content_type='image/jpeg', original_filename='a.jpg')))
        self.assertFalse(is_heic(SimpleNamespace(content_type='application/pdf', original_filename='b.pdf')))


class TestConvertHeic(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='heic', name='B40', year=2026)

    def _doc(self, *, ct='image/heic', fn='IMG_1234.HEIC'):
        prof = StudentProfile.objects.create(
            supabase_user_id=str(uuid.uuid4()), nric='030101-14-1234', name='S')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=prof, status='shortlisted')
        return ApplicantDocument.objects.create(
            application=app, doc_type='photo', storage_path='x/photo/heic',
            original_filename=fn, content_type=ct, size=100)

    def test_non_heic_is_noop(self):
        d = self._doc(ct='image/jpeg', fn='a.jpg')
        self.assertFalse(convert_heic_to_jpeg(d))
        d.refresh_from_db()
        self.assertEqual(d.content_type, 'image/jpeg')

    @patch.dict(sys.modules, {'pillow_heif': MagicMock()})
    @patch('apps.scholarship.storage.upload_object', return_value=True)
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'fake-heic-bytes')
    @patch('PIL.Image.open')
    def test_heic_converts_and_updates_row(self, mock_open, _fetch, mock_upload):
        img = MagicMock()
        img.convert.return_value = img
        img.save.side_effect = lambda buf, *a, **k: buf.write(b'jpeg-bytes')
        mock_open.return_value = img

        d = self._doc(ct='image/heic', fn='IMG_1234.HEIC')
        self.assertTrue(convert_heic_to_jpeg(d))
        d.refresh_from_db()
        self.assertEqual(d.content_type, 'image/jpeg')
        self.assertTrue(d.original_filename.lower().endswith('.jpg'))
        mock_upload.assert_called_once()
        # uploaded with the JPEG content-type, to the SAME storage path (in place).
        self.assertEqual(mock_upload.call_args[0][0], 'x/photo/heic')
        self.assertEqual(mock_upload.call_args[0][2], 'image/jpeg')

    @patch.dict(sys.modules, {'pillow_heif': MagicMock()})
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=None)
    def test_fetch_failure_leaves_original_untouched(self, _fetch):
        d = self._doc()
        self.assertFalse(convert_heic_to_jpeg(d))
        d.refresh_from_db()
        self.assertEqual(d.content_type, 'image/heic')

    @patch.dict(sys.modules, {'pillow_heif': MagicMock()})
    @patch('apps.scholarship.storage.upload_object', return_value=False)
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'fake-heic-bytes')
    @patch('PIL.Image.open')
    def test_upload_failure_leaves_original_untouched(self, mock_open, _fetch, _upload):
        img = MagicMock()
        img.convert.return_value = img
        img.save.side_effect = lambda buf, *a, **k: buf.write(b'jpeg-bytes')
        mock_open.return_value = img
        d = self._doc()
        self.assertFalse(convert_heic_to_jpeg(d))
        d.refresh_from_db()
        self.assertEqual(d.content_type, 'image/heic')
