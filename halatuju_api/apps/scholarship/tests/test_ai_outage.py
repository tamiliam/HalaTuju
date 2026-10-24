"""The 2026-10-24 incident: Gemini's prepaid credit ran out (HTTP 402) for ~20 hours.

Three faults made it worse, and each class below pins one of them shut:

1. **Outage != unreadable.** Every failed Gemini read was stored as ``student_verdict='unreadable'``,
   so the student was told to re-take a perfectly good photo AND the consent gate blocked them
   (``offer_letter_unreadable`` / ``results_slip_unreadable`` / ``income_document_unreadable``).
   OUR outage now stores the existing "AI skipped" state, ``review_manually``.
2. **Self-heal.** The hourly sweep re-reads those documents through the cockpit's Re-run core
   once the service answers, never over a good read, and never in a loop.
3. **Alert.** The only outage check looked at IC OCR (Google Vision), never at Gemini.
4. **Honest errors.** The cascade error kept the LAST model's message only — a retired model's
   404 — and hid the 402.

The adversarial review of that sprint (same day) added the rest: after submission a deferred read
still raised "send a clearer copy" requests through the verdict; answering a request during an
outage counted as a failed attempt; a deferred STR closed its own request; a model's unparseable
answer was treated as an outage; the sweep paid for OCR while Gemini was still down; the hourly
alert fired on one document; a re-run could overwrite a real verdict with our outage.
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import gemini, read_errors, vision
from apps.scholarship.models import ApplicantDocument, ResolutionItem
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application,
)

#: What Google returned all day on 2026-10-23/24, per model.
_402 = ("402 RESOURCE_EXHAUSTED. {'error': {'code': 402, 'message': 'Your prepayment credits are "
        "depleted. Please go to AI Studio to manage your project and billing.', 'status': "
        "'RESOURCE_EXHAUSTED'}}")
_404 = "404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-2.0-flash is not found'}}"
_IMAGE = b'\xff\xd8\xff\xe0 not a real jpeg, never decoded'


def _bad_key():
    """What Gemini answers a revoked or mistyped key with — a 400, not a 401/403."""
    from google.genai import errors as genai_errors
    return genai_errors.ClientError(400, {'error': {
        'code': 400, 'status': 'INVALID_ARGUMENT',
        'message': 'API key not valid. Please pass a valid API key.',
        'details': [{'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': 'API_KEY_INVALID'}]}})


_BAD_KEY = _bad_key()
_SERVICE_READ = {'fields': {}, 'warnings': [], 'student_verdict': 'review_manually', 'capture': 'ai',
                 'error': f'All AI models failed: gemini-2.5-flash: {_402[:80]}', 'service_error': True}


def _gemini_client(errors_by_model):
    """A stand-in `genai.Client` whose every model call raises that model's own error, and which
    records the models it was asked for."""
    client = MagicMock()
    client.asked = []

    def generate_content(model, contents, config=None):
        client.asked.append(model)
        raise RuntimeError(errors_by_model[model])
    client.models.generate_content.side_effect = generate_content
    return client


def _gemini_down():
    """Patch the SDK so every model in the cascade answers 402 — the incident, at the provider."""
    client = _gemini_client({m: _402 for m in ('gemini-2.5-flash', 'gemini-2.5-flash-lite',
                                               'gemini-2.5-pro')})
    return patch('google.genai.Client', return_value=client)


def _doc(application, doc_type, **kw):
    kw.setdefault('storage_path', f'test/{doc_type}/{ApplicantDocument.objects.count()}')
    kw.setdefault('content_type', 'image/jpeg')
    return ApplicantDocument.objects.create(application=application, doc_type=doc_type, **kw)


# ── 1. Our outage is not the student's unreadable document ─────────────────────────────────────

@override_settings(GEMINI_API_KEY='test-key', DOC_GENUINENESS_CHECK_ENABLED=False)
class OurOutageIsNotTheStudentsUnreadableDocument(TestCase):
    def setUp(self):
        self.app = make_application('shortlisted')
        self.name = self.app.profile.name

    def _read(self, doc, *, text='', image=_IMAGE, words=None):
        ocr = {'text': text, 'words': words, 'image': image, 'error': None}
        with _gemini_down():
            return vision.run_field_extraction_for_document(doc, names=[self.name], ocr=ocr)

    def _assert_deferred_not_blocked(self, doc, code):
        from apps.scholarship.help_engine import VERDICT_GUIDANCE, verdict_for_document
        from apps.scholarship.services import consent_blockers, document_unreadable_blockers
        doc.refresh_from_db()
        vf = doc.vision_fields
        self.assertEqual(vf['student_verdict'], 'review_manually')
        self.assertIs(vf['service_error'], True)
        self.assertIn('402', vf['error'])                       # the CAUSE, not a retired model's 404
        self.assertNotIn(code, document_unreadable_blockers(self.app))
        self.assertNotIn(code, consent_blockers(self.app))
        # The student is told a reviewer will check it by hand — not to re-take the photo.
        self.assertEqual(verdict_for_document(doc), 'review_manually')
        self.assertIn('could not auto-check', VERDICT_GUIDANCE['review_manually'])

    def test_a_402_on_an_offer_letter_is_a_deferred_read_and_does_not_block_consent(self):
        from apps.scholarship.pathway_engine import student_offer_check
        offer = _doc(self.app, 'offer_letter')
        self._read(offer, text='Tawaran kemasukan ke program')
        self._assert_deferred_not_blocked(offer, 'offer_letter_unreadable')
        self.assertEqual(student_offer_check(offer)['name'], 'pending')

    def test_a_402_on_a_results_slip_is_a_deferred_read_and_does_not_block_consent(self):
        from apps.scholarship.academic_engine import student_slip_check
        slip = _doc(self.app, 'results_slip')
        # No word boxes → the deterministic SPM parse cannot lock on → the Gemini image read.
        self._read(slip, words=[])
        self._assert_deferred_not_blocked(slip, 'results_slip_unreadable')
        chk = student_slip_check(slip)
        self.assertEqual((chk['name'], chk['subjects']), ('pending', 'pending'))

    def test_a_document_with_no_text_is_still_unreadable_and_still_blocks(self):
        """The other side of the line: a document-level failure ('no text') is the student's to
        fix, exactly as before. Without this the fix could pass by never saying 'unreadable'."""
        from apps.scholarship.services import document_unreadable_blockers
        offer = _doc(self.app, 'offer_letter')
        with patch('apps.scholarship.vision._call_gemini_json') as gem:
            vision.run_field_extraction_for_document(
                offer, names=[self.name], ocr={'text': '', 'words': None, 'image': None, 'error': None})
        gem.assert_not_called()
        offer.refresh_from_db()
        self.assertEqual(offer.vision_fields['student_verdict'], 'unreadable')
        self.assertIs(offer.vision_fields['service_error'], False)
        self.assertIn('offer_letter_unreadable', document_unreadable_blockers(self.app))

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_the_cockpit_re_run_door_stores_the_same_deferred_read(self):
        """AdminRunVisionView → `reextract_document` → the same choke point (the bulk commands and
        the hourly sweep use that core too)."""
        admin = make_admin('super', super_admin=True)
        offer = _doc(self.app, 'offer_letter')
        full = {'text': 'Tawaran kemasukan', 'words': None, 'image': _IMAGE, 'error': None}
        with _gemini_down(), patch('apps.scholarship.vision.ocr_document_full', return_value=full):
            r = authed_client(admin).post(
                f'/api/v1/admin/scholarship/applications/{self.app.id}/documents/{offer.id}/re-run-vision/')
        self.assertEqual(r.status_code, 200, r.content)
        offer.refresh_from_db()
        self.assertEqual(offer.vision_fields['student_verdict'], 'review_manually')

    def test_a_deferred_birth_certificate_does_not_block_as_an_unreadable_income_document(self):
        """The relationship doc's 'processed' test read the RUN STAMP, which a failed read sets
        too — so a deferred certificate still asked the family to re-upload it. The genuinely
        unreadable certificate beside it proves the branch is reached."""
        from apps.scholarship.income_engine import income_cluster_advice
        from apps.scholarship.services import document_unreadable_blockers
        app = make_application('shortlisted', income_route='str', income_earner='mother')
        now = timezone.now()
        _doc(app, 'parent_ic', household_member='mother', vision_run_at=now,
             vision_name='SITI BINTI AHMAD', vision_nric='750101-14-5678')
        bc = _doc(app, 'birth_certificate', vision_run_at=now, vision_fields_run_at=now,
                  vision_fields=dict(_SERVICE_READ))
        self.assertNotEqual(income_cluster_advice(app, 'mother'), 'income_rel_doc_unreadable')
        self.assertNotIn('income_document_unreadable', document_unreadable_blockers(app))
        bc.vision_fields = {'fields': {}, 'warnings': [], 'student_verdict': 'unreadable',
                            'capture': 'ai', 'error': 'no text read', 'service_error': False}
        bc.save(update_fields=['vision_fields'])
        self.assertEqual(income_cluster_advice(app, 'mother'), 'income_rel_doc_unreadable')
        self.assertIn('income_document_unreadable', document_unreadable_blockers(app))


class TheServiceErrorClassifier(TestCase):
    def test_our_side_failures_are_service_errors(self):
        for err in ('All AI models failed: gemini-2.5-flash: 402 RESOURCE_EXHAUSTED',
                    'All AI models failed: boom',
                    'AI service not configured (missing API key)', 'AI module not installed',
                    'rate_limited', 'OCR service failed: 403 billing disabled'):
            with self.subTest(err=err):
                self.assertTrue(read_errors.is_ai_service_error(err))

    def test_document_level_failures_are_not(self):
        for err in ('no text', 'no text read', 'no image for extraction', 'could not fetch image',
                    'no extractor for photo', '', None, 'Bad image data.',
                    'unparseable model response (gemini-2.5-flash): Expecting value'):
            with self.subTest(err=err):
                self.assertFalse(read_errors.is_ai_service_error(err))

    def test_the_ocr_split_is_the_ic_gates_own(self):
        for err in ('API quota exceeded', 'deadline exceeded', '403 billing disabled'):
            with self.subTest(err=err):
                self.assertTrue(read_errors.is_ocr_service_error(err))
        for err in ('empty image', 'Bad image data.', 'could not fetch image', 'no image', '', None):
            with self.subTest(err=err):
                self.assertFalse(read_errors.is_ocr_service_error(err))

    def test_a_read_with_fields_is_never_deferred(self):
        self.assertTrue(read_errors.read_deferred({}))
        self.assertTrue(read_errors.read_deferred(_SERVICE_READ))
        self.assertFalse(read_errors.read_deferred({'fields': {'name': 'X'}}))
        self.assertFalse(read_errors.read_deferred({'fields': {}, 'student_verdict': 'unreadable'}))


@override_settings(GEMINI_API_KEY='test-key', DOC_GENUINENESS_CHECK_ENABLED=False)
class WhatOurOutageMayNotDo(TestCase):
    """Review findings 4, 6a and 11: the line between our failure and the document's."""

    def setUp(self):
        self.app = make_application('shortlisted')
        self.name = self.app.profile.name

    def _answers(self, *per_model):
        """A client whose Nth model call answers per_model[N]: an Exception is raised, a string is
        the response body (None = a safety block with no body)."""
        client = MagicMock()
        replies = list(per_model)

        def generate_content(model, contents, config=None):
            r = replies.pop(0)
            if isinstance(r, Exception):
                raise r
            return MagicMock(text=r)
        client.models.generate_content.side_effect = generate_content
        return client

    def _json_read(self, client):
        with patch('google.genai.Client', return_value=client), \
                patch('apps.scholarship.usage.record_usage') as meter:
            return vision._call_gemini_json('prompt', {'type': 'object'}), meter

    def test_one_models_empty_answer_falls_through_to_the_next_model(self):
        r, meter = self._json_read(self._answers(None, '{"name": "ok"}'))
        self.assertEqual(r, {'name': 'ok'})
        self.assertEqual(meter.call_count, 2)                   # both answered, both billed

    def test_a_service_failure_and_an_empty_answer_is_still_ours(self):
        """Flash 402, lite answered with nothing: the healthy fallback never gave a real answer,
        so we cannot blame the document — a service error, and the sweep will try again."""
        r, _ = self._json_read(self._answers(RuntimeError(_402), None))
        self.assertTrue(read_errors.is_ai_service_error(r['_error']))
        self.assertIn('unparseable model response', r['_error'])

    def test_a_400_invalid_argument_from_every_model_is_the_documents_problem(self):
        from google.genai import errors as genai_errors
        bad = genai_errors.ClientError(400, {'error': {'code': 400, 'status': 'INVALID_ARGUMENT',
                                                       'message': 'Unable to process input image.'}})
        self.assertTrue(read_errors.model_rejected_document(bad))
        r, _ = self._json_read(self._answers(bad, bad))
        self.assertTrue(r['_error'].startswith(read_errors.DOCUMENT_FAILED))
        self.assertFalse(read_errors.is_ai_service_error(r['_error']))
        # Mixed — one model refused the file, the other was out of credit → ours.
        r, _ = self._json_read(self._answers(bad, RuntimeError(_402)))
        self.assertTrue(read_errors.is_ai_service_error(r['_error']))

    def test_only_a_400_that_names_the_file_is_the_documents_problem(self):
        """Round 3, finding 1: a revoked key, our own malformed request and a region/billing
        precondition are 400s too — blaming the student for those is the incident again."""
        from google.genai import errors as genai_errors

        def err(code, status, message):
            return genai_errors.ClientError(code, {'error': {'code': code, 'status': status,
                                                             'message': message}})
        theirs = (err(400, 'INVALID_ARGUMENT', 'Unable to process input image. Please retry.'),
                  err(400, 'INVALID_ARGUMENT', 'The document has no pages.'),
                  err(413, '', 'Request payload size exceeds the limit: 20971520 bytes.'),
                  RuntimeError('400 INVALID_ARGUMENT. Unable to process input image.'))   # no attributes
        ours = (_BAD_KEY,
                err(400, 'INVALID_ARGUMENT', 'Invalid JSON payload received. Unknown name "foo".'),
                err(400, 'FAILED_PRECONDITION', 'User location is not supported for the API use.'),
                err(400, 'INVALID_ARGUMENT', 'Unable to process input image: model is overloaded'),
                err(400, '', 'Bad request'), RuntimeError('400 Bad Request'),
                err(402, 'RESOURCE_EXHAUSTED', 'Your prepayment credits are depleted.'),
                err(403, 'PERMISSION_DENIED', 'Permission denied.'),
                err(404, 'NOT_FOUND', 'models/gemini-2.0-flash is not found'),
                err(429, 'RESOURCE_EXHAUSTED', 'Quota exceeded.'),
                genai_errors.ServerError(503, {'error': {'code': 503, 'status': 'UNAVAILABLE'}}),
                TimeoutError('read timed out'))
        for e in theirs:
            with self.subTest(theirs=str(e)[:60]):
                self.assertTrue(read_errors.model_rejected_document(e))
        for e in ours:
            with self.subTest(ours=str(e)[:60]):
                self.assertFalse(read_errors.model_rejected_document(e))

    def test_a_revoked_key_on_every_model_is_our_outage_end_to_end(self):
        """Deferred (not unreadable), picked up by the hourly sweep, and counted by the alert."""
        from apps.scholarship.services import detect_service_outages
        from apps.scholarship.services.read_retry import service_error_documents
        offer = _doc(self.app, 'offer_letter')
        with patch('google.genai.Client', return_value=self._answers(_BAD_KEY, _BAD_KEY)):
            vision.run_field_extraction_for_document(
                offer, names=[self.name],
                ocr={'text': 'Tawaran', 'words': None, 'image': _IMAGE, 'error': None})
        offer.refresh_from_db()
        self.assertEqual(offer.vision_fields['student_verdict'], 'review_manually')
        self.assertTrue(offer.vision_fields['error'].startswith('All AI models failed'))
        self.assertIn(offer.id, [d.id for d in service_error_documents(200)])
        self.assertEqual([s['service'] for s in detect_service_outages(2)], ['gemini'])

    def test_a_content_rejection_on_one_model_and_a_bad_key_on_the_other_is_ours(self):
        from google.genai import errors as genai_errors
        content = genai_errors.ClientError(400, {'error': {'code': 400, 'status': 'INVALID_ARGUMENT',
                                                           'message': 'Unable to process input image.'}})
        r, _ = self._json_read(self._answers(content, _BAD_KEY))
        self.assertTrue(read_errors.is_ai_service_error(r['_error']))

    def test_a_model_that_answers_with_no_json_is_the_documents_problem_and_billed_once(self):
        r, meter = self._json_read(self._answers(None, 'not json {'))
        err = r['_error']
        self.assertEqual(meter.call_count, 2)                   # every answered call was billed
        self.assertTrue(err.startswith(read_errors.DOCUMENT_FAILED))
        self.assertIn('gemini-2.5-flash-lite: unparseable model response', err)
        self.assertFalse(read_errors.is_ai_service_error(err))
        offer = _doc(self.app, 'offer_letter')
        with patch('apps.scholarship.vision._call_gemini_json', return_value={'_error': err}):
            vision.run_field_extraction_for_document(
                offer, names=[self.name],
                ocr={'text': 'Tawaran', 'words': None, 'image': _IMAGE, 'error': None})
        offer.refresh_from_db()
        self.assertEqual(offer.vision_fields['student_verdict'], 'unreadable')

    def test_the_prose_seam_treats_an_empty_answer_the_same_way(self):
        from apps.scholarship.profile_engine import _call_gemini_text
        with patch('google.genai.Client', return_value=self._answers('', '')):
            err = _call_gemini_text('prompt', 'English')['error']
        self.assertTrue(err.startswith(read_errors.DOCUMENT_FAILED))
        with patch('google.genai.Client', return_value=self._answers('', 'A profile.')):
            self.assertEqual(_call_gemini_text('prompt', 'English')['markdown'], 'A profile.')
        with patch('google.genai.Client', return_value=self._answers(RuntimeError(_402), '')):
            self.assertTrue(read_errors.is_ai_service_error(_call_gemini_text('p', 'English')['error']))

    def test_a_vision_ocr_outage_on_a_text_read_document_is_deferred_not_unreadable(self):
        slip = _doc(self.app, 'salary_slip')
        with patch('apps.scholarship.vision._call_gemini_json') as gem:
            vision.run_field_extraction_for_document(
                slip, names=[self.name], ocr={'text': '', 'error': '403 Cloud Vision billing disabled'})
        gem.assert_not_called()
        slip.refresh_from_db()
        self.assertEqual(slip.vision_fields['student_verdict'], 'review_manually')
        self.assertTrue(slip.vision_fields['error'].startswith('OCR service failed: 403'))
        bad = _doc(self.app, 'salary_slip')
        vision.run_field_extraction_for_document(
            bad, names=[self.name], ocr={'text': '', 'error': 'Bad image data.'})
        bad.refresh_from_db()
        self.assertEqual(bad.vision_fields['student_verdict'], 'unreadable')   # the file's problem

    def test_a_re_run_during_an_outage_never_replaces_a_real_verdict(self):
        real = {'fields': {}, 'warnings': [], 'student_verdict': 'unreadable', 'capture': 'ai',
                'error': 'no text', 'service_error': False}
        offer = _doc(self.app, 'offer_letter', vision_fields=dict(real))
        with _gemini_down():
            r = vision.run_field_extraction_for_document(
                offer, names=[self.name],
                ocr={'text': 'Tawaran', 'words': None, 'image': _IMAGE, 'error': None})
        self.assertTrue(r.get('stale_kept'))
        offer.refresh_from_db()
        self.assertEqual(offer.vision_fields, real)
        # …but a row that only ever held OUR old failure is fair game for the honest label.
        legacy = _doc(self.app, 'offer_letter', vision_fields={**_SERVICE_READ, 'student_verdict': 'unreadable'})
        with _gemini_down():
            vision.run_field_extraction_for_document(
                legacy, names=[self.name],
                ocr={'text': 'Tawaran', 'words': None, 'image': _IMAGE, 'error': None})
        legacy.refresh_from_db()
        self.assertEqual(legacy.vision_fields['student_verdict'], 'review_manually')

    def test_a_deferred_bank_statement_gets_the_reviewer_copy_not_upload_a_clearer_photo(self):
        from apps.scholarship.help_engine import verdict_for_document
        bank = _doc(self.app, 'bank_statement', vision_fields=dict(_SERVICE_READ))
        self.assertEqual(verdict_for_document(bank), 'review_manually')
        bank.vision_fields = {**_SERVICE_READ, 'student_verdict': 'incomplete', 'service_error': False}
        self.assertEqual(verdict_for_document(bank), 'bank_details_unclear')


