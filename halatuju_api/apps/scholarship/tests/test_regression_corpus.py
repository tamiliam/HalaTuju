"""TD-151 (1) — the problem-document corpus: the committed half.

`eval/regression_check.py` replays the REAL problem documents by hand (gitignored PII, absent from
the deploy gate). This file runs the SAME check functions on synthetic twins, and holds the labels
to the rules the script relies on: every check named in `labels.json` exists, and nothing in the
labels looks like a person. Committed tests read only what is committed (lessons.md, 2026-10-01).
"""
import json
import os
import re

from django.test import SimpleTestCase

from apps.scholarship.eval import regression_check as rc
from apps.scholarship.genuineness import results_doc

_LABELS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'eval', 'labels.json')
_NRIC = re.compile(r'\b\d{6}-?\d{2}-?\d{4}\b')
_PATRONYMIC = re.compile(r'\b(A/P|A/L|BIN|BINTI)\b', re.IGNORECASE)


def _labels():
    with open(_LABELS, encoding='utf-8') as fh:
        return json.load(fh)


def _str_text():
    """A synthetic MOF STR letter — one line per text signature of the STR letter family."""
    sigs = results_doc._FAMILIES['str']['str_letter']
    return '\n'.join(p[0] for _, p, _, kind in sigs if kind != 'visual')


class RegressionLabelsTest(SimpleTestCase):

    def test_the_corpus_names_the_known_problem_cases(self):
        cases = {e['case'] for e in _labels()['regressions'].values()}
        self.assertTrue({'#66', '#37', '#140', '#73'} <= cases, cases)

    def test_every_check_the_labels_name_exists_and_every_entry_is_shaped(self):
        for key, entry in _labels()['regressions'].items():
            with self.subTest(key):
                self.assertIn(entry['local'], (True, False))
                self.assertTrue(entry.get('note'))
                for name in entry.get('checks') or {}:
                    self.assertIn(name, rc.CHECKS)

    def test_the_labels_carry_no_identity(self):
        text = json.dumps(_labels()['regressions'], ensure_ascii=False)
        self.assertIsNone(_NRIC.search(text))
        self.assertIsNone(_PATRONYMIC.search(text))


class RegressionChecksOnSyntheticTwinsTest(SimpleTestCase):

    def _slip(self, n):
        return {'fields': {'results': [{'subject': f'S{i}', 'grade': 'A'} for i in range(n)]}}

    def test_66_a_half_read_two_column_slip_fails_the_declared_total(self):
        text = 'SIJIL PELAJARAN MALAYSIA\nJUMLAH MATA PELAJARAN : SEPULUH'
        self.assertTrue(rc.declared_subjects_match_stored(self._slip(10), text, True)[0])
        self.assertFalse(rc.declared_subjects_match_stored(self._slip(6), text, True)[0])

    def test_140_a_clipped_total_line_is_still_found(self):
        self.assertTrue(rc.declared_subjects_found({}, 'JMLAH MATA PELAJARAN SEBELAS', True)[0])

    def test_37_an_str_letter_in_the_epf_slot(self):
        text = _str_text()
        self.assertTrue(rc.signature_status({}, text, 'not_epf', doc_type='epf')[0])
        self.assertTrue(rc.epf_parser_declines({}, text, True)[0])

    def test_66_a_voucher_misread_gives_no_figure_rather_than_an_implausible_one(self):
        ok, detail = rc.salary_amount_plausible({'fields': {'gross_income': '32600'}}, '', True)
        self.assertTrue(ok)
        self.assertEqual(detail, 'no usable figure')

    def test_run_case_reports_every_check(self):
        entry = {'doc_type': 'epf', 'checks': {'signature_status': 'not_epf',
                                               'epf_parser_declines': True}}
        results = rc.run_case(entry, {}, _str_text())
        self.assertEqual([n for n, _, _ in results], ['signature_status', 'epf_parser_declines'])
        self.assertTrue(all(ok for _, ok, _ in results))
