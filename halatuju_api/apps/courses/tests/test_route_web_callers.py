"""RD-08 (audit A3.17) — every API route has a web caller, or says why it does not.

**The hole this closes.** A route nobody calls is code that still has to be secured, tested and
kept in step with the models, for no user. Two of them had grown (a student's referee list and
add) after the web screens that used them were replaced. This test turns "no web caller" from a
thing an audit finds once into a thing the suite refuses.

**How a caller is found.** The scan reads every non-test `.ts`/`.tsx` file under
`halatuju-web/src`, collects each string and template literal that contains a `/`, substitutes
module-level string constants (`const CT = '/api/v1/…'`), turns every other `${…}` into a
placeholder, and checks each live route (from Django's own resolver) against the tail of those
literals. It is lenient on purpose: a route is read as called if any literal ends with its path.
A miss therefore means the web code genuinely does not spell that path. A false "called" is
possible (two routes sharing a tail); a false "orphan" is the failure this test would announce,
and the fix is to teach `_literals` the new spelling, not to widen the allowlist.

**The allowlist** is the routes that are legitimately not called from the web, each with the
reason: a scheduler, a webhook, an email link, a script, or an external caller. Adding to it is a
statement that somebody outside the web bundle depends on the route. **A route with no reason
here and no caller is removed.**

**Deploy note.** The API build only triggers on `halatuju_api/**`, so a web-only push that removes
the last caller of a route passes its own build and fails the NEXT API deploy.
"""
import re
from functools import lru_cache
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import get_resolver
from django.urls.resolvers import URLResolver

_WEB_SRC = Path(__file__).resolve().parents[4] / 'halatuju-web' / 'src'

#: route (as Django prints it) -> why it has no web caller.
NOT_CALLED_FROM_WEB = {
    # ---- called by something that is not the web bundle ------------------------------------
    'api/v1/internal/cron/<str:job>/':
        'Cloud Scheduler jobs (docs/deployment.md); authenticated by a shared secret, not a user.',
    'api/v1/internal/vircle/airtable/':
        'Vircle Airtable automation posts here; an external caller with its own secret.',
    'api/v1/scholarship/whatsapp/inbound/':
        'Twilio webhook (inbound WhatsApp replies and STOP); called by Twilio, not the web.',
    'api/v1/admin/scholarship/applications/<int:pk>/release-nric-lock/':
        'Super-only break-glass for a wrongly locked IC (views_admin/sponsors.py docstring); used '
        'by support by hand, deliberately with no button.',
    # ---- wired, tested and kept, with no screen yet: an owner decision, not a dead route -----
    'api/v1/admin/referral-partners/':
        'TD-387: the super-only path exists, the screen needs a Stitch prototype first.',
    'api/v1/admin/referral-partners/<int:org_id>/':
        'TD-387: as the list above.',
    'api/v1/admin/graduation-messages/<int:pk>/review/':
        'TD-496 ruling B retired the moderation LIST and kept the review action; no screen calls '
        'it. Revisit with the owner whether moderation returns or this goes too.',
    'api/v1/admin/sponsorships/':
        'decisions.md (staff-permissions table): the same rows reach the console through the '
        'sponsor detail; the list route is read by no screen.',
    'api/v1/admin/staff/':
        'M1 staff list: its web caller lands with the M1b screens (separate session).',
    'api/v1/institutions/<str:institution_id>/':
        'Public catalogue detail; the web reads the list only. Kept as public API, pinned by '
        'courses/tests/test_api.py.',
    # ---- per-application profile actions: the pipeline runs from cron, the cockpit does not
    # ---- ever call these. Gemini-backed, so left for the owner to retire rather than cut here.
    'api/v1/admin/scholarship/applications/<int:pk>/generate-profile/':
        'Admin/scripted action; no web caller; Gemini-backed.',
    'api/v1/admin/scholarship/applications/<int:pk>/finalise-profile/':
        'Manual trigger for what the finalise-profiles cron (every 5 minutes) already does.',
    'api/v1/admin/scholarship/applications/<int:pk>/profile/':
        'Profile text edit; no screen since the cockpit replaced the old detail page.',
    'api/v1/admin/scholarship/applications/<int:pk>/publish/':
        'Pool publish of the profile; no screen since the cockpit replaced the old detail page.',
    'api/v1/admin/scholarship/applications/<int:pk>/anon-profile/publish/':
        'Anonymous-profile publish (Phase E2); no screen since the cockpit replaced the old page.',
    # ---- sponsor money: the sponsor portal is a mock (TD, SponsorDonateView) ---------------
    'api/v1/sponsor/wallet/donate/':
        'Mock donation-in (its docstring); the real money-in path is toyyibPay. Kept as the '
        'mock until that lands: money code is not cut in a dead-code sprint.',
    'api/v1/sponsor/sponsorships/':
        'Sponsor portal API with no screen yet; money, so kept for the owner to rule on.',
    'api/v1/sponsor/sponsorships/<int:pk>/cancel/':
        'As the sponsorships list above (money, kept).',
}

