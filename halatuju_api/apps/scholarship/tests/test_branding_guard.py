"""AST brand-guard (platform Sprint 5, decision D6).

Scans the STRING CONSTANTS (never comments or docstrings) of ``emails.py`` and ``help_engine.py``
for the platform brand literals — "BrightPath", "Cikgu Gopal", "halatuju.xyz" and the canonical
MS/TA brand strings. After the per-org extraction those literals live in exactly ONE sanctioned
home, ``branding.py``'s PLATFORM block; a fresh literal anywhere else is a leak waiting to happen,
so it fails here.

Self-checking (D6): the guard derives the ``send_*`` function set with ``inspect.getmembers`` —
never a hand-maintained list — and asserts a MINIMUM number of both scanned send functions and
scanned string constants, so a guard that silently scanned nothing fails loudly instead of passing.

⚠ ``emails`` IS A PACKAGE since code health H16 (2026-09-20), so the scan walks every module in
it rather than reading ``module.__file__``. A package's ``__file__`` is its ``__init__.py``, which
here is a re-export shell holding no copy at all — the guard would have read ~0 string constants
and, without the floor below, would have gone on passing while every line of email copy left its
sight. The floor is what turned that into a loud failure, which is the whole argument of TD-276.
"""
import ast
import inspect
import pathlib

from apps.scholarship import emails, help_engine
from apps.scholarship.tests.source_walk import floor_count, walk_sources

# The platform brand tokens that must NOT appear as a string constant outside branding.py.
# 'BrightPath' subsumes every EN/MS form ("BrightPath Bursary", "Bursari BrightPath", "Pasukan
# Program Bursari BrightPath", "BrightPath Bursary குழு"); the MS/TA canonicals are listed too,
# explicitly, per the sprint brief; the TA persona has no ASCII tell so it is named on its own.
FORBIDDEN = (
    'BrightPath',
    'Cikgu Gopal',
    'halatuju.xyz',
    'Bursari BrightPath',
    'Pasukan Program Bursari BrightPath',
    'BrightPath Bursary குழு',
    'சிக்கு கோபால்',
)

# The two modules under guard. branding.py is the ONE sanctioned home for these literals and is
# deliberately NOT scanned.
GUARDED = (emails, help_engine)

# Floors comfortably below the live counts (emails ≈ 1688, help_engine ≈ 322 string constants;
# 48 send_* functions) but far above zero, so a scanner that broke and found nothing fails.
MIN_STRING_CONSTANTS = {'emails': 1000, 'help_engine': 150}
MIN_SEND_FUNCTIONS = 40

#: `emails/` is 22 modules at H16. A minimum, not an equality: a new mail module must leave this
#: green, while a package that stopped being walked must not.
MIN_EMAIL_MODULES = 18


def _docstring_and_bare_string_ids(tree):
    """ids of Constant str nodes that are docstrings OR bare string-statements ("string comments")
    — the nodes the guard must NOT scan (only real code string literals are in scope)."""
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, 'body', [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                ids.add(id(body[0].value))          # a docstring
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            ids.add(id(node.value))                 # a bare string statement used as a comment
    return ids


def _sources_of(module):
    """Every source file the guard must read for `module` — one path, or a whole package.

    ⚠ A PACKAGE IS NOT ITS `__init__.py`. `emails.__file__` is a 135-line re-export shell with no
    copy in it at all; reading only that would scan ~0 string constants and assert nothing about
    the 4,200 lines of email copy beside it. `walk_sources` walks the package recursively and
    raises if it finds fewer modules than `MIN_EMAIL_MODULES` (TD-276).
    """
    path = pathlib.Path(module.__file__)
    if path.name != '__init__.py':
        return [path]
    return walk_sources(
        path.parent, '*.py', MIN_EMAIL_MODULES,
        f'the brand literals live in every module of `{module.__name__}`, not in its re-export '
        'shell; a scan that reads only the shell finds nothing and passes for ever')


def _scanned_string_constants(module):
    """(label, node) for every real string literal in `module` — docstrings and bare strings out."""
    out = []
    for path in _sources_of(module):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        skip = _docstring_and_bare_string_ids(tree)
        label = path.stem if path.name != '__init__.py' else path.parent.name
        out += [(label, n) for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]
    return out


def test_no_platform_brand_literals_outside_branding():
    leaks = []
    scanned = {}
    for module in GUARDED:
        name = module.__name__.rsplit('.', 1)[-1]
        consts = _scanned_string_constants(module)
        scanned[name] = len(consts)
        for label, node in consts:
            for tok in FORBIDDEN:
                if tok in node.value:
                    leaks.append(f'{label}:{node.lineno}: {tok!r} in string constant '
                                 f'{node.value[:60]!r}')
    assert not leaks, (
        'platform brand literal(s) found OUTSIDE branding.py — route them through the seam:\n'
        + '\n'.join(leaks))

    # Self-check: the scan actually looked at a real corpus (not silently zero).
    for name, floor in MIN_STRING_CONSTANTS.items():
        floor_count(
            [None] * scanned.get(name, 0), floor, f'string constants in `{name}`',
            'they are the corpus the brand literals would leak into; a scanner that reads none '
            'asserts nothing and would pass a real leak (the H16 package split is exactly how '
            'this corpus can vanish without a word)')


def test_send_function_floor_is_derived_not_hand_listed():
    """The guarded surface (the send_* functions) is derived via inspect, never hand-maintained,
    and there must be a healthy number of them — else the guard is meaningless."""
    send_funcs = [n for n, f in inspect.getmembers(emails, inspect.isfunction)
                  if n.startswith('send_')]
    assert len(send_funcs) >= MIN_SEND_FUNCTIONS, (
        f'only {len(send_funcs)} send_* functions found (< {MIN_SEND_FUNCTIONS}) — '
        f'the guarded surface shrank unexpectedly; re-check the extraction')
