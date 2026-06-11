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

    def test_income_proof_person_mismatch_is_earner_aware_not_hardcoded_father(self):
        """#4 — the wrong-person income coach must reference the SPECIFICS member + advise
        removal, not hardcode a 'father's payslip' example that misleads a mother-earner."""
        hint = help_engine.VERDICT_FIX_HINT['income_proof_person_mismatch'].lower()
        self.assertIn('specifics', hint)        # uses the named earner, not a fixed example
        self.assertIn('remove', hint)           # advises removing the wrong file

    def test_income_proof_optional_specifics_says_removable_and_not_needed(self):
        """#4 — on the STR route the salary slip is optional, so the SPECIFICS must tell the
        coach the proof is extra/removable and that none is needed if the earner has none."""
        block = help_engine._specifics_block({'member': 'mother', 'income_proof_optional': True})
        self.assertIn('OPTIONAL', block)
        self.assertIn('removed', block)
        # …and absent by default, so it never leaks into a compulsory-route message.
        self.assertNotIn('OPTIONAL', help_engine._specifics_block({'member': 'father'}))

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

    def test_slip_skewed_unclear_asks_for_a_straight_flat_photo(self):
        p = help_engine._build_help_prompt('results_slip', 'slip_skewed_unclear', 'Ravi',
                                           help_engine.DEFAULT_LANGUAGE).lower()
        self.assertIn('straight', p)
        self.assertIn('flat', p)
        self.assertIn('nothing is blocked', p)       # reassuring, never a block

    def test_slip_grade_uncertain_asks_to_double_check_never_asserts(self):
        p = help_engine._build_help_prompt('results_slip', 'slip_grade_uncertain', 'Ravi',
                                           help_engine.DEFAULT_LANGUAGE).lower()
        self.assertIn('double-check', p)
        self.assertIn('do not assert', p)            # never a confident "you're wrong"


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

    def test_unreadable_table_when_name_ok(self):
        # Gemini ran (name ok) but read no subject rows → ask for a clearer copy.
        doc = self._slip_doc('ok', [], {'math': 'A'})
        self.assertEqual(help_engine.verdict_for_document(doc), 'unreadable')

    def test_grade_uncertain_double_check_when_upright(self):
        # Typed A+ vs slip A (differ ONLY by +/- → uncertain) on an upright slip →
        # ask the student to double-check, NOT a confident mismatch.
        doc = self._slip_doc('ok', self._RES, {'math': 'A+'})
        self.assertEqual(help_engine.verdict_for_document(doc), 'slip_grade_uncertain')

    def test_grade_uncertain_skewed_asks_for_straight_retake(self):
        # Same doubtful read, but the photo was at an angle → blame the photo, ask for a
        # flat straight-on retake (not a profile edit).
        doc = self._slip_doc('ok', self._RES, {'math': 'A+'})
        doc.vision_fields['fields']['skew_angle'] = 89.3
        self.assertEqual(help_engine.verdict_for_document(doc), 'slip_skewed_unclear')

    def test_clean_rotated_slip_is_not_nagged(self):
        # THE ANTI-NAG RULE (Pavalaharasi): a rotated photo that nonetheless read CLEANLY
        # (every grade matches) gets NO coach and NO retake nudge.
        doc = self._slip_doc('ok', self._RES, {'math': 'A'})
        doc.vision_fields['fields']['skew_angle'] = 89.3
        self.assertEqual(help_engine.verdict_for_document(doc), '')


class TestOfferVerdictRouting(TestCase):
    """verdict_for_document on an offer letter: a wrong name OR IC → wrong-file coach."""

    @staticmethod
    def _offer_doc(student_verdict, fields, pname='Elan', pnric='710829-02-5709',
                   declared=None):
        declared = declared or {}
        return SimpleNamespace(
            doc_type='offer_letter', vision_name_match='not_found',
            vision_fields={'fields': fields, 'student_verdict': student_verdict},
            application=SimpleNamespace(
                profile=SimpleNamespace(name=pname, nric=pnric),
                chosen_programme={'course_name': declared.get('course_name', ''),
                                  'institution': declared.get('institution', '')},
                pre_u_track=declared.get('pre_u_track', ''),
                pre_u_institution=declared.get('pre_u_institution', '')),
        )

    def test_ic_mismatch_flags_wrong_file(self):
        doc = self._offer_doc('ok', {'candidate_name': 'Elan', 'candidate_nric': '999999-99-9999'})
        self.assertEqual(help_engine.verdict_for_document(doc), 'offer_name_mismatch')

    def test_name_mismatch_flags_wrong_file(self):
        doc = self._offer_doc('name_mismatch',
                              {'candidate_name': 'Someone Else', 'candidate_nric': '710829-02-5709'})
        self.assertEqual(help_engine.verdict_for_document(doc), 'offer_name_mismatch')

    def test_own_letter_no_coach(self):
        doc = self._offer_doc('ok', {'candidate_name': 'Elan', 'candidate_nric': '710829-02-5709'})
        self.assertEqual(help_engine.verdict_for_document(doc), '')

    def test_own_letter_clashing_pathway_soft_nudge(self):
        # Identity is fine but the offer is for a different field than declared →
        # the soft pathway-mismatch nudge (never the wrong-file one).
        doc = self._offer_doc(
            'ok',
            {'candidate_name': 'Elan', 'candidate_nric': '710829-02-5709',
             'programme': 'Diploma Kejuruteraan Elektrik', 'institution': 'UTeM'},
            declared={'course_name': 'Diploma Senibina', 'institution': 'UTeM'})
        self.assertEqual(help_engine.verdict_for_document(doc), 'offer_pathway_mismatch')

    def test_not_extracted_no_coach(self):
        doc = self._offer_doc(None, {})
        self.assertEqual(help_engine.verdict_for_document(doc), '')


