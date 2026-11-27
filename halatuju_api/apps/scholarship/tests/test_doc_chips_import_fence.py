"""The chip module is DISPLAY ONLY: no engine may reach it, directly or through other modules.

Three locks, because no single one is enough here:

1. DIRECT (static, lazy imports included): no engine file names ``doc_chips`` at all.
2. RING FENCE (static): outside the tests, only the document serializer and the dry run import
   ``doc_chips``, so the only road to it runs through the serializer.
3. TRANSITIVE (runtime, fresh interpreter): importing every engine module never loads ``doc_chips``.

Why not a static transitive walk: every package ``__init__`` here re-exports its package, so the
static closure of the engines (lazy imports included) is ~590 files, the whole app, serializers too.
It cannot tell an engine that uses the chips from one that merely shares a package with a view.
Lock 2 + lock 3 together say what that walk was meant to: no engine loads the module, and the only
importer is the serializer.

Engine modules: ``verdict_*``, ``fact_bands``, ``award*``, ``*_engine`` (the ``income_engine``
package whole, ``match_bands`` inside it), ``verdict_ladder`` — views, emails, management commands
and urls are not engines and are left out.
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
_ENGINE = re.compile(r'^(verdict_.*|fact_bands|award.*|.*_engine|match_bands|verdict_ladder|income_engine)$')
_NOT_ENGINES = ('tests', 'migrations', 'management', 'views', 'views_admin', 'emails', 'eval')
ALLOWED_IMPORTERS = {'serializers/documents.py', 'eval/chip_dry_run.py'}


def engine_files():
    out = []
    for p in sorted(PKG.rglob('*.py')):
        rel = p.relative_to(PKG)
        if rel.parts[0] in _NOT_ENGINES or rel.name.startswith('urls'):
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


class DocChipsImportFenceTests(SimpleTestCase):
    def test_the_engine_list_is_not_empty(self):
        names = {str(p).replace('\\', '/') for p in engine_files()}
        self.assertGreaterEqual(len(names), 40)
        for must in ('verdict_engine.py', 'verdict_ladder.py', 'fact_bands.py', 'award.py',
                     'income_engine/match_bands.py', 'income_engine/__init__.py', 'pathway_engine.py'):
            self.assertIn(must, names)

    def test_no_engine_file_names_doc_chips(self):
        bad = [str(p) for p in engine_files() if _names_doc_chips(ast.parse((PKG / p).read_text(encoding='utf-8')))]
        self.assertEqual(bad, [], 'an engine must never read the chips (display only)')

    def test_only_the_serializer_and_the_dry_run_import_doc_chips(self):
        importers = set()
        for p in PKG.rglob('*.py'):
            rel = p.relative_to(PKG)
            if rel.parts[0] in ('tests', 'migrations') or rel.name == 'doc_chips.py':
                continue
            if _names_doc_chips(ast.parse(p.read_text(encoding='utf-8'))):
                importers.add(str(rel).replace('\\', '/'))
        self.assertEqual(importers, ALLOWED_IMPORTERS)

    def test_importing_every_engine_never_loads_doc_chips(self):
        modules = ['apps.scholarship.' + '.'.join(p.with_suffix('').parts).replace('.__init__', '')
                   for p in engine_files()]
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