class ADeferredReadAsksTheStudentForNothing(TestCase):
    """Review findings 1 and 3: after submission the VERDICT raises the student's requests, and a
    deferred read must not become "send a clearer copy" there either. Each test also proves the
    real failure beside it still asks — or the fix could pass by never asking at all."""

    def _asks(self, app):
        from apps.scholarship.resolution import STUDENT_DOC_REQUEST_CODES, _ticketable_unresolved
        return set(_ticketable_unresolved(app)) & STUDENT_DOC_REQUEST_CODES

    def test_a_deferred_offer_raises_no_request_and_a_real_unreadable_one_does(self):
        app = make_application('profile_complete')
        offer = _doc(app, 'offer_letter', vision_fields=dict(_SERVICE_READ))
        self.assertNotIn('offer_unreadable', self._asks(app))
        offer.vision_fields = {**_SERVICE_READ, 'student_verdict': 'unreadable', 'error': 'no text',
                               'service_error': False}
        offer.save(update_fields=['vision_fields'])
        self.assertIn('offer_unreadable', self._asks(app))

    def test_a_deferred_birth_certificate_is_not_unreadable_anywhere(self):
        from apps.scholarship.income_engine import relationship_doc_unreadable, student_bc_check
        app = make_application('profile_complete', income_route='str', income_earner='mother')
        _doc(app, 'parent_ic', household_member='mother', vision_run_at=timezone.now(),
             vision_name='SITI BINTI AHMAD', vision_nric='750101-14-5678')
        bc = _doc(app, 'birth_certificate', vision_fields=dict(_SERVICE_READ))
        self.assertFalse(relationship_doc_unreadable(bc))
        self.assertFalse(student_bc_check(bc)['unreadable'])
        self.assertNotIn('birth_cert_unreadable', self._asks(app))
        bc.vision_fields = {**_SERVICE_READ, 'student_verdict': 'unreadable', 'error': 'no text',
                            'service_error': False}
        bc.save(update_fields=['vision_fields'])
        self.assertTrue(relationship_doc_unreadable(bc))
        self.assertIn('birth_cert_unreadable', self._asks(app))

    def test_a_deferred_str_is_pending_not_unreadable_and_keeps_its_request_open(self):
        from apps.scholarship.help_engine import verdict_for_document
        from apps.scholarship.income_engine import student_str_check
        from apps.scholarship.resolution import doc_match_verdict
        app = make_application('profile_complete', income_route='str', income_earner='mother')
        str_doc = _doc(app, 'str', household_member='mother', vision_fields=dict(_SERVICE_READ))
        self.assertEqual(student_str_check(str_doc)['current_status'], 'unknown')
        self.assertEqual(doc_match_verdict(str_doc), 'pending')    # must not close an open STR ask
        self.assertNotEqual(verdict_for_document(str_doc), 'str_not_current')
        self.assertNotIn('str_not_current', self._asks(app))
        # A real read whose approval did not show still reads 'unreadable' and still asks.
        str_doc.vision_fields = {'fields': {'recipient_name': 'SITI BINTI AHMAD', 'status': 'Dalam proses',
                                            'source_type': 'semakan_status'},
                                 'student_verdict': 'ok', 'error': ''}
        str_doc.save(update_fields=['vision_fields'])
        self.assertEqual(student_str_check(str_doc)['current_status'], 'unreadable')
        self.assertEqual(verdict_for_document(str_doc), 'str_not_current')

    def test_an_unread_str_bands_no_better_than_a_badly_read_one(self):
        """Round 2, finding 2: 'unknown' must not drop to the blue str_present_unverified band while
        a read-but-unconfirmed STR sits at Unsure — and it still asks the student for nothing."""
        from apps.scholarship.verdict_engine import build_verdict
        app = make_application('profile_complete', income_route='str', income_earner='father')
        _doc(app, 'parent_ic', household_member='father', vision_run_at=timezone.now(),
             vision_name='KUMAR A/L RAJU', vision_nric='700101-14-5677')
        str_doc = _doc(app, 'str', household_member='father', vision_fields=dict(_SERVICE_READ))

        def income():
            return next(f for f in build_verdict(app) if f['fact'] == 'income')
        deferred = income()
        self.assertIn('str_present_unverified', [i['code'] for i in deferred['unresolved']])
        self.assertNotIn('str_not_current', self._asks(app))
        str_doc.vision_fields = {'fields': {'recipient_name': 'KUMAR A/L RAJU', 'status': 'Dalam proses',
                                            'source_type': 'semakan_status'},
                                 'student_verdict': 'ok', 'error': ''}
        str_doc.save(update_fields=['vision_fields'])
        badly_read = income()
        self.assertIn('str_not_current', [i['code'] for i in badly_read['unresolved']])
        self.assertEqual(deferred['status'], badly_read['status'])

    def test_the_engine_version_moved_with_the_band(self):
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION
        self.assertEqual(VERDICT_ENGINE_VERSION, '2026-10-24.1')


