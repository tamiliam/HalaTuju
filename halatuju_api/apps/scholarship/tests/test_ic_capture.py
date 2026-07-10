"""IC capture-confidence tag: run_vision_for_document stamps vision_fields.capture
('deterministic' for the Vision-OCR read, 'ai' when the Gemini fallback is merged)."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import vision
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort

_CLEAN = {'nric': '030101-14-1234', 'name': 'PRIYA', 'address': '', 'error': ''}


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestIcCaptureTag(TestCase):
    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        profile = StudentProfile.objects.create(
            supabase_user_id='s', nric='030101-14-1234', name='Priya')
        self.app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='shortlisted')
        self.doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', storage_path='x', uploaded_at=timezone.now())

    def _cap(self):
        self.doc.refresh_from_db()
        return (self.doc.vision_fields or {}).get('capture')

    def test_deterministic_read_tags_exact(self):
        with patch.object(vision, '_fetch_image_bytes', return_value=b'img'), \
             patch.object(vision, 'extract_mykad', return_value=dict(_CLEAN)), \
             patch.object(vision, '_should_gemini_ic', return_value=False):
            vision.run_vision_for_document(self.doc)
        self.assertEqual(self._cap(), 'deterministic')

    def test_gemini_fallback_tags_ai(self):
        with patch.object(vision, '_fetch_image_bytes', return_value=b'img'), \
             patch.object(vision, 'extract_mykad', return_value={'nric': '', 'name': 'PRIYA', 'address': '', 'error': ''}), \
             patch.object(vision, '_should_gemini_ic', return_value=True), \
             patch.object(vision, '_gemini_ic_second_opinion', return_value={'nric': '030101-14-1234', 'name': 'PRIYA'}), \
             patch.object(vision, '_merge_ic_reads', return_value=dict(_CLEAN)):
            vision.run_vision_for_document(self.doc)
        self.assertEqual(self._cap(), 'ai')

    def test_no_image_leaves_no_tag(self):
        # A failed fetch must NOT stamp a capture (nothing was read).
        with patch.object(vision, '_fetch_image_bytes', return_value=None):
            vision.run_vision_for_document(self.doc)
        self.assertIsNone(self._cap())
