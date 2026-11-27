"""OCR-15 phase 1: the IC / parent IC read keeps the Vision text it already has (``ocr_keep``), and the one-off
``capture_parent_ic_text`` command fills the store for the live parent ICs read before that.

Every Vision and Gemini seam is mocked; no network. The card text and the IC number are made up
(000000-00-0000). Pins:
  * the IC read (``run_vision_for_document``) stores its text, for ``ic`` and ``parent_ic``, with no extra
    Vision call; a read with no text stores nothing and does not fail; a storage error never changes the
    read; the read's answer and ``vision_fields`` never carry the text;
  * the command's dry run makes no download, no Vision call and no write; ``--run`` needs ``--limit`` and
    ``--max-cost-usd``, stores only through ``ocr_keep.keep``, skips stored, superseded and queued
    documents, stops at the limit and the cost cap, counts a failing document and carries on, never calls
    Gemini, and changes nothing else in the database; its output carries ids and counts only.
"""
from io import StringIO
from unittest import mock

from django.apps import apps as django_apps
from django.core.management import CommandError, call_command
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import ocr_keep, vision
from apps.scholarship.management.commands import capture_parent_ic_text as cmd
from apps.scholarship.models import ApplicantDocument, ApplicantDocumentOcrText
from apps.scholarship.serializers import ApplicantDocumentSerializer
from apps.scholarship.tests.factories import create_document, make_application, make_student

V = 'apps.scholarship.vision.'
FAKE_NRIC = '000000-00-0000'
FAKE_NAME = 'MADE UP PARENT NAME'
CARD_TEXT = f'KAD PENGENALAN\nMyKad\n{FAKE_NRIC}\n{FAKE_NAME}\nNO 1 JALAN MADE UP\n'
CMD = 'capture_parent_ic_text'


def _vision(text=CARD_TEXT, error=None):
    return mock.patch(V + '_vision_document_text', return_value={'text': text, 'words': [], 'error': error})


def _now_on_commit():
    """A management command runs outside a transaction, so ``ocr_keep``'s on_commit write runs at once;
    a TestCase holds one open, so run it at once here too."""
    return mock.patch('apps.scholarship.ocr_keep.transaction.on_commit', side_effect=lambda fn, robust=False: fn())


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.app = make_application(student=make_student(name='MADE UP STUDENT', nric='010101-01-0101'))

    def doc(self, doc_type='parent_ic', **kw):
        kw.setdefault('storage_path', 'blob')
        kw.setdefault('content_type', 'image/jpeg')
        return create_document(application=self.app, doc_type=doc_type, **kw)

    def kept(self, doc):
        return ApplicantDocumentOcrText.objects.filter(document_id=doc.pk).first()


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=False)
class TestTheIcReadKeepsItsText(_Base):
    def _read(self, doc, **vision_kw):
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'), _vision(**vision_kw) as seam, \
                self.captureOnCommitCallbacks(execute=True):
            r = vision.run_vision_for_document(doc)
        return r, seam

    def test_a_parent_ic_read_keeps_the_vision_text(self):
        doc = self.doc()
        r, seam = self._read(doc)
        seam.assert_called_once()   # the read's own call: none added to fill the store
        row = self.kept(doc)
        self.assertEqual((row.text, row.source, row.reader), (CARD_TEXT, 'vision_ocr', 'run_vision_for_document'))
        self.assertEqual(r['nric'], FAKE_NRIC)

    def test_the_students_own_ic_read_keeps_it_too(self):
        doc = self.doc('ic')
        self._read(doc)
        self.assertEqual(self.kept(doc).text, CARD_TEXT)

    def test_the_answer_and_vision_fields_never_carry_the_text(self):
        doc = self.doc()
        r, _ = self._read(doc)
        self.assertEqual(set(r), {'nric', 'name', 'address', 'error'})
        self.assertNotIn('KAD PENGENALAN', str(r))
        doc.refresh_from_db()
        self.assertNotIn('KAD PENGENALAN', str(doc.vision_fields))
        data = ApplicantDocumentSerializer(doc).data
        self.assertNotIn('KAD PENGENALAN', str(data))
        self.assertNotIn('ocr', ' '.join(data).lower())

    def test_a_read_with_no_text_stores_nothing_and_does_not_fail(self):
        doc = self.doc()
        r, _ = self._read(doc, text='', error='Bad image data.')
        self.assertEqual(r['error'], 'Bad image data.')
        self.assertIsNone(self.kept(doc))
        doc.refresh_from_db()
        self.assertEqual(doc.vision_error, 'Bad image data.')

    def test_a_blank_vision_text_stores_nothing(self):
        doc = self.doc()
        self._read(doc, text='   ')
        self.assertIsNone(self.kept(doc))

    def test_a_failed_fetch_stores_nothing(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=None), _vision() as seam, \
                self.captureOnCommitCallbacks(execute=True):
            vision.run_vision_for_document(doc)
        seam.assert_not_called()
        self.assertIsNone(self.kept(doc))

    def test_a_storage_error_never_changes_the_read(self):
        doc = self.doc()
        boom = mock.patch.object(ApplicantDocumentOcrText.objects, 'update_or_create',
                                 side_effect=DatabaseError('made up failure'))
        with boom, self.assertLogs('apps.scholarship.ocr_keep', level='WARNING') as logs:
            r, _ = self._read(doc)
        self.assertEqual(r['nric'], FAKE_NRIC)
        self.assertIsNone(self.kept(doc))
        self.assertNotIn(FAKE_NRIC, ' '.join(logs.output))
        doc.refresh_from_db()
        self.assertEqual(doc.vision_nric, FAKE_NRIC)

    def test_extract_mykad_answers_the_same_with_or_without_the_text_list(self):
        seen = []
        with _vision():
            with_list = vision.extract_mykad(b'IMG', 'image/jpeg', text_out=seen)
            without = vision.extract_mykad(b'IMG', 'image/jpeg')
        self.assertEqual(with_list, without)
        self.assertEqual(seen, [CARD_TEXT])