class TestIcVerdictRouting(TestCase):
    """verdict_for_document on the student's OWN IC — name + IC-number checks vs the profile."""

    @staticmethod
    def _ic_doc(vision_name, vision_nric, pname='Elan A/L Venugopal', pnric='710829-02-5709'):
        return SimpleNamespace(
            doc_type='ic', vision_run_at='2026-06-05', vision_error='',
            vision_name=vision_name, vision_nric=vision_nric,
            application=SimpleNamespace(profile=SimpleNamespace(name=pname, nric=pnric)),
        )

    def test_name_ok_nric_mismatch_is_misread(self):
        # The headline case: name matches, only the IC number differs → likely a glare misread.
        doc = self._ic_doc('Elan A/L Venugopal', '999999-99-9999')
        self.assertEqual(help_engine.verdict_for_document(doc), 'ic_nric_misread')

    def test_both_mismatch_falls_back_to_generic(self):
        doc = self._ic_doc('Someone Else', '999999-99-9999')
        self.assertEqual(help_engine.verdict_for_document(doc), 'nric_mismatch')

    def test_nric_mismatch_with_no_name_read_is_generic(self):
        doc = self._ic_doc('', '999999-99-9999')
        self.assertEqual(help_engine.verdict_for_document(doc), 'nric_mismatch')

    def test_nric_ok_name_mismatch_is_name_mismatch(self):
        doc = self._ic_doc('Someone Else', '710829-02-5709')
        self.assertEqual(help_engine.verdict_for_document(doc), 'name_mismatch')

    def test_all_match_no_coach(self):
        doc = self._ic_doc('Elan A/L Venugopal', '710829-02-5709')
        self.assertEqual(help_engine.verdict_for_document(doc), '')

    def test_unreadable_when_no_nric(self):
        doc = self._ic_doc('Elan A/L Venugopal', '')
        self.assertEqual(help_engine.verdict_for_document(doc), 'unreadable')


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
        """The engine can ONLY be passed doc_type/verdict/first_name/target_language/context —
        there is no parameter through which an application, profile, sponsor profile,
        interview or score could reach it. ``context`` is a flat dict of NON-sensitive
        household specifics (member + document labels) — never a model object. The firewall
        is structural, not prompt-trust."""
        params = set(inspect.signature(help_engine.generate_document_help).parameters)
        self.assertEqual(params, {'doc_type', 'verdict', 'first_name', 'target_language', 'context'})

    def test_specifics_block_names_the_right_member_and_document(self):
        # The cluster coach supplies non-sensitive specifics so the message names the actual
        # earner + document (e.g. the mother's STR), not the generic father/payslip example.
        p = help_engine._build_help_prompt(
            'income_cluster', 'income_ic_needed', 'Elan', 'English',
            context={'member': 'mother', 'income_doc': 'STR document', 'rel_doc': ''})
        self.assertIn('SPECIFICS', p)
        self.assertIn('mother', p)
        self.assertIn('STR document', p)
        # No context → no specifics block (existing per-document coaches are unaffected).
        self.assertNotIn('SPECIFICS', help_engine._build_help_prompt('ic', 'nric_mismatch', 'Siti', 'English'))

    def test_rel_doc_needed_is_a_known_verdict(self):
        self.assertIn('income_rel_doc_needed', help_engine.VERDICT_GUIDANCE)
        self.assertIn('income_rel_doc_needed', help_engine.VERDICT_FIX_HINT)

    def test_rel_doc_unreadable_is_a_known_verdict(self):
        self.assertIn('income_rel_doc_unreadable', help_engine.VERDICT_GUIDANCE)
        self.assertIn('income_rel_doc_unreadable', help_engine.VERDICT_FIX_HINT)

    def test_income_proof_needed_is_a_known_verdict(self):
        self.assertIn('income_proof_needed', help_engine.VERDICT_GUIDANCE)
        self.assertIn('income_proof_needed', help_engine.VERDICT_FIX_HINT)

    def test_specifics_states_ic_confirmed_when_it_matches_the_income_doc(self):
        # When the earner IC is corroborated by the income doc, the prompt tells the coach the
        # MyKad is CONFIRMED so it points only at the relationship doc (drops the MyKad hedge).
        p = help_engine._build_help_prompt(
            'income_cluster', 'income_relationship_mismatch', 'Elan', 'English',
            context={'member': 'mother', 'rel_doc': 'birth certificate',
                     'ic_matches_income_doc': True})
        self.assertIn("the earner's MyKad has been CONFIRMED", p)   # the SPECIFICS fact line
        # Without the flag, the SPECIFICS don't state the MyKad is confirmed (the coach then
        # asks them to check both). NB the fix-hint text mentions "CONFIRMED" conditionally, so
        # assert on the specifics-line phrase, not the bare word.
        self.assertNotIn("the earner's MyKad has been CONFIRMED", help_engine._build_help_prompt(
            'income_cluster', 'income_relationship_mismatch', 'Elan', 'English',
            context={'member': 'mother', 'rel_doc': 'birth certificate'}))
