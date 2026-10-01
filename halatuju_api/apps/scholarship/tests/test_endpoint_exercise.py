"""TD-219 — PROVE that every wired endpoint is actually touched through the HTTP layer.

**The hole this closes.** On 2026-08-18 two defects landed with the same shape: a view called
its service with the wrong signature, and nothing noticed. `AdminOrgRequestAnswerView` kept
passing `index=` after TD-201 renamed the parameter to `comment_id=`, so **every answer, on
every request, for every organisation, raised `TypeError` before reaching the service and
500-ed — for eighteen days.** The service had tests. The endpoint had auth tests. *The call
between them had none*, and a gap between two well-tested halves is invisible to tests of
either half.

**What "exercised" means here, exactly.** A route is exercised when some test in the suite
makes an HTTP request whose path RESOLVES to that route, through Django's own resolver. The
scan is AST-driven, not textual: it walks every test module, finds every call whose method
name ends in a request verb (`self.client.post`, `self._patch`, `client.generic`, …), and
reconstructs the first argument that looks like a path — following f-strings, `+`
concatenation, module/class constants (`BASE = '/api/v1/…'`) and single-return URL helpers
(`def _url(self, pk): return f'…{pk}…'`), which is how this suite actually spells its URLs.
Interpolated values become `1`. Query strings are dropped. The reconstructed path is then
handed to `django.urls.resolve()`, and the route it reports — the full pattern, e.g.
`api/v1/admin/scholarship/applications/<int:pk>/qc-decision/` — is the key. **Nothing is
hand-listed**: add a route to `urls.py` and it is watched here the same day.

**⚠ THE BLIND SPOTS, STATED, because a guard whose limits are unwritten gets trusted for
things it never claimed:**

1. **It does not read assertions.** A test that asserts a 403, or a 404 behind a dark flag,
   exercises the URL and never reaches the service. The org-fence suite is full of exactly
   such requests, and they count here. So this is a floor — "somebody has driven this route"
   — not a promise that the seam behind it is covered.
2. **It does not distinguish HTTP METHODS.** A GET test marks a route whose POST is untested.
3. **It does not distinguish ROLES, feature flags or states.** One request marks the route.
4. **It cannot see a path assembled at run time** from pieces it cannot reconstruct (a list
   comprehension over verbs, a value read off a response). Those routes read as UNexercised,
   which is the safe direction: they land in the list below rather than vanishing.
5. **One route, one view class is NOT assumed.** Two `path()` entries sharing a view (the
   invoice/receipt PDF pair) are two routes here and each must be driven.
6. **`apps/courses/urls.py` is out of scope.** TD-219 is about the scholarship views and
   their services; widening it is a separate decision with its own allowlist.

The scan is static and reads no database, so it costs well under a second.
"""
import ast
import os
import re

from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from apps.scholarship import urls as scholarship_urls

#: The called name must END in a request verb, so `self.client.post`, `self._post` and a
#: test-local `api_get` wrapper all count, while `assertEqual` and `post_process` do not.
_VERB = re.compile(r'(?:^|_)(get|post|put|patch|delete|head|options|generic)$', re.I)

_TEST_ROOTS = ('scholarship', 'courses', 'reports')
_APPS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Anything an interpolated value stands in for. `1` resolves against `<int:…>`,
#: `<str:…>` and `<slug:…>` alike, which is all the converters these routes use.
_PLACEHOLDER = '1'


def _key(node):
    """The name a value was stored under: `BASE`, or `self.BASE`, or a def's own name."""
    if isinstance(node, ast.Name):
        return node.id
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id in ('self', 'cls')):
        return node.attr
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    return None


