"""OCR-first S0b: the text a read saw on a document is kept (``ApplicantDocumentOcrText``), privately,
and deleted with the document. Every OCR and model seam is mocked; the text is made up.

Pins: a read stores it (both choke points, both sources, and the upload read end to end); a blank read
stores nothing and does not fail; a storage error never fails or changes the read; deleting the document
(or its application) deletes the text; no serializer carries it, and only the listed modules may name it.
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


class TestStoredOnARead(_Base):
    def test_a_vision_read_is_kept(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'), _vision():
            r = vision.ocr_document_full(doc)
        self.assertEqual(r['text'], VISION_TEXT)
        row = self.kept(doc)
        self.assertEqual((row.text, row.source, row.reader), (VISION_TEXT, 'vision_ocr', 'ocr_document_full'))
        self.assertIsNotNone(row.stored_at)

    def test_a_digital_pdf_layer_is_kept_with_no_vision_call(self):
        doc = self.doc(content_type='application/pdf')
        with mock.patch(V + '_fetch_image_bytes', return_value=b'%PDF-1.7'), \
                mock.patch(V + '_pdf_text_layer', return_value=LAYER_TEXT), _vision() as words:
            r = vision.ocr_document_full(doc)
        words.assert_not_called()
        self.assertEqual(r, {'text': LAYER_TEXT, 'words': None, 'image': b'%PDF-1.7', 'error': None})
        self.assertEqual((self.kept(doc).text, self.kept(doc).source), (LAYER_TEXT, 'pdf_text_layer'))

    def test_ocr_document_keeps_vision_text(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'), \
                mock.patch(V + '_vision_document_text', return_value={'text': VISION_TEXT, 'error': None}):
            r = vision.ocr_document(doc)
        self.assertEqual(r, {'text': VISION_TEXT, 'error': None})
        self.assertEqual((self.kept(doc).source, self.kept(doc).reader), ('vision_ocr', 'ocr_document'))

    def test_ocr_document_names_a_pdf_layer_as_its_source(self):
        doc = self.doc(content_type='application/pdf')
        with mock.patch(V + '_fetch_image_bytes', return_value=b'%PDF-1.7'), \
                mock.patch(V + '_pdf_text_layer', return_value=LAYER_TEXT), \
                mock.patch(V + '_vision_document_text') as seam:
            r = vision.ocr_document(doc)
        seam.assert_not_called()
        self.assertEqual(r, {'text': LAYER_TEXT, 'error': None})
        self.assertEqual(self.kept(doc).source, 'pdf_text_layer')

    def test_a_newer_read_replaces_the_text(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'):
            with _vision('FIRST MADE UP READ'):
                vision.ocr_document_full(doc)
            with _vision('SECOND MADE UP READ'):
                vision.ocr_document_full(doc)
        self.assertEqual(ApplicantDocumentOcrText.objects.filter(document_id=doc.pk).count(), 1)
        self.assertEqual(self.kept(doc).text, 'SECOND MADE UP READ')

    def test_the_upload_read_keeps_the_text_end_to_end(self):
        """The queued upload read (``_read_copy``) of a supporting document, model and OCR mocked."""
        doc = self.doc('epf')
        with ExitStack() as s:
            p = lambda target, **kw: s.enter_context(mock.patch(target, **kw))  # noqa: E731 — short local helper in a test
            p('apps.scholarship.imaging.convert_heic_to_jpeg', return_value=None)
            p(V + '_fetch_image_bytes', return_value=b'IMG')
            s.enter_context(_vision())
            p('apps.scholarship.views._reslot_income_doc', return_value=False)
            p(V + 'run_vision_match_for_document', return_value=None)
            p('apps.scholarship.views.DocumentListCreateView._maybe_extract_fields', return_value=None)
            p('apps.scholarship.genuineness.sample_stamp.check_enabled', return_value=False)
            upload_read._read_copy(self.app, doc)
        self.assertEqual(self.kept(doc).text, VISION_TEXT)
        doc.refresh_from_db()
        self.assertNotIn(VISION_TEXT, str(doc.vision_fields or ''))   # never copied into vision_fields


class TestNothingToKeep(_Base):
    def test_a_blank_read_stores_nothing_and_does_not_fail(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'), _vision('', error='Bad image data.'):
            r = vision.ocr_document_full(doc)
        self.assertEqual(r['error'], 'Bad image data.')
        self.assertIsNone(self.kept(doc))

    def test_a_failed_fetch_stores_nothing(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=None):
            self.assertEqual(vision.ocr_document(doc), {'text': '', 'error': 'could not fetch image'})
        self.assertIsNone(self.kept(doc))

    def test_a_blank_re_read_keeps_the_earlier_text(self):
        doc = self.doc()
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'):
            with _vision():
                vision.ocr_document_full(doc)
            with _vision('   ', error='timeout'):
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
                self.assertLogs('apps.scholarship.ocr_keep', level='WARNING') as logs:
            r = vision.ocr_document_full(doc)
        self.assertEqual(r, {'text': VISION_TEXT, 'words': [], 'image': b'IMG', 'error': None})
        self.assertIsNone(self.kept(doc))
        self.assertNotIn('MADE UP', ' '.join(logs.output))   # the log never carries the text
        doc.refresh_from_db()                                  # the read's transaction is still usable

    def test_a_failing_source_callable_is_swallowed(self):
        def bad():
            raise ValueError('made up')
        self.assertFalse(ocr_keep.keep(self.doc(), 'TEXT', source=bad))


class TestDeletedWithTheDocument(_Base):
    def _keep(self, doc):
        self.assertTrue(ocr_keep.keep(doc, 'MADE UP TEXT', source='other', reader='test'))

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
        self.assertTrue(ocr_keep.keep(doc, 'MADE UP SECRET TEXT', source='other'))
        data = ApplicantDocumentSerializer(doc).data
        self.assertNotIn(FIELD, data)
        self.assertNotIn('ocr', ' '.join(data).lower())
        self.assertNotIn('MADE UP SECRET TEXT', str(data))

    def test_the_document_has_no_way_to_reach_it(self):
        names = {f.name for f in ApplicantDocument._meta.get_fields()}
        self.assertFalse({n for n in names if 'ocr' in n.lower()})

    ALLOWED = {
        'scholarship/models/__init__.py',
        'scholarship/models/documents.py',
        'scholarship/ocr_keep.py',
        'scholarship/vision/ocr.py',
    }
    PATTERN = re.compile(r'ApplicantDocumentOcrText|applicant_document_ocr_text|ocr_keep')

    def test_nothing_else_names_it(self):
        """No serializer, admin, export or view may name the table: only these modules."""
        apps_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        found = set()
        for root, dirs, files in os.walk(apps_dir):
            dirs[:] = [d for d in dirs if d not in ('tests', 'migrations', '__pycache__')]
            for name in files:
                if name.endswith('.py'):
                    path = os.path.join(root, name)
                    with open(path, encoding='utf-8') as fh:
                        if self.PATTERN.search(fh.read()):
                            found.add(os.path.relpath(path, apps_dir).replace(os.sep, '/'))
        self.assertEqual(found, self.ALLOWED)
