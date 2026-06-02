"""Tests for the document-help coach engine ("Cikgu Gopal") — Task 1 + guardrails (Task 4).

Every test mocks the ONE Gemini seam (``profile_engine._call_gemini_text``) — no billable
calls in CI (lessons.md: single mockable seam). The engine only *phrases* an already-decided
verdict; it never decides one and never receives admin data (structural firewall).
"""
import inspect
from types import SimpleNamespace
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

    def test_name_mismatch_prompt_is_bidirectional(self):
        """#6 — a name mismatch can be a misread photo OR a mistyped profile name; the
        prompt must offer BOTH fixes (re-upload AND fix the profile), not assume the
        document is the wrong one."""
        p = help_engine._build_help_prompt('ic', 'name_mismatch', 'Theresa',
                                           help_engine.DEFAULT_LANGUAGE).lower()
        self.assertIn('profile', p)        # the edit-your-name path
        self.assertIn('clearer', p)        # the re-upload path
        self.assertIn('both', p)           # explicitly offers both

    def test_non_name_verdict_uses_default_fix_hint(self):
        p = help_engine._build_help_prompt('ic', 'unreadable', 'Theresa',
                                           help_engine.DEFAULT_LANGUAGE)
        self.assertIn(help_engine.DEFAULT_FIX_HINT, p)

    def test_slip_grade_mismatch_directs_to_profile(self):
        """Results slip is authoritative — the grade fix is to update the PROFILE."""
        p = help_engine._build_help_prompt('results_slip', 'slip_grade_mismatch', 'Ravi',
                                           help_engine.DEFAULT_LANGUAGE).lower()
        self.assertIn('profile', p)
        self.assertIn('official', p)                 # slip is the official record
        self.assertIn('never suggest changing the slip', p)

    def test_slip_name_mismatch_says_wrong_file(self):
        p = help_engine._build_help_prompt('results_slip', 'slip_name_mismatch', 'Ravi',
                                           help_engine.DEFAULT_LANGUAGE).lower()
        self.assertIn('own results slip', p)         # upload YOUR own slip

    def test_slip_subjects_missing_adds_on_profile(self):
        p = help_engine._build_help_prompt('results_slip', 'slip_subjects_missing', 'Ravi',
                                           help_engine.DEFAULT_LANGUAGE).lower()
        self.assertIn('profile', p)
        self.assertIn('missing subject', p)


class TestSlipVerdictRouting(TestCase):
    """verdict_for_document picks the right slip verdict, most-important-first."""

    @staticmethod
    def _slip_doc(student_verdict, results, grades, name_match='found'):
        return SimpleNamespace(
            doc_type='results_slip', vision_name_match=name_match,
            vision_fields={'fields': {'results': results, 'candidate_name': 'X'},
                           'student_verdict': student_verdict},
            application=SimpleNamespace(profile=SimpleNamespace(grades=grades)),
        )

    _RES = [{'subject': 'MATEMATIK CEMERLANG TINGGI', 'grade': 'A'}]

    def test_name_mismatch_wins(self):
        doc = self._slip_doc('name_mismatch', self._RES, {'math': 'A'}, name_match='not_found')
        self.assertEqual(help_engine.verdict_for_document(doc), 'slip_name_mismatch')

    def test_subjects_missing(self):
        doc = self._slip_doc('ok', self._RES, {})   # nothing entered → Matematik missing
        self.assertEqual(help_engine.verdict_for_document(doc), 'slip_subjects_missing')

    def test_grade_mismatch(self):
        doc = self._slip_doc('ok', self._RES, {'math': 'B+'})
        self.assertEqual(help_engine.verdict_for_document(doc), 'slip_grade_mismatch')

    def test_all_good_no_coach(self):
        doc = self._slip_doc('ok', self._RES, {'math': 'A'})
        self.assertEqual(help_engine.verdict_for_document(doc), '')

    def test_not_extracted_no_coach(self):
        doc = self._slip_doc(None, [], {'math': 'A'})
        self.assertEqual(help_engine.verdict_for_document(doc), '')


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