def reconstruct(node, consts):
    """Best-effort source-time value of an expression, as a string.

    Deliberately lossy and deliberately optimistic: anything it cannot follow becomes the
    placeholder, so a path it half-understands still resolves. A wrong guess costs a route
    being marked exercised when it is not — which the reviewer sees as a missing entry in the
    list below, not as a silent pass — and the alternative (bailing out) loses whole modules.
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else _PLACEHOLDER
    if isinstance(node, ast.JoinedStr):
        return ''.join(reconstruct(p, consts) for p in node.values)
    if isinstance(node, ast.FormattedValue):
        known = _key(node.value)
        return consts[known] if known in consts else _PLACEHOLDER
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return reconstruct(node.left, consts) + reconstruct(node.right, consts)
    if isinstance(node, ast.Call):
        return reconstruct(node.func, consts)       # a `self._url(pk)` helper
    known = _key(node)
    if known in consts:
        return consts[known]
    return _PLACEHOLDER


def path_constants(tree):
    """Every name in one module that holds a path-ish string.

    Covers the three spellings this suite uses: a module constant
    (`BASE = '/api/v1/…'`), a class attribute, and a single-return helper method. Three
    passes so a chain settles — `BASE` → `DETAIL = f'{BASE}{pk}/'` → `def _url()`.
    """
    consts = {}
    for _pass in range(3):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value = reconstruct(node.value, consts)
                if '/' in value:
                    for target in node.targets:
                        name = _key(target)
                        if name:
                            consts[name] = value
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                returns = [n for n in ast.walk(node)
                           if isinstance(n, ast.Return) and n.value is not None]
                if len(returns) == 1:
                    value = reconstruct(returns[0].value, consts)
                    if value.startswith('/api/'):
                        consts[node.name] = value
    return consts


def request_paths(source):
    """Every `/api/v1/…` path this module hands to a request call."""
    try:
        tree = ast.parse(source)
    except SyntaxError:                                     # pragma: no cover - never today
        return []
    consts = path_constants(tree)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
        if not _VERB.search(name or ''):
            continue
        for arg in node.args:
            candidate = reconstruct(arg, consts).split('?')[0].split('#')[0].strip()
            if candidate.startswith('/api/v1/'):
                found.append(candidate)
                break                                       # the path is one argument
    return found


def exercised_routes():
    """The set of route patterns some test drives, and the count of files read."""
    routes, files = set(), 0
    for app in _TEST_ROOTS:
        for dirpath, _dirs, names in os.walk(os.path.join(_APPS_DIR, app, 'tests')):
            for name in sorted(names):
                if not name.endswith('.py'):
                    continue
                files += 1
                with open(os.path.join(dirpath, name), encoding='utf-8') as fh:
                    source = fh.read()
                for candidate in request_paths(source):
                    try:
                        routes.add(resolve(candidate).route)
                    except Resolver404:
                        pass        # a deliberate bad path, or one we half-reconstructed
    return routes, files


def wired_routes():
    """Every route `apps/scholarship/urls.py` wires, spelled as the resolver spells it."""
    return ['api/v1/' + str(pattern.pattern) for pattern in scholarship_urls.urlpatterns]


class TestEveryEndpointIsExercised(SimpleTestCase):
    """A URL nobody drives is a view nobody has ever run."""

    #: ⚠⚠ **A LEDGER THAT MAY ONLY SHRINK — the same shape as the org fence's
    #: `NOT_YET_SCANNED`.** Each line is a wired endpoint that **no test drives at all**, as
    #: measured on 2026-09-18 at code health H3. A route here is a DECISION to ship it
    #: untested, written down; the reason is the check. Write a test that touches the route
    #: and `test_the_list_only_shrinks` fails with "remove me" — which is the point: the list
    #: cannot be left behind by the work that empties it.
    #:
    #: ⚠ The comments say why each one MATTERS, not why it is acceptable. Twenty-two lines were
    #: recorded at H3; TD-203 (2026-09-30) drove `cancel-decline` and TD-257 (Now sprint 1,
    #: 2026-10-01) drove twenty more — the money-out routes, the cool-off brake, the reporting
    #: date, closure, the sponsor-membership gate, six Requests verbs, the verdict summary, the
    #: sponsor-terms editors, the graduation relay and the document help — each with the role,
    #: the flag and an assertion on what the service wrote (`test_endpoints_*.py`).
    #:
    #: The twenty-second, the per-slot interview DELETE, had no caller anywhere (an exported web
    #: function nothing imported, no cron) and was DELETED on the owner's ruling the same day,
    #: with its view and its service function — so the ledger is EMPTY and TD-257 is closed.
    #:
    #: ⚠ EMPTY IS THE STEADY STATE NOW, AND `test_the_ledger_stays_empty` HOLDS IT THERE. A new
    #: route with no test fails `test_every_wired_endpoint_is_exercised_or_listed`; the answer is
    #: a test, and adding a line here is a decision to ship untested that the reviewer must see —
    #: which is why the empty-ledger test fails on it too and names this comment.
    NOT_YET_EXERCISED = {}

    #: The routes `apps/scholarship/urls.py` wired on 2026-10-01 after the dead DELETE left: 199.
    #: A FLOOR with margin, never an equality (lessons.md, H16): adding routes must not turn it
    #: red, and an empty ledger must never let the guard pass while the walk saw nothing.
    MIN_WIRED_ROUTES = 190

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.exercised, cls.files_read = exercised_routes()
        cls.wired = wired_routes()

    def test_the_scan_actually_found_the_suite(self):
        """THE FLOOR, and the only reason the assertions below mean anything. A scan that
        walked no files, or reconstructed no paths, would report every route as unexercised —
        or, after somebody "fixed" that by widening the list, as exercised. Either way the
        guard would be decorative. These numbers are what it saw on 2026-09-18, less a wide
        margin for ordinary churn."""
        self.assertGreater(self.files_read, 200, 'the test tree moved or was not found')
        self.assertGreater(len(self.exercised), 150, 'no paths reconstructed — check the AST walk')
        self.assertGreaterEqual(len(self.wired), self.MIN_WIRED_ROUTES,
                                'urls.py moved or was not found')
        # With the ledger EMPTY, "exercised or listed" is just "exercised" — so the rule below
        # only means something if the exercised set actually COVERS the wired set it is held to.
        self.assertGreaterEqual(len(set(self.wired) & self.exercised), self.MIN_WIRED_ROUTES,
                                'fewer wired routes resolved as exercised than the floor')

    def test_the_ledger_stays_empty(self):
        """TD-257 closed the ledger on 2026-10-01 (twenty routes tested, the dead one deleted).
        With nothing left in it, `test_the_list_only_shrinks` below can no longer fail, so THIS
        is the test that keeps the ledger honest: a new line is a decision to ship a route
        untested, and it must be argued in review, not slipped in."""
        self.assertEqual(
            self.NOT_YET_EXERCISED, {},
            'NOT_YET_EXERCISED was emptied by TD-257 (2026-10-01). Write an endpoint test for the '
            'route instead; if it genuinely cannot be tested yet, change THIS test in the same '
            'diff and say why, so the reviewer sees the decision.')

    def test_every_wired_endpoint_is_exercised_or_listed(self):
        """The rule. A new endpoint with no test that drives it fails HERE, on the day it is
        wired, rather than eighteen days later in production."""
        missing = [r for r in self.wired
                   if r not in self.exercised and r not in self.NOT_YET_EXERCISED]
        self.assertEqual(
            missing, [],
            'Endpoint(s) wired in urls.py that NO test drives through the HTTP layer. Write a '
            'test that makes a real request to the route (see TD-219 — this is the gap that '
            '500-ed for eighteen days), or, if it genuinely cannot be tested yet, add it to '
            'NOT_YET_EXERCISED with a reason:\n' + '\n'.join(missing))

    def test_the_list_only_shrinks(self):
        """The other direction. Cover one of these and the entry must GO — otherwise the list
        outlives the debt, stops describing anything, and quietly re-permits the next one."""
        now_covered = sorted(r for r in self.NOT_YET_EXERCISED if r in self.exercised)
        self.assertEqual(
            now_covered, [],
            'These endpoints ARE now exercised — remove them from NOT_YET_EXERCISED:\n'
            + '\n'.join(now_covered))

    def test_every_listed_endpoint_is_still_wired(self):
        """A stale entry is worse than none: it reads as a known gap while the route it names
        no longer exists, so the list overstates the debt and nobody can tell which part."""
        wired = set(self.wired)
        stale = sorted(r for r in self.NOT_YET_EXERCISED if r not in wired)
        self.assertEqual(
            stale, [],
            'NOT_YET_EXERCISED names route(s) urls.py no longer wires — remove them:\n'
            + '\n'.join(stale))