class CheckTwoHoldsItsRequestsWhileOurOutageHasADocumentUnread(TestCase):
    """Round 3, finding 3: a deferred read is neither an answer nor a reason to ask again. The
    request is HELD — not raised, not resolved — until the read lands; then the normal rule."""

    def setUp(self):
        self.app = make_application('profile_complete')

    def _status(self, code):
        from apps.scholarship.check2_queries import sync_check2_queries
        sync_check2_queries(self.app)
        item = self.app.resolution_items.filter(source='check2', code=code).first()
        return item.status if item else None

    def test_a_bill_request_is_held_while_deferred_then_follows_the_read(self):
        import datetime
        bill = _doc(self.app, 'water_bill', vision_fields=dict(_SERVICE_READ))
        self.assertIsNone(self._status('water_bill_recheck'))            # no ask while unread
        bill.delete()
        self.assertEqual(self._status('water_bill_recheck'), 'open')     # none on file → asked
        bill = _doc(self.app, 'water_bill', vision_fields=dict(_SERVICE_READ))
        self.assertEqual(self._status('water_bill_recheck'), 'open')     # unread is no answer
        bill.vision_fields = {'fields': {}, 'student_verdict': 'unreadable', 'error': 'no text'}
        bill.save(update_fields=['vision_fields'])
        self.assertEqual(self._status('water_bill_recheck'), 'open')     # a bad read: still asked
        cur = datetime.date.today()
        bill.vision_fields = {'fields': {'amount': 'RM40', 'address': '12 Jln Mawar', 'name': 'Priya Devi',
                                         'billing_period': f'{cur.month:02d}/{cur.year}'},
                              'student_verdict': 'ok', 'error': ''}
        bill.save(update_fields=['vision_fields'])
        self.assertEqual(self._status('water_bill_recheck'), 'resolved')  # a good read answers it

    def test_a_held_school_leaving_certificate_request_neither_resolves_nor_re_asks(self):
        from apps.scholarship.models import ResolutionItem as RI
        RI.objects.create(application=self.app, source='check2', code='school_leaving_cert_missing',
                          fact='academic', kind='doc', doc_type='school_leaving_cert', status='open')
        cert = _doc(self.app, 'school_leaving_cert', vision_fields=dict(_SERVICE_READ))
        self.assertEqual(self._status('school_leaving_cert_missing'), 'open')
        cert.vision_fields = {'fields': {'school': 'SMK Test'}, 'student_verdict': 'ok', 'error': ''}
        cert.save(update_fields=['vision_fields'])
        self.assertEqual(self._status('school_leaving_cert_missing'), 'resolved')

    def test_the_held_codes_are_the_syncs_own_document_requests(self):
        from apps.scholarship.check2_deferred import HELD_WHILE_DEFERRED
        from apps.scholarship.check2_queries import DOC_SPECS
        for code in HELD_WHILE_DEFERRED:
            with self.subTest(code=code):
                self.assertIn('doc_type', DOC_SPECS[code])


