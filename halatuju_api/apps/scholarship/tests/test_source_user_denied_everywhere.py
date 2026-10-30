"""Source sign-in S1 (2026-10-30) — DENY BY DEFAULT, proven against every admin route.

A source user (`PartnerAdmin.role='source_partner'`) is planted in an organisation that has
applications naming its source, a scholar, a gift linked to the source and staff: the most a source
could ever be entitled to. Every `api/v1/admin/` route the project serves is then called with every
method its view implements, and nothing may answer 2xx except the short `ALLOWED` list.

⚠ THE ROUTES ARE READ FROM THE URL RESOLVER, never listed by hand, so a route added tomorrow is
swept the day it lands, and a floor stops the sweep from passing because it found nothing.

⚠ THE MECHANISM IS ONE GATE, `PartnerAdminMixin.get_admin`, which answers None to a source user on
any view that has not opted in (`source_partner_methods`). Before it, a source user — who must carry
its source's organisation as `owning_organisation` — would have passed every view that checks only
"is an admin, inside the org fence" (the assignable-staff list was one). This test is what keeps
the gate honest: a view that resolves its caller some other way shows up here as a 2xx.

The dark-shipped flags are switched ON so a flag's 404 cannot hide a leak behind it.
"""
import re

from django.test import TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver
from django.urls.resolvers import RoutePattern

from apps.scholarship.models import ProgrammeReferralSource
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_source,
)

#: (route, method) pairs a source user may receive data from in S1. Each is about the caller's
#: OWN account, or is the source's own scope list; see `test_the_allowed_routes_serve_only_the_
#: callers_own_things` for what each one returns.
ALLOWED = {
    ('api/v1/admin/role/', 'get'),
    ('api/v1/admin/scholarship/scopes/', 'get'),
    ('api/v1/admin/profile/', 'get'),
}

#: What a refused call may answer: not an admin (403), not found / dark (404), or a method the view
#: does not take (405). A 400 or a 500 would mean the view ran past its gate, so neither is here.
REFUSED = {403, 404, 405}

WRITE_METHODS = ('post', 'put', 'patch', 'delete')

#: The project serves ~190 admin routes (2026-10-30). Well under that, so a new route never fails
#: it, and far above zero, so a resolver change that hides the routes cannot pass silently.
MIN_ROUTES = 150

DARK_FLAGS_ON = dict(
    BURSARY_AGREEMENT_ENABLED=True, BILLING_USAGE_ENABLED=True, REQUESTS_ENABLED=True,
    SPONSOR_POOL_ENABLED=True, SPONSOR_TERMS_ENABLED=True, INTERVIEW_SCHEDULING_ENABLED=True,
    PARTNER_COMMS_ENABLED=True, SPONSOR_COMMS_ENABLED=True,
)


def admin_routes():
    """``[(route, URLPattern)]`` for every `api/v1/admin/` route, walked off the live resolver."""
    found, other = [], []

    def walk(patterns, prefix):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                route = prefix + str(p.pattern)
                if not route.startswith('api/v1/admin/'):
                    continue
                (found if isinstance(p.pattern, RoutePattern) else other).append((route, p))

    walk(get_resolver('halatuju.urls').url_patterns, '')
    assert not other, f'a regex admin route the sweep cannot fill: {[r for r, _ in other]}'
    return found


def methods_of(pattern):
    """The HTTP methods the route's view implements (GET always tried)."""
    view = getattr(pattern.callback, 'view_class', None)
    if view is None:
        return ['get', 'post']
    return ['get'] + [m for m in WRITE_METHODS if hasattr(view, m)]


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   **DARK_FLAGS_ON)
class TestSourceUserIsDeniedEveryAdminRoute(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.gift = make_programme(organisation=cls.org)
        cohort = make_cohort(programme=cls.gift)
        cls.source = make_source(organisation=cls.org)
        ProgrammeReferralSource.objects.create(programme=cls.gift, source=cls.source)
        cls.app = make_application('submitted', cohort=cohort, source=cls.source)
        cls.scholar = make_application('active', cohort=cohort, source=cls.source)
        cls.staff = make_admin('org_admin', owning_org=cls.org)
        cls.user = make_admin('source_partner', owning_org=cls.org, source=cls.source)

    def _url(self, route):
        ids = {'pk': self.app.pk, 'admin_id': self.staff.pk, 'org_id': self.org.pk,
               'user_id': self.app.profile.supabase_user_id, 'kind': 'weekly_summary',
               'action': 'approve'}

        def one(m):
            conv, name = m.group(1) or 'str', m.group(2)
            if name in ids:
                return str(ids[name])
            return str(self.app.pk) if conv == 'int' else 'x'
        return '/' + re.sub(r'<(?:(\w+):)?(\w+)>', one, route)

    def test_no_admin_route_serves_a_source_user(self):
        routes = admin_routes()
        self.assertGreaterEqual(len(routes), MIN_ROUTES)
        client = authed_client(self.user)
        leaks, seen = [], set()
        for route, pattern in routes:
            url = self._url(route)
            for method in methods_of(pattern):
                if (route, method) in seen:
                    continue
                seen.add((route, method))
                resp = client.generic(method.upper(), url, data='{}',
                                      content_type='application/json')
                if (route, method) in ALLOWED:
                    if resp.status_code != 200:
                        leaks.append(f'{method.upper()} {url} -> {resp.status_code} (allowed, '
                                     f'expected 200)')
                elif resp.status_code not in REFUSED:
                    leaks.append(f'{method.upper()} {url} -> {resp.status_code}')
        self.assertEqual(leaks, [], 'a source user reached an admin route:\n' + '\n'.join(leaks))
        # Every allowed pair really exists, so the list cannot rot into naming nothing.
        self.assertEqual(ALLOWED - seen, set())

    def test_the_allowed_routes_serve_only_the_callers_own_things(self):
        client = authed_client(self.user)
        role = client.get('/api/v1/admin/role/').json()
        self.assertEqual((role['role'], role['source_id'], role['source_name']),
                         ('source_partner', self.source.pk, self.source.name))
        self.assertEqual(role['permissions'], [])
        profile = client.get('/api/v1/admin/profile/').json()
        self.assertEqual((profile['id'], profile['email']), (self.user.pk, self.user.email))
        scopes = client.get('/api/v1/admin/scholarship/scopes/').json()
        self.assertEqual([o['id'] for o in scopes['organisations']], [self.org.pk])
        self.assertEqual([p['id'] for p in scopes['programmes']], [self.gift.pk])

    def test_the_profile_write_is_refused(self):
        resp = authed_client(self.user).put('/api/v1/admin/profile/', {'name': 'Renamed'},
                                            format='json')
        self.assertEqual(resp.status_code, 403)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.name, 'Renamed')
