"""No test may read the GITIGNORED eval corpus (`apps/scholarship/eval/snapshots` or `/fixtures`).

⚠ Both folders are real applicants' documents — PII, gitignored (eval/README.md, "Committed? No") —
so they exist on a developer's machine and NOT in the deploy gate's build. A test that reads them is
green on the dev box and red in the gate, which is exactly what refused the push of 3a82e8e0
(build 2650b9c7, 2026-10-01): four EPF tests found 0 snapshots. A committed test carries its own
data (`tests/fixtures_epf.py`); a real-corpus measurement is a hand-run script under `eval/`.

The scan reads CODE, not prose: string constants that are not docstrings, and path joins
(`os.path.join(..., 'eval', 'snapshots')`, `Path(...) / 'eval' / 'fixtures'`). A comment or a
docstring may NAME the folder; only reading it is refused. `test_eval_doc_recognition` builds its
own `snapshots` folder in a temp dir, which is not the corpus and is not flagged.
"""
import ast
import glob
import os
import re

from django.test import SimpleTestCase

_APPS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#: Spelt in pieces so this file's own constants do not describe the thing it refuses.
_EVAL = 'ev' + 'al'
_CORPUS = ('snap' + 'shots', 'fix' + 'tures')
_PATH_RE = re.compile(rf'{_EVAL}[/\\]+(?:{"|".join(_CORPUS)})\b')
#: Measured 2026-10-01: 327 test modules under apps/*/tests. A MINIMUM — never an equality.
_FLOOR_FILES = 300


def _docstrings(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                out.add(id(body[0].value))
    return out


def _div_operands(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _div_operands(node.left) + _div_operands(node.right)
    return [node]


def corpus_reads(source):
    """The offending constants in ``source`` — empty when it reads no gitignored corpus."""
    tree = ast.parse(source)
    skip = _docstrings(tree)
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in skip and _PATH_RE.search(node.value)):
            found.append(node.value)
        seqs = []
        if isinstance(node, ast.Call):
            seqs.append(node.args)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            seqs.append(_div_operands(node))
        for seq in seqs:
            vals = [a.value if isinstance(a, ast.Constant) else None for a in seq]
            for a, b in zip(vals, vals[1:]):
                if a == _EVAL and b in _CORPUS:
                    found.append(f'{a} + {b}')
    return found


class TestNoTestReadsTheGitignoredCorpus(SimpleTestCase):

    def test_no_test_module_reads_eval_snapshots_or_fixtures(self):
        files = sorted(glob.glob(os.path.join(_APPS, '*', 'tests', '**', '*.py'), recursive=True))
        self.assertGreaterEqual(
            len(files), _FLOOR_FILES,
            'The scan found fewer test modules than on 2026-10-01 — the tests moved, and a scan '
            'that sees nothing passes for ever. Point it at them again.')
        bad = {}
        for path in files:
            with open(path, encoding='utf-8') as fh:
                hits = corpus_reads(fh.read())
            if hits:
                bad[os.path.relpath(path, _APPS)] = hits
        self.assertEqual(
            bad, {},
            'A test reads the gitignored eval corpus. It will pass here and fail in the deploy '
            'gate, which has no corpus. Commit synthetic data beside the test (see '
            'tests/fixtures_epf.py); measure the real corpus with a hand-run script in eval/.')

    def test_the_detector_sees_every_shape_it_claims_to(self):
        """Positive and negative controls, so the scan above cannot be green by seeing nothing."""
        e, s, f = _EVAL, _CORPUS[0], _CORPUS[1]
        for bad in (f"os.path.join(HERE, '{e}', '{s}')",
                    f"Path(__file__).parent / '{e}' / '{f}' / 'x.pdf'",
                    f"open('apps/scholarship/{e}/{s}/epf__a1.ocr.txt')",
                    f"glob.glob(r'..\\\\{e}\\\\{f}\\\\*.jpg')"):
            with self.subTest(bad=bad):
                self.assertTrue(corpus_reads(bad), bad)
        for fine in (f'"""Reads nothing: the corpus is `{e}/{s}`, named in prose only."""',
                     f"# a comment about {e}/{s}\nx = 1",
                     f"os.makedirs(os.path.join(tmp, '{s}'))",
                     f"Path(__file__).parent / '{f}' / 'golden.json'"):
            with self.subTest(fine=fine):
                self.assertEqual(corpus_reads(fine), [], fine)
