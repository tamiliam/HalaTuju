"""Student maintenance S7a (2026-10-31) — a MENTOR is DENIED BY DEFAULT, proven against every admin route.

The source user's sweep (`test_source_user_denied_everywhere.py`), for the mentor role: a mentor login
is planted in an organisation with applications, a scholar, a gift, a source, staff and other mentors
— the most a mentor could ever be near. Every `api/v1/admin/` route the project serves is then called
with every method its view implements, and nothing may answer 2xx except the short `ALLOWED` list.

⚠ THE ROUTES ARE READ FROM THE URL RESOLVER, never listed by hand, so a route added tomorrow is swept
the day it lands; a floor stops the sweep passing because it found nothing.

⚠ THE MECHANISM IS ONE GATE, `PartnerAdminMixin.get_admin`, which answers None to a mentor on any view
that has not opted in (`mentor_methods`). A view that resolves its caller some other way shows up here
as a 2xx. The dark-shipped flags are switched ON so a flag's 404 cannot hide a leak behind it.
"""
from django.test import TestCase, override_settings

from apps.scholarship.models import Mentor, ProgrammeReferralSource
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_source,
)
from apps.scholarship.tests import test_source_user_denied_everywhere as source_sweep
from apps.scholarship.tests.test_source_user_denied_everywhere import (
    DARK_FLAGS_ON, MIN_ROUTES, REFUSED, admin_routes, methods_of,
)

#: (route, method) pairs a mentor may receive data from in S7a. Each is about the caller's OWN
#: account: the sign-in record, the common Profile page (`admin/me/`), the reviewer cards a mentor also
#: fills in (`admin/reviewer-profile/`), and removing its own photo (none here, so nothing to remove).
ALLOWED = {
    ('api/v1/admin/role/', 'get'),
    ('api/v1/admin/me/', 'get'),
    ('api/v1/admin/me/', 'patch'),
    ('api/v1/admin/me/photo/', 'delete'),
    ('api/v1/admin/reviewer-profile/', 'get'),
    ('api/v1/admin/reviewer-profile/', 'patch'),
}

#: (route, method) pairs a mentor's call REACHES, which serve no data. With the sweep's empty body:
#: set-password 400 `password_too_short` (only ever the CALLER'S own password, while a temporary one is
#: owed — a temp-password mentor needs it); the own password change 400 `current_password_required`;
#: the photo upload 415 (multipart only).
REACHED = {
    ('api/v1/admin/set-password/', 'post'): 400,
    ('api/v1/admin/me/password/', 'post'): 400,
    ('api/v1/admin/me/photo/', 'post'): 415,
}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   **DARK_FLAGS_ON)
class TestMentorIsDeniedEveryAdminRoute(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.gift = make_programme(organisation=cls.org)
        cohort = make_cohort(programme=cls.gift)
        source = make_source(organisation=cls.org)
        ProgrammeReferralSource.objects.create(programme=cls.gift, source=source)
        cls.app = make_application('submitted', cohort=cohort, source=source)
        cls.scholar = make_application('active', cohort=cohort, source=source)
        cls.staff = make_admin('org_admin', owning_org=cls.org)
        cls.colleague = make_admin('mentor', owning_org=cls.org)
        cls.user = make_admin('mentor', owning_org=cls.org)

    # The source sweep's URL filler (the module, never the class: an imported TestCase runs twice).
    _url = source_sweep.TestSourceUserIsDeniedEveryAdminRoute._url

    def test_no_admin_route_serves_a_mentor(self):
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
                elif (route, method) in REACHED:
                    if resp.status_code != REACHED[(route, method)]:
                        leaks.append(f'{method.upper()} {url} -> {resp.status_code} (reached, '
                                     f'expected {REACHED[(route, method)]})')
                elif resp.status_code not in REFUSED:
                    leaks.append(f'{method.upper()} {url} -> {resp.status_code}')
        self.assertEqual(leaks, [], 'a mentor reached an admin route:\n' + '\n'.join(leaks))
        # Every allowed pair really exists, so the list cannot rot into naming nothing.
        self.assertEqual((ALLOWED | set(REACHED)) - seen, set())

    def test_the_allowed_routes_serve_only_the_callers_own_things(self):
        client = authed_client(self.user)
        role = client.get('/api/v1/admin/role/').json()
        self.assertEqual((role['role'], role['permissions'], role['source_id']), ('mentor', [], None))
        me = client.get('/api/v1/admin/me/').json()
        self.assertEqual((me['id'], me['role'], me['permissions'], me['programmes'], me['source']),
                         (self.user.pk, 'mentor', [], [], None))
        self.assertEqual(me['mentoring_area'], '')
        profile = client.get('/api/v1/admin/reviewer-profile/')
        self.assertEqual(profile.status_code, 200)
        self.assertNotIn('partner_admin', profile.json())

    def test_the_mentors_page_and_the_invite_are_refused(self):
        client = authed_client(self.user)
        self.assertEqual(client.get('/api/v1/admin/mentors/').status_code, 403)
        made = client.post('/api/v1/admin/invitations/',
                           {'audience': 'mentor', 'name': 'X', 'email': 'x@example.test'},
                           format='json')
        self.assertEqual(made.status_code, 403)
        self.assertEqual(Mentor.objects.count(), 2)
