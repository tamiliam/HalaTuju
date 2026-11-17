"""The H9 hand-run sample check's scoring and cost cap (apps/scholarship/eval/sample_check_eval.py).
The model is mocked: no paid call, no picture read."""
import importlib.util
import os

from django.test import SimpleTestCase

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'eval', 'sample_check_eval.py')
_spec = importlib.util.spec_from_file_location('sample_check_run_script', _PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _items(n, set_name='real', expected='not_sample'):
    return [{'id': f'{set_name}{i}', 'set': set_name, 'expected': expected, 'path': ''} for i in range(n)]


def _ans(is_sample, tin=1000, tout=200):
    return {'is_sample': is_sample, 'reason': 'r', 'input_tokens': tin, 'output_tokens': tout,
            'model': 'gemini-2.5-flash'}


class TestSampleCheckRun(SimpleTestCase):
    def test_cost_uses_input_and_output_rates(self):
        self.assertAlmostEqual(mod.cost_usd(1_000_000, 0), 0.30)
        self.assertAlmostEqual(mod.cost_usd(0, 1_000_000), 2.50)
        self.assertEqual(mod.cost_usd(None, None), 0)

    def test_scoring_right_wrong_and_no_answer(self):
        items = _items(2) + _items(2, 'stamped', 'sample')
        answers = iter([_ans(False), _ans(True), _ans(True), _ans(False)])
        rows, summary = mod.run_check(items, lambda it: next(answers))
        s = summary['scores']
        self.assertEqual(s['real'], {'n': 2, 'right': 1, 'wrong': 1, 'no_answer': 0})
        self.assertEqual(s['stamped'], {'n': 2, 'right': 1, 'wrong': 1, 'no_answer': 0})
        self.assertEqual(summary['calls'], 4)
        self.assertEqual(rows[1]['verdict'], 'sample')

    def test_no_answer_is_retried_once_then_recorded(self):
        calls = []

        def ask(it):
            calls.append(it['id'])
            return _ans(None)
        rows, summary = mod.run_check(_items(1), ask)
        self.assertEqual(len(calls), 2)
        self.assertEqual(rows[0]['verdict'], 'no_answer')
        self.assertEqual(summary['scores']['real']['no_answer'], 1)

    def test_retry_that_answers_counts_as_answered(self):
        answers = iter([_ans(None), _ans(False)])
        rows, summary = mod.run_check(_items(1), lambda it: next(answers))
        self.assertEqual(rows[0]['verdict'], 'not_sample')
        self.assertEqual(summary['calls'], 2)

    def test_cap_stops_before_the_call_that_would_pass_it(self):
        calls = []

        def ask(it):
            calls.append(1)
            return _ans(False, 0, 400_000)      # USD 1.00 a call
        rows, summary = mod.run_check(_items(5), ask, max_usd=1.10)
        self.assertEqual(len(calls), 1)
        self.assertTrue(summary['stopped_by_cap'])
        self.assertLessEqual(summary['cost_usd'], 1.10)

    def test_list_set_uses_file_stems_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for n in ('a.jpg', 'b.PDF', 'c.txt'):
                open(os.path.join(d, n), 'wb').close()
            ids = [i['id'] for i in mod.list_set(d, 'real', 'not_sample')]
        self.assertEqual(ids, ['a', 'b'])
