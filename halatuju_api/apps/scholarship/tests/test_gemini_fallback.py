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
from apps.scholarship.read_errors import CASCADE_FAILED
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

        def seam(prompt, model, images=None, timeout_ms=None):
            seen.append(images)
            if model == CONFIGURED:
                raise _NotFound('404')
            return 'ok'
        gemini.generate_with_fallback(seam, 'p', CONFIGURED, fatal=ValueError, images=['i'])
        self.assertEqual(seen, [['i'], ['i']])

    def test_a_missing_answer_moves_on_like_an_empty_one(self):
        seam = _seam({CONFIGURED: None, MODEL_CASCADE[0]: 'ok'})
        self.assertEqual(gemini.generate_with_fallback(seam, 'p', CONFIGURED, fatal=ValueError),
                         ('ok', MODEL_CASCADE[0]))

    def test_when_every_model_fails_the_whole_story_is_logged(self):
        with self.assertLogs('apps.scholarship.gemini', 'WARNING') as logs:
            with self.assertRaises(_NotFound):
                gemini.generate_with_fallback(_all_fail(), 'p', CONFIGURED, fatal=ValueError)
        story = [line for line in logs.output if CASCADE_FAILED in line]
        self.assertEqual(len(story), 1)
        for model in cascade_from(CONFIGURED):
            self.assertIn(f'404 {model}', story[0])


class TestTheDeadline(SimpleTestCase):
    """Review fix: the runner works inside a web request (gunicorn kills a worker at 120 s), so it
    has an overall deadline. A fake clock stands in for time; nothing sleeps."""

    def _run(self, seconds_per_model, answers):
        """Each model "takes" `seconds_per_model[model]` on the fake clock. Returns the seam, which
        records each try's `timeout_ms` on `.timeouts`."""
        now = [1000.0]
        inner = _seam(answers)

        def seam(prompt, model, timeout_ms=None):
            seam.timeouts.append(timeout_ms)
            now[0] += seconds_per_model.get(model, 0)
            return inner(prompt, model)
        seam.timeouts, seam.asked = [], inner.asked
        with patch.object(gemini, '_clock', lambda: now[0]):
            try:
                seam.result = gemini.generate_with_fallback(seam, 'p', CONFIGURED,
                                                            fatal=ValueError)
            except _NotFound as e:
                seam.result = e
        return seam

    def test_the_first_try_gets_100_s_and_each_later_one_what_is_left_of_115(self):
        seam = self._run({CONFIGURED: 40, MODEL_CASCADE[0]: 50},
                         {CONFIGURED: _NotFound('a'), MODEL_CASCADE[0]: _NotFound('b'),
                          MODEL_CASCADE[1]: 'ok'})
        self.assertEqual(seam.result, ('ok', MODEL_CASCADE[1]))
        self.assertEqual(seam.timeouts, [100_000, 75_000, 25_000])

    def test_a_later_try_still_starts_with_exactly_15_s_left(self):
        seam = self._run({CONFIGURED: 100}, {CONFIGURED: _NotFound('a'), MODEL_CASCADE[0]: 'ok'})
        self.assertEqual(seam.result, ('ok', MODEL_CASCADE[0]))
        self.assertEqual(seam.timeouts, [100_000, 15_000])

    def test_with_under_15_s_left_no_later_try_starts_and_the_last_error_goes_up(self):
        first = _NotFound('404 first')
        seam = self._run({CONFIGURED: 101}, {CONFIGURED: first, MODEL_CASCADE[0]: 'ok'})
        self.assertIs(seam.result, first)
        self.assertEqual(seam.asked, [CONFIGURED])

    def test_the_deadline_counts_from_the_start_not_per_try(self):
        seam = self._run({CONFIGURED: 60, MODEL_CASCADE[0]: 45},
                         {m: _NotFound(m) for m in cascade_from(CONFIGURED)})
        self.assertEqual(seam.asked, [CONFIGURED, MODEL_CASCADE[0]])
        self.assertEqual(seam.timeouts, [100_000, 55_000])
        self.assertEqual(str(seam.result), MODEL_CASCADE[0])


