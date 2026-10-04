"""TD-228 (2026-10-05): the ORGANISATION crumb narrows the Requests list.

`GET admin/scholarship/requests/?org=<code>` narrows INSIDE the fence (`_AdminBase._org_narrowing`,
the sibling of the gift narrowing): a super names any organisation and sees only its requests; an
organisation admin may name only their own (a no-op) and any other code — or an unknown one — is
404, never 403, so it cannot confirm that organisation exists. Absent, nothing changes.
Sponsors and Sources are still TD-228's open half.
"""
from django.test import TestCase, override_settings

from apps.scholarship.models import OrgRequest
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org,
)

URL = '/api/v1/admin/scholarship/requests/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True)
class TestTheOrganisationCrumbNarrowsRequests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.orgs, cls.admins = {}, {}
        for tag in ('a', 'b'):
            org = make_org(code=f'td228-{tag}')
            oa = make_admin('org_admin', owning_org=org)
            OrgRequest.objects.create(organisation=org, submitted_by=oa, kind='feature',
                                      title=f'Request {tag}', description='a page')
            cls.orgs[tag], cls.admins[tag] = org, oa
        cls.super = make_admin('super', super_admin=True)

    def _titles(self, who, q=''):
        r = authed_client(who).get(f'{URL}{q}')
        self.assertEqual(r.status_code, 200, r.content[:200])
        return sorted(x['title'] for x in r.json()['requests'])

    def test_a_super_naming_an_organisation_sees_only_its_requests(self):
        self.assertEqual(self._titles(self.super, '?org=td228-a'), ['Request a'])
        self.assertEqual(self._titles(self.super, '?org=td228-b'), ['Request b'])

    def test_absent_it_is_exactly_what_the_fence_allows(self):
        self.assertEqual(self._titles(self.super), ['Request a', 'Request b'])
        self.assertEqual(self._titles(self.admins['a']), ['Request a'])

    def test_an_org_admin_naming_their_own_organisation_is_a_no_op(self):
        self.assertEqual(self._titles(self.admins['a'], '?org=td228-a'), ['Request a'])

    def test_an_org_admin_naming_another_organisation_is_404_never_403(self):
        r = authed_client(self.admins['a']).get(f'{URL}?org=td228-b')
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('Request b', r.content.decode())

    def test_an_unknown_code_is_the_same_404_for_everyone(self):
        for who in (self.super, self.admins['a']):
            with self.subTest(who=who.role):
                self.assertEqual(authed_client(who).get(f'{URL}?org=no-such-org').status_code, 404)

    def test_an_org_admin_with_no_organisation_cannot_name_one(self):
        orphan = make_admin('org_admin')
        self.assertEqual(authed_client(orphan).get(f'{URL}?org=td228-a').status_code, 404)

    def test_dark_the_route_is_404_before_the_crumb_is_read(self):
        with self.settings(REQUESTS_ENABLED=False):
            self.assertEqual(authed_client(self.super).get(f'{URL}?org=td228-a').status_code, 404)
