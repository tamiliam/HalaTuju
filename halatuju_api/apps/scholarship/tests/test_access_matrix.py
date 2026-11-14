"""Advisor action 4, part 1 — the role-by-endpoint ACCESS MATRIX, every route, every caller.

What it proves, per (route, method, caller), against `access_manifest.json`:

* ``allow`` — the caller gets past the gate: NOT 401, 403 or 404 (a 400 or a 2xx is a call the
  view ran). For an object route this also proves the seeded id is real for that caller.
* ``hide``  — the caller is refused by a 404 (the code hides that the object exists, or there is
  nothing of theirs at that id). 401/403 are accepted too: a refusal that got louder is still one.
* every other caller — ``deny``: 401 or 403, nothing else.

⚠ THE ROUTES ARE WALKED OFF THE LIVE RESOLVER (nested includes, every pattern), so a route added
tomorrow is in the sweep the day it lands. A route or method with no manifest entry FAILS
(`test_every_route_has_a_manifest_entry`, and each of its cases) — the ratchet: a new endpoint
must say who may use it. A manifest entry naming a route that no longer exists fails too.

⚠ HOLES ARE ASSERTED AS THEY STAND, NOT MARKED xfail. The project's code-standards guard forbids
skip/xfail markers outright (`test_code_standards.py`, budget 0). A hole is therefore written into
the manifest as the CURRENT behaviour with a `"HOLE: ..."` flag, and `test_holes_are_listed`
keeps the flagged list in one place. When a hole is closed, its case fails here — exactly what
`xfail(strict=True)` would do — and the entry is corrected in the same change as the fix.

⚠ INTENT-UNCLEAR entries record the CURRENT behaviour where the code does not say what was meant.

The secret callers (cron family keys, the Vircle key, a Twilio signature) are swept only against
the three internal routes that read those headers; everywhere else they carry no JWT and ARE the
anonymous caller. The dark-shipped flags are switched ON so a flag's 404 cannot hide a leak.
Nothing leaves the process: sockets to anything but loopback are refused, and the cron runner is
replaced, so a call that gets through runs no job, sends no mail and spends no credit.
"""
import json
import pathlib
import socket
from unittest import mock

import pytest
from django.core.cache import cache
from django.db import transaction
from django.test import override_settings
from django.urls import URLPattern, URLResolver, get_resolver
from django.urls.resolvers import RoutePattern

from apps.scholarship.tests import access_world
from apps.scholarship.tests.access_world import INTERNAL_ROUTES, JWT_ROLES, roles_for
from apps.scholarship.tests.factories import TEST_JWT_SECRET

MANIFEST_PATH = pathlib.Path(__file__).with_name('access_manifest.json')
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
ENTRIES = {(e['route'], e['method']): e for e in MANIFEST['entries']}
SKIPS = {s['route']: s['reason'] for s in MANIFEST['skips']}
#: ``(route, method, caller) -> (status, reason)``: an ALLOWED caller whose call is pinned to one
#: exact status it cannot help giving here. ``BUG: `` is a real app defect (the case fails the day
#: it is fixed, so the entry is corrected with the fix); ``ENV: `` is a service switched off in
#: tests (AI, storage signing) or a file upload sent JSON — the gate was passed, the work was not.
PINNED = {(p['route'], p['method'], caller): (p['status'], p['reason'])
          for p in MANIFEST['pinned'] for caller in p['callers']}

#: The two routes outside the sweep, locked: a third skip must be argued for here, not slipped in.
LOCKED_SKIPS = {
    'admin/': 'Django admin site: its own session login, not the API',
    'api/v1/health/': 'liveness probe: public by design, no data',
}

WRITE_METHODS = ('post', 'put', 'patch', 'delete')
DENY = {401, 403}
HIDE = {401, 403, 404}
#: An ALLOWED caller never gets one of these unless the case is pinned: a 5xx is a crash, not a
#: pass, and a 415 is DRF refusing the body before the view's own work.
BROKEN = {415}

#: The flags an entry may carry. An entry with NOBODY allowed proves no fence (every caller gets
#: the same refusal), so it must say why: ``UNCOVERED: `` (the world cannot reach the rightful
#: caller's state) or ``STATE: `` (the refusal is the case's state, not who is asking).
FLAG_PREFIXES = ('HOLE: ', 'INTENT-UNCLEAR: ', 'UNCOVERED: ', 'STATE: ')
NO_FENCE_FLAGS = ('UNCOVERED: ', 'STATE: ')

#: The owner-side caller and the other party OF THE SAME RANK on the same object: an object entry
#: must allow the first and refuse the second (so the refusal is about the object, not the role),
#: or hide the object (404) from a cross-tenant / cross-owner caller while someone is allowed.
OBJECT_PAIRS = (('org_admin_a', 'org_admin_b'), ('student_a', 'student_b'),
                ('sponsor_a', 'sponsor_b'), ('reviewer_a', 'reviewer_a2'))
