"""OCR-11 (owner 2026-11-21): an AI read with every real field empty is a FAILED read (cannot read, the
retry path), never a stored 'ok' and never a checked-but-unapproved approval.

* Offer: `candidate_nric_source` (the IC guard writes 'none' on every IC-less read) no longer fills a read;
  an all-empty answer is `read_errors.EMPTY_ANSWER`, judged before the IC guard and its text backstop.
* Results slip / higher results: `_slip_ocr_diag` and the `results_kind_*` routing detection no longer
  fill a read; an all-empty AI answer is `EMPTY_ANSWER`.
* Income approval: an all-empty / all-"no" answer goes through `failed()` (the retry window), so the
  document is still checking, then the officer's, never `approval_missing` ("unapproved").
* The marked white page (TD row 2, item 1): a page white apart from a footer mark passes the blank-page
  guard, reaches the model, and its empty answer is a failed read too.

Synthetic data only: invented names, a made-up IC, blank images.
"""
import io
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.scholarship import offer_reader as orr
from apps.scholarship import vision
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.read_errors import EMPTY_ANSWER
from apps.scholarship.tests.factories import create_document, make_application
from apps.scholarship.tests.test_offer_reader import text_pdf
from apps.scholarship.vision.field_extraction import _build_read_result
from apps.scholarship.vision.judge import BOOKKEEPING_FIELDS, doc_student_verdict

FAKE_IC = '010203-14-5678'
#: What a model answers for a white page: every offer field blank, the IC source 'none'.
EMPTY_OFFER = {**{f: '' for f in orr._FIELDS}, 'candidate_nric_source': 'none', 'warnings': []}


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (600, 800), 'white').save(buf, format='PNG')
    return buf.getvalue()


def _answer(answer):
    """A fake `_call_gemini_json` that gives ``answer`` (a fresh copy) to every call."""
    return mock.patch.object(vision, '_call_gemini_json',
                             side_effect=lambda *a, **k: {**answer, '_model': 'gemini-3.8-flash'})


def _verdict(doc_type, ex):
    return _build_read_result(ApplicantDocument(doc_type=doc_type), ex, names=['ZORBEX A/L QUENTARO'],
                              postcode='', city='', street='', check_address=False)


class BookkeepingNeverFillsARead(SimpleTestCase):

    def test_each_bookkeeping_key_alone_is_not_a_filled_read(self):
        alone = {'offer_letter': {'candidate_nric_source': 'none'},
                 'results_slip': {'_slip_ocr_diag': {'reason': 'no_table'}, 'exam': '', 'results': []},
                 'higher_results': {'results_kind_detected': 'stpm', 'results_kind_markers': ['stpm'],
                                    'results_kind_issuer': 'MPM', 'candidate_name': '', 'results': []}}
        for doc_type, fields in alone.items():
            with self.subTest(doc_type):
                self.assertEqual(doc_student_verdict(doc_type, fields, names=['X']), 'wrong_doc')
        self.assertEqual(BOOKKEEPING_FIELDS, {'candidate_nric_source', '_slip_ocr_diag', 'results_kind_detected',
                                              'results_kind_markers', 'results_kind_issuer'})

    def test_one_real_field_still_fills_it(self):
        self.assertEqual(doc_student_verdict('offer_letter', {'candidate_nric_source': 'none',
                                                              'programme': 'DIPLOMA QORVANE'}, names=['X']), 'ok')


class AnEmptyOfferAnswerIsAFailedRead(SimpleTestCase):

    def test_an_all_empty_answer_is_cannot_read_not_ok(self):
        with _answer(EMPTY_OFFER) as gem:
            ex = orr.read_offer('', image=_png(), content_type='image/png')
        self.assertGreaterEqual(gem.call_count, 1)
        self.assertEqual((ex['error'], ex['fields']), (EMPTY_ANSWER, {}))
        self.assertEqual(ex['offer_reader_version'], '2.10.0')
        self.assertEqual(_verdict('offer_letter', ex)['student_verdict'], 'unreadable')

    def test_the_marked_white_page_with_an_ic_in_its_footer_is_still_a_failed_read(self):
        """TD row 2 item 1: white apart from a "Page 1 of 1" footer (and an IC the text backstop could copy).
        The blank-page guard lets it through (it has a mark); the model sees nothing; the read fails."""
        page = text_pdf([f'Page 1 of 1   {FAKE_IC}'])
        with _answer({**EMPTY_OFFER, 'warnings': ['Only a page footer is visible.']}) as gem:
            ex = orr.read_offer('', image=page, content_type='application/pdf', profile_nric=FAKE_IC)
        self.assertGreaterEqual(gem.call_count, 1)                    # the page reached the model
        self.assertEqual((ex['error'], ex['fields'], ex['warnings']), (EMPTY_ANSWER, {}, []))
        self.assertEqual(_verdict('offer_letter', ex)['student_verdict'], 'unreadable')

    def test_a_read_with_one_field_is_still_an_ok_read(self):
        with _answer({**EMPTY_OFFER, 'programme': 'DIPLOMA QORVANE', 'institution': 'KOLEJ QORVANE'}):
            ex = orr.read_offer('', image=_png(), content_type='image/png')
        self.assertEqual(ex['error'], '')
        self.assertEqual(ex['fields']['programme'], 'DIPLOMA QORVANE')


