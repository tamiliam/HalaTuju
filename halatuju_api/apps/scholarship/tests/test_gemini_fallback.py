"""Gemini Phase 1 — every former Pro job falls back down the Flash cascade.

`gemini-2.5-pro` answers 404 for our key (since about 2026-10-25), so request triage was dead and
the contract and sponsor-terms quiz and the Word import would fail. The owner ruled on 2026-11-10:
3.8 Flash replaces 2.5 Pro, and every former Pro job may fall back to the Flash cascade, contracts
included (superseding "Owner decision 4: no downgrade"). `docs/decisions.md`, 2026-11-10.

Each single-model caller is driven through its OWN `_gemini_generate` seam, patched by the same
path the rest of the suite uses, so these tests prove the patch targets still land.
"""
import json
import os
from unittest import mock
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import contracts, gemini, org_requests, sponsor_terms
from apps.scholarship.models import UsageEvent
from apps.scholarship.profile_engine import MODEL_CASCADE, PRO_CASCADE, cascade_from
from apps.scholarship.tests.contract_helpers import seed_draft
from apps.scholarship.tests.test_org_requests import _GOOD, _Base as _RequestBase
from apps.scholarship.tests.test_sponsor_terms import _draft as _terms_draft

CONFIGURED = 'gemini-3.8-flash'
QUIZ = {'tag': 'T', 'plain': 'p', 'question': 'q?', 'options': ['a', 'b', 'c'],
        'correct': 1, 'why': 'w'}
QUIZ_JSON = json.dumps({'en': QUIZ, 'ms': QUIZ, 'ta': QUIZ})
SEGMENTS_JSON = json.dumps([{'heading': 'A', 'body': 'a', 'level': 0}])


class _NotFound(Exception):
    """Stands in for the provider's 404 on a retired model."""


def _seam(answers):
    """A fake seam: `answers[model]` is returned, or raised if it is an exception. Records the
    order the models were asked in on `.asked`."""
    def call(prompt, model, **kwargs):
        call.asked.append(model)
        out = answers[model]
        if isinstance(out, Exception):
            raise out
        return out
    call.asked = []
    return call


def _first_fails(text):
    """The configured model 404s; the first Flash model answers."""
    return _seam({CONFIGURED: _NotFound('404 gemini'), MODEL_CASCADE[0]: text,
                  MODEL_CASCADE[1]: text})


def _all_fail():
    return _seam({m: _NotFound(f'404 {m}') for m in cascade_from(CONFIGURED)})


class TestTheOrder(SimpleTestCase):
    def test_the_pro_cascade_starts_on_3_8_flash_without_a_repeat(self):
        self.assertEqual(PRO_CASCADE, [CONFIGURED, *MODEL_CASCADE])
        self.assertNotIn('gemini-2.5-pro', PRO_CASCADE)

    def test_both_settings_default_to_3_8_flash(self):
        """The defaults, read from the settings module (an env var on the host still overrides)."""
        from halatuju.settings import base
        for name in ('CONTRACT_QUIZ_MODEL', 'REQUESTS_TRIAGE_MODEL'):
            with self.subTest(setting=name):
                self.assertEqual(getattr(base, name), os.environ.get(name, CONFIGURED))

    def test_a_configured_model_already_in_the_cascade_is_not_tried_twice(self):
        self.assertEqual(cascade_from(MODEL_CASCADE[1]), [MODEL_CASCADE[1], MODEL_CASCADE[0]])
        self.assertEqual(cascade_from(''), list(MODEL_CASCADE))


