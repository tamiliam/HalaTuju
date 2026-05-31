"""Tests for the document-help coach engine ("Cikgu Gopal") — Task 1 + guardrails (Task 4).

Every test mocks the ONE Gemini seam (``profile_engine._call_gemini_text``) — no billable
calls in CI (lessons.md: single mockable seam). The engine only *phrases* an already-decided
verdict; it never decides one and never receives admin data (structural firewall).
"""
import inspect
from unittest.mock import patch

from django.test import TestCase

from apps.scholarship import help_engine

SEAM = 'apps.scholarship.profile_engine._call_gemini_text'


class TestShouldHelp(TestCase):
    """A good/absent verdict means nothing to help with → no Gemini call at all."""

    def test_ok_verdict_returns_none_and_does_not_call_gemini(self):
        with patch(SEAM) as m:
            r = help_engine.generate_document_help('ic', 'ok')
        self.assertEqual(r['source'], 'none')
        self.assertEqual(r['message'], '')
        m.assert_not_called()

    def test_blank_verdict_returns_none_and_does_not_call_gemini(self):
        with patch(SEAM) as m:
            r = help_engine.generate_document_help('salary_slip', '')
        self.assertEqual(r['source'], 'none')
        m.assert_not_called()

    def test_match_verdict_returns_none(self):
        with patch(SEAM) as m:
            r = help_engine.generate_document_help('ic', 'match')
        self.assertEqual(r['source'], 'none')
        m.assert_not_called()


class TestGenerateHelp(TestCase):
    def test_success_returns_ai_message(self):
        with patch(SEAM, return_value={'markdown': 'No worries, Aisyah! Let me help.',
                                       'model_used': 'gemini-2.5-flash'}):
            r = help_engine.generate_document_help('salary_slip', 'name_mismatch', first_name='Aisyah')
        self.assertEqual(r['source'], 'ai')
        self.assertIn('No worries', r['message'])
        self.assertEqual(r['model_used'], 'gemini-2.5-flash')

    def test_engine_error_degrades_to_fallback(self):
        with patch(SEAM, return_value={'error': 'AI service not configured'}):
            r = help_engine.generate_document_help('ic', 'nric_mismatch')
        self.assertEqual(r['source'], 'fallback')
        self.assertEqual(r['message'], '')

    def test_empty_model_text_degrades_to_fallback(self):
        with patch(SEAM, return_value={'markdown': '   ', 'model_used': 'x'}):
            r = help_engine.generate_document_help('ic', 'unreadable')
        self.assertEqual(r['source'], 'fallback')

    def test_every_known_verdict_builds_a_prompt_with_its_cause(self):
        for v, cause in help_engine.VERDICT_GUIDANCE.items():
            p = help_engine._build_help_prompt('salary_slip', v, 'Ravi', help_engine.DEFAULT_LANGUAGE)
            self.assertIn(cause, p)
            self.assertIn('Ravi', p)


class TestGuardrails(TestCase):
    """Task 4 — the hard rule: coach, never ghostwriter; never leak a score; firewalled."""

    def test_prompt_forbids_ghostwriting_for_every_verdict_and_language(self):
        for lang in ('English', 'Malay (Bahasa Melayu)'):
            for v in help_engine.VERDICT_GUIDANCE:
                p = help_engine._build_help_prompt('ic', v, 'Siti', lang).lower()
                self.assertIn('never write', p)          # no drafting their answers
                self.assertIn('answer', p)
                self.assertIn('do not have access', p)   # no scores/reviewer opinions

    def test_prompt_names_the_persona(self):
        p = help_engine._build_help_prompt('ic', 'nric_mismatch', 'Siti', help_engine.DEFAULT_LANGUAGE)
        self.assertIn('Cikgu Gopal', p)

    def test_engine_signature_is_structurally_firewalled(self):
        """The engine can ONLY be passed doc_type/verdict/first_name/target_language —
        there is no parameter through which an application, profile, sponsor profile,
        interview or score could reach it. The firewall is structural, not prompt-trust."""
        params = set(inspect.signature(help_engine.generate_document_help).parameters)
        self.assertEqual(params, {'doc_type', 'verdict', 'first_name', 'target_language'})
