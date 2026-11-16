"""H9 - an uploaded SAMPLE (stamped SAMPLE / CONTOH / SPECIMEN) is flagged not genuine and never
accepted; a real document that merely has the word "contoh" in its normal text is not flagged.
The model is mocked (no live call, no document read)."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import help_engine, resolution, upload_read
from apps.scholarship.genuineness import sample_stamp
from apps.scholarship.genuineness.bands import needs_attention
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.serializers import ApplicantDocumentSerializer
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

SEAM = 'apps.scholarship.vision._call_gemini_json'
IMG = 'apps.scholarship.vision._as_image_for_gemini'


def _doc(doc_type='str', **kw):
    app = make_application(cohort=make_cohort(), student=make_student())
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, storage_path='test/' + doc_type, content_type='image/jpeg',
        vision_fields=kw.pop('vision_fields', {'authenticity': {'status': 'genuine', 'reason': 'ok'}}),
        **kw)


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestSampleCheck(TestCase):
    def test_stamped_sample_is_flagged_not_genuine_with_both_messages(self):
        doc = _doc('str')
        with patch(SEAM, return_value={'is_sample': True, 'reason': 'x'}) as m, patch(IMG, return_value=('i', 'image/jpeg')):
            self.assertTrue(sample_stamp.check_uploaded_sample(doc, b'img', text='CONTOH  STR'))
        self.assertTrue(m.called)
        doc.refresh_from_db()
        auth = doc.vision_fields['authenticity']
        self.assertEqual(auth['status'], 'not_str')
        self.assertEqual(auth['doc_seen'], 'sample_document')
        self.assertIn('sample document', auth['reason'])            # the reviewer's reason
        self.assertEqual(auth['scored_status'], 'genuine')
        self.assertTrue(needs_attention(auth['status'], 'str'))     # the existing not-genuine path
        shown = ApplicantDocumentSerializer(doc).data['authenticity']   # what the student's card reads
        self.assertEqual((shown['status'], shown['doc_seen']), ('not_str', 'sample_document'))
        # never accepted: the Action Centre keeps the request open, the coach has its own verdict
        self.assertEqual(resolution.doc_match_verdict(doc), 'mismatch')
        self.assertEqual(help_engine.verdict_for_document(doc), 'sample_document')

    def test_ic_is_asked_without_text(self):
        doc = _doc('ic')
        with patch(SEAM, return_value={'is_sample': True, 'reason': 'x'}), patch(IMG, return_value=('i', 'image/jpeg')):
            self.assertTrue(sample_stamp.check_uploaded_sample(doc, b'img'))

    def test_real_document_with_contoh_in_its_text_is_not_flagged(self):
        doc = _doc('str')
        with patch(SEAM, return_value={'is_sample': False, 'reason': 'ordinary text'}), patch(IMG, return_value=('i', 'image/jpeg')):
            self.assertFalse(sample_stamp.check_uploaded_sample(doc, b'img', text='contoh tandatangan pemohon'))
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'genuine')
        self.assertFalse(sample_stamp.is_sample_flagged(doc))
        self.assertNotEqual(resolution.doc_match_verdict(doc), 'mismatch')

    def test_text_without_a_sample_word_never_asks_the_model(self):
        doc = _doc('str')
        with patch(SEAM) as m:
            self.assertFalse(sample_stamp.check_uploaded_sample(doc, b'img', text='Kementerian Kewangan STR'))
        m.assert_not_called()

    def test_outage_and_error_mean_no_flag(self):
        doc = _doc('str')
        for reply in ({'_error': 'down'}, None, {}):
            with patch(SEAM, return_value=reply), patch(IMG, return_value=('i', 'image/jpeg')):
                self.assertFalse(sample_stamp.check_uploaded_sample(doc, b'img', text='SAMPLE'))
        with patch(SEAM, side_effect=RuntimeError('boom')), patch(IMG, return_value=('i', 'image/jpeg')):
            self.assertFalse(sample_stamp.check_uploaded_sample(doc, b'img', text='SAMPLE'))
        self.assertFalse(sample_stamp.is_sample_flagged(doc))

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_flag_off_means_no_check(self):
        doc = _doc('str')
        with patch(SEAM) as m:
            self.assertFalse(sample_stamp.check_uploaded_sample(doc, b'img', text='SAMPLE'))
        m.assert_not_called()

    def test_read_copy_runs_the_check_after_the_read(self):
        doc = _doc('str')
        ocr = {'text': 'SAMPLE', 'image': b'img', 'words': None, 'error': None}
        with patch('apps.scholarship.vision.ocr_document_full', return_value=ocr), \
                patch('apps.scholarship.vision.run_vision_match_for_document', return_value=None), \
                patch('apps.scholarship.views.DocumentListCreateView._maybe_extract_fields', return_value=None), \
                patch('apps.scholarship.imaging.convert_heic_to_jpeg'), \
                patch.object(sample_stamp, 'check_uploaded_sample', return_value=True) as chk:
            upload_read._read_copy(doc.application, doc)
        chk.assert_called_once()
        self.assertEqual(chk.call_args.kwargs.get('text'), 'SAMPLE')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestSampleCheckFixRound1(TestCase):
    def test_clean_result_records_the_version_but_an_outage_does_not(self):
        doc = _doc('str')
        with patch(SEAM, return_value={'is_sample': False, 'reason': 'ordinary'}), patch(IMG, return_value=('i', 'image/jpeg')):
            self.assertFalse(sample_stamp.check_uploaded_sample(doc, b'img', text='contoh tandatangan'))
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['sample_check_version'], sample_stamp.SAMPLE_CHECK_VERSION)
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'genuine')
        gated = _doc('str')                  # text with no sample word: checked by the gate, clean
        self.assertFalse(sample_stamp.check_uploaded_sample(gated, b'img', text='Kementerian Kewangan'))
        gated.refresh_from_db()
        self.assertEqual(gated.vision_fields['sample_check_version'], sample_stamp.SAMPLE_CHECK_VERSION)
        down = _doc('str')                   # no answer: never checked, nothing recorded
        with patch(SEAM, return_value={'_error': 'down'}), patch(IMG, return_value=('i', 'image/jpeg')):
            self.assertFalse(sample_stamp.check_uploaded_sample(down, b'img', text='SAMPLE'))
        down.refresh_from_db()
        self.assertNotIn('sample_check_version', down.vision_fields)

    def test_reviewer_sees_the_sample_reason_on_every_type_the_check_can_flag(self):
        for doc_type in ('bank_statement', 'income_support_doc', 'guardianship_letter', 'semester_result'):
            doc = _doc(doc_type)
            self.assertIsNone(ApplicantDocumentSerializer(doc).data['authenticity'])     # unflagged: still hidden
            with patch(SEAM, return_value={'is_sample': True, 'reason': 'x'}), patch(IMG, return_value=('i', 'image/jpeg')):
                self.assertTrue(sample_stamp.check_uploaded_sample(doc, b'img', text='SAMPLE'))
            doc.refresh_from_db()
            shown = ApplicantDocumentSerializer(doc).data['authenticity']
            self.assertEqual((shown['status'], shown['doc_seen']), ('not_' + doc_type, 'sample_document'))
            self.assertIn('sample document', shown['reason'])

    def test_switch_off_skips_the_check_and_the_extra_storage_fetch(self):
        for env, kw in (({'SAMPLE_CHECK_ENABLED': '0'}, {}), ({}, {'DOC_GENUINENESS_CHECK_ENABLED': False})):
            doc = _doc('ic')
            with override_settings(**kw), patch.dict('os.environ', env), \
                    patch('apps.scholarship.vision._fetch_image_bytes') as fetch, \
                    patch(SEAM) as m:
                upload_read._check_sample(doc, None)
                self.assertFalse(sample_stamp.check_uploaded_sample(doc, b'img', text='SAMPLE'))
            fetch.assert_not_called()
            m.assert_not_called()
        with patch.dict('os.environ', {'SAMPLE_CHECK_ENABLED': '1'}):      # on: the IC image is fetched
            with patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'x') as fetch, \
                    patch.object(sample_stamp, 'check_uploaded_sample', return_value=False):
                upload_read._check_sample(_doc('ic'), None)
            fetch.assert_called_once()
