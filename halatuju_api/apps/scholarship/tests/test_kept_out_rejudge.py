"""Audit sprint A2.8a (TD-393) — an upload our outage kept out of its slot is re-read AND judged.

Before A2.8a a re-upload made during an outage over a live readable copy was staged, read as deferred,
kept out (its quality proxy is below an `ok` copy) and never read again: the hourly sweep re-read only
LIVE documents. Now the sweep also re-reads such a kept-out copy and judges it through the upload's own
judging (`upload_read.judge`). Mocks only: no paid or network call.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import create_document, make_application

_SERVICE_READ = {'fields': {}, 'warnings': [], 'student_verdict': 'review_manually', 'capture': 'ai',
                 'error': 'All AI models failed: gemini-2.5-flash: 402 RESOURCE_EXHAUSTED', 'service_error': True}
_IMAGE = b'\xff\xd8\xff\xe0 not a real jpeg, never decoded'


@override_settings(GEMINI_API_KEY='test-key', DOC_GENUINENESS_CHECK_ENABLED=False)
class TheSweepJudgesAnUploadOurOutageKeptOut(TestCase):

    def setUp(self):
        self.app = make_application('shortlisted')
        self.name = self.app.profile.name
        self.full = {'text': 'penyata gaji', 'words': None, 'image': _IMAGE, 'error': None}
        self.good = {'name': self.name, 'employer': 'ACME', 'gross_income': '3000',
                     'net_income': '2700', 'period': 'Jan 2026', 'warnings': []}
        self.live = create_document(
            self.app, 'salary_slip', storage_path='test/slip/live', content_type='image/jpeg',
            vision_run_at=timezone.now(), vision_fields_run_at=timezone.now() - timedelta(days=2),
            vision_fields={'fields': {'name': self.name, 'gross_income': '2500'}, 'warnings': [],
                           'student_verdict': 'ok', 'capture': 'ai', 'error': ''})

    def _kept_out(self, keeper=None, **vf):
        return create_document(
            self.app, 'salary_slip', storage_path=f'test/slip/{ApplicantDocument.objects.count()}',
            content_type='image/jpeg', superseded_at=timezone.now(), superseded_by=keeper or self.live,
            vision_run_at=timezone.now(), vision_fields_run_at=timezone.now() - timedelta(hours=3),
            vision_fields={**_SERVICE_READ, **vf})

    def _sweep(self, gemini_answer, ocr=None):
        from apps.scholarship.services import reprocess_unread_ic_documents
        with patch('apps.scholarship.vision.ocr_document_full', return_value=ocr or self.full), \
                patch('apps.scholarship.vision._call_gemini_json', return_value=gemini_answer) as gem:
            return reprocess_unread_ic_documents(), gem

    def test_a_kept_out_copy_that_now_reads_is_promoted_over_the_older_live_copy(self):
        new = self._kept_out()
        r, gem = self._sweep(dict(self.good))
        self.assertEqual(gem.call_count, 1)
        new.refresh_from_db()
        self.live.refresh_from_db()
        self.assertEqual(new.vision_fields['student_verdict'], 'ok')
        self.assertIsNone(new.superseded_at)                         # her newer document holds the slot
        self.assertEqual(self.live.superseded_by_id, new.id)         # the old one is history
        self.assertEqual(r['processed'], 1)

    def test_a_kept_out_copy_whose_read_says_the_file_is_bad_stays_out(self):
        new = self._kept_out()
        self._sweep(dict(self.good), ocr={'text': '', 'words': None, 'image': _IMAGE, 'error': None})
        new.refresh_from_db()
        self.live.refresh_from_db()
        self.assertEqual(new.vision_fields['student_verdict'], 'unreadable')
        self.assertIsNotNone(new.superseded_at)                      # judged: not usable, kept out
        self.assertIsNone(self.live.superseded_at)

    def test_still_down_it_is_probed_once_stays_out_and_gets_the_window(self):
        new = self._kept_out()
        down = {'_error': 'All AI models failed: gemini-2.5-flash: 402 RESOURCE_EXHAUSTED'}
        r, gem = self._sweep(down)
        self.assertEqual(gem.call_count, 1)
        new.refresh_from_db()
        self.assertIsNotNone(new.superseded_at)
        self.assertIn('service_retry_until', new.vision_fields)
        self.assertIsNone(ApplicantDocument.objects.get(pk=self.live.pk).superseded_at)

    def test_a_copy_whose_keeper_was_itself_replaced_is_left_alone(self):
        new = self._kept_out()
        newer = create_document(self.app, 'salary_slip', storage_path='test/slip/newer', content_type='image/jpeg',
                                vision_fields={'fields': {'gross_income': '2600'}, 'student_verdict': 'ok',
                                               'error': ''}, request_code='officer_9')
        ApplicantDocument.objects.filter(pk=self.live.pk).update(superseded_at=timezone.now(), superseded_by=newer)
        from apps.scholarship.services.read_retry import service_error_documents
        self.assertNotIn(new.id, [d.id for d in service_error_documents(50)])

    def test_a_copy_a_newer_decided_upload_follows_is_left_alone(self):
        from apps.scholarship.upload_read import kept_out_by_outage
        new = self._kept_out()
        self.assertTrue(kept_out_by_outage(new))
        self._kept_out(student_verdict='ok', fields={'gross_income': '2700'}, error='', service_error=False)
        self.assertFalse(kept_out_by_outage(ApplicantDocument.objects.get(pk=new.pk)))

    def test_a_normally_replaced_older_copy_or_a_read_kept_copy_is_never_picked(self):
        from apps.scholarship.services.read_retry import service_error_documents
        old = create_document(self.app, 'salary_slip', storage_path='test/slip/old', content_type='image/jpeg',
                              request_code='officer_7', superseded_at=timezone.now(), vision_fields=dict(_SERVICE_READ))
        newer = create_document(self.app, 'salary_slip', storage_path='test/slip/new7', content_type='image/jpeg',
                                request_code='officer_7', vision_fields={'fields': {'gross_income': '2600'},
                                                                         'student_verdict': 'ok', 'error': ''})
        ApplicantDocument.objects.filter(pk=old.pk).update(superseded_by=newer)   # replaced by a NEWER upload
        read = self._kept_out(student_verdict='mismatch', fields={'name': 'SOMEONE ELSE'}, error='', service_error=False)
        picked = [d.id for d in service_error_documents(50)]
        self.assertNotIn(old.id, picked)
        self.assertNotIn(read.id, picked)