CROSS_CALLERS = {'org_admin_b', 'student_b', 'sponsor_b', 'reviewer_a2'}

#: Just below the 439 (route, method) pairs served on 2026-11-13: a resolver change that hides
#: routes cannot pass silently.
MIN_PAIRS = 435

DARK_FLAGS_ON = dict(
    BURSARY_AGREEMENT_ENABLED=True, BILLING_USAGE_ENABLED=True, REQUESTS_ENABLED=True,
    SPONSOR_POOL_ENABLED=True, SPONSOR_TERMS_ENABLED=True, INTERVIEW_SCHEDULING_ENABLED=True,
    PARTNER_COMMS_ENABLED=True, SPONSOR_COMMS_ENABLED=True, BANK_DETAILS_CAPTURE_ENABLED=True,
    AWARD_ACCEPTANCE_ENABLED=True, CHECK2_STUDENT_QUERIES_ENABLED=True, PHONE_VERIFY_ENABLED=True,
)
#: No live credential can be reached from here (defence in depth beside the socket guard).
NO_CREDENTIALS = dict(SUPABASE_URL='', SUPABASE_SERVICE_ROLE_KEY='', GEMINI_API_KEY='',
                      TWILIO_ACCOUNT_SID='', TWILIO_WHATSAPP_FROM='', WHATSAPP_ENABLED=False)


# ── The routes ──────────────────────────────────────────────────────────────────────────────
def served_pairs():
    """``([(route, method)], [unwalkable])`` for every pattern the resolver serves, minus the
    skips. A function view (no class, so no methods to read) or a regex route (whose text is not
    a fillable path) cannot be swept honestly, so it is returned as UNWALKABLE and fails."""
    pairs, unwalkable = [], []

    def walk(patterns, prefix):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                route = prefix + str(p.pattern)
                if any(route.startswith(skip) for skip in SKIPS):
                    continue
                view = getattr(p.callback, 'view_class', None)
                if view is None or not isinstance(p.pattern, RoutePattern):
                    unwalkable.append(route)
                    continue
                pairs.extend((route, m) for m in ('get',) + WRITE_METHODS
                             if hasattr(view, m) and m in view.http_method_names)

    walk(get_resolver('halatuju.urls').url_patterns, '')
    return pairs, unwalkable


PAIRS, UNWALKABLE = served_pairs()


def _cases():
    for route, method in PAIRS:
        for role in roles_for(route):
            yield pytest.param(route, method, role, id=f'{method.upper()} {route} as {role}')


# ── The world, once per module ──────────────────────────────────────────────────────────────
_LOOPBACK = {'localhost', '127.0.0.1', '::1', '', None}


def _no_network():
    """Refuse every socket that is not loopback / a local file, so no call can reach a paid or
    external service whatever a view tries. (Tests run on SQLite; a local Postgres still works.)"""
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def connect(self, address):
        if isinstance(address, tuple) and address[0] not in _LOOPBACK:
            raise OSError('network disabled in the access matrix')
        return real_connect(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if host not in _LOOPBACK:
            raise OSError('network disabled in the access matrix')
        return real_getaddrinfo(host, *args, **kwargs)

    return [mock.patch.object(socket.socket, 'connect', connect),
            mock.patch.object(socket, 'getaddrinfo', getaddrinfo)]


@pytest.fixture(scope='module')
def world(django_db_setup, django_db_blocker):
    patches = _no_network() + [
        mock.patch('apps.scholarship.cron_health.run_job', return_value={'ok': True}),
        # The PDF + storage seams, as `test_bursary_agreement.py` patches them: a call that gets
        # through answers its REAL status instead of a 500 from a blocked socket.
        mock.patch('apps.scholarship.bursary.generate_pdf', return_value=b'%PDF-1.4 test'),
        mock.patch('apps.scholarship.storage.upload_object', return_value=True),
        mock.patch('apps.scholarship.storage.create_signed_download_url',
                   return_value='https://signed.example/file.pdf'),
    ]
    settings = override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                                 **DARK_FLAGS_ON, **NO_CREDENTIALS, **access_world.TEST_SECRETS)
    for p in patches:
        p.start()
    settings.enable()
    try:
        with django_db_blocker.unblock():
            with transaction.atomic():
                yield access_world.build_world()
                transaction.set_rollback(True)
    finally:
        settings.disable()
        for p in reversed(patches):
            p.stop()


