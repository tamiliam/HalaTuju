"""Sprint M1a (2026-11-10): a `member` ("No group") opens SIX views and nothing else.

Brief `docs/plans/2026-11-10-m1-staff-list-brief.md` §2 items 3-10 and §12 item 1. The mechanism is the
deny-by-default gate `PartnerAdminMixin.get_admin`: a member is refused on every view that has not opted
in through `member_methods`. The sweep below reads EVERY `api/v1/admin/` route off the live resolver (the
source-user sweep's walker), so a route added tomorrow is swept the day it lands.

The member here is the most entitled shape a member can be: in an organisation with applications, a
scholar and staff, keeping a (deactivated) mentor link — the neighbouring states (suspended, no link,
another organisation) are below.
"""
import re

from django.test import TestCase, override_settings
from django.urls import get_resolver
from django.utils import timezone

from apps.courses import staff_permissions, staff_tables
from apps.courses.models import PartnerAdmin
from apps.scholarship import staff_tables_admin as sta
from apps.scholarship.models import Mentor
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)
from apps.scholarship.tests.test_source_user_denied_everywhere import (
    DARK_FLAGS_ON, MIN_ROUTES, REFUSED, admin_routes, methods_of,
)

#: The six views (brief §2 "What a member may open"), by class, with the methods each opts in.
MEMBER_VIEWS = {
    'AdminMeView': ('get', 'patch'),
    'AdminMePhotoView': ('post', 'delete'),
    'AdminMeActivityView': ('get',),
    'AdminMePasswordView': ('post',),
    'AdminRoleView': ('get',),
    'AdminSetPasswordView': ('post',),
}

#: (route, method) a member is served 200 by: its OWN account only.
ALLOWED = {
    ('api/v1/admin/role/', 'get'),
    ('api/v1/admin/me/', 'get'),
    ('api/v1/admin/me/', 'patch'),          # the sweep's empty body writes nothing
    ('api/v1/admin/me/activity/', 'get'),
    ('api/v1/admin/me/photo/', 'delete'),   # no photo: nothing removed
}

#: Reached with the sweep's empty body, refusing it on its own terms (as for a source user).
REACHED = {
    ('api/v1/admin/set-password/', 'post'): 400,
    ('api/v1/admin/me/password/', 'post'): 400,
    ('api/v1/admin/me/photo/', 'post'): 415,
}


def _member(org, *, link=True, **kw):
    mentor = Mentor.objects.create(organisation=org, deactivated_at=timezone.now()) if link else None
    return make_admin('member', owning_org=org, mentor=mentor, first_seen_at=timezone.now(), **kw)


class MemberOptInListTest(TestCase):
    def test_exactly_six_views_opt_a_member_in(self):
        found = {}

        def walk(patterns):
            for p in patterns:
                if hasattr(p, 'url_patterns'):
                    walk(p.url_patterns)
                    continue
                cls = getattr(p.callback, 'view_class', None)
                methods = tuple(getattr(cls, 'member_methods', ()) or ())
                if cls is not None and methods:
                    found[cls.__name__] = methods
        walk(get_resolver('halatuju.urls').url_patterns)
        self.assertEqual(found, MEMBER_VIEWS)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, **DARK_FLAGS_ON)
