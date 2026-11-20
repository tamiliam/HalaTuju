"""TD-693 lint: no test asserts an elapsed time under the shared wall-clock backstop.

A tight time limit fails on a slow build machine although the code is fine (Cloud Build: 2.5 s against a 1.0 s
limit, 18.9 s against 8.0 s). A test pins its guard by the WORK it counts (calls, parses, children spawned,
budgets); time stays only as a backstop of at least WALL_BACKSTOP_S (see _timing.py).

The scan flags an assertLess / assertLessEqual / assertGreater / assertGreaterEqual call, or a bare `assert a < b`,
when one side reads a clock (time.perf_counter / monotonic / time / process_time, or a name assigned from one)
and the other side is a number under WALL_BACKSTOP_S or a name that is not WALL_BACKSTOP_S.
"""
import ast
import os

from django.test import SimpleTestCase

from apps.scholarship.tests._timing import WALL_BACKSTOP_S

API_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CLOCKS = {'perf_counter', 'monotonic', 'time', 'process_time', 'perf_counter_ns', 'monotonic_ns'}
RULE = ('TD-693: a test may not assert an elapsed time under WALL_BACKSTOP_S; pin the guard by the work it counts '
        '(calls, parses, children spawned, budgets) and keep time only as wall_backstop (apps/scholarship/tests/_timing.py)')
_LESS = {'assertLess', 'assertLessEqual'}
_GREATER = {'assertGreater', 'assertGreaterEqual'}


def _called(sub):
    return sub.func.attr if isinstance(sub.func, ast.Attribute) else getattr(sub.func, 'id', None)


def _reads_clock(node, timed, timed_fns=frozenset()):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and _called(sub) in timed_fns:
            return True
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr in CLOCKS \
                and isinstance(sub.func.value, ast.Name) and sub.func.value.id == 'time':
            return True
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in CLOCKS - {'time'}:
            return True
        if isinstance(sub, ast.Name) and sub.id in timed:
            return True
    return False


def _tight(bound):
    """A limit under the backstop: a small number, or any name or expression other than WALL_BACKSTOP_S."""
    if isinstance(bound, ast.Constant) and isinstance(bound.value, (int, float)):
        return bound.value < WALL_BACKSTOP_S
    return not any(isinstance(sub, (ast.Name, ast.Attribute)) and getattr(sub, 'id', getattr(sub, 'attr', None))
                   == 'WALL_BACKSTOP_S' for sub in ast.walk(bound))


def tight_wall_clock(source, filename='<test>'):
    """Return the line numbers of elapsed-time asserts under the backstop in one test file's source."""
    tree = ast.parse(source, filename)
    timed = set()       # names assigned from a clock reading (t0 = time.perf_counter(); took = time.time() - t0)
    timed_fns = set()   # helpers that return an elapsed time (old `_hostile`, `_at_once`)
    for _round in range(3):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _reads_clock(node.value, timed, timed_fns):
                for target in node.targets:
                    timed.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                    isinstance(r, ast.Return) and r.value is not None and _reads_clock(r.value, timed, timed_fns)
                    for r in ast.walk(node)):
                timed_fns.add(node.name)
    hits = []
    for node in ast.walk(tree):
        pairs = []
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and len(node.args) >= 2:
            if node.func.attr in _LESS:
                pairs.append((node.args[0], node.args[1]))
            elif node.func.attr in _GREATER:
                pairs.append((node.args[1], node.args[0]))
        elif isinstance(node, ast.Compare) and len(node.ops) == 1:
            if isinstance(node.ops[0], (ast.Lt, ast.LtE)):
                pairs.append((node.left, node.comparators[0]))
            elif isinstance(node.ops[0], (ast.Gt, ast.GtE)):
                pairs.append((node.comparators[0], node.left))
        for elapsed, bound in pairs:
            if _reads_clock(elapsed, timed, timed_fns) and not _reads_clock(bound, timed, timed_fns) and _tight(bound):
                hits.append(node.lineno)
    return sorted(set(hits))


def _test_files():
    for folder, dirs, files in os.walk(API_ROOT):
        dirs[:] = [d for d in dirs if d not in {'node_modules', '.git', '__pycache__', 'venv', '.venv', 'staticfiles'}]
        for name in files:
            if name.startswith('test') and name.endswith('.py'):
                yield os.path.join(folder, name)


class NoTightWallClock(SimpleTestCase):
    def test_no_test_asserts_a_tight_elapsed_time(self):
        found = []
        for path in _test_files():
            with open(path, encoding='utf-8') as f:
                source = f.read()
            for line in tight_wall_clock(source, path):
                found.append(f'{os.path.relpath(path, API_ROOT)}:{line}')
        self.assertEqual(found, [], RULE)

    def test_the_scan_catches_the_two_forms_that_failed_on_cloud_build(self):
        # test_offer_parse_s5.py:358 before TD-693 (a literal 1.0 limit on a named start time)
        s5 = ('import time\nclass T:\n    def test_2(self):\n        t0 = time.perf_counter()\n'
              '        parse_govt_offer(x)\n        self.assertLess(time.perf_counter() - t0, 1.0)\n')
        self.assertEqual(tight_wall_clock(s5), [6])
        # test_ocr_visible_paths.py:133 before TD-693 (a limit passed in as a parameter, 8.0 at the caller)
        paths = ('import time\nclass T:\n    def _hostile(self, data, limit=3.0):\n        t0 = time.perf_counter()\n'
                 '        pdf_text_layer(data)\n        self.assertLess(time.perf_counter() - t0, limit)\n')
        self.assertEqual(tight_wall_clock(paths), [6])

    def test_the_scan_catches_other_tight_shapes(self):
        for src in ('took = time.time() - t0\nassert took < 2\n',
                    't0 = time.monotonic()\nself.assertLessEqual(time.monotonic() - t0, 5.0)\n',
                    't0 = time.perf_counter()\nself.assertGreater(3.0, time.perf_counter() - t0)\n',
                    'from time import perf_counter\nt0 = perf_counter()\nself.assertLess(perf_counter() - t0, 59)\n',
                    # a helper that returns the elapsed time (old test_ocr_visible `_hostile`, test_pdfium_child `_at_once`)
                    'def _hostile(self, d):\n    t0 = time.perf_counter()\n    return time.perf_counter() - t0\n'
                    'def test(self):\n    self.assertLess(self._hostile(d), 3.0)\n',
                    'def _at_once(self):\n    t0 = time.perf_counter()\n    return out, time.perf_counter() - t0\n'
                    'def test(self):\n    out, took = self._at_once()\n    self.assertLess(took, 2 * 1.0)\n'):
            with self.subTest(src):
                self.assertNotEqual(tight_wall_clock(src), [])

    def test_the_backstop_passes(self):
        for src in ('t0 = time.perf_counter()\nself.assertLess(time.perf_counter() - t0, WALL_BACKSTOP_S)\n',
                    't0 = time.perf_counter()\nself.assertLess(time.perf_counter() - t0, 60.0)\n',
                    't0 = time.perf_counter()\nself.assertLess(time.perf_counter() - t0, _timing.WALL_BACKSTOP_S)\n',
                    'self.assertLess(spawned.call_count, 2)\n', 'assert row[0] < 5.0\n'):
            with self.subTest(src):
                self.assertEqual(tight_wall_clock(src), [])