class _CommandBase(_Base):
    def run_cmd(self, *args):
        out = StringIO()
        call_command(CMD, *args, stdout=out)
        return out.getvalue()

    def snapshot(self):
        """Every scholarship and courses table's row count but the text store, and every document's row."""
        counts = {}
        for label in ('scholarship', 'courses'):
            for m in django_apps.get_app_config(label).get_models():
                if m._meta.managed and not m._meta.proxy and m is not ApplicantDocumentOcrText:
                    counts[m._meta.label] = m.objects.count()
        return counts, list(ApplicantDocument.objects.order_by('pk').values())


class TestTheDryRun(_CommandBase):
    def test_counts_only_no_download_no_vision_no_write(self):
        docs = [self.doc(), self.doc(), self.doc()]
        before = self.snapshot()
        with mock.patch(V + '_fetch_image_bytes') as fetch, _vision() as seam, \
                mock.patch.object(ocr_keep, 'keep') as keep:
            out = self.run_cmd()
        fetch.assert_not_called()
        seam.assert_not_called()
        keep.assert_not_called()
        self.assertFalse(ApplicantDocumentOcrText.objects.exists())
        self.assertEqual(self.snapshot(), before)
        self.assertIn('DRY RUN', out)
        self.assertIn('to read: 3', out)
        self.assertIn('estimated Vision units: 3', out)
        self.assertIn('US$0.0045', out)
        self.assertNotIn('ids:', out)
        self.assertEqual(len(docs), 3)

    def test_the_dry_run_honours_the_limit(self):
        self.doc(), self.doc(), self.doc()
        self.assertIn('to read (limit 2): 2', self.run_cmd('--limit', '2'))


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class TestTheRun(_CommandBase):
    def _run(self, *args, fetch=b'IMG', **vision_kw):
        keep_spy = mock.patch.object(ocr_keep, 'keep', wraps=ocr_keep.keep)
        with mock.patch(V + '_fetch_image_bytes', return_value=fetch) as f, _vision(**vision_kw) as seam, \
                mock.patch(V + '_gemini_ic_second_opinion') as gemini, \
                mock.patch(V + 'ic_genuineness') as genuineness, keep_spy as keep, _now_on_commit():
            out = self.run_cmd('--run', *args)
        gemini.assert_not_called()
        genuineness.assert_not_called()
        return out, f, seam, keep

    def test_run_needs_a_limit_and_a_cost_cap(self):
        for args in (['--run'], ['--run', '--limit', '5'], ['--run', '--max-cost-usd', '1']):
            with self.subTest(args=args), self.assertRaises(CommandError):
                self.run_cmd(*args)

    def test_the_limit_and_the_cap_have_ceilings(self):
        for args in (['--limit', '0', '--max-cost-usd', '1'], ['--limit', str(cmd.MAX_LIMIT + 1), '--max-cost-usd', '1'],
                     ['--limit', '5', '--max-cost-usd', '0'], ['--limit', '5', '--max-cost-usd', '5.01'],
                     ['--limit', '5', '--max-cost-usd', 'lots'], ['--limit', '5', '--max-cost-usd', 'NaN']):
            with self.subTest(args=args), self.assertRaises(CommandError):
                self.run_cmd('--run', *args)

    def test_it_stores_the_text_through_ocr_keep_only_and_changes_nothing_else(self):
        docs = [self.doc(), self.doc()]
        before = self.snapshot()
        out, fetch, seam, keep = self._run('--limit', '10', '--max-cost-usd', '1')
        self.assertEqual(seam.call_count, 2)
        self.assertEqual(keep.call_count, 2)
        for d in docs:
            row = self.kept(d)
            self.assertEqual((row.text, row.source, row.reader), (CARD_TEXT, 'vision_ocr', 'capture_parent_ic_text'))
        self.assertEqual(self.snapshot(), before)   # no document field, verdict, status or other row moved
        self.assertIn('stored: 2', out)
        for private in (FAKE_NRIC, FAKE_NAME, 'KAD PENGENALAN', 'blob'):
            self.assertNotIn(private, out)

    def test_a_re_run_skips_what_is_stored(self):
        first, second = self.doc(), self.doc()
        ApplicantDocumentOcrText.objects.create(document=first, text='EARLIER MADE UP', source='vision_ocr',
                                                reader='run_vision_for_document', stored_at=timezone.now())
        out, fetch, seam, _ = self._run('--limit', '10', '--max-cost-usd', '1')
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(self.kept(first).text, 'EARLIER MADE UP')
        self.assertEqual(self.kept(second).reader, 'capture_parent_ic_text')
        out, fetch, seam, _ = self._run('--limit', '10', '--max-cost-usd', '1')
        fetch.assert_not_called()
        self.assertIn('to read (limit 10): 0', out)

    def test_superseded_queued_and_other_documents_are_not_read(self):
        old = self.doc(superseded_at=timezone.now())
        queued = self.doc(read_state='pending')
        student_ic = self.doc('ic')
        live = self.doc()
        self.assertEqual(cmd.parent_ic_capture_ids(), [live.pk])
        self._run('--limit', '10', '--max-cost-usd', '1')
        for d in (old, queued, student_ic):
            self.assertIsNone(self.kept(d))
        self.assertIsNotNone(self.kept(live))

    def test_the_limit_stops_it(self):
        docs = [self.doc() for _ in range(3)]
        out, fetch, _, _ = self._run('--limit', '2', '--max-cost-usd', '1')
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual([bool(self.kept(d)) for d in docs], [True, True, False])

    def test_the_cost_cap_stops_it_before_the_read_that_would_pass_it(self):
        docs = [self.doc() for _ in range(3)]
        out, fetch, _, _ = self._run('--limit', '10', '--max-cost-usd', '0.003')   # 2 units at US$0.0015
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual([bool(self.kept(d)) for d in docs], [True, True, False])
        self.assertIn('STOPPED: cost cap', out)
        self.assertIn('not reached: 1', out)

    def test_a_failing_document_is_counted_and_the_run_carries_on(self):
        bad, good = self.doc(), self.doc()
        real = vision.extract_mykad

        def read(image, content_type='', *, text_out=None):
            if image == b'BAD':
                raise RuntimeError('made up failure with ' + FAKE_NRIC)
            return real(image, content_type, text_out=text_out)
        with mock.patch(V + 'extract_mykad', side_effect=read), \
                self.assertLogs('apps.scholarship.management.commands.capture_parent_ic_text', 'WARNING') as logs:
            with mock.patch(V + '_fetch_image_bytes', side_effect=lambda p: b'BAD' if p == 'bad' else b'IMG'):
                ApplicantDocument.objects.filter(pk=bad.pk).update(storage_path='bad')
                with _vision(), _now_on_commit():
                    out = self.run_cmd('--run', '--limit', '10', '--max-cost-usd', '1')
        self.assertIn('error: 1', out)
        self.assertIn(f'error ids: {bad.pk}', out)
        self.assertIn('stored: 1', out)
        self.assertIsNotNone(self.kept(good))
        self.assertNotIn(FAKE_NRIC, ' '.join(logs.output) + out)

    def test_reason_codes_for_a_failed_fetch_a_failed_read_and_no_text(self):
        d = self.doc()
        out, _, seam, _ = self._run('--limit', '10', '--max-cost-usd', '1', fetch=None)
        seam.assert_not_called()
        self.assertIn(f'fetch_failed ids: {d.pk}', out)
        out, _, _, _ = self._run('--limit', '10', '--max-cost-usd', '1', text='', error='Bad image data.')
        self.assertIn(f'read_failed ids: {d.pk}', out)
        out, _, _, _ = self._run('--limit', '10', '--max-cost-usd', '1', text='  ')
        self.assertIn(f'no_text ids: {d.pk}', out)
        self.assertIsNone(self.kept(d))

    def test_it_stops_when_the_first_reads_all_fail(self):
        for _ in range(cmd.FAIL_FAST + 2):
            self.doc()
        out, fetch, _, _ = self._run('--limit', '50', '--max-cost-usd', '1', text='', error='403 made up')
        self.assertEqual(fetch.call_count, cmd.FAIL_FAST)
        self.assertIn('STOPPED: the first', out)
        self.assertIn('not reached: 2', out)