_STR = re.compile(r"""'((?:\\.|[^'\\\n])*)'|"((?:\\.|[^"\\\n])*)\"""")


def _template_literals(src):
    """Backtick templates, brace-aware, so a nested `${a ? 'x' : 'y'}` does not end the scan."""
    out, i, n = [], 0, len(src)
    while i < n:
        if src[i] != '`':
            i += 1
            continue
        j, depth, buf = i + 1, 0, []
        while j < n:
            c = src[j]
            if c == '\\':
                buf.append(src[j:j + 2])
                j += 2
                continue
            if depth == 0 and c == '`':
                break
            if c == '$' and src[j:j + 2] == '${':
                depth += 1
                buf.append('${')
                j += 2
                continue
            if depth and c == '}':
                depth -= 1
            elif depth and c == '{':
                depth += 1
            buf.append(c)
            j += 1
        out.append(''.join(buf))
        i = j + 1
    return out


def _strip_expr(text):
    """Replace every brace-balanced `${…}` with the placeholder `X`."""
    out, i = [], 0
    while i < len(text):
        if text[i:i + 2] == '${':
            depth, j = 1, i + 2
            while j < len(text) and depth:
                depth += (text[j] == '{') - (text[j] == '}')
                j += 1
            out.append('X')
            i = j
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


_QUOTED = r"""(?:'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`)"""
_STR_CONST = re.compile(r'(?:const|let)\s+([A-Za-z_]\w*)\s*(?::[^=\n]+)?=\s*' + _QUOTED)
#: `const base = (id: number) => `/api/v1/…/${id}/…`` and `function url(id) { return `…` }`.
_FN_CONST = re.compile(
    r'(?:const\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::[^=]+)?=>\s*'
    r'|function\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*(?::[^{]+)?\{\s*return\s*)' + _QUOTED)


def _file_consts(src):
    consts = {}
    for m in _STR_CONST.finditer(src):
        val = next(g for g in m.groups()[1:] if g is not None)
        if '/' in val:
            consts[m.group(1)] = val
    for m in _FN_CONST.finditer(src):
        val = next(g for g in m.groups()[2:] if g is not None)
        if '/' in val:
            consts[m.group(1) or m.group(2)] = val
    return consts


def _expand(text, consts):
    """Substitute `${NAME}` and `${NAME(…)}` from `consts`, to a fixed point, then blank the rest."""
    for _ in range(4):
        changed = False
        for name, val in consts.items():
            new = re.sub(r'\$\{' + re.escape(name) + r'(?:\([^()}]*(?:\([^()]*\)[^()}]*)*\))?\}',
                         lambda _m, v=val: v, text)
            changed |= new != text
            text = new
        if not changed:
            break
    return _strip_expr(text)


