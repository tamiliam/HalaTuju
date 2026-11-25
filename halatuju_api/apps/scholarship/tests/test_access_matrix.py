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


# ── M3c: a team member GRANTED the organisation admin's keys ────────────────────────────────────
#: `access_world` seeds `admin_granted_a`: an `admin` of organisation A given, through the real editor,
#: every key of `ORG_ADMIN_SET` (A9 / A12). It is held to org admin A's answer on every route: it gets
#: through exactly where org admin A does, except the routes below — each one a power that comes with
#: Organisation admin powers (`manage_team`, D4; S2 / M4a: through the key, no longer the role) or a
#: platform-wide power fenced to organisation admins and supers (the sponsor account and the sponsor
#: terms, the M3c fence). The payment seats (E1, by role until M4) never differed at the route: the
#: `admin` preset holds `payments_prepare`; who signs what is `test_m4a_maker_checker`'s.
GRANTED, GRANTED_LIKE = 'admin_granted_a', 'org_admin_a'
GRANTED_DIFFERS = {
    ('api/v1/admin/invite/', 'post'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/admins/<int:admin_id>/', 'delete'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/admins/<int:admin_id>/revoke/', 'patch'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/admins/<int:admin_id>/resend/', 'post'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/admins/<int:admin_id>/role/', 'patch'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/admins/<int:admin_id>/permissions/', 'get'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/admins/<int:admin_id>/permissions/', 'patch'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/reviewers/<int:pk>/pause/', 'post'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/reviewers/<int:pk>/programme/', 'post'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/team/<str:table>/', 'post'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/team/<str:table>/candidates/', 'get'): 'manage_team: team changes stay with the organisation admin (D4)',
    ('api/v1/admin/scholarship/requests/<int:pk>/approve/', 'post'): 'requests.approve: never grantable (O15)',
    ('api/v1/admin/scholarship/requests/<int:pk>/decline/', 'post'): 'requests.approve: never grantable (O15)',
    # NAVKEYS review: acting on the bill is `billing.edit`, never grantable (O15); the reads stay on billing.view.
    ('api/v1/admin/scholarship/billing/invoices/<int:pk>/declaration/<str:action>/', 'post'):
        'billing.edit: never grantable (O15)',
    ('api/v1/admin/scholarship/billing/bill-to/', 'post'): 'billing.edit: never grantable (O15)',
    ('api/v1/admin/sponsors/<int:pk>/review/', 'post'): 'sponsor ACCOUNT vetting reaches every organisation (M3c fence)',
    ('api/v1/admin/scholarship/sponsor-terms/<int:pk>/publish/', 'post'): 'the sponsor terms bind every organisation (M3c fence)',
}


@pytest.mark.django_db
@pytest.mark.parametrize('route,method', [p for p in PAIRS if p[0] not in INTERNAL_ROUTES],
                         ids=lambda v: v if isinstance(v, str) else None)
def test_a_granted_team_member_opens_what_an_org_admin_does(world, route, method):
    def passes(role):
        cache.clear()
        with transaction.atomic():
            code = world.call(role, route, method).status_code
            transaction.set_rollback(True)
        return code not in HIDE
    lead, granted = passes(GRANTED_LIKE), passes(GRANTED)
    differs = (route, method) in GRANTED_DIFFERS
    assert granted == (lead != differs), (
        f'{method.upper()} {route}: org admin A {"passes" if lead else "is refused"}, the granted team member '
        f'{"passes" if granted else "is refused"}' + (f' (listed: {GRANTED_DIFFERS[(route, method)]})'
                                                      if differs else ''))


def test_the_granted_differences_are_still_served():
    assert set(GRANTED_DIFFERS) <= set(PAIRS)


