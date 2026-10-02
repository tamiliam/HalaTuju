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
        ApplicantDocument.objects.create(            # a photo-only type → out of scope
            application=self.app, doc_type='photo', storage_path='ph',
            vision_run_at=None)
        with patch('apps.scholarship.vision.run_vision_for_document',
                   return_value={'error': ''}) as m, \
                patch('apps.scholarship.reextract.reextract_document') as rx:
            r = reprocess_unread_ic_documents()
        self.assertEqual([c.args[0].id for c in m.call_args_list], [stuck.id])
        rx.assert_not_called()
        self.assertEqual(r, {'scanned': 1, 'processed': 1, 'errored': 0})

    # ── TD-151 (3): the other read documents a submission gate depends on ──────────────────
    def _doc(self, doc_type, **kw):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path=f'p/{doc_type}/{len(kw)}', **kw)

    def test_sweeps_every_gating_read_type_left_with_no_read_at_all(self):
        from apps.scholarship.services.blockers import _SELF_HEAL_READ_TYPES
        stuck = [self._doc(t) for t in _SELF_HEAL_READ_TYPES]
        with patch('apps.scholarship.reextract.reextract_document') as rx:
            r = reprocess_unread_ic_documents()
        self.assertEqual(sorted(c.args[0].id for c in rx.call_args_list),
                         sorted(d.id for d in stuck))
        self.assertEqual(r, {'scanned': len(stuck), 'processed': len(stuck), 'errored': 0})
        self.assertIn('results_slip', _SELF_HEAL_READ_TYPES)
        self.assertIn('offer_letter', _SELF_HEAL_READ_TYPES)

    def test_never_re_reads_a_document_that_has_any_read_or_was_replaced(self):
        now = timezone.now()
        self._doc('results_slip', vision_run_at=now)                 # name check ran
        self._doc('offer_letter', vision_fields_run_at=now)         # field extraction ran
        # Review F1: an older read with BOTH stamps NULL but stored fields — never re-read, or the
        # sweep would overwrite a read nobody asked it to redo.
        self._doc('epf', vision_fields={'fields': {'employer': 'X'}})
        self._doc('salary_slip', superseded_at=now)                  # replaced by a newer copy
        with patch('apps.scholarship.reextract.reextract_document') as rx:
            r = reprocess_unread_ic_documents()
        rx.assert_not_called()
        self.assertEqual(r['scanned'], 0)

    def test_a_non_ic_read_that_raises_is_stamped_so_it_cannot_loop(self):
        doc = self._doc('offer_letter')
        with patch('apps.scholarship.reextract.reextract_document',
                   side_effect=RuntimeError('boom')):
            r = reprocess_unread_ic_documents()
        doc.refresh_from_db()
        self.assertIsNotNone(doc.vision_run_at)
        self.assertEqual(r['errored'], 1)
        with patch('apps.scholarship.reextract.reextract_document') as rx:
            reprocess_unread_ic_documents()
        rx.assert_not_called()

    def test_dry_run_counts_by_type_and_reads_nothing(self):
        self._doc('results_slip'); self._doc('epf')
        ApplicantDocument.objects.create(application=self.app, doc_type='ic',
                                         storage_path='i', vision_run_at=None)
        with patch('apps.scholarship.vision.run_vision_for_document') as m, \
                patch('apps.scholarship.reextract.reextract_document') as rx:
            r = reprocess_unread_ic_documents(dry_run=True)
        m.assert_not_called(); rx.assert_not_called()
        self.assertEqual(r, {'scanned': 3, 'by_type': {'results_slip': 1, 'epf': 1, 'ic': 1}})

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

    # ── 2026-10-02: one 2 MB PDF killed the instance mid-read, hourly. Stamp BEFORE reading. ──
    def test_the_row_is_stamped_before_the_reader_is_called(self):
        from apps.scholarship.services.blockers import REPROCESS_ATTEMPTED
        doc = self._doc('salary_slip')
        seen = {}

        def reader(d):
            row = ApplicantDocument.objects.get(pk=d.pk)
            seen.update(error=row.vision_error, run_at=row.vision_run_at, fields=row.vision_fields)
        with patch('apps.scholarship.reextract.reextract_document', side_effect=reader):
            reprocess_unread_ic_documents()
        self.assertEqual(seen['error'], REPROCESS_ATTEMPTED)
        self.assertIsNotNone(seen['run_at'])
        self.assertEqual(seen['fields'], {})             # F1: the pre-stamp never touches a read
        doc.refresh_from_db()
        self.assertEqual(doc.vision_error, '')           # a clean read leaves no marker behind

    def test_a_process_killed_mid_read_never_re_picks_the_same_document(self):
        from apps.scholarship.services.blockers import REPROCESS_ATTEMPTED, _stuck_unread_documents

        class Killed(BaseException):                     # not an Exception: like an OOM kill,
            pass                                         # nothing after the read gets to run
        slip = self._doc('salary_slip', content_type='application/pdf')
        ic = ApplicantDocument.objects.create(application=self.app, doc_type='ic',
                                              storage_path='k-ic', vision_run_at=None)
        for target, doc in (('apps.scholarship.reextract.reextract_document', slip),
                            ('apps.scholarship.vision.run_vision_for_document', ic)):
            with patch(target, side_effect=Killed), self.assertRaises(Killed):
                reprocess_unread_ic_documents()
            doc.refresh_from_db()
            self.assertEqual(doc.vision_error, REPROCESS_ATTEMPTED)
            self.assertIsNotNone(doc.vision_run_at)
            self.assertNotIn(doc.id, [d.id for d in _stuck_unread_documents(200)])
        with patch('apps.scholarship.vision.run_vision_for_document') as m, \
                patch('apps.scholarship.reextract.reextract_document') as rx:
            r = reprocess_unread_ic_documents()
        m.assert_not_called(); rx.assert_not_called()
        self.assertEqual(r['scanned'], 0)