class AnsweringARequestDuringAnOutageIsNoFailedAttempt(TestCase):
    """Review finding 2: the attempt counter and the circuit-breaker are about the STUDENT."""

    def _item(self, app):
        return ResolutionItem.objects.create(application=app, source='system', code='offer_unreadable',
                                             fact='pathway', status='open')

    def test_a_deferred_upload_stamps_no_attempt_and_trips_no_breaker(self):
        from apps.scholarship.views import _note_unresolved_attempts, _stage_attempts_exhausted
        app = make_application('profile_complete')
        item = self._item(app)
        item.params = {'attempts': 50}                          # far past any organisation's K
        item.save(update_fields=['params'])
        deferred = _doc(app, 'offer_letter', vision_fields=dict(_SERVICE_READ))
        _note_unresolved_attempts(app, deferred, [], True)
        item.refresh_from_db()
        self.assertEqual(item.params['attempts'], 50)           # not stamped
        self.assertFalse(_stage_attempts_exhausted(app, deferred, None))
        real = _doc(app, 'offer_letter', vision_fields={'fields': {}, 'student_verdict': 'unreadable',
                                                        'error': 'no text'})
        self.assertTrue(_stage_attempts_exhausted(app, real, None))   # the breaker is live for her
        _note_unresolved_attempts(app, real, [], True)
        item.refresh_from_db()
        self.assertEqual(item.params['attempts'], 51)