# ── S2 / M4a: Payments by switches, not labels ─────────────────────────────────────────────────────
#: The payment routes, and who passes their gate (`payments.may_read` / `may_prepare`), by KEY: an admin
#: with Approve only and one with View only pass exactly where `finance_a` does (the reads, and the sign
#: route, whose step the chain refuses after the gate); an organisation admin whose Organisation admin
#: powers are off passes none, where org admin A passes them all.
PAYMENT_PAIRS = [p for p in PAIRS if p[0].startswith(('api/v1/admin/scholarship/payment-runs/',
                                                      'api/v1/admin/scholarship/payments/'))]


@pytest.mark.django_db
@pytest.mark.parametrize('route,method', PAYMENT_PAIRS, ids=lambda v: v if isinstance(v, str) else None)
def test_payments_open_by_switch(world, route, method):
    def passes(role):
        cache.clear()
        with transaction.atomic():
            code = world.call(role, route, method).status_code
            transaction.set_rollback(True)
        return code not in HIDE
    finance, lead = passes('finance_a'), passes('org_admin_a')
    assert lead, f'{method.upper()} {route}: org admin A (the powers on) is refused'
    got = {role: passes(role) for role in access_world.PAYMENT_CALLERS}
    assert got == {'payments_holder_a': finance, 'payments_viewer_a': finance, 'oa_unkeyed_a': False}, (
        f'{method.upper()} {route}: finance_a {"passes" if finance else "is refused"}; {got}')


def test_the_payment_routes_are_served():
    assert len(PAYMENT_PAIRS) >= 4, PAYMENT_PAIRS


# ── S3 / M4b: wallet credits by switches, not labels ─────────────────────────────────────────────────
#: The credit routes, and who passes their doors by KEY: Sponsors: edit opens the ledger, record, sign and
#: cancel; Payments Approve (`payments_holder_a`, which reads Sponsors: view through its check) opens the
#: ledger and sign, whose step is the chain's, and never record or cancel (owner Q-A, Q-B).
CREDIT_PAIRS = [p for p in PAIRS if p[0].startswith('api/v1/admin/scholarship/credits/')]
CREDIT_READ_OR_SIGN = {('api/v1/admin/scholarship/credits/', 'get'),
                       ('api/v1/admin/scholarship/credits/<int:pk>/sign/', 'post')}


def _passes(world, role, route, method):
    cache.clear()
    with transaction.atomic():
        code = world.call(role, route, method).status_code
        transaction.set_rollback(True)
    return code not in HIDE


@pytest.mark.django_db
@pytest.mark.parametrize('route,method', CREDIT_PAIRS, ids=lambda v: v if isinstance(v, str) else None)
def test_credits_open_by_switch(world, route, method):
    got = {role: _passes(world, role, route, method)
           for role in (*access_world.CREDIT_CALLERS, 'payments_holder_a')}
    assert got == {'sponsors_editor_a': True,
                   'payments_holder_a': (route, method) in CREDIT_READ_OR_SIGN}, f'{method.upper()} {route}: {got}'


def test_the_credit_routes_are_served():
    assert len(CREDIT_PAIRS) == 4 and CREDIT_READ_OR_SIGN <= set(CREDIT_PAIRS), CREDIT_PAIRS


