"""The chip module is DISPLAY ONLY: no engine may reach it, directly or through other modules.

Four locks, because no single one is enough here:

1. DIRECT (static, lazy imports included): no engine file names ``doc_chips`` at all.
2. RING FENCE (static, the whole api: every app plus the ``halatuju`` project package): outside the
   tests, only the document serializer and the dry run import ``doc_chips``, so the only road to it
   runs through the serializer.
3. TRANSITIVE (runtime, fresh interpreter): importing every engine module never loads ``doc_chips``.
4. NO READ-BACK (static): no engine reads a served chip off a payload (``['chips']``,
   ``.get('chips')``) or names ``chip_pill`` at all, so a serialized document's chips can never
   feed a verdict even without an import.

Why not a static transitive walk: every package ``__init__`` here re-exports its package, so the
static closure of the engines (lazy imports included) is ~590 files, the whole app, serializers too.
It cannot tell an engine that uses the chips from one that merely shares a package with a view.
Locks 2 + 3 together say what that walk was meant to: no engine loads the module, and the only
importer is the serializer.

Engine modules (any app): ``verdict_*``, ``fact_bands``, ``award*``, ``*_engine`` / ``engine`` (the
``income_engine`` package whole, ``match_bands`` inside it), ``verdict_ladder``; and the
verdict-adjacent ones: ``resolution*``, the ``genuineness`` package whole, ``link_display``,
``higher_results``, ``income_str_ownership``, the eligibility modules (``eligibility*``, ``pool``,
``payments``) and the gift modules (``*_gift``, ``gift_*``, ``*_gifts``). Views, emails, management
commands, evals and urls are not engines and are left out.
"""
import ast
import os
import pathlib
import re
import subprocess
import sys

from django.test import SimpleTestCase

PKG = pathlib.Path(__file__).resolve().parents[1]           # apps/scholarship
API_ROOT = PKG.parents[1]                                   # halatuju_api
SCAN_ROOTS = ('apps', 'halatuju')                           # every app + the project package
_ENGINE = re.compile(
    r'^(verdict_.*|fact_bands|award.*|.*_engine|engine|match_bands|verdict_ladder|income_engine'
    r'|resolution.*|genuineness|link_display|higher_results|income_str_ownership'
    r'|eligibility.*|pool|payments|.*_gift|gift_.*|.*_gifts)$')
_NOT_ENGINES = {'tests', 'migrations', 'management', 'views', 'views_admin', 'emails', 'eval'}
ALLOWED_IMPORTERS = {'apps/scholarship/serializers/documents.py', 'apps/scholarship/eval/chip_dry_run.py'}
_CHIP_KEYS = {'chips', 'chip_pill'}
# Engine files allowed to read a 'chips' key, each with its reason. Empty today.
CHIP_READ_ALLOWLIST: dict = {}


def _py_files():
    for root in SCAN_ROOTS:
        for p in sorted((API_ROOT / root).rglob('*.py')):
            yield p.relative_to(API_ROOT)


def _posix(rel):
    return str(rel).replace('\\', '/')


def engine_files():
    out = []
    for rel in _py_files():
        if _NOT_ENGINES & set(rel.parts) or rel.name.startswith('urls'):
            continue
        if any(_ENGINE.match(part) for part in rel.with_suffix('').parts):
            out.append(rel)
    return out


def _names_doc_chips(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or '').split('.')[-1] == 'doc_chips' or any(a.name == 'doc_chips' for a in node.names):
                return True
        elif isinstance(node, ast.Import):
            if any(a.name.split('.')[-1] == 'doc_chips' for a in node.names):
                return True
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and 'doc_chips' in node.value:
            return True                                     # importlib.import_module('...doc_chips')
    return False


