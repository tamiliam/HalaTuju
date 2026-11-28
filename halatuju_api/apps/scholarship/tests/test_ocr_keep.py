"""OCR-first S0b: the text a read saw on a document is kept (``ApplicantDocumentOcrText``), privately,
and deleted with the document. Every OCR and model seam is mocked; the text is made up.

Pins: a read stores it (both choke points, both sources, and the upload read end to end); the write runs
only after the caller commits; a long text is cut with a marker; a blank read stores nothing and does not
fail; a storage error never fails or changes the read; deleting the document (or its application) deletes
the text; no serializer carries it, and only the listed modules may name it.

The write is handed to ``transaction.on_commit``, and a TestCase never commits, so each read runs inside
``self.committed()`` (``captureOnCommitCallbacks(execute=True)``), which runs the write as a commit would.
"""
import os
import re
from contextlib import ExitStack
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase

from apps.scholarship import ocr_keep, upload_read, vision
from apps.scholarship.models import ApplicantDocument, ApplicantDocumentOcrText, ScholarshipApplication
from apps.scholarship.serializers import ApplicantDocumentSerializer
from apps.scholarship.tests.factories import create_document, make_application, make_student

V = 'apps.scholarship.vision.'
VISION_TEXT = 'KWSP PENYATA AHLI\nMADE UP LINE ONE\nMADE UP LINE TWO'
LAYER_TEXT = 'DIGITAL STATEMENT\nTHIS IS A MADE UP TEXT LAYER OF ENOUGH LENGTH'
FIELD = 'ocr_text'   # nothing a client sees may carry a field of this name, or the text


def _vision(text=VISION_TEXT, error=None):
    return mock.patch(V + '_vision_words', return_value={'words': [], 'text': text, 'error': error})


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.app = make_application(student=make_student(name='MADE UP NAME', nric='010101-01-0101'))

    def doc(self, doc_type='epf', content_type='image/jpeg'):
        return create_document(application=self.app, doc_type=doc_type, storage_path='blob',
                               content_type=content_type)

    def kept(self, doc):
        return ApplicantDocumentOcrText.objects.filter(document_id=doc.pk).first()

    def committed(self):
        return self.captureOnCommitCallbacks(execute=True)


