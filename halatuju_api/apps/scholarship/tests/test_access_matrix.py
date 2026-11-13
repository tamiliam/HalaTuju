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

from apps.scholarship.tests import access_world
from apps.scholarship.tests.access_world import INTERNAL_ROUTES, JWT_ROLES, roles_for
from apps.scholarship.tests.factories import TEST_JWT_SECRET

MANIFEST_PATH = pathlib.Path(__file__).with_name('access_manifest.json')
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
ENTRIES = {(e['route'], e['method']): e for e in MANIFEST['entries']}
SKIPS = {s['route']: s['reason'] for s in MANIFEST['skips']}

WRITE_METHODS = ('post', 'put', 'patch', 'delete')
DENY = {401, 403}
HIDE = {401, 403, 404}

#: Below the 439 (route, method) pairs served on 2026-11-13, far above zero: a resolver change
#: that hides the routes cannot pass silently.
MIN_PAIRS = 400

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
    """``[(route, method)]`` for every pattern the resolver serves, minus the manifest's skips."""
    pairs = []

    def walk(patterns, prefix):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                route = prefix + str(p.pattern)
                if any(route.startswith(skip) for skip in SKIPS):
                    continue
                view = getattr(p.callback, 'view_class', None)
                methods = ([m for m in ('get',) + WRITE_METHODS
                            if hasattr(view, m) and m in view.http_method_names]
                           if view is not None else ['?'])
                pairs.extend((route, m) for m in methods)

    walk(get_resolver('halatuju.urls').url_patterns, '')
    return pairs


PAIRS = served_pairs()


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
        for flag in entry.get('flags', []):
            assert flag.startswith(('HOLE: ', 'INTENT-UNCLEAR: ')), (route, method, flag)
    for route in SKIPS:
        assert SKIPS[route], f'skip {route} has no reason'
    assert set(INTERNAL_ROUTES) <= {r for r, _ in PAIRS}


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
    if role in entry['allow']:
        assert code not in HIDE, f'{role} is ALLOWED {method.upper()} {route} but got {code}'
    elif role in entry['hide']:
        assert code in HIDE, f'{role} must be refused (404) {method.upper()} {route}, got {code}'
    else:
        assert code in DENY, f'{role} must be DENIED {method.upper()} {route}, got {code}'