class TestTheRunner(SimpleTestCase):
    def test_the_configured_model_is_asked_first_and_its_answer_wins(self):
        seam = _seam({CONFIGURED: 'ok'})
        self.assertEqual(gemini.generate_with_fallback(seam, 'p', CONFIGURED, fatal=ValueError),
                         ('ok', CONFIGURED))
        self.assertEqual(seam.asked, [CONFIGURED])

    def test_a_failure_moves_to_the_next_model_and_names_the_one_that_answered(self):
        seam = _first_fails('ok')
        self.assertEqual(gemini.generate_with_fallback(seam, 'p', CONFIGURED, fatal=ValueError),
                         ('ok', MODEL_CASCADE[0]))
        self.assertEqual(seam.asked, [CONFIGURED, MODEL_CASCADE[0]])

    def test_an_empty_answer_moves_on_too(self):
        seam = _seam({CONFIGURED: '  ', MODEL_CASCADE[0]: 'ok'})
        self.assertEqual(gemini.generate_with_fallback(seam, 'p', CONFIGURED, fatal=ValueError),
                         ('ok', MODEL_CASCADE[0]))

    def test_when_every_model_fails_the_last_error_goes_up(self):
        seam = _all_fail()
        with self.assertRaises(_NotFound) as cm:
            gemini.generate_with_fallback(seam, 'p', CONFIGURED, fatal=ValueError)
        self.assertIn(MODEL_CASCADE[-1], str(cm.exception))
        self.assertEqual(seam.asked, cascade_from(CONFIGURED))

    def test_when_every_model_is_empty_the_empty_answer_comes_back(self):
        seam = _seam({m: '' for m in cascade_from(CONFIGURED)})
        self.assertEqual(gemini.generate_with_fallback(seam, 'p', CONFIGURED, fatal=ValueError),
                         ('', CONFIGURED))

    def test_no_key_or_no_sdk_is_not_retried(self):
        seam = _seam({CONFIGURED: ValueError('quiz_ai_unconfigured')})
        with self.assertRaises(ValueError):
            gemini.generate_with_fallback(seam, 'p', CONFIGURED, fatal=ValueError)
        self.assertEqual(seam.asked, [CONFIGURED])

    def test_extra_arguments_reach_every_try(self):
        seen = []

        def seam(prompt, model, images=None):
            seen.append(images)
            if model == CONFIGURED:
                raise _NotFound('404')
            return 'ok'
        gemini.generate_with_fallback(seam, 'p', CONFIGURED, fatal=ValueError, images=['i'])
        self.assertEqual(seen, [['i'], ['i']])


@override_settings(GEMINI_API_KEY='test-key', CONTRACT_QUIZ_MODEL=CONFIGURED)
class TestTheContractModule(TestCase):
    def setUp(self):
        self.clause = seed_draft('2026-gp1').clauses.get(order=2)

    def test_the_quiz_falls_back_and_stamps_the_model_that_answered(self):
        seam = _first_fails(QUIZ_JSON)
        with patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            contracts.generate_quiz(self.clause)
        self.clause.refresh_from_db()
        self.assertEqual(seam.asked, [CONFIGURED, MODEL_CASCADE[0]])
        self.assertEqual(self.clause.quiz_generated_model, MODEL_CASCADE[0])

    def test_the_quiz_still_raises_when_every_model_fails(self):
        seam = _all_fail()
        with patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            with self.assertRaises(_NotFound):
                contracts.generate_quiz(self.clause)
        self.assertEqual(seam.asked, cascade_from(CONFIGURED))
        self.clause.refresh_from_db()
        self.assertEqual(self.clause.quiz_en, {})

    def test_the_quiz_still_refuses_with_no_key_after_one_try(self):
        seam = _seam({CONFIGURED: contracts.ContractsError('quiz_ai_unconfigured')})
        with patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            with self.assertRaises(contracts.ContractsError) as cm:
                contracts.generate_quiz(self.clause)
        self.assertEqual(cm.exception.code, 'quiz_ai_unconfigured')
        self.assertEqual(seam.asked, [CONFIGURED])

    @patch('apps.scholarship.contracts._extract_docx_text', return_value='flat text')
    @patch('apps.scholarship.contracts._docx_structure', return_value=None)
    def test_the_word_import_falls_back(self, _struct, _text):
        seam = _first_fails(SEGMENTS_JSON)
        with patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            got = contracts.segment_docx(b'x')
        self.assertEqual(seam.asked, [CONFIGURED, MODEL_CASCADE[0]])
        self.assertEqual([c['heading'] for c in got['clauses']], ['A'])

    @patch('google.genai.Client')
    def test_the_meter_records_the_model_that_answered(self, client_cls):
        response = MagicMock(text=QUIZ_JSON)
        response.usage_metadata.prompt_token_count = 10
        response.usage_metadata.candidates_token_count = 5

        def generate_content(model, contents):
            if model == CONFIGURED:
                raise _NotFound('404')
            return response
        client_cls.return_value.models.generate_content.side_effect = generate_content
        contracts.generate_quiz(self.clause)
        self.assertEqual(list(UsageEvent.objects.values_list('model', 'source')),
                         [(MODEL_CASCADE[0], 'contract_quiz')])