@pytest.mark.django_db
def test_a_credit_runs_by_switch(world):
    """The maker-checker chain through the HTTP routes, every seat a switch (owner Q-A to Q-C, 23 Nov): the
    Sponsors: edit holder records and signs first; an organisation admin may not record; the check is armed
    (finance A and the Payments Approve holders), so the organisation admin waits; the Payments Approve
    holder checks and may not approve their own check; the organisation admin approves."""
    base = '/api/v1/admin/scholarship/credits/'

    def post(role, url, body):
        cache.clear()
        return world.clients[role].post(url, body, format='json')

    def sign(role, pk):
        return post(role, f'{base}{pk}/sign/', {'typed_name': getattr(world, role).name})

    with transaction.atomic():
        body = access_world.BODIES['api/v1/admin/scholarship/credits/'](world)
        refused = post('org_admin_a', base, body)
        assert (refused.status_code, refused.data['code']) == (400, 'wrong_role')       # Q-A
        made = post('sponsors_editor_a', base, body)
        assert made.status_code == 201, made.data
        pk = made.data['id']
        assert sign('sponsors_editor_a', pk).data['status'] == 'admin_signed'
        assert sign('sponsors_editor_a', pk).data['code'] == 'wrong_role'              # not an approver
        assert sign('org_admin_a', pk).data['code'] == 'finance_check_required'
        assert sign('payments_holder_a', pk).data['status'] == 'finance_checked'
        assert sign('payments_holder_a', pk).data['code'] == 'same_signer'             # Q-C: never twice
        assert sign('org_admin_a', pk).data['status'] == 'confirmed'
        transaction.set_rollback(True)


# ── POST-AWARD-CUT review (18 Nov): the per-case writes in every case stage ───────────────────────────
#: app_a is seeded ACTIVE, so the matrix above proves only the past-the-award stage WITH a scholar file. The
#: manifest's `case_stages` lists the pairs whose callers turn on the stage; each is replayed here with app_a
#: moved to every seed of every stage — OPEN (still assigned to reviewer_a), ENDED BEFORE THE AWARD
#: (`students.approve` holders and supers only, owner 18 Nov) and PAST THE AWARD with no file (awarded with no
#: wallet; closed from awarded and reopened) — after asserting `case_stage` puts the seed in that stage. The
#: two writers without a read (`WRITERS_WITHOUT_A_READ`) are swept too and are allowed nowhere (round 2, H1).
STAGES = MANIFEST['case_stages']
STAGE_NAMES = ('open', 'pre_award_end', 'past_award')
STAGE_PAIRS = [tuple(p.split(' ', 1)) for p in STAGES['pairs']]
#: A seed before the award is a case that never reached it: the active app_a's award stamps are cleared.
NEVER_AWARDED = {'awarded_at': None, 'active_at': None, 'vircle_activated_at': None}


def test_the_case_stage_pairs_are_served_entries():
    for method, route in STAGE_PAIRS:
        assert (route, method.lower()) in ENTRIES, f'case_stages names {method} {route}, which has no entry'
    for stage in STAGE_NAMES:
        assert set(STAGES[stage]['except']) <= set(STAGES['pairs']), stage
    assert set(STAGES['ai_off']) <= set(STAGES['pairs'])


def _seed_fields(stage, seed):
    from django.utils import timezone
    fields = dict(NEVER_AWARDED, decision_reopened_at=None, pre_decline_status='') \
        if stage != 'past_award' else {'decision_reopened_at': None}
    fields.update({k: timezone.now() if v == 'now' else v for k, v in seed.items() if k != 'state'})
    return fields


@pytest.mark.django_db
@pytest.mark.parametrize('stage', STAGE_NAMES)
@pytest.mark.parametrize('method,route', STAGE_PAIRS, ids=lambda v: v)
def test_a_case_stage_decides_who_writes(world, stage, method, route):
    from apps.scholarship.models import ScholarshipApplication
    from apps.scholarship.staff_lifecycle import case_stage
    spec = STAGES[stage]
    allow = set(spec['except'].get(f'{method} {route}', spec)['allow'])
    ai_off = f'{method} {route}' in STAGES['ai_off']
    wrong = []
    for seed in spec['seeds']:
        if f'{method} {route}' in seed.get('state', {}):
            continue
        for role in roles_for(route) + access_world.WRITERS_WITHOUT_A_READ:
            cache.clear()
            with transaction.atomic():
                ScholarshipApplication.objects.filter(pk=world.app_a.pk).update(**_seed_fields(stage, seed))
                seen = case_stage(ScholarshipApplication.objects.get(pk=world.app_a.pk))
                assert seen == stage, f'seed {seed} is {seen}, not {stage}'
                code = world.call(role, route, method.lower()).status_code
                transaction.set_rollback(True)
            # A crash is wrong, unless the AI (off in tests) answers it: 503 for a caller let through.
            broke = code in BROKEN or (code >= 500 and not (ai_off and code == 503))
            if (role in allow) == (code in HIDE) or broke:
                wrong.append(f'{seed["status"]} {role}: {code}')
    assert not wrong, f'{stage} {method} {route}: allowed {sorted(allow)}, but ' + ', '.join(wrong)


