"""Self-heal sweep: re-run Vision on IC/parent_ic docs stuck unprocessed (silent upload
OCR failures that strand a student behind a false 'ic_service_down' consent block)."""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import reprocess_unread_ic_documents


class TestReprocessUnreadIc(TestCase):
    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='ric', name='B40', year=2026)
        profile = StudentProfile.objects.create(
            supabase_user_id='ric-stu', nric='030101-14-1234', name='Stu')
        self.app = ScholarshipApplication.objects.create(cohort=cohort, profile=profile)

    def test_reruns_only_unprocessed_ic_docs(self):
        stuck = ApplicantDocument.objects.create(
            application=self.app, doc_type='parent_ic', household_member='mother',
            storage_path='m-ic', vision_run_at=None)
        ApplicantDocument.objects.create(            # already processed → left alone
            application=self.app, doc_type='ic', storage_path='s-ic',
            vision_run_at=timezone.now())
        ApplicantDocument.objects.create(            # non-IC pipeline → out of scope
            application=self.app, doc_type='offer_letter', storage_path='off',
            vision_run_at=None)
        with patch('apps.scholarship.vision.run_vision_for_document',
                   return_value={'error': ''}) as m:
            r = reprocess_unread_ic_documents()
        self.assertEqual([c.args[0].id for c in m.call_args_list], [stuck.id])
        self.assertEqual(r, {'scanned': 1, 'processed': 1, 'errored': 0})

    def test_records_outcome_if_run_raises(self):
        # run_vision should never raise, but if it does we stamp an outcome so the sweep
        # can't retry the same doc forever (billable Vision in a loop).
        stuck = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', storage_path='s', vision_run_at=None)
        with patch('apps.scholarship.vision.run_vision_for_document',
                   side_effect=RuntimeError('boom')):
            r = reprocess_unread_ic_documents()
        stuck.refresh_from_db()
        self.assertIsNotNone(stuck.vision_run_at)
        self.assertEqual(stuck.vision_error, 'reprocess_failed')
        self.assertEqual(r['errored'], 1)