class AnEmptyResultsAnswerIsAFailedRead(TestCase):

    def _upload(self, doc_type, text):
        app = make_application('profile_complete')
        doc = create_document(application=app, doc_type=doc_type, storage_path=f'{app.id}/r/x')
        empty = {'fields': {'candidate_name': '', 'exam': '', 'results': []}, 'warnings': [], 'error': ''}
        with mock.patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img'), \
             mock.patch('apps.scholarship.vision._extract_slip_deterministic', return_value=(None, {'reason': 'x'})), \
             mock.patch('apps.scholarship.higher_results._exact_read', return_value=(None, '')), \
             mock.patch('apps.scholarship.vision.extract_document_fields', return_value=empty), \
             mock.patch('apps.scholarship.vision.ocr_document', return_value={'text': text, 'error': None}):
            return vision.run_field_extraction_for_document(doc, names=['ZORBEX A/L QUENTARO'])

    def test_an_empty_slip_answer_is_cannot_read_though_the_diag_and_year_backfill_are_there(self):
        vf = self._upload('results_slip', 'SIJIL PELAJARAN MALAYSIA\nPEPERIKSAAN TAHUN 2030\nPage 1 of 1')
        self.assertEqual((vf['student_verdict'], vf['error'], vf['fields']), ('unreadable', EMPTY_ANSWER, {}))

    def test_an_empty_higher_results_answer_is_cannot_read_though_the_kind_was_detected(self):
        vf = self._upload('higher_results', 'MAJLIS PEPERIKSAAN MALAYSIA\nSIJIL TINGGI PERSEKOLAHAN MALAYSIA')
        self.assertEqual((vf['student_verdict'], vf['error'], vf['fields']), ('unreadable', EMPTY_ANSWER, {}))


class AnEmptyApprovalAnswerIsAFailedRead(SimpleTestCase):
    """The income path: never a checked read that says "unapproved" for a page the model did not see."""

    NOTHING = {'issuer_header': '', 'approver_name': '', 'approver_title': '', 'has_stamp_or_signature': 'no',
               'has_signature': 'no', 'has_stamp': 'no'}

    def _read(self, answer):
        from apps.scholarship.income_declaration import read_approval
        doc = ApplicantDocument(doc_type='income_support_doc', content_type='image/jpeg', vision_fields={})
        ex = {'fields': {'amount': 'RM800'}, 'warnings': [], 'error': ''}
        with _answer(answer):
            out = read_approval(doc, ex, 'SURAT PENGESAHAN PENDAPATAN\nRM800', lambda: b'img')
        doc.vision_fields = {**out, 'fields': out['fields']}
        return doc, out

    def test_an_all_no_answer_is_a_failed_read_still_checking_not_unapproved(self):
        from apps.scholarship.income_declaration import (APPROVAL_ERROR, APPROVAL_FIELDS, approval_missing,
                                                         approval_unchecked)
        for answer in (self.NOTHING, {k: '' for k in self.NOTHING}):
            with self.subTest(marks=answer['has_stamp']):
                doc, out = self._read(answer)
                self.assertEqual(out[APPROVAL_ERROR], EMPTY_ANSWER)
                self.assertFalse(set(APPROVAL_FIELDS) & set(out['fields']))
                self.assertEqual(out['fields']['amount'], 'RM800')
                self.assertTrue(approval_unchecked(doc))
                self.assertEqual(approval_missing(doc), ())

    def test_any_one_mark_is_still_a_checked_read(self):
        from apps.scholarship.income_declaration import APPROVAL_ERROR, approval_missing
        for key, value in (('issuer_header', 'JKKK KAMPUNG CONTOH'), ('has_stamp', 'yes'),
                           ('has_signature', 'yes'), ('approver_name', 'QORVA BIN ZELT')):
            with self.subTest(key):
                doc, out = self._read({**self.NOTHING, key: value})
                self.assertNotIn(APPROVAL_ERROR, out)
                self.assertEqual(out['fields'][key], value)
                self.assertNotEqual(approval_missing(doc), ())