# ── 2. The hourly sweep heals what the outage left behind ──────────────────────────────────────

@override_settings(GEMINI_API_KEY='test-key', DOC_GENUINENESS_CHECK_ENABLED=False)
class TheSweepReReadsServiceErrorReads(TestCase):
    def setUp(self):
        self.app = make_application('shortlisted')
        self.name = self.app.profile.name
        self.full = {'text': 'penyata gaji', 'words': None, 'image': _IMAGE, 'error': None}
        self.good = {'name': self.name, 'employer': 'ACME', 'gross_income': '3000',
                     'net_income': '2700', 'period': 'Jan 2026', 'warnings': []}

    def _sweep(self, gemini_answer):
        from apps.scholarship.services import reprocess_unread_ic_documents
        with patch('apps.scholarship.vision.ocr_document_full', return_value=self.full), \
                patch('apps.scholarship.vision._call_gemini_json', return_value=gemini_answer) as gem:
            return reprocess_unread_ic_documents(), gem

    def _service_doc(self, **vf):
        return _doc(self.app, 'salary_slip', vision_run_at=timezone.now(),
                    vision_fields_run_at=timezone.now() - timedelta(hours=3),
                    vision_fields={**_SERVICE_READ, **vf})

    def test_a_service_error_read_is_re_read_and_recovers(self):
        doc = self._service_doc()
        r, gem = self._sweep(dict(self.good))
        doc.refresh_from_db()
        self.assertEqual(gem.call_count, 1)
        self.assertEqual(doc.vision_fields['student_verdict'], 'ok')
        self.assertEqual(doc.vision_fields['fields']['gross_income'], '3000')
        self.assertNotIn('service_retry_until', doc.vision_fields)
        self.assertEqual(r, {'scanned': 1, 'processed': 1, 'errored': 0})

    def test_a_row_stored_before_the_marker_is_healed_too(self):
        """The incident's own rows say 'unreadable' with the cascade error and carry no marker."""
        doc = self._service_doc(student_verdict='unreadable', service_error=None)
        self._sweep(dict(self.good))
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['student_verdict'], 'ok')

    def test_a_good_read_is_never_touched(self):
        good = _doc(self.app, 'salary_slip', vision_run_at=timezone.now(),
                    vision_fields_run_at=timezone.now(),
                    vision_fields={'fields': {'gross_income': '2500'}, 'warnings': [],
                                   'student_verdict': 'ok', 'capture': 'ai', 'error': ''})
        # Defensive: even a row whose error looks like ours is left alone while it holds fields.
        odd = self._service_doc(fields={'gross_income': '1800'})
        r, gem = self._sweep({'_error': 'All AI models failed: still down'})
        gem.assert_not_called()
        self.assertEqual(r['scanned'], 0)
        for doc, figure in ((good, '2500'), (odd, '1800')):
            doc.refresh_from_db()
            self.assertEqual(doc.vision_fields['fields']['gross_income'], figure)

    def test_still_down_probes_once_then_waits_and_the_window_runs_out(self):
        """Findings 5 and 8: one paid probe, the rest of the batch waits; while the recent reads
        say Gemini is down nothing is re-read at all; and each document has 72 hours."""
        first, second = self._service_doc(), self._service_doc()
        down = {'_error': f'All AI models failed: gemini-2.5-flash: {_402}'}
        with patch('apps.scholarship.vision.ocr_document_full', return_value=self.full) as ocr, \
                patch('apps.scholarship.vision._call_gemini_json', return_value=down) as gem:
            from apps.scholarship.services import reprocess_unread_ic_documents
            r = reprocess_unread_ic_documents()
            self.assertEqual((gem.call_count, ocr.call_count), (1, 1))     # one probe, then stop
            self.assertEqual(r, {'scanned': 1, 'processed': 0, 'errored': 1})
            r = reprocess_unread_ic_documents()                 # its failure is now the recent window
            self.assertEqual((gem.call_count, ocr.call_count), (1, 1))     # nothing billed
            self.assertEqual(r['scanned'], 0)
        first.refresh_from_db()
        second.refresh_from_db()
        tried = [d for d in (first, second) if 'service_retry_until' in d.vision_fields]
        self.assertEqual(len(tried), 1)                         # the other was never touched
        probed = tried[0]
        vf = probed.vision_fields
        self.assertEqual(vf['student_verdict'], 'review_manually')
        until = vf['service_retry_until']
        self.assertAlmostEqual(until, (timezone.now() + timedelta(hours=72)).timestamp(), delta=120)
        from apps.scholarship.services.read_retry import service_error_documents
        probed.vision_fields = {**vf, 'service_retry_until': int(timezone.now().timestamp()) - 1}
        probed.save(update_fields=['vision_fields'])
        self.assertNotIn(probed.id, [d.id for d in service_error_documents(200)])

    def test_a_process_killed_mid_read_has_already_started_its_window(self):
        class Killed(BaseException):
            pass
        from apps.scholarship.services import reprocess_unread_ic_documents
        doc = self._service_doc()
        before = doc.vision_fields_run_at
        with patch('apps.scholarship.reextract.reextract_document', side_effect=Killed), \
                self.assertRaises(Killed):
            reprocess_unread_ic_documents()
        doc.refresh_from_db()
        self.assertIn('service_retry_until', doc.vision_fields)
        self.assertGreater(doc.vision_fields_run_at, before)    # moved to the back of the queue

    def test_a_closed_case_is_left_alone(self):
        from apps.scholarship.services.read_retry import service_error_documents
        closed = make_application('rejected')
        _doc(closed, 'salary_slip', vision_fields=dict(_SERVICE_READ),
             vision_fields_run_at=timezone.now() - timedelta(hours=3))
        live = self._service_doc()
        self.assertEqual([d.id for d in service_error_documents(200)], [live.id])

    def test_the_soft_and_post_award_reads_are_retried_too(self):
        from apps.scholarship.services.read_retry import service_error_documents
        kinds = ('water_bill', 'electricity_bill', 'bank_statement', 'school_leaving_cert',
                 'semester_result')
        made = {_doc(self.app, k, vision_fields=dict(_SERVICE_READ),
                     vision_fields_run_at=timezone.now() - timedelta(hours=3)).id for k in kinds}
        self.assertEqual({d.id for d in service_error_documents(200)}, made)

    def test_a_broken_retry_query_does_not_stop_the_never_read_sweep(self):
        from apps.scholarship.services import reprocess_unread_ic_documents
        stuck = _doc(self.app, 'offer_letter')                  # never read at all
        with patch('apps.scholarship.services.read_retry.reduce', side_effect=RuntimeError('db')), \
                patch('apps.scholarship.reextract.reextract_document') as rx:
            r = reprocess_unread_ic_documents()
        self.assertEqual([c.args[0].id for c in rx.call_args_list], [stuck.id])
        self.assertEqual(r['scanned'], 1)

    def test_a_document_level_failure_and_a_replaced_copy_are_not_re_read(self):
        _doc(self.app, 'salary_slip', vision_fields_run_at=timezone.now(),
             vision_fields={'fields': {}, 'student_verdict': 'unreadable', 'error': 'no text read'})
        replaced = self._service_doc()
        replaced.superseded_at = timezone.now()
        replaced.save(update_fields=['superseded_at'])
        r, gem = self._sweep(dict(self.good))
        gem.assert_not_called()
        self.assertEqual(r['scanned'], 0)

    @override_settings(DOC_ASSIST_RATE_LIMIT_PER_HOUR=2)
    def test_a_rate_limited_read_waits_for_the_same_hourly_cap_the_upload_path_uses(self):
        throttled = _doc(self.app, 'epf', vision_fields_run_at=timezone.now() - timedelta(hours=2),
                         vision_fields={'fields': {}, 'warnings': [],
                                        'student_verdict': 'review_manually', 'error': 'rate_limited'})
        busy = [_doc(self.app, 'water_bill', vision_fields_run_at=timezone.now(),
                     vision_fields={'student_verdict': 'ok', 'error': ''}) for _ in range(2)]
        from apps.scholarship.services.read_retry import service_error_documents
        self.assertEqual(service_error_documents(200), [])      # two reads this hour = the cap
        busy[0].vision_fields_run_at = timezone.now() - timedelta(hours=2)
        busy[0].save(update_fields=['vision_fields_run_at'])
        self.assertEqual([d.id for d in service_error_documents(200)], [throttled.id])

    def test_dry_run_counts_them_and_reads_nothing(self):
        from apps.scholarship.services import reprocess_unread_ic_documents
        self._service_doc()
        with patch('apps.scholarship.reextract.reextract_document') as rx:
            r = reprocess_unread_ic_documents(dry_run=True)
        rx.assert_not_called()
        self.assertEqual(r, {'scanned': 1, 'by_type': {'salary_slip': 1}})


