"""The bulk reextract command: self-batching by the pass marker, scoped to supporting
doc types (photos/ICs excluded), advancing each run. The actual per-doc read is mocked
(no Vision/Gemini in tests) — we assert the batching + marking contract."""
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)

MARKER = 'reextract_2026_06'


class ReextractCommandTests(TestCase):
    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        profile = StudentProfile.objects.create(supabase_user_id='s', nric='030101-14-1234', name='P')
        self.app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='interviewing')
        for i in range(3):
            ApplicantDocument.objects.create(
                application=self.app, doc_type='offer_letter', storage_path=f'o{i}')
        # A photo must NEVER be picked up (not an extractable type).
        ApplicantDocument.objects.create(application=self.app, doc_type='photo', storage_path='p')

    def _marked(self):
        return ApplicantDocument.objects.filter(**{f'vision_fields__{MARKER}': True}).count()

    @patch('apps.scholarship.management.commands.reextract_documents.reextract_document')
    def test_batches_advance_and_skip_photos(self, mock_re):
        mock_re.return_value = True
        # Batch 1 of 2 → 2 processed + marked.
        call_command('reextract_documents', '--limit', '2')
        self.assertEqual(mock_re.call_count, 2)
        self.assertEqual(self._marked(), 2)
        # Batch 2 → the remaining offer letter (3rd); photo stays untouched.
        call_command('reextract_documents', '--limit', '2')
        self.assertEqual(mock_re.call_count, 3)        # only the 3 offer letters, never the photo
        self.assertEqual(self._marked(), 3)
        photo = ApplicantDocument.objects.get(doc_type='photo')
        self.assertNotIn(MARKER, (photo.vision_fields or {}))
        # Batch 3 → nothing left to do.
        call_command('reextract_documents', '--limit', '2')
        self.assertEqual(mock_re.call_count, 3)

    @patch('apps.scholarship.management.commands.reextract_documents.reextract_document',
           side_effect=RuntimeError('boom'))
    def test_error_still_marks_so_the_pass_never_wedges(self, _mock):
        call_command('reextract_documents', '--limit', '5')
        # All 3 offer letters marked despite the read raising — the batch advances.
        self.assertEqual(self._marked(), 3)
