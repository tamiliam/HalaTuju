"""The chip modules are DISPLAY ONLY: no engine may reach them, directly or through other modules.

The chip modules are ``doc_chips`` (the officer's chips) and ``doc_chips_student`` (the student's,
chip standard S1). Five locks, because no single one is enough here:

1. DIRECT (static, lazy imports included): no engine file names a chip module at all: imported,
   named as code (N1: a ``doc_chips`` / ``chips_for`` / ``pill_for`` Name or Attribute), or named in
   a string (an ``importlib`` path).
2. RING FENCE (static, the whole api: every app plus the ``halatuju`` project package): outside the
   tests and the chip family itself, only the document serializer and the dry run name a chip
   module, so the only road to them runs through the serializer.
3. TRANSITIVE (runtime, fresh interpreter): importing every engine module never loads either one.
4. NO READ-BACK (static): no engine names the string ``'chips'`` (N3: bare too, not only as
   ``['chips']`` / ``.get('chips')``) or anything naming ``chip_pill``, so a serialized document's
   chips can never feed a verdict even without an import. Docstrings are skipped (N7).
5. NO PAYLOAD MAKER (static, N2): no engine imports, from inside the api (a relative import, or a path
   under ``apps`` / ``halatuju``), any module whose path has a part starting with ``serializers``
   (``serializers``, ``serializers_admin``, ``serializers_org_requests`` ...), or ``sgd_conversion`` or
   ``upload_read``, where the chips are served (``PAYLOAD_IMPORT_ALLOWLIST``: one reason per file;
   empty today). DRF's own ``rest_framework.serializers`` is not a payload maker and is not flagged.

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
_CHIP_MODULES = {'doc_chips', 'doc_chips_student'}
# The chip family itself (the student module imports the officer one), by FULL path: a file elsewhere
# that merely shares the name is still scanned.
_CHIP_PATHS = {f'apps/scholarship/{m}.py' for m in _CHIP_MODULES}
_CHIP_NAMES = _CHIP_MODULES | {'chips_for', 'pill_for'}     # N1: names that only the chip modules give
_CHIP_KEYS = {'chips', 'chip_pill'}
# Engine files allowed to read a 'chips' key, each with its reason. Empty today.
CHIP_READ_ALLOWLIST: dict = {}
# N2: an engine never imports the payload makers (any ``serializers*`` module of the api, the officer
# serializer in sgd_conversion, upload_read), since those are where the chips are served. Each engine
# file allowed one of them, with why.
_PAYLOAD_PREFIX = 'serializers'
_PAYLOAD_MODULES = {'sgd_conversion', 'upload_read'}
_API_PACKAGES = set(SCAN_ROOTS)                             # an absolute path inside the api starts here
PAYLOAD_IMPORT_ALLOWLIST: dict = {}


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


def _docstrings(tree):
    """N7: the docstring nodes (a module / class / function's first bare string), which say what a
    file does and are not code, so a string scan skips them."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                out.add(id(first.value))
    return out


def _strings(tree):
    """Every string constant that is not a docstring."""
    skip = _docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            yield node.value


def _imports(tree):
    """Every module path and imported name, as their dotted parts."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield from (node.module or '').split('.')
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                yield from a.name.split('.')


def _names_doc_chips(tree):
    """A chip module reached: imported (lazy imports too), named as code (N1: ``doc_chips.x``,
    ``chips_for(...)``, ``pill_for``), or named in a string (``importlib.import_module``)."""
    if _CHIP_MODULES & set(_imports(tree)):
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _CHIP_NAMES:
            return True
        if isinstance(node, ast.Attribute) and node.attr in _CHIP_NAMES:
            return True
    return any(m in v for v in _strings(tree) for m in _CHIP_MODULES)


def _api_import_paths(tree):
    """Each import INSIDE the api (relative, or absolute under ``apps`` / ``halatuju``) as its dotted
    parts, the imported name included. Third-party imports (``rest_framework.serializers``) are left out."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = [p for p in (node.module or '').split('.') if p]
            if node.level == 0 and (not base or base[0] not in _API_PACKAGES):
                continue
            for a in node.names:
                yield base + [a.name]
        elif isinstance(node, ast.Import):
            for a in node.names:
                parts = a.name.split('.')
                if parts[0] in _API_PACKAGES:
                    yield parts


def _imports_a_payload_maker(tree):
    return any(p.startswith(_PAYLOAD_PREFIX) or p in _PAYLOAD_MODULES
               for parts in _api_import_paths(tree) for p in parts)


def _drf_names(tree):
    """The local names bound from ``rest_framework`` (``from rest_framework import serializers``,
    ``import rest_framework.serializers`` binds ``rest_framework``, ``from rest_framework.x import y``)."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0                 and (node.module or '').split('.')[0] == 'rest_framework':
            out.update(a.asname or a.name for a in node.names)
        elif isinstance(node, ast.Import):
            out.update((a.asname or a.name.split('.')[0]) for a in node.names
                       if a.name.split('.')[0] == 'rest_framework')
    return out


def _chain_root(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_payload_word(text):
    return text.startswith(_PAYLOAD_PREFIX) or text in _PAYLOAD_MODULES


def _reaches_a_payload_maker_dynamically(tree):
    """N2 round 2: a payload maker reached WITHOUT an import statement: a non-docstring string naming
    one (``importlib.import_module('apps.scholarship.serializers')``, ``__import__(...)``), or an
    attribute of that name (``import apps.scholarship as s; s.serializers.X``). An attribute chain
    rooted at a name bound from ``rest_framework`` is DRF's own ``serializers`` and passes."""
    if any(w in v for v in _strings(tree) for w in (_PAYLOAD_PREFIX, *_PAYLOAD_MODULES)):
        return True
    drf = _drf_names(tree)
    return any(isinstance(n, ast.Attribute) and _is_payload_word(n.attr) and _chain_root(n) not in drf
               for n in ast.walk(tree))


def _skipped_by_the_importer_scan(rel):
    """The tests, the migrations and the chip family itself (by full path, never by bare file name)."""
    return bool({'tests', 'migrations'} & set(rel.parts)) or _posix(rel) in _CHIP_PATHS


def _reads_chips(tree):
    """A served chip read back: ``x['chips']`` / ``x.get('chips')`` (or pop / setdefault), and (N3)
    the bare string ``'chips'`` or anything naming ``chip_pill``, docstrings aside (N7)."""
    for v in _strings(tree):
        if v in _CHIP_KEYS or 'chip_pill' in v:
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
            if _skipped_by_the_importer_scan(rel):
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

    def test_n3_a_bare_chips_string_is_caught_but_a_docstring_is_not(self):
        for src in ("KEY = 'chips'", "f(d, 'chips')", "getattr(d, 'chip_pill')"):
            with self.subTest(src):
                self.assertTrue(_reads_chips(ast.parse(src)))
        for src in ('"""It never reads chips or chip_pill."""',
                    'def f():\n    """chip_pill: never read here."""\n    return 1',
                    "class C:\n    'chips'\n", "x = 'chips_seen'"):
            with self.subTest(src):
                self.assertFalse(_reads_chips(ast.parse(src)))

    def test_n1_a_chip_name_used_as_code_is_caught(self):
        for src in ('doc_chips.chips_for(d)', 'chips_for(d)', 'f = pill_for', 'm.doc_chips_student',
                    'from . import doc_chips_student', "import_module('apps.scholarship.doc_chips')"):
            with self.subTest(src):
                self.assertTrue(_names_doc_chips(ast.parse(src)))
        for src in ('"""Never touches doc_chips."""', 'chips = []', 'pill = 1'):
            with self.subTest(src):
                self.assertFalse(_names_doc_chips(ast.parse(src)))

    def test_n2_no_engine_imports_a_payload_maker(self):
        bad = [_posix(p) for p in engine_files()
               if _posix(p) not in PAYLOAD_IMPORT_ALLOWLIST and _imports_a_payload_maker(_tree(p))]
        self.assertEqual(bad, [], 'an engine must never import serializers / sgd_conversion / upload_read')
        dynamic = [_posix(p) for p in engine_files()
                   if _posix(p) not in PAYLOAD_IMPORT_ALLOWLIST and _reaches_a_payload_maker_dynamically(_tree(p))]
        self.assertEqual(dynamic, [], 'an engine must never reach a payload maker by string or attribute')

    def test_n2_round2_the_dynamic_bypasses_are_caught(self):
        for src in ("import importlib\nimportlib.import_module('apps.scholarship.serializers')",
                    "__import__('apps.scholarship.sgd_conversion')",
                    "x = 'apps.scholarship.upload_read'",
                    "import apps.scholarship as s\ns.serializers.X",
                    "import apps.scholarship as s\ns.serializers_admin.X",
                    "import apps.scholarship as s\ns.sgd_conversion.f",
                    "import apps.scholarship as s\ns.upload_read"):
            with self.subTest(src):
                self.assertTrue(_reaches_a_payload_maker_dynamically(ast.parse(src)))

    def test_n2_round2_drf_forms_and_docstrings_pass(self):
        for src in ("from rest_framework import serializers\nclass A(serializers.ModelSerializer): pass",
                    "from rest_framework import serializers as s\nx = s.SerializerMethodField()",
                    "import rest_framework.serializers\nrest_framework.serializers.ModelSerializer",
                    "from rest_framework.serializers import ModelSerializer\nModelSerializer.Meta",
                    "'''Never touches serializers or sgd_conversion.'''",
                    "def f():\n    '''upload_read is not used here.'''\n    return 1"):
            with self.subTest(src):
                self.assertFalse(_reaches_a_payload_maker_dynamically(ast.parse(src)))

    def test_n2_the_payload_check_catches_each_shape(self):
        for src in ('from .serializers import X', 'from .. import serializers', 'from .sgd_conversion import f',
                    'import apps.scholarship.upload_read', 'from apps.scholarship.serializers.documents import X'):
            with self.subTest(src):
                self.assertTrue(_imports_a_payload_maker(ast.parse(src)))
        self.assertFalse(_imports_a_payload_maker(ast.parse('from rest_framework import fields')))

        for src in ('from rest_framework import serializers', 'import rest_framework.serializers',
                    'from rest_framework.serializers import ModelSerializer',
                    'from rest_framework import serializers as s'):
            with self.subTest(src):
                self.assertFalse(_imports_a_payload_maker(ast.parse(src)))

    def test_n2_every_serializers_module_of_the_api_is_a_payload_maker(self):
        for src in ('from .serializers_admin import AdminApplicationDetailSerializer',
                    'from .. import serializers_org_requests', 'from ..serializers_admin import X',
                    'from apps.scholarship.serializers_admin import X',
                    'import apps.scholarship.serializers_org_requests',
                    'from apps.scholarship import serializers_admin',
                    'from halatuju.serializers_x import Y'):
            with self.subTest(src):
                self.assertTrue(_imports_a_payload_maker(ast.parse(src)))

    def test_n2_drf_serializers_is_not_a_payload_maker(self):
        for src in ('from rest_framework import serializers', 'import rest_framework.serializers',
                    'from rest_framework.serializers import ModelSerializer',
                    'from rest_framework import serializers as s'):
            with self.subTest(src):
                self.assertFalse(_imports_a_payload_maker(ast.parse(src)))

    def test_the_importer_scan_skips_the_chip_files_by_full_path_only(self):
        for rel in ('apps/scholarship/doc_chips.py', 'apps/scholarship/doc_chips_student.py',
                    'apps/scholarship/tests/test_x.py', 'apps/courses/migrations/0001_x.py'):
            with self.subTest(rel):
                self.assertTrue(_skipped_by_the_importer_scan(pathlib.PurePosixPath(rel)))
        for rel in ('apps/courses/doc_chips.py', 'apps/scholarship/views/doc_chips_student.py',
                    'halatuju/doc_chips.py'):
            with self.subTest(rel):                      # same bare name, another place: still scanned
                self.assertFalse(_skipped_by_the_importer_scan(pathlib.PurePosixPath(rel)))

    def test_importing_every_engine_never_loads_doc_chips(self):
        modules = ['.'.join(p.with_suffix('').parts).replace('.__init__', '') for p in engine_files()]
        script = (
            'import importlib, sys, django\n'
            'django.setup()\n'
            f'for m in {modules!r}:\n'
            '    importlib.import_module(m)\n'
            "    if {'apps.scholarship.doc_chips', 'apps.scholarship.doc_chips_student'} & set(sys.modules):\n"
            "        print('LOADED_BY ' + m); sys.exit(3)\n"
            "print('CLEAN')\n"
        )
        env = {**os.environ, 'DJANGO_SETTINGS_MODULE': os.environ.get(
            'DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')}
        done = subprocess.run([sys.executable, '-c', script], cwd=str(API_ROOT), env=env,
                              capture_output=True, text=True, timeout=300)
        self.assertIn('CLEAN', done.stdout, done.stdout[-2000:] + done.stderr[-2000:])
        self.assertEqual(done.returncode, 0)