# ── S4 (owner Q3, Q-B, Q-E, 25 Nov): a scholar's file by switches, not labels ───────────────────────────
#: Reading a file is View scholars (`scholars`); every change to it is Manage scholar files (`scholars.approve`).
#: app_a is ACTIVE with a file, so every scholars/ POST and the past-award case writes below are file writes.
SCHOLARS_ROUTES = 'api/v1/admin/scholarship/scholars/'
SCHOLAR_CASE_WRITES = {(f'api/v1/admin/scholarship/applications/<int:pk>/{tail}', 'post')
                       for tail in ('reporting-date/', 'maintenance/', 'close/', 'cancel-decline/')}
SCHOLAR_WRITE_PAIRS = sorted({p for p in PAIRS if p[0].startswith(SCHOLARS_ROUTES) and p[1] != 'get'
                              and '/mentoring/' not in p[0]} | SCHOLAR_CASE_WRITES)
SCHOLAR_READ_PAIRS = sorted({(f'{SCHOLARS_ROUTES}<int:pk>/{tail}', 'get')
                             for tail in ('', 'results/', 'letters/', 'activity/')} & set(PAIRS))


@pytest.mark.django_db
@pytest.mark.parametrize('route,method', SCHOLAR_WRITE_PAIRS, ids=lambda v: v if isinstance(v, str) else None)
def test_scholar_files_open_by_switch(world, route, method):
    """Manage scholar files writes, as org admin A does; View scholars alone, and a member newly invited to
    Admins (the admin preset only: View on, Manage off, owner Q-E), are refused."""
    got = {role: _passes(world, role, route, method)
           for role in ('org_admin_a', 'admin_a', 'scholars_manager_a', 'scholars_viewer_a', 'admin_invited_a')}
    assert got == {'org_admin_a': True, 'admin_a': True, 'scholars_manager_a': True,
                   'scholars_viewer_a': False, 'admin_invited_a': False}, f'{method.upper()} {route}: {got}'


@pytest.mark.django_db
@pytest.mark.parametrize('route,method', SCHOLAR_READ_PAIRS, ids=lambda v: v if isinstance(v, str) else None)
def test_scholar_files_read_by_view(world, route, method):
    got = {role: _passes(world, role, route, method) for role in (*access_world.SCHOLAR_CALLERS, 'manage_only_a')}
    assert all(got.values()), f'{method.upper()} {route}: View scholars (or Manage, which brings it) reads; {got}'


def test_the_scholar_routes_are_served():
    assert len(SCHOLAR_WRITE_PAIRS) >= 8 and SCHOLAR_CASE_WRITES <= set(PAIRS), SCHOLAR_WRITE_PAIRS
    assert len(SCHOLAR_READ_PAIRS) >= 3, SCHOLAR_READ_PAIRS