# ── 3. The alert covers Gemini, and the hourly mode mails the start only ───────────────────────

@override_settings(ADMIN_NOTIFY_EMAIL='ops@example.test')
class TheOutageAlertCoversGeminiReads(TestCase):
    def setUp(self):
        self.app = make_application('shortlisted')
        self.other = make_application('shortlisted')
        self.now = timezone.now()

    def _read(self, hours_ago, *, error='', capture='ai', app=None):
        return _doc(app or self.app, 'offer_letter',
                    vision_fields_run_at=self.now - timedelta(hours=hours_ago),
                    vision_fields={'fields': {}, 'student_verdict': 'review_manually' if error else 'ok',
                                   'capture': capture, 'error': error})

    def _fail(self, hours_ago, app=None):
        return self._read(hours_ago, error=f'All AI models failed: gemini-2.5-flash: {_402}', app=app)

    def _fail_twice(self, hours_ago):
        """The hourly mode's floor: two failures, two families."""
        self._fail(hours_ago)
        self._fail(hours_ago, app=self.other)

    def _down(self, **kw):
        from apps.scholarship.services import detect_service_outages
        return [s['service'] for s in detect_service_outages(now=self.now, **kw)]

    def test_a_gemini_only_outage_is_detected_and_mailed_with_its_cause(self):
        self._fail(1)
        self._fail(3)
        self.assertEqual(self._down(), ['gemini'])
        call_command('alert_vision_outage')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Gemini', mail.outbox[0].subject)
        self.assertIn('prepayment credits are depleted', mail.outbox[0].body)
        self.assertIn('repeat daily', mail.outbox[0].body)

    def test_one_success_means_not_down(self):
        self._fail(1)
        self._read(5)
        self.assertEqual(self._down(), [])

    def test_an_exact_read_or_our_own_throttle_proves_nothing_either_way(self):
        self._fail(1)
        self._read(2, capture='deterministic')                  # never asked Gemini
        self.assertEqual(self._down(), ['gemini'])
        ApplicantDocument.objects.all().delete()
        self._read(1, error='rate_limited', capture='')
        self.assertEqual(self._down(), [])

    def test_the_hourly_mode_mails_the_hour_an_outage_starts_and_not_the_next(self):
        self._read(2.5)                                         # the last success
        self._fail_twice(0.5)
        self.assertEqual(self._down(window_hours=2, start_edge=True), ['gemini'])
        # One hour later — give or take Cloud Scheduler's jitter — the outage is still on, and the
        # previous run already reported it.
        for minutes in (55, 60, 65):
            with self.subTest(minutes=minutes):
                self.now = timezone.now() + timedelta(minutes=minutes)
                self.assertEqual(self._down(window_hours=2), ['gemini'])
                self.assertEqual(self._down(window_hours=2, start_edge=True), [])
            self.now = timezone.now()

    def test_a_late_scheduler_tick_does_not_swallow_the_first_alert(self):
        """The previous run fired five minutes late (65 minutes ago) and saw nothing: failures that
        began 62 minutes ago are news to it, so this run must still mail."""
        self._fail_twice(62 / 60)
        self.assertEqual(self._down(window_hours=2, start_edge=True), ['gemini'])

    def test_the_hourly_mode_needs_two_failures_from_two_families(self):
        self._fail(0.5)
        self._fail(0.4)                                         # two failures, ONE application
        self.assertEqual(self._down(window_hours=2), ['gemini'])          # the daily rule: down
        self.assertEqual(self._down(window_hours=2, start_edge=True), [])  # hourly: not yet
        self._fail(0.3, app=self.other)
        self.assertEqual(self._down(window_hours=2, start_edge=True), ['gemini'])

    def test_the_hourly_command_mails_once_with_the_start_wording(self):
        last_success = self._read(2.5)
        self._fail_twice(0.5)
        call_command('alert_vision_outage', '--hourly')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('STARTS', mail.outbox[0].body)
        # An outage the run an hour ago could already see (no success in ITS window) is not news.
        last_success.delete()
        self._fail_twice(1.5)
        mail.outbox.clear()
        call_command('alert_vision_outage', '--hourly')
        self.assertEqual(len(mail.outbox), 0)

    def test_a_supporting_documents_vision_failure_counts_for_vision_not_gemini(self):
        """Round 2, finding 6: a Vision outage on supporting documents raised no alert at all."""
        self._read(1, error='OCR service failed: 403 billing disabled')
        for app in (self.app, self.other):                      # OCR ran and found no text: the files'
            _doc(app, 'water_bill', vision_run_at=self.now - timedelta(hours=1),
                 vision_error='no text read')                   # problem, never an outage on its own
        self.assertEqual(self._down(), [])
        for app in (self.app, self.other):
            _doc(app, 'salary_slip', vision_run_at=self.now - timedelta(hours=1),
                 vision_error='403 Cloud Vision API billing disabled')
        self.assertEqual(self._down(), ['vision'])
        _doc(self.app, 'water_bill', vision_run_at=self.now - timedelta(hours=1),
             vision_error='no text read')                       # the file's problem, not Vision's
        self.assertEqual(self._down(), ['vision'])
        _doc(self.app, 'water_bill', vision_run_at=self.now - timedelta(hours=1), vision_error='')
        self.assertEqual(self._down(), [])                      # one OCR success: Vision is up

    def test_a_clean_pdf_payslip_does_not_mask_an_ic_vision_outage(self):
        """Round 3, finding 2: a digital PDF is read from its text layer and never reaches Vision,
        but the name check still stamps `vision_run_at` — it is no proof Vision is up."""
        for app in (self.app, self.other):
            _doc(app, 'ic', vision_run_at=self.now - timedelta(hours=1),
                 vision_error='403 Cloud Vision API has not been used in project')
        _doc(self.app, 'salary_slip', content_type='application/pdf',
             vision_run_at=self.now - timedelta(hours=1), vision_error='')
        self.assertEqual(self._down(), ['vision'])
        _doc(self.app, 'salary_slip', vision_run_at=self.now - timedelta(hours=1), vision_error='')
        self.assertEqual(self._down(), [])                      # an IMAGE that read: Vision is up

    def test_the_hourly_job_has_a_cron_door_and_carries_its_flag(self):
        from apps.scholarship.views import CronRunView
        self.assertEqual(CronRunView.JOBS['read-outage-start'], ('alert_vision_outage', ('--hourly',)))
        self.assertEqual(CronRunView.JOBS['vision-outage'], 'alert_vision_outage')   # daily: unchanged