@override_settings(GEMINI_API_KEY='test-key', CONTRACT_QUIZ_MODEL=CONFIGURED)
class TestSponsorTerms(TestCase):
    def setUp(self):
        self.section = _terms_draft('gp1').sections.first()

    def test_the_quiz_falls_back_and_stamps_the_model_that_answered(self):
        seam = _first_fails(QUIZ_JSON)
        with patch('apps.scholarship.sponsor_terms._gemini_generate', side_effect=seam):
            sponsor_terms.generate_quiz(self.section)
        self.section.refresh_from_db()
        self.assertEqual(seam.asked, [CONFIGURED, MODEL_CASCADE[0]])
        self.assertEqual(self.section.quiz_generated_model, MODEL_CASCADE[0])

    def test_the_quiz_still_raises_when_every_model_fails(self):
        seam = _all_fail()
        with patch('apps.scholarship.sponsor_terms._gemini_generate', side_effect=seam):
            with self.assertRaises(_NotFound):
                sponsor_terms.generate_quiz(self.section)
        self.assertEqual(seam.asked, cascade_from(CONFIGURED))

    @patch('apps.scholarship.contracts._extract_docx_text', return_value='flat text')
    @patch('apps.scholarship.contracts._docx_structure', return_value=None)
    def test_the_word_import_falls_back(self, _struct, _text):
        seam = _first_fails(SEGMENTS_JSON)
        with patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            out = sponsor_terms.import_docx(b'x')
        self.assertEqual(seam.asked, [CONFIGURED, MODEL_CASCADE[0]])
        self.assertEqual([s['heading_en'] for s in out['sections']], ['A'])


@override_settings(REQUESTS_TRIAGE_MODEL=CONFIGURED)
class TestRequestTriage(_RequestBase):
    def test_triage_falls_back_and_records_the_model_that_answered(self):
        r = self._req()
        seam = _first_fails(_GOOD)
        with mock.patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            org_requests.run_ai_review(r)
        r.refresh_from_db()
        self.assertEqual(seam.asked, [CONFIGURED, MODEL_CASCADE[0]])
        self.assertEqual(r.ai_draft_model, MODEL_CASCADE[0])
        self.assertEqual(r.ai_run_count, 1)

    def test_when_every_model_fails_it_is_still_triage_ai_unavailable(self):
        r = self._req()
        seam = _all_fail()
        with mock.patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            with self.assertRaises(org_requests.OrgRequestError) as cm:
                org_requests.run_ai_review(r)
        self.assertEqual(cm.exception.code, 'triage_ai_unavailable')
        self.assertEqual(seam.asked, cascade_from(CONFIGURED))
        r.refresh_from_db()
        self.assertEqual(r.ai_run_count, 0)

    def test_no_key_is_still_triage_ai_unconfigured_after_one_try(self):
        r = self._req()
        seam = _seam({CONFIGURED: contracts.ContractsError('quiz_ai_unconfigured')})
        with mock.patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            with self.assertRaises(org_requests.OrgRequestError) as cm:
                org_requests.run_ai_review(r)
        self.assertEqual(cm.exception.code, 'triage_ai_unconfigured')
        self.assertEqual(seam.asked, [CONFIGURED])