#: Where the newly invited member (admin preset only, owner Q-E) and `admin_a` (the preset after 0101) differ:
#: every past-award write on app_a's case and file, and nothing else (every read the same; money per Q-B).
INVITED, INVITED_LIKE = 'admin_invited_a', 'admin_a'
_PAST_AWARD_WRITES = {*SCHOLAR_WRITE_PAIRS, *(
    (f'api/v1/admin/scholarship/applications/<int:pk>/{tail}', method) for tail, method in (
        ('', 'patch'), ('hold-award/', 'post'), ('finalise-profile/', 'post'), ('verify-accept/', 'post'),
        ('suggest-gaps/', 'post'), ('interview-slots/', 'post'), ('reject/', 'post'), ('profile/', 'put'),
        ('request-info/', 'post'), ('publish/', 'post'), ('referees/', 'post'), ('anon-profile/publish/', 'post'),
        ('referees/<int:ref_id>/', 'delete'), ('resolution-items/', 'post'),
        ('documents/<int:doc_id>/re-run-vision/', 'post'), ('generate-profile/', 'post'), ('interview/', 'post'),
        ('record-verdict/', 'post'), ('interview/submit/', 'post'), ('interview/reopen/', 'post'),
        ('submit-decline/', 'post'))),
    ('api/v1/admin/scholarship/resolution-items/<int:item_id>/<str:action>/', 'post')}
INVITED_DIFFERS = {**{p: 'a past-award write on the scholar file or case: Manage scholar files'
                      for p in _PAST_AWARD_WRITES},
                   ('api/v1/admin/scholarship/withdrawal-requests/<int:pk>/cancel/', 'post'):
                       'only the maker cancels a withdrawal request (the seeded one is admin_a\'s)'}


@pytest.mark.django_db
@pytest.mark.parametrize('route,method', [p for p in PAIRS if p[0] not in INTERNAL_ROUTES],
                         ids=lambda v: v if isinstance(v, str) else None)
def test_a_newly_invited_admin_reads_and_never_changes_a_scholar_file(world, route, method):
    lead, invited = _passes(world, INVITED_LIKE, route, method), _passes(world, INVITED, route, method)
    differs = (route, method) in INVITED_DIFFERS
    assert invited == (lead and not differs), (
        f'{method.upper()} {route}: admin_a {"passes" if lead else "is refused"}, the newly invited member '
        f'{"passes" if invited else "is refused"}' + (f' (listed: {INVITED_DIFFERS[(route, method)]})'
                                                      if differs else ''))


def test_the_invited_differences_are_still_served():
    assert set(INVITED_DIFFERS) <= set(PAIRS), sorted(set(INVITED_DIFFERS) - set(PAIRS))


@pytest.mark.django_db
def test_money_on_a_scholar_file_is_view_plus_prepare(world):
    """Owner Q-B: a tranche, release, withhold, return or hold past the award = View scholars + Payments:
    Prepare; Manage scholar files is never a second key to money (and never enough without Prepare)."""
    routes = [('api/v1/admin/scholarship/applications/<int:pk>/disbursements/', 'post'),
              ('api/v1/admin/scholarship/disbursements/<int:pk>/<str:action>/', 'post')]
    got = {role: [_passes(world, role, r, m) for r, m in routes]
           for role in ('admin_invited_a', 'scholars_viewer_a', 'scholars_manager_a', 'payments_holder_a')}
    assert got == {'admin_invited_a': [True, True], 'scholars_viewer_a': [False, False],
                   'scholars_manager_a': [False, False], 'payments_holder_a': [False, False]}, got
    url = f'/api/v1/admin/scholarship/applications/{world.app_a.pk}/maintenance/'
    hold = {}
    for role in ('admin_invited_a', 'scholars_viewer_a', 'scholars_manager_a'):
        cache.clear()
        with transaction.atomic():
            hold[role] = world.clients[role].post(url, {'substate': 'on_hold'}, format='json').status_code
            transaction.set_rollback(True)
    assert hold['admin_invited_a'] not in HIDE and hold['scholars_viewer_a'] in HIDE \
        and hold['scholars_manager_a'] in HIDE, hold


@pytest.mark.django_db
def test_manage_alone_reads_a_scholar_file(world):
    """Manage scholar files brings View scholars on the server too (`holds_scholars_key` reads the v2 view)."""
    assert _passes(world, 'manage_only_a', 'api/v1/admin/scholarship/scholars/<int:pk>/', 'get')