# ── 4. The cascade error names every model ─────────────────────────────────────────────────────

@override_settings(GEMINI_API_KEY='test-key')
class TheCascadeErrorCarriesEveryModel(TestCase):
    def test_the_json_seam_reports_each_models_own_error(self):
        client = _gemini_client({'gemini-2.5-flash': _402, 'gemini-2.5-flash-lite': 'lite: 503 UNAVAILABLE'})
        with patch('google.genai.Client', return_value=client):
            err = vision._call_gemini_json('prompt', {'type': 'object'})['_error']
        self.assertEqual(client.asked, ['gemini-2.5-flash', 'gemini-2.5-flash-lite'])
        self.assertTrue(err.startswith('All AI models failed: gemini-2.5-flash: 402'))
        self.assertIn('gemini-2.5-flash-lite: lite: 503 UNAVAILABLE', err)
        self.assertLessEqual(len(err), 600)

    def test_the_prose_seam_reports_each_models_own_error(self):
        from apps.scholarship.profile_engine import _call_gemini_text
        client = _gemini_client({'gemini-2.5-flash': _402, 'gemini-2.5-flash-lite': 'lite down'})
        with patch('google.genai.Client', return_value=client):
            err = _call_gemini_text('prompt', 'English')['error']
        self.assertIn('gemini-2.5-flash: 402', err)
        self.assertIn('gemini-2.5-flash-lite: lite down', err)

    def test_long_errors_are_cut_so_every_model_still_shows(self):
        err = gemini.cascade_failure([('gemini-2.5-pro', 'x' * 5000), ('gemini-2.5-flash', _402 * 5),
                                      ('gemini-2.5-flash-lite', _404)])
        self.assertLessEqual(len(err), 600)
        for model in ('gemini-2.5-pro: ', 'gemini-2.5-flash: 402', 'gemini-2.5-flash-lite: 404'):
            self.assertIn(model, err)
        self.assertTrue(read_errors.is_ai_service_error(err))

    def test_the_retired_model_is_in_no_runtime_cascade(self):
        from apps.courses.management.commands import map_course_careers
        from apps.reports import report_engine
        from apps.scholarship import profile_engine
        for cascade in (profile_engine.MODEL_CASCADE, profile_engine.PRO_CASCADE,
                        report_engine.MODEL_CASCADE, map_course_careers.MODEL_CASCADE):
            with self.subTest(cascade=cascade):
                self.assertTrue(cascade)
                self.assertNotIn('gemini-2.0-flash', cascade)
