"""Code-health S2 #5/#22: the pipeline never destroys a good read, and OCRs once.

The blob on a document row is immutable, so a re-run that reads NOTHING where a prior
run succeeded is OUR failure (Storage outage / checkout without Storage access) — the
known incident mode that used to wipe ``vision_fields``. These tests pin the clobber
guards on all three writers, and the single-Vision-call contract of ``ocr_document_full``.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import vision
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort


def _doc(doc_type='salary_slip', vision_fields=None, **kw):
    cohort = ScholarshipCohort.objects.create(
        code=f'c{ScholarshipCohort.objects.count()}', name='B40', year=2026)
    profile = StudentProfile.objects.create(
        supabase_user_id=f'u{StudentProfile.objects.count()}', name='Muthu Raman')
    app = ScholarshipApplication.objects.create(cohort=cohort, profile=profile, status='interviewing')
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, storage_path='blob',
        vision_fields=vision_fields or {}, **kw)


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestFieldExtractionClobberGuard(TestCase):
    GOOD = {'fields': {'name': 'Muthu Raman', 'gross_income': '2500'},
            'warnings': [], 'student_verdict': 'ok', 'capture': 'ai', 'error': ''}

    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=None)
    def test_failed_rerun_keeps_stored_extraction(self, _fetch):
        doc = _doc(vision_fields=dict(self.GOOD))
        doc.vision_fields_run_at = timezone.now()
        doc.save(update_fields=['vision_fields_run_at'])
        before = doc.vision_fields_run_at
        r = vision.run_field_extraction_for_document(doc, names=['Muthu Raman'])
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['fields']['gross_income'], '2500')  # untouched
        self.assertEqual(doc.vision_fields_run_at, before)                      # no save
        self.assertTrue(r.get('stale_kept'))
        self.assertTrue(r['error'])

    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=None)
    def test_first_read_failure_still_stores_unreadable(self, _fetch):
        # The guard protects PRIOR GOOD reads only — a fresh doc's failure must still be
        # recorded (the honest 'unreadable' state the student/officer can see).
        doc = _doc()
        r = vision.run_field_extraction_for_document(doc, names=['Muthu Raman'])
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['student_verdict'], 'unreadable')
        self.assertFalse(r.get('stale_kept'))

    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=None)
    def test_stored_text_read_also_protected(self, _fetch):
        # vision_fields may hold a TEXT read (letter of intent) — protected the same way.
        doc = _doc(doc_type='statement_of_intent',
                   vision_fields={'text': 'my motivation letter', 'student_verdict': 'read', 'error': ''})
        r = vision.read_text_document(doc)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['text'], 'my motivation letter')
        self.assertEqual(r['text'], 'my motivation letter')


class TestVisionMatchClobberGuard(TestCase):
    def test_failed_rerun_keeps_stored_verdicts(self):
        doc = _doc(doc_type='electricity_bill')
        doc.vision_name_match = 'found'
        doc.vision_address_match = 'found'
        doc.save(update_fields=['vision_name_match', 'vision_address_match'])
        r = vision.run_vision_match_for_document(
            doc, names=['Muthu Raman'], check_address=True,
            ocr={'text': '', 'error': 'could not fetch image'})
        doc.refresh_from_db()
        self.assertEqual(doc.vision_name_match, 'found')      # not downgraded to unreadable
        self.assertEqual(doc.vision_address_match, 'found')
        self.assertTrue(r.get('stale_kept'))

    def test_first_read_failure_still_stores_unreadable(self):
        doc = _doc(doc_type='electricity_bill')
        r = vision.run_vision_match_for_document(
            doc, names=['Muthu Raman'], check_address=True,
            ocr={'text': '', 'error': 'could not fetch image'})
        doc.refresh_from_db()
        self.assertEqual(doc.vision_name_match, 'unreadable')
        self.assertFalse(r.get('stale_kept'))


class TestOcrDocumentFull(TestCase):
    @patch('apps.scholarship.vision._vision_words')
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'imgbytes')
    def test_one_vision_call_serves_text_and_words(self, _fetch, mock_words):
        mock_words.return_value = {'words': [{'text': 'BAHASA', 'cx': 1, 'cy': 1, 'h': 9, 'angle': 0}],
                                   'text': 'BAHASA MELAYU A', 'error': None}
        doc = _doc(doc_type='results_slip')
        r = vision.ocr_document_full(doc)
        self.assertEqual(mock_words.call_count, 1)
        self.assertEqual(r['text'], 'BAHASA MELAYU A')
        self.assertEqual(len(r['words']), 1)
        self.assertEqual(r['image'], b'imgbytes')
        self.assertIsNone(r['error'])

    @patch('apps.scholarship.vision._vision_words')
    @patch('apps.scholarship.vision._pdf_text_layer', return_value='x' * 500)
    @patch('apps.scholarship.vision._is_pdf', return_value=True)
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'%PDF-fake')
    def test_digital_pdf_keeps_the_free_text_layer_path(self, _fetch, _ispdf, _layer, mock_words):
        # A digital PDF must NOT start paying for a Vision call it never needed.
        doc = _doc(doc_type='salary_slip', content_type='application/pdf')
        r = vision.ocr_document_full(doc)
        mock_words.assert_not_called()
        self.assertEqual(r['text'], 'x' * 500)
        self.assertIsNone(r['words'])   # not computed — consumers fall back as before

    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=None)
    def test_fetch_failure_shape(self, _fetch):
        doc = _doc()
        r = vision.ocr_document_full(doc)
        self.assertEqual(r, {'text': '', 'words': None, 'image': None,
                             'error': 'could not fetch image'})


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestWordsReuseInExtraction(TestCase):
    @patch('apps.scholarship.academic_engine.parse_spm_slip')
    @patch('apps.scholarship.vision._vision_words')
    def test_slip_extraction_reuses_words_from_ocr(self, mock_words, mock_parse):
        # With a full ocr dict (words + image), the slip's deterministic parse must NOT
        # make a second billable Vision call (#22: previously 2 identical calls per slip).
        mock_parse.return_value = {'slip_name': 'MUTHU RAMAN',
                                   'subjects': [{'name': 'Bahasa Melayu', 'grade': 'A'}]}
        doc = _doc(doc_type='results_slip')
        words = [{'text': 'BAHASA', 'cx': 1, 'cy': 1, 'h': 9, 'angle': 0}]
        r = vision.run_field_extraction_for_document(
            doc, names=['Muthu Raman'],
            ocr={'text': 'BAHASA MELAYU A', 'words': words, 'image': b'img', 'error': None})
        mock_words.assert_not_called()
        mock_parse.assert_called_once_with(words)
        self.assertEqual(r['capture'], 'deterministic')
