"""Guard (audit A3.12): no NEW private (`_name`) import from another app.

A leading underscore says "mine, not for others". When one app imports `_x` from another, the
owner can no longer rename or move it without breaking a stranger, and nothing says so. Today's
ones are listed below by exact (file, module, name); they are debt, to be paid down, never added to.

The scan reads every .py under apps/<app>/ with `ast` (so multi-line and relative imports are
seen) and flags `from <other-app>.<mod> import _x`, however spelt:
`from apps.courses.m import _x`, `from courses.m import _x`, or a relative form that climbs out of
the app. It covers all three apps, so courses -> scholarship and reports -> either are guarded too.

Two safeguards against a scan that passes because it found nothing: a floor (every allowlisted
import must be FOUND, so a scanner that goes blind fails), and a self-test that feeds the scanner a
synthetic violation.
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

APPS_DIR = Path(__file__).resolve().parents[2]          # .../halatuju_api/apps
APP_NAMES = tuple(sorted(p.name for p in APPS_DIR.iterdir() if (p / '__init__.py').exists()))

# (file relative to apps/, imported module, private name). Today's debt: shrink it, never grow it.
ALLOWED = frozenset({
    ('scholarship/mentor_gift.py', 'apps.courses.staff_gift', '_gift_refusal'),
    ('scholarship/mentor_gift.py', 'apps.courses.staff_gift', '_not_found'),
    ('scholarship/sponsor_invite_gifts.py', 'apps.courses.staff_gift', '_as_id'),
    ('scholarship/scholars.py', 'apps.courses.search', '_digits_expr'),
    ('scholarship/staff_tables_admin.py', 'apps.courses.views_admin', '_staff_target_manageable'),
    ('scholarship/views_admin/staff.py', 'apps.courses.views_admin', '_staff_target_manageable'),
    ('scholarship/tests/test_mentor_is_not_staff.py', 'apps.courses.views_admin',
     '_staff_target_manageable'),
    ('scholarship/tests/test_source_user_is_not_staff.py', 'apps.courses.views_admin',
     '_staff_target_manageable'),
    ('scholarship/serializers_admin/names.py', 'apps.courses.views_admin', '_fetch_auth_data'),
    ('scholarship/views_admin/source_users.py', 'apps.courses.views_admin', '_invitation_dict'),
    # baseline from M1a (live b2fc146a5); route through apps.courses.public later, TD-414
    ('scholarship/staff_list.py', 'apps.courses.staff_fence', '_deletable_now'),
    ('scholarship/staff_list.py', 'apps.courses.staff_fence', '_staff_target_manageable'),
    ('scholarship/tests/test_m1a_review_fixes.py', 'apps.courses.tests.test_m1a_archive_restore',
     '_reviewed'),
    ('scholarship/tests/test_m1a_review_fixes.py', 'apps.courses.tests.test_m1a_archive_restore',
     '_unused'),
    # courses -> scholarship, all in courses tests (found by this scan, 2026-11-10):
    ('courses/tests/test_islamic_spm_subjects.py', 'apps.scholarship.academic_engine',
     '_SUBJECT_BM'),
    ('courses/tests/test_permission_catalogue_v2.py', 'apps.scholarship.views_admin', '_AdminBase'),
    ('courses/tests/test_permission_presets.py', 'apps.scholarship.scheduling', '_can_review'),
    ('courses/tests/test_permission_presets.py', 'apps.scholarship.services.assignment',
     '_can_review'),
    ('courses/tests/test_permission_presets.py', 'apps.scholarship.views_admin', '_AdminBase'),
    ('courses/tests/test_permission_presets.py', 'apps.scholarship.views_admin.reviewers',
     '_ReviewersBase'),
    ('courses/tests/test_tvet_doors.py', 'apps.scholarship.funding_estimate',
     '_classify_programme'),
})


def _is_private(name):
    return name.startswith('_') and not (name.startswith('__') and name.endswith('__'))


def _absolute_module(rel_path, node):
    """The dotted module a `from ... import` names, with a relative form resolved against the file.

    `rel_path` is the file relative to apps/ (e.g. scholarship/views_admin/staff.py), so the
    package of the file is ['apps', 'scholarship', 'views_admin'].
    """
    mod = node.module or ''
    if node.level == 0:
        return mod
    pkg = ['apps'] + list(Path(rel_path).parts[:-1])
    base = pkg[:len(pkg) - (node.level - 1)] if node.level > 1 else pkg
    return '.'.join(base + ([mod] if mod else []))


def _other_app(module, own_app):
    """The app a module belongs to when it is a DIFFERENT app, else None."""
    bits = module.split('.')
    if bits[0] == 'apps' and len(bits) >= 2:
        app = bits[1]
    else:
        app = bits[0]                       # bare `from courses.x import _y`
    return app if app in APP_NAMES and app != own_app else None


def scan_source(rel_path, source):
    """Every private cross-app import in one file: a set of (rel_path, module, name)."""
    own_app = Path(rel_path).parts[0]
    found = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _absolute_module(rel_path, node)
        if not _other_app(module, own_app):
            continue
        for alias in node.names:
            if _is_private(alias.name):
                found.add((rel_path, module, alias.name))
    return found


def scan_tree():
    found = set()
    for app in APP_NAMES:
        for path in (APPS_DIR / app).rglob('*.py'):
            if 'migrations' in path.parts:
                continue
            rel = path.relative_to(APPS_DIR).as_posix()
            found |= scan_source(rel, path.read_text(encoding='utf-8'))
    return found


class TestNoNewPrivateCrossAppImports(SimpleTestCase):
    def test_no_private_import_beyond_the_allowlist(self):
        new = sorted(scan_tree() - ALLOWED)
        self.assertEqual(
            new, [],
            'A private (_name) name was imported from another app. Add a public function to the '
            "owning app (courses: apps/courses/public.py) instead of reaching for `_x`:\n"
            + '\n'.join(f'  {f}: from {m} import {n}' for f, m, n in new))

    def test_the_scan_still_finds_every_allowlisted_import(self):
        # The floor. A scanner that stops seeing imports would pass the test above while finding
        # nothing; an allowlist entry that no longer exists is debt paid, so remove it here.
        missing = sorted(ALLOWED - scan_tree())
        self.assertEqual(missing, [],
                         'Allowlisted private imports the scan did not find (paid down? delete the '
                         f'line; or the scanner broke): {missing}')

    def test_the_allowlist_only_shrinks(self):
        # 14 scholarship -> courses pairs (10 old + 4 M1a baseline) + 7 courses -> scholarship test pairs. Lower this when a
        # line is deleted; raising it means a new private import got waved through.
        self.assertLessEqual(len(ALLOWED), 21)


class TestTheScannerItself(SimpleTestCase):
    def test_it_catches_a_synthetic_violation_in_every_spelling(self):
        cases = {
            'from apps.courses.staff_gift import _x': ('apps.courses.staff_gift', '_x'),
            'from apps.courses import _x': ('apps.courses', '_x'),
            'from courses.models import ok, _y': ('courses.models', '_y'),
            'from apps.courses.m import (\n    ok,\n    _z,\n)': ('apps.courses.m', '_z'),
            'from ...courses.m import _w': ('apps.courses.m', '_w'),
        }
        for src, (mod, name) in cases.items():
            with self.subTest(src=src):
                got = scan_source('scholarship/sub/x.py', src)
                self.assertEqual(got, {('scholarship/sub/x.py', mod, name)})

    def test_it_ignores_what_is_fine(self):
        fine = (
            'from apps.courses.models import StudentProfile\n'      # public name
            'from apps.scholarship.x import _own\n'                   # same app
            'from .sibling import _own\n'                             # relative, same app
            'from apps.courses.m import __version__\n'                # dunder
            'import apps.courses._hidden\n'                           # plain import, not a from
            'from os.path import _splitext\n'                         # not an app
        )
        self.assertEqual(scan_source('scholarship/x.py', fine), set())

    def test_it_also_guards_courses_and_reports(self):
        self.assertEqual(scan_source('courses/x.py', 'from apps.scholarship.m import _q'),
                         {('courses/x.py', 'apps.scholarship.m', '_q')})
        self.assertEqual(scan_source('reports/x.py', 'from apps.courses.m import _q'),
                         {('reports/x.py', 'apps.courses.m', '_q')})


# ---------------------------------------------------------------------------------------------
# A3.13: the back-edges go through the facade. courses -> scholarship, and reports -> courses /
# scholarship, must import from `apps.<other>.public`, never from a file behind it. Every skip is
# an exact (file, module, name) and says why. Shrink it, never grow it. Test files are exempt:
# they build fixtures from the other app's factories and are counted by the budget, not here.

# (file relative to apps/, imported module, name)
DOOR_ALLOWED = frozenset()   # F2 package 2 emptied it: views_admin and report_engine use the doors
# app -> the apps it must reach only through their `public` module
DOOR_RULES = {'courses': ('scholarship',), 'reports': ('courses', 'scholarship')}


def _door_edge(bits, guarded):
    """True when the dotted path `bits` reaches a guarded app by a way other than its `public`."""
    app = bits[1] if bits[0] == 'apps' and len(bits) > 1 else bits[0]
    return app in guarded and not (len(bits) > 2 and bits[2] == 'public')


def scan_doors(rel_path, source):
    """(rel_path, module, name) for every import of another app that does NOT go through its
    `public` module. Rules: DOOR_RULES. Spellings caught: `from apps.x.y import n`,
    `from apps import x` (the app itself as a name), `import apps.x.y [as z]` (empty name), and
    `importlib.import_module('apps.x.y')` / `import_module('apps.x.y')` with a string literal."""
    own_app = Path(rel_path).parts[0]
    guarded = DOOR_RULES.get(own_app, ())
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            module = _absolute_module(rel_path, node)
            bits = module.split('.')
            if bits == ['apps']:
                for alias in node.names:    # `from apps import scholarship`
                    if alias.name in guarded:
                        found.add((rel_path, 'apps', alias.name))
                continue
            app = bits[1] if bits[0] == 'apps' and len(bits) > 1 else bits[0]
            if app not in guarded:
                continue
            if len(bits) > 2 and bits[2] == 'public':
                continue
            for alias in node.names:
                if alias.name == 'public' and len(bits) <= 2:
                    continue                # `from apps.scholarship import public`
                found.add((rel_path, module, alias.name))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _door_edge(alias.name.split('.'), guarded):
                    found.add((rel_path, alias.name, ''))
        elif isinstance(node, ast.Call) and node.args:
            fn = node.func
            called = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, 'id', '')
            arg = node.args[0]
            if (called == 'import_module' and isinstance(arg, ast.Constant)
                    and isinstance(arg.value, str)
                    and _door_edge(arg.value.split('.'), guarded)):
                found.add((rel_path, arg.value, ''))
    return found


def scan_door_tree():
    found = set()
    for app in DOOR_RULES:
        for path in (APPS_DIR / app).rglob('*.py'):
            if 'migrations' in path.parts or 'tests' in path.parts or path.name.startswith('test_'):
                continue
            rel = path.relative_to(APPS_DIR).as_posix()
            found |= scan_doors(rel, path.read_text(encoding='utf-8'))
    return found


class TestBackEdgesGoThroughTheFacade(SimpleTestCase):
    def test_no_new_import_past_the_public_door(self):
        new = sorted(scan_door_tree() - DOOR_ALLOWED)
        self.assertEqual(
            new, [],
            'courses -> scholarship and reports -> courses/scholarship must import from '
            '`apps.<app>.public`. Add the name to that facade (re-export only) and import it from '
            'there:' + chr(10) + chr(10).join(f'  {f}: from {m} import {n}' for f, m, n in new))

    def test_the_scan_still_finds_every_skipped_edge(self):
        missing = sorted(DOOR_ALLOWED - scan_door_tree())
        self.assertEqual(missing, [],
                         'Skipped edges the scan did not find (routed now? delete the line; or the '
                         f'scanner broke): {missing}')

    def test_the_skip_list_only_shrinks(self):
        # Emptied by F2 package 2; it must stay empty.
        self.assertEqual(len(DOOR_ALLOWED), 0)

    def test_the_door_scanner_catches_each_spelling(self):
        cases = {
            'from apps.scholarship.models import X': {('courses/x.py', 'apps.scholarship.models', 'X')},
            'from apps.scholarship import emails': {('courses/x.py', 'apps.scholarship', 'emails')},
            'import apps.scholarship.emails': {('courses/x.py', 'apps.scholarship.emails', '')},
            'from apps.scholarship.public import X': set(),
            'from apps.scholarship import public': set(),
            'from apps.courses.models import Y': set(),        # courses -> courses is its own app
            'from apps import scholarship': {('courses/x.py', 'apps', 'scholarship')},
            'from apps import courses, scholarship': {('courses/x.py', 'apps', 'scholarship')},
            'from apps import public': set(),
            'import apps.scholarship.emails as e': {('courses/x.py', 'apps.scholarship.emails', '')},
            'import apps.scholarship.public as p': set(),
            "import importlib; importlib.import_module('apps.scholarship.emails')":
                {('courses/x.py', 'apps.scholarship.emails', '')},
            "from importlib import import_module; import_module('apps.scholarship')":
                {('courses/x.py', 'apps.scholarship', '')},
            "importlib.import_module('apps.scholarship.public')": set(),
            "importlib.import_module('apps.courses.models')": set(),
        }
        for src, want in cases.items():
            with self.subTest(src=src):
                self.assertEqual(scan_doors('courses/x.py', src), want)
        self.assertEqual(scan_doors('reports/x.py', 'from apps.courses.models import Y'),
                         {('reports/x.py', 'apps.courses.models', 'Y')})
        self.assertEqual(scan_doors('scholarship/x.py', 'from apps.courses.models import Y'), set())