class MemberIsDeniedEveryOtherAdminRouteTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.gift = make_programme(organisation=cls.org)
        cohort = make_cohort(programme=cls.gift)
        cls.app = make_application('submitted', cohort=cohort)
        cls.scholar = make_application('active', cohort=cohort)
        cls.staff = make_admin('org_admin', owning_org=cls.org)
        cls.user = _member(cls.org)

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

    def test_no_admin_route_serves_a_member_except_the_six(self):
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
                resp = client.generic(method.upper(), url, data='{}', content_type='application/json')
                if (route, method) in ALLOWED:
                    if resp.status_code != 200:
                        leaks.append(f'{method.upper()} {url} -> {resp.status_code} (allowed, expected 200)')
                elif (route, method) in REACHED:
                    if resp.status_code != REACHED[(route, method)]:
                        leaks.append(f'{method.upper()} {url} -> {resp.status_code} '
                                     f'(reached, expected {REACHED[(route, method)]})')
                elif resp.status_code not in REFUSED:
                    leaks.append(f'{method.upper()} {url} -> {resp.status_code}')
        self.assertEqual(leaks, [], 'a member reached an admin route:\n' + '\n'.join(leaks))
        self.assertEqual((ALLOWED | set(REACHED)) - seen, set())

    def test_role_answers_no_tables_no_keys_no_mentoring(self):
        role = authed_client(self.user).get('/api/v1/admin/role/').json()
        self.assertEqual((role['is_admin'], role['role']), (True, 'member'))
        self.assertEqual((role['tables'], role['permissions'], role['page_keys'], role['mentoring']),
                         ([], [], [], False))

    def test_the_model_answers_hold_no_key(self):
        self.assertEqual(staff_permissions.resolve(self.user), ())
        self.assertEqual(staff_permissions.preset_for('member'), ())
        self.assertEqual(staff_tables.tables(self.user), ())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class MemberNeighbouringStatesTest(TestCase):
    def setUp(self):
        self.org = make_org()
        self.lead = make_admin('org_admin', owning_org=self.org)

    def test_a_suspended_member_is_not_an_admin_at_all(self):
        user = _member(self.org, is_active=False)
        self.assertFalse(authed_client(user).get('/api/v1/admin/role/').json()['is_admin'])

    def test_a_member_without_a_link_opens_its_profile(self):
        user = _member(self.org, link=False)
        client = authed_client(user)
        self.assertEqual(client.get('/api/v1/admin/me/').status_code, 200)
        self.assertEqual(client.get('/api/v1/admin/scholarship/applications/').status_code, 403)

    def test_another_organisations_member_is_not_the_lead_s_to_touch(self):
        other = _member(make_org())
        client = authed_client(self.lead)
        self.assertEqual(client.get(f'/api/v1/admin/admins/{other.pk}/permissions/').status_code, 404)
        resp = client.post('/api/v1/admin/team/admins/', {'admin_id': other.pk, 'action': 'add'},
                           format='json')
        self.assertEqual(resp.status_code, 404)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class MemberDoorsTest(TestCase):
    """§2 item 7, 9, 10: a member joins a group with that group's preset; Change role refuses it; the
    person page reads it but offers no editor."""

    def setUp(self):
        self.org = make_org()
        self.lead = make_admin('org_admin', owning_org=self.org)

    def test_add_to_admins_gives_the_admin_preset(self):
        user = _member(self.org)
        target, plan = sta.change(user.pk, sta.ADMINS, 'add', by=self.lead)
        target.refresh_from_db()
        self.assertEqual((target.role, target.permissions), ('admin', None))
        self.assertEqual(list(staff_permissions.resolve(target)), list(staff_permissions.preset_for('admin')))
        self.assertEqual(staff_tables.tables(target), ('admins',))
        self.assertFalse(target.mentors_now)   # the kept link stays deactivated

    def test_add_to_reviewers_gives_the_reviewer_preset(self):
        user = _member(self.org, link=False)
        target, _ = sta.change(user.pk, sta.REVIEWERS, 'add', by=self.lead)
        target.refresh_from_db()
        self.assertEqual((target.role, target.permissions), ('reviewer', None))
        self.assertEqual(staff_tables.tables(target), ('reviewers',))

    def test_the_add_sheet_offers_a_member(self):
        user = _member(self.org)
        for table in sta.TABLES:
            with self.subTest(table=table):
                offered = [a.pk for a, _ in sta.candidates(self.lead, table, self.org.pk)]
                self.assertIn(user.pk, offered)
        self.assertEqual(sta.addable_tables(self.lead, user), [sta.ADMINS, sta.REVIEWERS])

    def test_a_suspended_member_is_not_offered(self):
        user = _member(self.org, is_active=False)
        offered = [a.pk for a, _ in sta.candidates(self.lead, sta.ADMINS, self.org.pk)]
        self.assertNotIn(user.pk, offered)

    def test_change_role_refuses_a_member_both_ways(self):
        user = _member(self.org)
        admin = make_admin('admin', owning_org=self.org)
        client = authed_client(self.lead)
        for target, new_role in ((user, 'admin'), (admin, 'member')):
            with self.subTest(target=target.role, new_role=new_role):
                resp = client.patch(f'/api/v1/admin/admins/{target.pk}/role/', {'role': new_role},
                                    format='json')
                self.assertEqual((resp.status_code, resp.json()['code']), (400, 'not_eligible'))
        self.assertEqual(PartnerAdmin.objects.get(pk=admin.pk).role, 'admin')

    def test_the_person_page_reads_a_member_but_offers_no_editor(self):
        user = _member(self.org)
        body = authed_client(self.lead).get(f'/api/v1/admin/admins/{user.pk}/permissions/').json()
        self.assertEqual((body['role'], body['editable'], body['tables'], body['permissions']),
                         ('member', False, [], []))
