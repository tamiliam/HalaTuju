"""TD-319 — an EPF statement whose contribution table the in-house reader reports as ``unknown``
falls back to Gemini for the contribution fields (owner, 2026-10-01: *"allow."*).

Driven through the real extraction entry point, `vision.run_field_extraction_for_document`, with
the real KWSP parser over the committed synthetic statements in ``fixtures_epf`` (invented people
and amounts — no test reads ``eval/snapshots``). Gemini is mocked at
`vision.extract_document_fields`, the one name the fallback is handed.

The three behaviours the owner's ruling needs:
  * an ``unknown`` table → Gemini is called, and its contribution figures land (and the salary
    estimate can now be made from them);
  * a statement the parser READ → Gemini is NOT called (no paid call for a readable statement);
  * Gemini failing → the deterministic reading stands, with no figure.
"""
from unittest.mock import patch

from django.test import TestCase

from apps.scholarship import vision
from apps.scholarship.epf_contribution_fallback import (
    CONTRIBUTION_FIELDS, deterministic_or_epf_fallback)
from apps.scholarship.income_engine.salary_figures import _epf_monthly_salary
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests import fixtures_epf
from apps.scholarship.tests.factories import make_application

GEMINI = 'apps.scholarship.vision.extract_document_fields'

#: What Gemini returns for the cut-off statement in the "it could read it" case (invented).
GEMINI_READ = {'fields': {
    'name': 'SOMEONE ELSE ENTIRELY', 'nric': '000000000000', 'latest_balance': 'RM1.00',
    'contribution_status': 'has', 'monthly_contribution': 'RM480.00', 'months_counted': '6',
    'employer_contribution_total': 'RM1560.00', 'employee_contribution_total': 'RM1320.00',
    'last_contribution': 'RM480.00'}, 'warnings': [], 'error': ''}


class TestEpfUnknownFallsBackToGemini(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.app = make_application('submitted')

    def _read(self, text):
        doc = ApplicantDocument.objects.create(application=self.app, doc_type='epf',
                                               storage_path='x', household_member='father')
        vision.run_field_extraction_for_document(doc, names=[], ocr={'text': text, 'error': None})
        doc.refresh_from_db()
        return doc.vision_fields

    def test_the_fixture_still_reads_unknown_deterministically(self):
        # The premise: without this, every assertion below is about a different case.
        from apps.scholarship.doc_parse import parse_by_labels
        self.assertEqual(
            parse_by_labels('epf', fixtures_epf.TRUNCATED)['contribution_status'], 'unknown')

    @patch(GEMINI)
    def test_unknown_table_calls_gemini_and_its_figures_land(self, mock_gemini):
        mock_gemini.return_value = GEMINI_READ
        vf = self._read(fixtures_epf.TRUNCATED)
        mock_gemini.assert_called_once_with(fixtures_epf.TRUNCATED, 'epf')
        f = vf['fields']
        self.assertEqual(f['contribution_status'], 'has')
        self.assertEqual(f['employer_contribution_total'], 'RM1560.00')
        self.assertEqual(f['employee_contribution_total'], 'RM1320.00')
        self.assertEqual(f['months_counted'], '6')
        self.assertEqual(vf['capture'], 'ai')
        # ...and the salary estimate that had nothing to work from now has: max(1560/(6·.13), 1320/(6·.11))
        self.assertEqual(_epf_monthly_salary(f), 2000.0)

    @patch(GEMINI)
    def test_the_deterministic_identity_fields_are_kept(self, mock_gemini):
        mock_gemini.return_value = GEMINI_READ
        f = self._read(fixtures_epf.TRUNCATED)['fields']
        self.assertEqual(f['name'], 'KUMARAN A/L CONTOHAN')     # not Gemini's "SOMEONE ELSE"
        self.assertEqual(f['nric'], '780808-08-5858')
        self.assertEqual(f['latest_balance'], 'RM12000.00')

    @patch(GEMINI)
    def test_a_readable_statement_never_calls_gemini(self, mock_gemini):
        vf = self._read(fixtures_epf.FLAT_FIVE)
        mock_gemini.assert_not_called()
        self.assertEqual(vf['fields']['contribution_status'], 'has')
        self.assertEqual(vf['capture'], 'deterministic')

    @patch(GEMINI)
    def test_a_genuine_zero_never_calls_gemini(self, mock_gemini):
        vf = self._read(fixtures_epf.TIADA)
        mock_gemini.assert_not_called()
        self.assertEqual(vf['fields']['contribution_status'], 'zero')

    @patch(GEMINI)
    def test_gemini_error_leaves_the_deterministic_reading_with_no_figure(self, mock_gemini):
        mock_gemini.return_value = {'fields': {}, 'warnings': [], 'error': 'gemini timeout'}
        vf = self._read(fixtures_epf.TRUNCATED)
        mock_gemini.assert_called_once()
        f = vf['fields']
        self.assertEqual(f['contribution_status'], 'unknown')
        self.assertEqual(f['name'], 'KUMARAN A/L CONTOHAN')
        self.assertEqual(vf['capture'], 'deterministic')
        self.assertEqual(vf['error'], '')                       # the reading itself did not fail
        self.assertFalse(f.get('employer_contribution_total'))
        self.assertIsNone(_epf_monthly_salary(f))

    @patch(GEMINI)
    def test_gemini_that_cannot_read_it_either_changes_nothing(self, mock_gemini):
        mock_gemini.return_value = {'fields': {'contribution_status': 'unknown',
                                               'employer_contribution_total': 'RM9.00'},
                                    'warnings': [], 'error': ''}
        f = self._read(fixtures_epf.TRUNCATED)['fields']
        self.assertEqual(f['contribution_status'], 'unknown')
        self.assertFalse(f.get('employer_contribution_total'))


class TestTheHelperAlone(TestCase):
    """The helper's own edges, without a database row."""

    def test_another_doc_type_with_unknown_is_never_sent(self):
        calls = []
        ex = deterministic_or_epf_fallback('salary_slip', {'contribution_status': 'unknown'}, 't',
                                           lambda *a: calls.append(a))
        self.assertEqual(calls, [])
        self.assertEqual(ex['capture'], 'deterministic')

    def test_an_exception_in_the_extractor_keeps_the_reading(self):
        def boom(*a):
            raise RuntimeError('network')
        parsed = {'contribution_status': 'unknown', 'name': 'A'}
        ex = deterministic_or_epf_fallback('epf', parsed, 't', boom)
        self.assertEqual(ex['fields'], parsed)
        self.assertEqual(ex['capture'], 'deterministic')

    def test_only_contribution_fields_are_taken(self):
        parsed = {'contribution_status': 'unknown', 'name': 'A', 'address': 'X'}
        ex = deterministic_or_epf_fallback('epf', parsed, 't', lambda *a: GEMINI_READ)
        self.assertEqual(ex['fields']['name'], 'A')
        self.assertEqual(ex['fields']['address'], 'X')
        self.assertEqual(set(ex['fields']) - set(parsed), set(CONTRIBUTION_FIELDS) - {'contribution_status'})
