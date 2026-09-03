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

    def test_super_sees_every_TENANT_organisation_and_programme(self):
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

    def test_a_REFERRAL_organisation_is_never_offered_as_a_tenant(self):
        """The bug this endpoint shipped with, and the reason this file exists twice over.

        `partner_organisations` holds tenant organisations AND referral organisations (schools,
        NGOs that send us students) in ONE table with no flag between them. Production has ten
        rows and exactly one tenant. The first cut listed the table, so a super's switcher offered
        Sri Murugan Centre and Tara Foundation as if they were tenants to switch into.

        A referral org owns no programme and has no org_admin. Its logins, where it has any, are
        `partner`-role course-selector accounts — which is why the tenant test keys on
        `role='org_admin'` and not on "has a PartnerAdmin".
        """
        referral = _org('sri-murugan-centre')
        PartnerAdmin.objects.create(
            supabase_user_id='course-selector-login', email='cs@example.com', name='CS',
            role='partner', is_active=True, org=referral,      # referring org, NOT owning
        )
        body = self._as(_admin('super-ref', role='super', super_=True)).json()
        self.assertNotIn('sri-murugan-centre', [o['code'] for o in body['organisations']])

    def test_a_tenant_mid_creation_still_appears(self):
        """Org + org_admin but no programme yet — the create form makes all three together, and
        a tenant must not vanish from the switcher between those writes."""
        fresh = _org('new-tenant')
        _admin('new-tenant-admin', org=fresh, role='org_admin')
        body = self._as(_admin('super-fresh', role='super', super_=True)).json()
        self.assertIn('new-tenant', [o['code'] for o in body['organisations']])

    def test_a_tenant_whose_admin_was_revoked_still_appears(self):
        """It owns a live programme and holds applications; losing its admin does not un-tenant
        it. This is why the rule is OWNS-A-PROGRAMME **or** HAS-AN-ORG-ADMIN, not either alone."""
        body = self._as(_admin('super-revoked', role='super', super_=True)).json()
        # org_a owns a programme and has no org_admin in this fixture.
        self.assertIn('tenant-a', [o['code'] for o in body['organisations']])

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

    # ⚠ REVERSED DELIBERATELY, 2026-09-03. This asserted that an inactive programme is NOT offered,
    # which was reasonable when the switcher was decorative and read "where you are". It became
    # wrong the moment the crumb started choosing which gift the Configuration screen edits: a gift
    # is CREATED INACTIVE and must be configured BEFORE it is switched on, so "not switched on yet"
    # is the state an org_admin spends the most time inside. The owner created a second gift,
    # pressed into it, and the console showed them the first gift's settings — because this list
    # did not contain the new one, so the selection was discarded and fell back.
    #
    # The INACTIVE-ORGANISATION test below is untouched and still correct: nobody configures a
    # tenant that has been switched off, and it is a different question.
    def test_an_inactive_programme_IS_offered_because_that_is_when_it_is_configured(self):
        _programme(self.org_a, 'a-draft', active=False)
        body = self._as(_admin('org-a2', org=self.org_a)).json()
        self.assertEqual(sorted(p['code'] for p in body['programmes']), ['a-bursary', 'a-draft'])

    def test_it_says_which_programmes_are_switched_on(self):
        # So a switcher can MARK one rather than leaving the reader to discover it from the screen
        # underneath. Without this the crumb would name a draft gift as if it were live.
        _programme(self.org_a, 'a-draft-2', active=False)
        body = self._as(_admin('org-a3', org=self.org_a)).json()
        by_code = {p['code']: p['is_active'] for p in body['programmes']}
        self.assertFalse(by_code['a-draft-2'])
        self.assertTrue(by_code['a-bursary'])

    def test_widening_on_is_active_did_NOT_widen_on_the_organisation(self):
        # The assertion that says the fence did not move with the filter.
        _programme(self.org_b, 'b-draft', active=False)
        body = self._as(_admin('org-a4', org=self.org_a)).json()
        self.assertNotIn('b-draft', [p['code'] for p in body['programmes']])

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