def _reads_chips(tree):
    """A served chip read back: ``x['chips']`` / ``x['chip_pill']``, ``x.get('chips')`` (or pop /
    setdefault), or the string ``chip_pill`` anywhere."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            s = node.slice
            if isinstance(s, ast.Constant) and s.value in _CHIP_KEYS:
                return True
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ('get', 'pop', 'setdefault') and node.args:
            a = node.args[0]
            if isinstance(a, ast.Constant) and a.value in _CHIP_KEYS:
                return True
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and 'chip_pill' in node.value:
            return True
    return False


def _tree(rel):
    return ast.parse((API_ROOT / rel).read_text(encoding='utf-8'))


class DocChipsImportFenceTests(SimpleTestCase):
    def test_the_engine_list_is_not_empty(self):
        names = {_posix(p) for p in engine_files()}
        self.assertGreaterEqual(len(names), 80)
        s = 'apps/scholarship/'
        for must in (s + 'verdict_engine.py', s + 'verdict_ladder.py', s + 'fact_bands.py', s + 'award.py',
                     s + 'income_engine/match_bands.py', s + 'income_engine/__init__.py', s + 'pathway_engine.py',
                     s + 'resolution.py', s + 'resolution_doc_match.py', s + 'genuineness/__init__.py',
                     s + 'genuineness/bands.py', s + 'link_display.py', s + 'higher_results.py',
                     s + 'income_str_ownership.py', s + 'pool.py', s + 'payments.py', s + 'gift_sources.py',
                     s + 'standing_gift.py', 'apps/courses/engine.py', 'apps/courses/stpm_engine.py',
                     'apps/courses/eligibility_service.py', 'apps/courses/staff_gift.py'):
            self.assertIn(must, names)
        for never in (s + 'views/resolution.py', s + 'views_admin/gifts.py', s + 'doc_chips.py',
                      'apps/courses/views/eligibility.py'):
            self.assertNotIn(never, names)

    def test_no_engine_file_names_doc_chips(self):
        bad = [_posix(p) for p in engine_files() if _names_doc_chips(_tree(p))]
        self.assertEqual(bad, [], 'an engine must never read the chips (display only)')

    def test_only_the_serializer_and_the_dry_run_import_doc_chips(self):
        importers = set()
        for rel in _py_files():
            if {'tests', 'migrations'} & set(rel.parts) or rel.name == 'doc_chips.py':
                continue
            if _names_doc_chips(_tree(rel)):
                importers.add(_posix(rel))
        self.assertEqual(importers, ALLOWED_IMPORTERS)

    def test_no_engine_reads_a_served_chip_back(self):
        bad = [_posix(p) for p in engine_files()
               if _posix(p) not in CHIP_READ_ALLOWLIST and _reads_chips(_tree(p))]
        self.assertEqual(bad, [], "an engine must never read 'chips' / 'chip_pill' off a payload")

    def test_the_read_back_check_catches_the_three_shapes(self):
        for src in ("d['chips']", "d.get('chips')", "x = 'chip_pill'", 'd["chip_pill"][0]'):
            with self.subTest(src):
                self.assertTrue(_reads_chips(ast.parse(src)))
        for src in ("d['chip']", "chips = []", "d.get('rejection_chip')"):
            with self.subTest(src):
                self.assertFalse(_reads_chips(ast.parse(src)))

    def test_importing_every_engine_never_loads_doc_chips(self):
        modules = ['.'.join(p.with_suffix('').parts).replace('.__init__', '') for p in engine_files()]
        script = (
            'import importlib, sys, django\n'
            'django.setup()\n'
            f'for m in {modules!r}:\n'
            '    importlib.import_module(m)\n'
            "    if 'apps.scholarship.doc_chips' in sys.modules:\n"
            "        print('LOADED_BY ' + m); sys.exit(3)\n"
            "print('CLEAN')\n"
        )
        env = {**os.environ, 'DJANGO_SETTINGS_MODULE': os.environ.get(
            'DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')}
        done = subprocess.run([sys.executable, '-c', script], cwd=str(API_ROOT), env=env,
                              capture_output=True, text=True, timeout=300)
        self.assertIn('CLEAN', done.stdout, done.stdout[-2000:] + done.stderr[-2000:])
        self.assertEqual(done.returncode, 0)