@override_settings(GEMINI_API_KEY='test-key')
class TestTheClientTimeout(TestCase):
    """The HTTP timeout is set ONLY on the runner's path; every other caller of `generate_text`
    (vision, the prose cascade, `apply_copy_draft`) builds the client exactly as before."""

    def _generate(self, client_cls, **kw):
        client_cls.return_value.models.generate_content.return_value = MagicMock(text='ok')
        return gemini.generate_text('p', CONFIGURED, exc=ValueError, unconfigured='u',
                                    unavailable='a', **kw)

    @patch('google.genai.Client')
    def test_by_default_the_client_is_built_as_before(self, client_cls):
        self.assertEqual(self._generate(client_cls), 'ok')
        client_cls.assert_called_once_with(api_key='test-key')

    @patch('google.genai.Client')
    def test_a_timeout_goes_into_the_clients_http_options(self, client_cls):
        self._generate(client_cls, timeout_ms=42_000)
        self.assertEqual(client_cls.call_args.kwargs['http_options'].timeout, 42_000)

    @patch('google.genai.Client')
    def test_the_seams_pass_the_runners_timeout_through(self, client_cls):
        client_cls.return_value.models.generate_content.return_value = MagicMock(text='ok')
        for seam in (contracts._gemini_generate, sponsor_terms._gemini_generate):
            with self.subTest(seam=seam.__module__):
                client_cls.reset_mock()
                seam('p', CONFIGURED, timeout_ms=7_000)
                self.assertEqual(client_cls.call_args.kwargs['http_options'].timeout, 7_000)


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

    @patch('apps.scholarship.contracts._extract_docx_text', return_value='flat text')
    @patch('apps.scholarship.contracts._docx_structure', return_value=None)
    def test_the_word_import_still_raises_when_every_model_fails(self, _struct, _text):
        seam = _all_fail()
        with patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            with self.assertRaises(_NotFound):
                contracts.segment_docx(b'x')
        self.assertEqual(seam.asked, cascade_from(CONFIGURED))

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

    @patch('apps.scholarship.contracts._extract_docx_text', return_value='flat text')
    @patch('apps.scholarship.contracts._docx_structure', return_value=None)
    def test_the_word_import_still_raises_when_every_model_fails(self, _struct, _text):
        seam = _all_fail()
        with patch('apps.scholarship.contracts._gemini_generate', side_effect=seam):
            with self.assertRaises(_NotFound):
                sponsor_terms.import_docx(b'x')
        self.assertEqual(seam.asked, cascade_from(CONFIGURED))

    @override_settings(GEMINI_API_KEY='')
    def test_the_quiz_still_refuses_with_no_key_after_one_try(self):
        with patch('apps.scholarship.sponsor_terms._gemini_generate',
                   wraps=sponsor_terms._gemini_generate) as seam:
            with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
                sponsor_terms.generate_quiz(self.section)
        self.assertEqual(cm.exception.code, 'quiz_ai_unconfigured')
        self.assertEqual(seam.call_count, 1)
        self.assertEqual(seam.call_args.args[1], CONFIGURED)


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

    @override_settings(GEMINI_API_KEY='test-key')
    @patch('google.genai.Client')
    def test_the_meter_records_the_model_that_answered(self, client_cls):
        response = MagicMock(text=_GOOD)
        response.usage_metadata.prompt_token_count = 10
        response.usage_metadata.candidates_token_count = 5

        def generate_content(model, contents):
            if model == CONFIGURED:
                raise _NotFound('404')
            return response
        client_cls.return_value.models.generate_content.side_effect = generate_content
        org_requests.run_ai_review(self._req())
        self.assertEqual(list(UsageEvent.objects.values_list('model', 'source')),
                         [(MODEL_CASCADE[0], 'requests_triage')])