# ── The ratchet ─────────────────────────────────────────────────────────────────────────────
def test_every_route_has_a_manifest_entry():
    assert len(PAIRS) >= MIN_PAIRS
    assert not UNWALKABLE, ('route(s) the sweep cannot walk (a function view or a regex route): '
                            'make it a class view on path(), or skip it here with a reason:\n'
                            + '\n'.join(UNWALKABLE))
    served = set(PAIRS)
    missing = sorted(served - set(ENTRIES))
    stale = sorted(set(ENTRIES) - served)
    assert not missing, ('route(s) with no access-manifest entry — say who may use each one in '
                         'access_manifest.json:\n' + '\n'.join(f'{m.upper()} {r}' for r, m in missing))
    assert not stale, ('manifest entries for routes that are no longer served:\n'
                       + '\n'.join(f'{m.upper()} {r}' for r, m in stale))


def test_manifest_is_well_formed():
    known = set(JWT_ROLES) | set(access_world.SECRET_ROLES)
    for (route, method), entry in ENTRIES.items():
        allow, hide = set(entry['allow']), set(entry['hide'])
        assert allow <= known and hide <= known, (route, method, (allow | hide) - known)
        assert not allow & hide, (route, method, allow & hide)
        flags = entry.get('flags', [])
        for flag in flags:
            assert flag.startswith(FLAG_PREFIXES), (route, method, flag)
        no_fence = any(f.startswith(NO_FENCE_FLAGS) for f in flags)
        # Nobody allowed proves nothing: a 404 (or 403) for EVERYONE passes as a "fence" while the
        # route's real caller is never shown to get through. Such an entry must say so.
        assert allow or no_fence, (
            f'{method.upper()} {route}: nobody is allowed, so the refusals prove no fence; seed '
            'the rightful caller, or flag it "UNCOVERED: <why>" / "STATE: <why>"')
        if entry['object']:
            # The cross-tenant / cross-owner claim: on the SAME seeded object, the owner side gets
            # through AND the other party is refused (hidden, or denied while its counterpart of
            # the same rank is let in).
            assert not no_fence, (route, method, 'an object entry cannot also be UNCOVERED/STATE')
            proved = (allow and hide & CROSS_CALLERS) or any(
                owner in allow and other not in allow for owner, other in OBJECT_PAIRS)
            assert proved, (f'{method.upper()} {route}: marked object {entry["object"]} but no '
                            'owner is allowed with the other party refused on it')
    assert SKIPS == LOCKED_SKIPS, 'the skip list is locked to its two routes; argue a change here'
    assert set(INTERNAL_ROUTES) <= {r for r, _ in PAIRS}
    for p in MANIFEST['pinned']:
        entry = ENTRIES[(p['route'], p['method'])]
        assert p['reason'].startswith(('BUG: ', 'ENV: ')), p
        assert set(p['callers']) <= set(entry['allow']), (
            p, 'a pinned status is for an ALLOWED caller whose call cannot finish here')


def test_known_bugs_are_listed():
    """The header's ``known_bugs`` is exactly the BUG-pinned routes, so the owner reads every
    known defect the matrix is pinned to in one place."""
    pinned = sorted({f'{p["method"].upper()} {p["route"]}' for p in MANIFEST['pinned']
                     if p['reason'].startswith('BUG: ')})
    assert pinned == sorted(MANIFEST['known_bugs'])


def test_holes_are_listed():
    """The HOLE list in the manifest header is exactly the entries flagged HOLE, so the owner reads
    every open hole in one place and none hides in the body."""
    flagged = sorted(f'{e["method"].upper()} {e["route"]}' for e in MANIFEST['entries']
                     if any(f.startswith('HOLE: ') for f in e.get('flags', [])))
    assert flagged == sorted(MANIFEST['holes'])


# ── The matrix ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
@pytest.mark.parametrize('route,method,role', list(_cases()))
def test_access(world, route, method, role):
    entry = ENTRIES.get((route, method))
    assert entry is not None, f'no access-manifest entry for {method.upper()} {route}'
    cache.clear()  # rate limits and cached reads must not carry from one caller to the next
    code = world.call(role, route, method).status_code
    pinned = PINNED.get((route, method, role))
    if pinned is not None:
        status, reason = pinned
        assert code == status, (
            f'{role} {method.upper()} {route} is pinned to {status} ({reason}) but got {code}: '
            'if the bug is fixed or the service now answers, correct the "pinned" entry')
    elif role in entry['allow']:
        assert code not in HIDE, f'{role} is ALLOWED {method.upper()} {route} but got {code}'
        assert code < 500 and code not in BROKEN, (
            f'{role} is ALLOWED {method.upper()} {route} but the call broke ({code})')
    elif role in entry['hide']:
        assert code in HIDE, f'{role} must be refused (404) {method.upper()} {route}, got {code}'
    else:
        assert code in DENY, f'{role} must be DENIED {method.upper()} {route}, got {code}'
