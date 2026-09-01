"""Layer 1 A2 — the colour picker's endpoint.

What matters here, in order:

1. **An unreadable colour is REFUSED and nothing is stored.** Not warned about, not stored-with-a-
   flag. A warning is dismissed by the person who chose the colour; the person who cannot read the
   page is a student who never saw it.
2. **The organisation is derived, never sent.** It comes from the same `owning_organisation` the org
   fence uses, so this endpoint cannot widen access however it is called.
3. **Reset really resets.** DELETE removes the row, so a tenant can always get back to the platform
   colours in `globals.css` exactly — which is what makes trying a colour safe.
"""
import datetime

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses import theme_tokens
from apps.courses.models import OrganisationTheme, PartnerAdmin, PartnerOrganisation

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
URL = '/api/v1/admin/scholarship/organisation/theme/'
PUBLISH = URL + 'publish/'
REVERT = URL + 'revert/'

GOOD = '#a21caf'      # purple — passes every pair
UNREADABLE = '#facc15'  # yellow — fails the text pairs badly


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestOrganisationThemeEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Two tenants. Each qualifies via an ACTIVE org_admin — the `tenants()` rule — so neither
        # needs a programme, and the referral organisation below is correctly excluded.
        cls.org_a = PartnerOrganisation.objects.create(code='alpha', name='Alpha Foundation')
        cls.org_b = PartnerOrganisation.objects.create(code='beta', name='Beta Trust')
        cls.referral = PartnerOrganisation.objects.create(code='a-school', name='A School')

        cls.oa_a = PartnerAdmin.objects.create(
            supabase_user_id='oa-a', role='org_admin', is_active=True,
            owning_organisation=cls.org_a, name='OrgAdmin A', email='oaa@x.com')
        cls.oa_b = PartnerAdmin.objects.create(
            supabase_user_id='oa-b', role='org_admin', is_active=True,
            owning_organisation=cls.org_b, name='OrgAdmin B', email='oab@x.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-a', role='reviewer', is_active=True,
            owning_organisation=cls.org_a, name='Reviewer A', email='reva@x.com')
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    # ── reading ──────────────────────────────────────────────────────────────────────────────
    def test_an_org_admin_sees_its_own_organisation_at_the_default(self):
        self._auth('oa-a')
        body = self.client.get(URL).json()
        self.assertEqual(body['organisation'], {'code': 'alpha', 'name': 'Alpha Foundation'})
        self.assertIsNone(body['live'])
        self.assertIsNone(body['draft'])
        self.assertIsNone(body['tokens'])
        self.assertFalse(body['can_revert'])

    def test_the_payload_carries_no_student_data(self):
        self._auth('oa-a')
        self.client.put(URL, {'colour': GOOD}, format='json')
        body = self.client.get(URL).json()
        self.assertEqual(set(body), {
            'organisation', 'live', 'draft', 'previous_colour', 'can_revert',
            'published_at', 'published_by', 'tokens'})

    # ── the gate ─────────────────────────────────────────────────────────────────────────────
    def test_a_readable_colour_is_saved_as_a_DRAFT_and_nothing_goes_live(self):
        # ⚠ THE WHOLE OF A3 IN ONE TEST. A save used to change what every applicant saw, instantly
        # and with no undo. Now it makes a draft and leaves the live colour exactly as it was.
        self._auth('oa-a')
        r = self.client.put(URL, {'colour': GOOD}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['draft']['colour'], GOOD)
        self.assertIsNone(r.json()['live'])
        self.assertIsNone(r.json()['tokens'])

        row = OrganisationTheme.objects.get(organisation=self.org_a)
        self.assertEqual(row.status, 'draft')
        self.assertEqual(row.tokens, theme_tokens.tokens_from_colour(GOOD))
        self.assertEqual(row.tokens['light']['brand-500'], row.tokens['dark']['brand-500'])
        # Every check comes back so the screen can show the reader why it is allowed, not just that.
        self.assertTrue(all(c['passes'] for c in r.json()['draft']['checks']))

    def test_an_unreadable_colour_is_refused_and_NOTHING_is_stored(self):
        self._auth('oa-a')
        r = self.client.put(URL, {'colour': UNREADABLE}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'unreadable')
        self.assertIn('filled_button', r.json()['failing'])
        self.assertFalse(OrganisationTheme.objects.filter(organisation=self.org_a).exists())

    def test_a_refusal_still_reports_the_checks_that_PASSED(self):
        # The screen shows a list, not one line, so a tenant can see how close they were and which
        # way to move. Gold fails three of six — yellow fails all six, which is why it is the wrong
        # colour to make this point with.
        self._auth('oa-a')
        body = self.client.put(URL, {'colour': '#d97706'}, format='json').json()
        self.assertEqual(body['code'], 'unreadable')
        self.assertTrue(len(body['checks']) > len(body['failing']))
        self.assertTrue(any(c['passes'] for c in body['checks']))

    def test_a_refusal_never_disturbs_a_colour_already_saved(self):
        self._auth('oa-a')
        self.client.put(URL, {'colour': GOOD}, format='json')
        self.client.put(URL, {'colour': UNREADABLE}, format='json')
        self.assertEqual(
            OrganisationTheme.objects.get(organisation=self.org_a).source_colour, GOOD)

    def test_a_colour_that_is_not_a_colour_is_refused(self):
        self._auth('oa-a')
        for bad in ('blue', '#12345', '', 'rgb(1,2,3)', '#gggggg'):
            r = self.client.put(URL, {'colour': bad}, format='json')
            self.assertEqual(r.status_code, 400, bad)
            self.assertEqual(r.json()['code'], 'bad_colour', bad)

    # ── discarding a draft ───────────────────────────────────────────────────────────────────
    def test_delete_throws_the_draft_away_and_leaves_the_live_colour_alone(self):
        self._auth('oa-a')
        self.client.put(URL, {'colour': GOOD}, format='json')
        self.client.post(PUBLISH, {}, format='json')
        self.client.put(URL, {'colour': '#0f766e'}, format='json')   # a second, unpublished idea

        r = self.client.delete(URL)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['draft'])
        # ⚠ The live colour is untouched. A draft you throw away costs nobody anything, which is
        # the property that makes trying one safe.
        self.assertEqual(r.json()['live']['colour'], GOOD)

    def test_delete_with_no_draft_is_harmless(self):
        self._auth('oa-a')
        self.assertEqual(self.client.delete(URL).status_code, 200)

    # ── who may ──────────────────────────────────────────────────────────────────────────────
    def test_a_reviewer_may_not_set_a_colour(self):
        self._auth('rev-a')
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.client.put(URL, {'colour': GOOD}, format='json').status_code, 403)

    def test_anonymous_is_refused(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))

    # ── the fence ────────────────────────────────────────────────────────────────────────────
    def test_another_organisation_is_404_never_403(self):
        # 403 would confirm the tenant exists. The org fence's own rule.
        self._auth('oa-a')
        self.assertEqual(self.client.get(f'{URL}?org=beta').status_code, 404)
        self.assertEqual(
            self.client.put(f'{URL}?org=beta', {'colour': GOOD}, format='json').status_code, 404)
        self.assertFalse(OrganisationTheme.objects.filter(organisation=self.org_b).exists())

    def test_two_organisations_cannot_leak_into_each_other(self):
        self._auth('oa-a')
        self.client.put(URL, {'colour': '#a21caf'}, format='json')
        self.client.post(PUBLISH, {}, format='json')
        self._auth('oa-b')
        self.client.put(URL, {'colour': '#0f766e'}, format='json')
        self.client.post(PUBLISH, {}, format='json')

        self._auth('oa-a')
        self.assertEqual(self.client.get(URL).json()['live']['colour'], '#a21caf')
        self._auth('oa-b')
        self.assertEqual(self.client.get(URL).json()['live']['colour'], '#0f766e')

    def test_a_super_with_two_tenants_must_name_one(self):
        self._auth('super-uid')
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'organisation_required')
        # BrightPath is seeded as org #1 by a data migration and is a tenant too, so the list is
        # the three of them. What matters is that BOTH test tenants are offered and none is picked.
        self.assertLessEqual({'alpha', 'beta'}, set(r.json()['organisations']))

    def test_a_super_may_name_either(self):
        self._auth('super-uid')
        self.assertEqual(self.client.get(f'{URL}?org=alpha').json()['organisation']['code'], 'alpha')
        self.assertEqual(self.client.get(f'{URL}?org=beta').json()['organisation']['code'], 'beta')

    def test_a_referral_organisation_is_not_a_tenant(self):
        # `partner_organisations` is dual-role. A school that sends us students has no colours to
        # set, and `tenants()` is what keeps it out of this endpoint entirely.
        self._auth('super-uid')
        self.assertEqual(self.client.get(f'{URL}?org=a-school').status_code, 404)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheAuditTrail(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='alpha', name='Alpha Foundation')
        PartnerAdmin.objects.create(
            supabase_user_id='oa-a', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OrgAdmin A', email='oaa@x.com')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("oa-a")}')

    def test_drafting_and_discarding_are_recorded(self):
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            self.client.put(URL, {'colour': GOOD}, format='json')
        line = '\n'.join(logs.output)
        self.assertIn('AUDIT organisation_theme_draft_saved', line)
        self.assertIn('org=alpha', line)
        self.assertIn('oaa@x.com', line)

        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            self.client.delete(URL)
        self.assertIn('AUDIT organisation_theme_draft_discarded', '\n'.join(logs.output))

    def test_publishing_and_reverting_are_recorded(self):
        """⚠ A PUBLISH IS THE MOMENT APPLICANTS SEE SOMETHING NEW, so it is the line that has to be
        in the log. Its audit says what it replaced, not just what it set."""
        self.client.put(URL, {'colour': GOOD}, format='json')
        with self.assertLogs('apps.courses.theme_versions', level='INFO') as logs:
            self.client.post(PUBLISH, {}, format='json')
        line = '\n'.join(logs.output)
        self.assertIn('AUDIT organisation_theme_published', line)
        self.assertIn('was=default', line)   # the first publish records that there was none
        self.assertIn('oaa@x.com', line)

        with self.assertLogs('apps.courses.theme_versions', level='INFO') as logs:
            self.client.post(REVERT, {}, format='json')
        self.assertIn('AUDIT organisation_theme_reverted', '\n'.join(logs.output))

    def test_a_refused_colour_writes_no_audit_line(self):
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            self.client.put(URL, {'colour': UNREADABLE}, format='json')
            # assertLogs needs at least one record; this one is not the audit line.
            import logging
            logging.getLogger('apps.scholarship.views_admin').info('probe')
        self.assertNotIn('AUDIT organisation_theme_draft_saved', '\n'.join(logs.output))


class TestStoredThemesAreAlwaysFenced(TestCase):
    def test_the_endpoint_can_never_store_a_tone(self):
        """Belt and braces across the two modules: whatever the endpoint derives, the model's own
        fence has to accept it. If `tokens_from_colour` ever grew a family a tenant may not set,
        this fails at the save rather than reaching a page."""
        org = PartnerOrganisation.objects.create(code='alpha', name='Alpha')
        tokens = theme_tokens.tokens_from_colour(GOOD)
        OrganisationTheme.objects.create(organisation=org, source_colour=GOOD, tokens=tokens)
        families = {theme_tokens.family_of(k) for k in tokens['light']}
        self.assertEqual(families, {'brand'})
        for family in theme_tokens.PLATFORM_FAMILIES:
            self.assertNotIn(family, families)

    def test_the_derived_set_never_needs_the_read_filter_to_repair_it(self):
        # `applied_tokens` exists for rows edited around the ORM. What the ENDPOINT writes must
        # already be clean, or the filter is quietly doing work the gate should have done.
        tokens = theme_tokens.tokens_from_colour(GOOD)
        self.assertEqual(theme_tokens.applied_tokens(tokens), tokens)
