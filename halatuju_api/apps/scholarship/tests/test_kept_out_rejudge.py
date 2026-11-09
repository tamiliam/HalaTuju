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


class _KeptOut(TestCase):

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

    def _kept_out(self, keeper=None, staged=True, run_at=None, **vf):
        keeper = keeper or self.live
        return create_document(
            self.app, 'salary_slip', storage_path=f'test/slip/{ApplicantDocument.objects.count()}',
            content_type='image/jpeg', superseded_at=timezone.now(), superseded_by=keeper,
            vision_run_at=timezone.now(), vision_fields_run_at=run_at or timezone.now() - timedelta(hours=3),
            read_plan={'staged': staged, 'stale_ids': [keeper.id], 'existing_live': keeper.id},
            vision_fields={**_SERVICE_READ, **vf})

    def _sweep(self, gemini_answer, ocr=None):
        from apps.scholarship.services import reprocess_unread_ic_documents
        with patch('apps.scholarship.vision.ocr_document_full', return_value=ocr or self.full), \
                patch('apps.scholarship.vision._call_gemini_json', return_value=gemini_answer) as gem:
            return reprocess_unread_ic_documents(), gem


@override_settings(GEMINI_API_KEY='test-key', DOC_GENUINENESS_CHECK_ENABLED=False)
class TheSweepJudgesAnUploadOurOutageKeptOut(_KeptOut):

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


@override_settings(GEMINI_API_KEY='test-key', DOC_GENUINENESS_CHECK_ENABLED=False)
class TheReviewFixes(_KeptOut):
    """A2.8a adversarial review (FIX-FIRST): the selection admits only what it re-judges, only before QC
    accept, the judging re-checks the slot on a fresh row, and the re-read reslots like the upload."""

    def _bulk(self, n, **kw):
        old = timezone.now() - timedelta(days=5)
        vf = {**_SERVICE_READ, **kw.pop('vf', {})}
        ApplicantDocument.objects.bulk_create([ApplicantDocument(
            application=self.app, doc_type='salary_slip', storage_path=f'test/slip/bulk{i}{kw.get("read_state", "")}',
            content_type='image/jpeg', superseded_at=timezone.now(), superseded_by=self.live,
            vision_fields_run_at=old, vision_fields=vf,
            read_plan={'staged': True, 'stale_ids': [self.live.id], 'existing_live': self.live.id}, **kw)
            for i in range(n)])

    def test_item1_old_rows_the_check_drops_never_fill_the_batch(self):
        from apps.scholarship.services.read_retry import service_error_documents
        self._bulk(60, vf={'student_verdict': 'unreadable'})          # legacy: unreadable + a service error
        self._bulk(60, read_state='pending')                          # still queued for the upload's read
        genuine = self._kept_out()
        self.assertEqual(ApplicantDocument.objects.filter(superseded_at__isnull=False).count(), 121)
        picked = [d.id for d in service_error_documents(50)]
        self.assertEqual(picked, [genuine.id])

    def test_item2_a_copy_kept_out_on_a_decided_case_is_left_for_the_officer(self):
        from apps.scholarship.services.read_retry import service_error_documents
        new = self._kept_out()
        for status in ('recommended', 'awarded', 'active', 'maintenance'):
            with self.subTest(status=status):
                type(self.app).objects.filter(pk=self.app.pk).update(status=status)
                self.assertNotIn(new.id, [d.id for d in service_error_documents(50)])
                _r, gem = self._sweep(dict(self.good))
                self.assertEqual(gem.call_count, 0)
                self.assertIsNotNone(ApplicantDocument.objects.get(pk=new.pk).superseded_at)
        type(self.app).objects.filter(pk=self.app.pk).update(status='interviewed')   # before QC accept: picked
        self.assertIn(new.id, [d.id for d in service_error_documents(50)])

    def test_item3_a_fresh_upload_decided_during_the_re_read_is_never_pushed_out(self):
        new = self._kept_out()
        made = {}

        def answer(*_a, **_k):                                        # the student uploads while we read
            if 'doc' not in made:
                made['doc'] = self._kept_out(student_verdict='ok', fields={'gross_income': '2700'}, error='',
                                             service_error=False)
            return dict(self.good)
        from apps.scholarship.services import reprocess_unread_ic_documents
        with patch('apps.scholarship.vision.ocr_document_full', return_value=self.full), \
                patch('apps.scholarship.vision._call_gemini_json', side_effect=answer):
            reprocess_unread_ic_documents()
        new.refresh_from_db()
        self.live.refresh_from_db()
        self.assertEqual(new.vision_fields['student_verdict'], 'ok')    # it was re-read ...
        self.assertIsNotNone(new.superseded_at)                         # ... but not promoted
        self.assertIsNone(self.live.superseded_at)

    def test_item3_a_keeper_replaced_since_the_pick_is_not_re_judged(self):
        from apps.scholarship.upload_read import judge_reread_copy
        new = self._kept_out()
        stale = ApplicantDocument.objects.get(pk=new.pk)               # the sweep's in-memory row
        other = create_document(self.app, 'salary_slip', storage_path='test/slip/other', content_type='image/jpeg',
                                request_code='officer_3', vision_fields={'fields': {}, 'student_verdict': 'ok'})
        ApplicantDocument.objects.filter(pk=self.live.pk).update(superseded_at=timezone.now(), superseded_by=other)
        self.assertIsNone(judge_reread_copy(stale))
        self.assertIsNotNone(ApplicantDocument.objects.get(pk=new.pk).superseded_at)

    def test_item4_a_copy_never_judged_as_staged_does_not_qualify(self):
        from apps.scholarship.services.read_retry import service_error_documents
        from apps.scholarship.upload_read import kept_out_by_outage
        pushed = self._kept_out(staged=False)                          # e.g. pushed out by the dedupe
        bare = self._kept_out()
        ApplicantDocument.objects.filter(pk=bare.pk).update(read_plan=None)   # a row from before the queue
        picked = [d.id for d in service_error_documents(50)]
        for doc in (pushed, bare):
            self.assertNotIn(doc.id, picked)
            self.assertFalse(kept_out_by_outage(ApplicantDocument.objects.get(pk=doc.pk)))

    def test_item5_the_sweep_re_read_files_an_epf_in_the_payslip_slot_as_an_epf(self):
        from apps.scholarship.tests.test_reslot_income_doc import _EPF_TEXT
        new = self._kept_out()
        self._sweep(dict(self.good), ocr={'text': _EPF_TEXT, 'words': None, 'image': _IMAGE, 'error': None})
        self.assertEqual(ApplicantDocument.objects.get(pk=new.pk).doc_type, 'epf')

    def test_item5_an_officer_re_run_still_leaves_the_slot_alone(self):
        from apps.scholarship.reextract import reextract_document
        from apps.scholarship.tests.test_reslot_income_doc import _EPF_TEXT
        with patch('apps.scholarship.vision.ocr_document_full',
                   return_value={'text': _EPF_TEXT, 'words': None, 'image': _IMAGE, 'error': None}), \
                patch('apps.scholarship.vision._call_gemini_json', return_value=dict(self.good)):
            reextract_document(self.live)
        self.assertEqual(ApplicantDocument.objects.get(pk=self.live.pk).doc_type, 'salary_slip')