@lru_cache(maxsize=1)
def _literals():
    files = []
    for path in _WEB_SRC.rglob('*'):
        if path.suffix not in ('.ts', '.tsx') or '__tests__' in path.parts or '.test.' in path.name:
            continue
        files.append(path.read_text(encoding='utf8'))
    per_file = [_file_consts(src) for src in files]
    # A constant imported from another file: use it only when every file that defines it agrees.
    seen = {}
    for consts in per_file:
        for k, v in consts.items():
            seen.setdefault(k, set()).add(v)
    shared = {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}
    lits = set()
    for src, own in zip(files, per_file):
        consts = {**shared, **own}
        raw = [a or b for a, b in _STR.findall(src)] + _template_literals(src)
        for text in raw:
            text = _expand(text, consts).split('?')[0]
            text = re.sub(r'/{2,}', '/', text)
            # Page links (`/admin/staff`) are not API calls: keep a literal only when it names the
            # API prefix, or starts with an interpolated base (`${base(id)}sessions/`).
            if '/' in text and ('api/v1/' in text or text.startswith('X')):
                lits.add(text.strip('/'))
                # A trailing `${query}` is not part of the path, but a trailing `${id}` is: the
                # scan cannot tell them apart, so it keeps both readings.
                if text.endswith('X'):
                    lits.add(re.sub(r'(?:/?X)+$', '', text).strip('/'))
    return lits


def _routes():
    def walk(resolver, prefix=''):
        for p in resolver.url_patterns:
            if isinstance(p, URLResolver):
                yield from walk(p, prefix + str(p.pattern))
            else:
                yield prefix + str(p.pattern)
    return [r for r in walk(get_resolver()) if r.startswith('api/v1/')]


def _segment_matches(route_seg, lit_seg):
    """A route segment (`pdf`, `<int:pk>`) against a literal one (`pdf`, `X`, `Xs`, `${kind}s`)."""
    if route_seg.startswith('<'):
        return True
    if lit_seg == 'X':
        return False   # a bare placeholder is an id or a verb: it may not stand for a fixed segment
    if 'X' not in lit_seg:
        return route_seg == lit_seg
    # `X` stands for an interpolated value: `Xs` is `invoices` or `receipts`, `X` is anything.
    return re.fullmatch(re.escape(lit_seg).replace('X', '.*'), route_seg) is not None


def _called(route, literals):
    """True when some literal's trailing segments spell the route's path."""
    segs = route[len('api/v1/'):].strip('/').split('/')
    for lit in literals:
        lit_segs = lit.split('/')
        if len(lit_segs) < len(segs):
            continue
        if all(_segment_matches(r, l) for r, l in zip(segs, lit_segs[-len(segs):])):
            return True
    return False


@lru_cache(maxsize=1)
def uncalled_routes():
    lits = {lit.replace('api/v1/', '', 1) if lit.startswith('api/v1/') else lit for lit in _literals()}
    return tuple(sorted(r for r in _routes() if not _called(r, lits)))


class RouteWebCallerTest(SimpleTestCase):

    def test_the_scan_sees_the_web_source(self):
        self.assertTrue(_WEB_SRC.is_dir(), f'{_WEB_SRC} not found: the scan would pass on nothing')
        self.assertGreater(len(_literals()), 200)

    def test_every_route_has_a_web_caller_or_a_stated_reason(self):
        orphans = [r for r in uncalled_routes() if r not in NOT_CALLED_FROM_WEB]
        self.assertEqual(
            orphans, [],
            'API routes with no web caller and no reason in NOT_CALLED_FROM_WEB. Remove the route '
            'and its view, or add it to the allowlist with the script, scheduler, email or '
            'external caller that uses it.')

    def test_the_allowlist_has_no_stale_entries(self):
        live = set(_routes())
        stale = [r for r in NOT_CALLED_FROM_WEB if r not in live]
        self.assertEqual(stale, [], 'allowlisted routes that no longer exist')
        called = [r for r in NOT_CALLED_FROM_WEB if r not in uncalled_routes()]
        self.assertEqual(called, [], 'allowlisted routes that the web now calls: drop the entry')


class ScannerSelfTest(SimpleTestCase):
    """The scanner must tell a called route from an orphaned one, or the guard above is blind."""

    def test_a_called_route_is_seen_and_an_orphan_is_not(self):
        src = "const BASE = '/api/v1/widgets/';" + chr(10) + "fetch(`${BASE}${id}/pdf/`);"
        consts = _file_consts(src)
        text = _expand(_template_literals(src)[0], consts).split('?')[0]
        lits = {re.sub(r'/{2,}', '/', text).strip('/').replace('api/v1/', '', 1)}
        self.assertEqual(lits, {'widgets/X/pdf'})
        self.assertTrue(_called('api/v1/widgets/<int:pk>/pdf/', lits))
        self.assertFalse(_called('api/v1/gadgets/<int:pk>/pdf/', lits))
