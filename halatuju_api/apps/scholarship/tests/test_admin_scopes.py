"""N3a — the scopes endpoint behind the breadcrumb switchers.

⚠ What these tests are NOT proving: access. `AdminScopeListView` answers "what may I LOOK AT",
and its answer is derived from the same `owning_organisation` the org fence uses, so it cannot
widen anything — a client ignoring it entirely reaches exactly the same data. The fence itself is
`_org_scoped` / `_org_allows` and is proven in `test_org_fence.py`.

What they DO pin is that the list a person is offered matches the data they can reach. A switcher
offering a tenant you cannot open is a bug report waiting to happen, and one offering a REFERRAL
organisation would say that a school is an access scope — which is the confusion the 2026-07-15
surface-partition sprint exists to have corrected.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.models import Programme
from apps.scholarship.tests.test_api import TEST_JWT_SECRET, _make_token

URL = '/api/v1/admin/scholarship/scopes/'


def _org(code, active=True):
    return PartnerOrganisation.objects.create(code=code, name=code.title(), is_active=active)


def _programme(org, code, active=True, **names):
    return Programme.objects.create(
        organisation=org, code=code, name_en=names.get('en', code.title()),
        name_ms=names.get('ms', ''), name_ta=names.get('ta', ''), is_active=active,
    )


def _admin(uid, org=None, role='org_admin', super_=False):
    return PartnerAdmin.objects.create(
        supabase_user_id=uid, email=f'{uid}@example.com', name=uid,
        role=role, is_super_admin=super_, is_active=True, owning_organisation=org,
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestScopeList(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org_a = _org('tenant-a')
        self.org_b = _org('tenant-b')
        self.prog_a = _programme(self.org_a, 'a-bursary', en='A Bursary', ms='Biasiswa A')
        self.prog_b = _programme(self.org_b, 'b-bursary', en='B Bursary')

    def _as(self, admin, query=''):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_make_token(admin.supabase_user_id)}')
        return self.client.get(URL + query)

    def test_super_sees_every_organisation_and_programme(self):
        resp = self._as(_admin('super-1', role='super', super_=True))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Subset, not an exact set: migration 0098 seeds BrightPath into every test database, so
        # asserting "exactly these two" would be asserting a fixture rather than the behaviour.
        codes = [o['code'] for o in body['organisations']]
        self.assertIn('tenant-a', codes)
        self.assertIn('tenant-b', codes)
        prog_codes = [p['code'] for p in body['programmes']]
        self.assertIn('a-bursary', prog_codes)
        self.assertIn('b-bursary', prog_codes)

    def test_an_org_admin_sees_only_their_own(self):
        body = self._as(_admin('org-a', org=self.org_a)).json()
        self.assertEqual([o['code'] for o in body['organisations']], ['tenant-a'])
        self.assertEqual([p['code'] for p in body['programmes']], ['a-bursary'])

    def test_a_partner_gets_nothing_because_a_referral_org_is_not_a_scope(self):
        """`PartnerAdmin.org` / `referred_by_org` mean the REFERRING organisation — attribution,
        never access. Offering a school a scope switcher would assert otherwise."""
        body = self._as(_admin('partner-1', org=self.org_a, role='partner')).json()
        self.assertEqual(body, {'organisations': [], 'programmes': []})

    def test_an_admin_with_no_organisation_gets_empty_lists_not_a_500(self):
        """A reviewer with NULL owning_organisation is a real row in production."""
        resp = self._as(_admin('no-org', org=None, role='reviewer'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'organisations': [], 'programmes': []})

    def test_an_inactive_programme_is_not_offered(self):
        _programme(self.org_a, 'a-retired', active=False)
        body = self._as(_admin('org-a2', org=self.org_a)).json()
        self.assertEqual([p['code'] for p in body['programmes']], ['a-bursary'])

    def test_an_inactive_organisation_is_not_offered(self):
        _org('gone', active=False)
        body = self._as(_admin('super-2', role='super', super_=True)).json()
        self.assertNotIn('gone', [o['code'] for o in body['organisations']])

    def test_a_programme_carries_its_organisation_so_the_switcher_can_pair_them(self):
        body = self._as(_admin('super-3', role='super', super_=True)).json()
        by_code = {p['code']: p for p in body['programmes']}
        self.assertEqual(by_code['a-bursary']['organisation_id'], self.org_a.id)

    def test_the_code_is_the_one_PF1_settled_on(self):
        """`Programme.code` is what /scholarship/apply?p=<code> uses. One vocabulary for
        'which programme', not two."""
        body = self._as(_admin('super-4', role='super', super_=True)).json()
        self.assertIn('a-bursary', [p['code'] for p in body['programmes']])

    def test_names_resolve_per_language_with_an_en_fallback(self):
        admin = _admin('org-a3', org=self.org_a)
        self.assertEqual(self._as(admin, '?lang=ms').json()['programmes'][0]['name'], 'Biasiswa A')
        # ta is blank on this programme → falls back to en rather than rendering empty
        self.assertEqual(self._as(admin, '?lang=ta').json()['programmes'][0]['name'], 'A Bursary')
        self.assertEqual(self._as(admin, '?lang=zz').json()['programmes'][0]['name'], 'A Bursary')

    def test_it_refuses_a_caller_who_is_not_an_admin_at_all(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_make_token("not-an-admin")}')
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_the_offered_list_matches_what_the_fence_would_allow(self):
        """The property that matters: a switcher must not offer a tenant you cannot open."""
        body = self._as(_admin('org-b', org=self.org_b)).json()
        self.assertEqual([o['id'] for o in body['organisations']], [self.org_b.id])
        self.assertNotIn(self.org_a.id, [o['id'] for o in body['organisations']])