class TestStoredOnARead(_Base):
    def test_a_vision_read_is_kept(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'), _vision(), self.committed():
            r = vision.ocr_document_full(doc)
        self.assertEqual(r['text'], VISION_TEXT)
        row = self.kept(doc)
        self.assertEqual((row.text, row.source, row.reader), (VISION_TEXT, 'vision_ocr', 'ocr_document_full'))
        self.assertIsNotNone(row.stored_at)

    def test_a_digital_pdf_layer_is_kept_with_no_vision_call(self):
        doc = self.doc(content_type='application/pdf')
        with mock.patch(V + '_fetch_image_bytes', return_value=b'%PDF-1.7'), \
                mock.patch(V + '_pdf_text_layer', return_value=LAYER_TEXT), _vision() as words, self.committed():
            r = vision.ocr_document_full(doc)
        words.assert_not_called()
        self.assertEqual(r, {'text': LAYER_TEXT, 'words': None, 'image': b'%PDF-1.7', 'error': None})
        self.assertEqual((self.kept(doc).text, self.kept(doc).source), (LAYER_TEXT, 'pdf_text_layer'))

    def test_ocr_document_keeps_vision_text(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'), \
                mock.patch(V + '_vision_document_text', return_value={'text': VISION_TEXT, 'error': None}), \
                self.committed():
            r = vision.ocr_document(doc)
        self.assertEqual(r, {'text': VISION_TEXT, 'error': None})
        self.assertEqual((self.kept(doc).source, self.kept(doc).reader), ('vision_ocr', 'ocr_document'))

    def test_a_newer_read_replaces_the_text(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'):
            with _vision('FIRST MADE UP READ'), self.committed():
                vision.ocr_document_full(doc)
            with _vision('SECOND MADE UP READ'), self.committed():
                vision.ocr_document_full(doc)
        self.assertEqual(ApplicantDocumentOcrText.objects.filter(document_id=doc.pk).count(), 1)
        self.assertEqual(self.kept(doc).text, 'SECOND MADE UP READ')

    def test_the_upload_read_keeps_the_text_end_to_end(self):
        """The queued upload read (``_read_copy``) of a supporting document, model and OCR mocked."""
        doc = self.doc('epf')
        with ExitStack() as s:
            def p(target, **kw):
                return s.enter_context(mock.patch(target, **kw))
            p('apps.scholarship.imaging.convert_heic_to_jpeg', return_value=None)
            p(V + '_fetch_image_bytes', return_value=b'IMG')
            s.enter_context(_vision())
            p('apps.scholarship.views._reslot_income_doc', return_value=False)
            p(V + 'run_vision_match_for_document', return_value=None)
            p('apps.scholarship.views.DocumentListCreateView._maybe_extract_fields', return_value=None)
            p('apps.scholarship.genuineness.sample_stamp.check_enabled', return_value=False)
            with self.committed():
                upload_read._read_copy(self.app, doc)
        self.assertEqual(self.kept(doc).text, VISION_TEXT)
        doc.refresh_from_db()
        self.assertNotIn(VISION_TEXT, str(doc.vision_fields or ''))   # never copied into vision_fields


class TestOcrDocumentReadsAPdfLayerOnce(_Base):
    """Fix round: ``ocr_document`` reads a PDF's text layer once, and answers exactly as before."""

    def _read(self, layer, png=b'PNG', vision_text=VISION_TEXT):
        doc = self.doc(content_type='application/pdf')
        with mock.patch(V + '_fetch_image_bytes', return_value=b'%PDF-1.7'), \
                mock.patch(V + '_pdf_text_layer', return_value=layer) as lay, \
                mock.patch(V + '_pdf_first_page_png', return_value=png), \
                mock.patch(V + '_vision_document_text',
                           return_value={'text': vision_text, 'error': None}) as seam, self.committed():
            r = vision.ocr_document(doc)
        lay.assert_called_once()
        return doc, r, seam

    def test_a_digital_pdf(self):
        doc, r, seam = self._read(LAYER_TEXT)
        seam.assert_not_called()
        self.assertEqual(r, {'text': LAYER_TEXT, 'error': None})
        self.assertEqual(self.kept(doc).source, 'pdf_text_layer')

    def test_a_scanned_pdf_sends_page_one_to_vision(self):
        doc, r, seam = self._read('CamScanner')
        seam.assert_called_once_with(b'PNG')
        self.assertEqual(r, {'text': VISION_TEXT, 'error': None})
        self.assertEqual(self.kept(doc).source, 'vision_ocr')

    def test_a_pdf_that_will_not_rasterise(self):
        doc, r, seam = self._read('', png=None)
        seam.assert_not_called()
        self.assertEqual(r, {'text': '', 'error': 'Bad image data.'})
        self.assertIsNone(self.kept(doc))


class TestTheCap(_Base):
    def test_a_long_text_keeps_its_head_and_a_marker(self):
        doc = self.doc()
        long_text = 'A' * ocr_keep.MAX_CHARS + 'TAIL'
        with self.committed():
            self.assertTrue(ocr_keep.keep(doc, long_text, source='other'))
        text = self.kept(doc).text
        self.assertTrue(text.startswith('A' * ocr_keep.MAX_CHARS))
        self.assertNotIn('TAIL', text)
        self.assertTrue(text.endswith(f'cut at {ocr_keep.MAX_CHARS} of {len(long_text)} characters]'))

    def test_a_text_that_fits_is_unchanged(self):
        self.assertEqual(ocr_keep.capped('B' * ocr_keep.MAX_CHARS), 'B' * ocr_keep.MAX_CHARS)


class TestAfterTheCallersCommit(_Base):
    """Fix round: the key is DEFERRABLE INITIALLY DEFERRED, so the write waits for the caller's commit."""

    def test_nothing_is_written_inside_the_callers_transaction(self):
        doc = self.doc()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.assertTrue(ocr_keep.keep(doc, 'MADE UP TEXT', source='other'))
            self.assertIsNone(self.kept(doc))
        self.assertEqual(len(callbacks), 1)
        self.assertIsNone(self.kept(doc))   # a read that rolled back keeps nothing

    def test_a_document_deleted_before_the_commit_stores_nothing(self):
        doc = self.doc()
        with self.committed():
            self.assertTrue(ocr_keep.keep(doc, 'MADE UP TEXT', source='other'))
            ApplicantDocument.objects.filter(pk=doc.pk).delete()
        self.assertFalse(ApplicantDocumentOcrText.objects.exists())


class TestNothingToKeep(_Base):
    def test_a_blank_read_stores_nothing_and_does_not_fail(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'), \
                _vision('', error='Bad image data.'), self.committed():
            r = vision.ocr_document_full(doc)
        self.assertEqual(r['error'], 'Bad image data.')
        self.assertIsNone(self.kept(doc))

    def test_a_failed_fetch_stores_nothing(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=None), self.committed():
            self.assertEqual(vision.ocr_document(doc), {'text': '', 'error': 'could not fetch image'})
        self.assertIsNone(self.kept(doc))

    def test_a_blank_re_read_keeps_the_earlier_text(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'):
            with _vision(), self.committed():
                vision.ocr_document_full(doc)
            with _vision('   ', error='timeout'), self.committed():
                vision.ocr_document_full(doc)
        self.assertEqual(self.kept(doc).text, VISION_TEXT)

    def test_an_unsaved_document_is_skipped(self):
        self.assertFalse(ocr_keep.keep(ApplicantDocument(), 'TEXT', source='other'))
        self.assertFalse(ocr_keep.keep(mock.MagicMock(), 'TEXT', source='other'))


class TestAStorageErrorNeverBreaksTheRead(_Base):
    def test_the_read_is_unchanged_and_nothing_is_stored(self):
        doc = self.doc()
        boom = mock.patch.object(ApplicantDocumentOcrText.objects, 'update_or_create',
                                 side_effect=DatabaseError('made up failure'))
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'), _vision(), boom, \
                self.assertLogs('apps.scholarship.ocr_keep', level='WARNING') as logs, self.committed():
            r = vision.ocr_document_full(doc)
        self.assertEqual(r, {'text': VISION_TEXT, 'words': [], 'image': b'IMG', 'error': None})
        self.assertIsNone(self.kept(doc))
        self.assertNotIn('MADE UP', ' '.join(logs.output))   # the log never carries the text
        doc.refresh_from_db()                                  # the read's transaction is still usable

    def test_a_failure_handing_on_the_write_is_swallowed(self):
        with mock.patch('apps.scholarship.ocr_keep.transaction.on_commit', side_effect=RuntimeError('made up')):
            self.assertFalse(ocr_keep.keep(self.doc(), 'TEXT', source='other'))


class TestDeletedWithTheDocument(_Base):
    def _keep(self, doc):
        with self.committed():
            self.assertTrue(ocr_keep.keep(doc, 'MADE UP TEXT', source='other', reader='test'))
        self.assertIsNotNone(self.kept(doc))

    def test_deleting_the_document_deletes_the_text(self):
        doc = self.doc()
        self._keep(doc)
        doc.delete()
        self.assertFalse(ApplicantDocumentOcrText.objects.exists())

    def test_a_queryset_delete_deletes_the_text(self):
        """The student's Remove deletes by queryset (views/documents.py)."""
        doc = self.doc()
        self._keep(doc)
        ApplicantDocument.objects.filter(id__in=[doc.id]).delete()
        self.assertFalse(ApplicantDocumentOcrText.objects.exists())

    def test_deleting_the_application_deletes_the_text(self):
        app = make_application(student=make_student(name='OTHER MADE UP', nric='020202-02-0202'))
        doc = create_document(application=app, doc_type='epf', storage_path='blob2')
        self._keep(doc)
        ScholarshipApplication.objects.filter(pk=app.pk).delete()
        self.assertFalse(ApplicantDocumentOcrText.objects.exists())


class TestPrivate(_Base):
    def test_the_document_serializer_never_carries_it(self):
        doc = self.doc()
        with self.committed():
            self.assertTrue(ocr_keep.keep(doc, 'MADE UP SECRET TEXT', source='other'))
        data = ApplicantDocumentSerializer(doc).data
        self.assertNotIn(FIELD, data)
        self.assertNotIn('ocr', ' '.join(data).lower())
        self.assertNotIn('MADE UP SECRET TEXT', str(data))

    def test_the_document_has_no_way_to_reach_it(self):
        names = {f.name for f in ApplicantDocument._meta.get_fields()}
        self.assertFalse({n for n in names if 'ocr' in n.lower()})

    #: (a) The only modules that may name the table (migrations aside): its model and ocr_keep.
    TABLE = {
        'scholarship/models/__init__.py',
        'scholarship/models/documents.py',
        'scholarship/ocr_keep.py',
    }
    #: (b) The only modules that may call an ocr_keep READ function: owner-approved read-only jobs.
    READERS = {
        # #85: re-scores payslips on their stored text (in memory only, never printed), no read, no AI call.
        'scholarship/management/commands/rescore_salary_statutory.py',
        # OCR-15: the one-off parent IC capture asks which documents already have text (ids only).
        'scholarship/management/commands/capture_parent_ic_text.py',
        # OCR-16: the paid eval scores slips on their text and finds sample words (ids printed only).
        'scholarship/management/commands/eval_genuineness_38.py',
    }
    #: (c) The modules that call ``ocr_keep.keep`` (unchanged by the read path).
    KEEPERS = {
        'scholarship/vision/ocr.py',
        'scholarship/vision/ic.py',   # OCR-15: the IC / parent IC read keeps its Vision text
        'scholarship/management/commands/capture_parent_ic_text.py',
    }
    TABLE_PATTERN = re.compile(r'ApplicantDocumentOcrText|applicant_document_ocr_text')
    READ_PATTERN = re.compile(r'\b(?:kept_texts|ids_with_kept_text\w*)\b')
    #: Naming ocr_keep at all (an import, an alias, a docstring) is for the modules above only.
    MODULE_PATTERN = re.compile(r'ocr_keep')

    @classmethod
    def _naming(cls, pattern):
        """The app modules (tests and migrations aside) whose source matches ``pattern``."""
        apps_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        found = set()
        for root, dirs, files in os.walk(apps_dir):
            dirs[:] = [d for d in dirs if d not in ('tests', 'migrations', '__pycache__')]
            for name in files:
                if name.endswith('.py'):
                    path = os.path.join(root, name)
                    with open(path, encoding='utf-8') as fh:
                        if pattern.search(fh.read()):
                            found.add(os.path.relpath(path, apps_dir).replace(os.sep, '/'))
        return found

    def test_nothing_else_names_it(self):
        """No serializer, admin, export, view or job may name the table: only its model and ocr_keep."""
        self.assertEqual(self._naming(self.TABLE_PATTERN), self.TABLE)

    def test_only_the_listed_jobs_call_the_read_path(self):
        self.assertEqual(self._naming(self.READ_PATTERN) - {'scholarship/ocr_keep.py'}, self.READERS)

    def test_only_the_listed_modules_name_ocr_keep(self):
        """A new module cannot reach the text through an alias: naming ocr_keep at all needs a list."""
        self.assertEqual(self._naming(self.MODULE_PATTERN),
                         self.READERS | self.KEEPERS | {'scholarship/ocr_keep.py', 'scholarship/models/documents.py'})

    def test_the_guard_patterns_catch_what_they_guard(self):
        self.assertTrue(self.READ_PATTERN.search('ocr_keep.ids_with_kept_text_containing(w, ids)'))
        self.assertTrue(self.READ_PATTERN.search('from apps.scholarship.ocr_keep import kept_texts'))
        self.assertFalse(self.READ_PATTERN.search('ocr_keep.keep(doc, text, source=s)'))
        self.assertFalse(self.TABLE_PATTERN.search('from apps.scholarship import ocr_keep'))


class TestTheReadPath(_Base):
    """OCR-16: the one approved read path. Synthetic text; each read is bounded by the caller's ids."""

    def _store(self, text, reader='test'):
        doc = self.doc()
        with self.committed():
            self.assertTrue(ocr_keep.keep(doc, text, source='other', reader=reader))
        return doc

    def test_kept_texts_returns_only_the_ids_asked_for(self):
        a, b, plain = self._store('MADE UP A'), self._store('MADE UP B'), self.doc()
        self.assertEqual(ocr_keep.kept_texts([a.pk, plain.pk]), {a.pk: 'MADE UP A'})
        self.assertEqual(ocr_keep.kept_texts({a.pk, b.pk}), {a.pk: 'MADE UP A', b.pk: 'MADE UP B'})
        self.assertEqual(ocr_keep.kept_texts([]), {})
        self.assertEqual(ocr_keep.kept_texts(ApplicantDocument.objects.filter(pk=b.pk).values('pk')),
                         {b.pk: 'MADE UP B'})

    def test_ids_with_kept_text_and_by_reader(self):
        a, b, plain = self._store('MADE UP A', reader='one'), self._store('MADE UP B', reader='two'), self.doc()
        ids = [a.pk, b.pk, plain.pk]
        self.assertEqual(ocr_keep.ids_with_kept_text(ids), {a.pk, b.pk})
        self.assertEqual(ocr_keep.ids_with_kept_text(ids, reader='two'), {b.pk})
        self.assertEqual(ocr_keep.ids_with_kept_text([plain.pk]), set())

    def test_ids_with_kept_text_containing_any_word_ignoring_case(self):
        a, b, c = self._store('MADE UP Sample STAMP'), self._store('made up contoh'), self._store('MADE UP')
        ids = [a.pk, b.pk, c.pk]
        self.assertEqual(ocr_keep.ids_with_kept_text_containing(('sample', 'contoh'), ids), {a.pk, b.pk})
        self.assertEqual(ocr_keep.ids_with_kept_text_containing(('sample',), [b.pk, c.pk]), set())
        self.assertEqual(ocr_keep.ids_with_kept_text_containing((), ids), set())   # no words is never "all"

    def test_a_read_without_ids_is_refused(self):
        self._store('MADE UP A')
        for bad in (None, 5, '5'):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                ocr_keep.kept_texts(bad)
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                ocr_keep.ids_with_kept_text(bad)
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                ocr_keep.ids_with_kept_text_containing(('made',), bad)

    def test_the_reads_never_log_the_text(self):
        a = self._store('MADE UP SECRET')
        with self.assertNoLogs('apps.scholarship.ocr_keep'):
            ocr_keep.kept_texts([a.pk])
            ocr_keep.ids_with_kept_text_containing(('secret',), [a.pk])


class TestWritesRefused(_Base):
    """OCR-16: the read-only jobs' write guard, owned here: no keep, no direct save, restored after."""

    def test_keep_stores_nothing_inside_it(self):
        doc = self.doc()
        with ocr_keep.writes_refused('a made up job'), self.committed():
            self.assertFalse(ocr_keep.keep(doc, 'MADE UP TEXT', source='other'))
        self.assertIsNone(self.kept(doc))

    def test_a_write_handed_on_before_it_stores_nothing_inside_it(self):
        doc = self.doc()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.assertTrue(ocr_keep.keep(doc, 'MADE UP TEXT', source='other'))
        with ocr_keep.writes_refused('a made up job'):
            for fn in callbacks:
                fn()
        self.assertIsNone(self.kept(doc))

    def test_a_direct_save_raises_and_is_restored_after(self):
        doc = self.doc()
        with ocr_keep.writes_refused('a made up job'):
            with self.assertRaisesMessage(RuntimeError, 'a made up job writes no OCR text'):
                ApplicantDocumentOcrText.objects.create(document=doc, text='MADE UP', source='other')
            with ocr_keep.writes_refused('nested'):
                self.assertFalse(ocr_keep.keep(doc, 'MADE UP', source='other'))
            self.assertFalse(ocr_keep.keep(doc, 'MADE UP', source='other'))   # still refused after the inner one
        self.assertFalse(ApplicantDocumentOcrText.objects.exists())
        with self.committed():
            self.assertTrue(ocr_keep.keep(doc, 'MADE UP AFTER', source='other'))
        self.assertEqual(self.kept(doc).text, 'MADE UP AFTER')
        self.assertEqual(ocr_keep._refusing, 0)
