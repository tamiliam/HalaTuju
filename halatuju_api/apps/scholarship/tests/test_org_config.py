"""Org Config Sprint A — organisation-tunable values.

What matters here, in order:

1. **Blank means the platform default, live.** An organisation with no row behaves byte-identically
   to the platform before the sprint; the stored dict holds ONLY what was changed.
2. **The registry is the fence and it runs at the MODEL.** A shell caller cannot store an unknown
   key, a non-integer, or an out-of-range value.
3. **The one wired setting actually does its job**: `pool_funded_grace_days` moves the funded-card
   window PER ORGANISATION in `pool.display_pool_queryset` — including the NULL-org trap, where a
   bare `~Q(owning_organisation_id__in=…)` would silently drop NULL-org applications.
4. **The endpoint is fenced like its neighbour** (organisation derived, cross-org 404, org_admin +
   super only) and PUT is all-or-nothing.
"""
from datetime import timedelta

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses import org_config
from apps.courses.models import OrganisationConfiguration, PartnerAdmin, PartnerOrganisation
from apps.scholarship import pool
from apps.scholarship.models import Programme, ScholarshipApplication, ScholarshipCohort

from .test_sponsor_pool import _make_eligible_app

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
URL = '/api/v1/admin/scholarship/organisation/configuration/'
KEY = 'pool_funded_grace_days'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


# ─── the registry and the model fence ────────────────────────────────────────

class TestRegistryFence(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='fence-org', name='Fence Org')

    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(org_config.OrgConfigError) as ctx:
            org_config.validate_values({'made_up_setting': 5})
        self.assertEqual(ctx.exception.code, 'unknown_setting')

    def test_a_non_integer_is_refused_and_so_is_a_bool(self):
        # `True` IS an int in Python; without the explicit bool check it would store as 1.
        for bad in ('30', 30.5, True, None, [30]):
            with self.assertRaises(org_config.OrgConfigError, msg=repr(bad)):
                org_config.validate_values({KEY: bad})

    def test_out_of_range_is_refused_and_the_bounds_are_inclusive(self):
        spec = org_config.SETTINGS[KEY]
        for bad in (spec['min'] - 1, spec['max'] + 1, 0, -3):
            with self.assertRaises(org_config.OrgConfigError, msg=repr(bad)):
                org_config.validate_values({KEY: bad})
        org_config.validate_values({KEY: spec['min']})
        org_config.validate_values({KEY: spec['max']})

    def test_the_fence_runs_at_the_MODEL_so_a_shell_caller_cannot_go_around_it(self):
        row = OrganisationConfiguration(organisation=self.org, values={KEY: 9999})
        with self.assertRaises(org_config.OrgConfigError):
            row.save()
        self.assertFalse(OrganisationConfiguration.objects.exists())

    @override_settings(POOL_FUNDED_GRACE_HOURS=72)
    def test_the_default_delegates_to_django_settings_live(self):
        # The registry speaks DAYS; the platform value has always been HOURS. 72h → 3 days,
        # read at call time so an env change needs no deploy.
        self.assertEqual(org_config.default(KEY), 3.0)

    def test_value_falls_back_to_the_default_and_prefers_the_stored_value(self):
        self.assertEqual(org_config.value(self.org, KEY), org_config.default(KEY))
        OrganisationConfiguration.objects.create(organisation=self.org, values={KEY: 30})
        self.org.refresh_from_db()
        self.assertEqual(org_config.value(self.org, KEY), 30)
        self.assertEqual(org_config.stored(self.org, KEY), 30)

    def test_custom_values_lists_only_organisations_that_changed_the_key(self):
        other = PartnerOrganisation.objects.create(code='fence-org-2', name='Fence Org 2')
        OrganisationConfiguration.objects.create(organisation=self.org, values={KEY: 30})
        OrganisationConfiguration.objects.create(organisation=other, values={})
        self.assertEqual(org_config.custom_values(KEY), {self.org.id: 30})


# ─── the wired setting: the funded-card window, per organisation ─────────────

@override_settings(POOL_FUNDED_GRACE_HOURS=48)
class TestPerOrgFundedGraceWindow(TestCase):
    """`pool_funded_grace_days` governs how long a funded card lingers, PER ORGANISATION."""

    @classmethod
    def setUpTestData(cls):
        # ⚠ An application's `owning_organisation` copies from the COHORT's own
        # `owning_organisation` FK (the source of truth), NOT from programme.organisation —
        # so the cohorts here must carry it or every app lands org-NULL.
        from .test_sponsor_pool import fixture_programme
        fixture = fixture_programme()          # org `fixture-org`, shared with _make_eligible_app
        cls.cohort = ScholarshipCohort.objects.create(
            code='oc-a', name='B40', year=2026,
            programme=fixture, owning_organisation=fixture.organisation)
        cls.other_org = PartnerOrganisation.objects.create(code='oc-other', name='Other Org')
        other_programme = Programme.objects.create(
            code='oc-other-gift', organisation=cls.other_org, name_en='Other Gift')
        cls.other_cohort = ScholarshipCohort.objects.create(
            code='oc-b', name='B40 Other', year=2026,
            programme=other_programme, owning_organisation=cls.other_org)

    def _ids(self):
        return list(pool.display_pool_queryset(ScholarshipApplication)
                    .values_list('id', flat=True))

    def _fund(self, app, *, days_ago):
        app.status = 'awarded'
        app.awarded_at = timezone.now() - timedelta(days=days_ago)
        app.save(update_fields=['status', 'awarded_at'])

    def _configure(self, org_code, days):
        org = PartnerOrganisation.objects.get(code=org_code)
        row, _ = OrganisationConfiguration.objects.get_or_create(organisation=org)
        row.values = {KEY: days}
        row.save()

    def test_no_configuration_keeps_the_platform_window(self):
        fresh = _make_eligible_app(self.cohort, suffix='w1')
        stale = _make_eligible_app(self.cohort, suffix='w2')
        self._fund(fresh, days_ago=1)
        self._fund(stale, days_ago=3)
        ids = self._ids()
        self.assertIn(fresh.id, ids)
        self.assertNotIn(stale.id, ids)

    def test_a_configured_organisation_keeps_its_cards_longer(self):
        # THE SPRINT'S HEADLINE: 30 days configured → a card funded 20 days ago still shows;
        # one funded 40 days ago has genuinely lapsed.
        kept = _make_eligible_app(self.cohort, suffix='w3')
        lapsed = _make_eligible_app(self.cohort, suffix='w4')
        self._fund(kept, days_ago=20)
        self._fund(lapsed, days_ago=40)
        self._configure('fixture-org', 30)
        ids = self._ids()
        self.assertIn(kept.id, ids)
        self.assertNotIn(lapsed.id, ids)

    def test_another_organisation_stays_on_the_default(self):
        # One tenant's choice must never stretch a NEIGHBOUR's window.
        theirs = _make_eligible_app(self.other_cohort, suffix='w5')
        self._fund(theirs, days_ago=3)
        self._configure('fixture-org', 30)
        self.assertNotIn(theirs.id, self._ids())

    def test_a_null_org_application_follows_the_default_and_never_vanishes(self):
        # ⚠ THE `~Q` TRAP. SQL's `NOT (col IN (…))` is NULL-false for a NULL column, so the
        # default arm spelled as a bare negation silently drops every NULL-org application the
        # moment ANY organisation configures a window. Blank org = platform default, visibly.
        app = _make_eligible_app(self.cohort, suffix='w6')
        self._fund(app, days_ago=1)
        ScholarshipApplication.objects.filter(id=app.id).update(owning_organisation=None)
        self._configure('fixture-org', 30)
        self.assertIn(app.id, self._ids())


# ─── the endpoint ────────────────────────────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   POOL_FUNDED_GRACE_HOURS=48)
class TestOrganisationConfigurationEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Two tenants (each qualifies via an ACTIVE org_admin — the `tenants()` rule) plus a
        # referral organisation that must never surface here.
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

    def _row(self, body):
        return next(r for r in body['settings'] if r['key'] == KEY)

    # ── reading ──────────────────────────────────────────────────────────────
    def test_an_org_admin_reads_the_registry_at_the_default(self):
        self._auth('oa-a')
        body = self.client.get(URL).json()
        self.assertEqual(body['organisation'], {'code': 'alpha', 'name': 'Alpha Foundation'})
        row = self._row(body)
        # None = "following the platform default" — the value is NEVER a copied default.
        self.assertIsNone(row['value'])
        self.assertEqual(row['default'], 2.0)
        self.assertEqual(row['unit'], 'days')
        self.assertEqual((row['min'], row['max']), (1, 90))
        self.assertEqual(row['group'], 'sponsor_page')

    def test_the_payload_shape_is_exactly_organisation_plus_settings(self):
        self._auth('oa-a')
        body = self.client.get(URL).json()
        self.assertEqual(set(body), {'organisation', 'settings'})
        self.assertEqual(
            set(self._row(body)),
            {'key', 'group', 'unit', 'min', 'max', 'value', 'default'})

    # ── writing ──────────────────────────────────────────────────────────────
    def test_a_valid_value_is_stored_and_only_that_key_is_stored(self):
        self._auth('oa-a')
        r = self.client.put(URL, {'values': {KEY: 30}}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._row(r.json())['value'], 30)
        row = OrganisationConfiguration.objects.get(organisation=self.org_a)
        # ONLY the changed key — never a snapshot of the defaults (a copied default rots).
        self.assertEqual(row.values, {KEY: 30})
        self.assertEqual(row.updated_by_email, 'oaa@x.com')

    def test_null_clears_back_to_the_platform_default(self):
        self._auth('oa-a')
        self.client.put(URL, {'values': {KEY: 30}}, format='json')
        r = self.client.put(URL, {'values': {KEY: None}}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(self._row(r.json())['value'])
        self.assertEqual(
            OrganisationConfiguration.objects.get(organisation=self.org_a).values, {})

    def test_out_of_range_is_refused_and_NOTHING_is_stored(self):
        self._auth('oa-a')
        r = self.client.put(URL, {'values': {KEY: 365}}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'out_of_range')
        self.assertEqual(r.json()['key'], KEY)
        self.assertFalse(OrganisationConfiguration.objects.exists())

    def test_a_non_integer_is_refused(self):
        self._auth('oa-a')
        for bad in ('30', 30.5, True):
            r = self.client.put(URL, {'values': {KEY: bad}}, format='json')
            self.assertEqual(r.status_code, 400, msg=repr(bad))
            self.assertEqual(r.json()['code'], 'bad_value')

    def test_an_unknown_setting_is_404(self):
        self._auth('oa-a')
        for value in (5, None):
            r = self.client.put(URL, {'values': {'made_up': value}}, format='json')
            self.assertEqual(r.status_code, 404, msg=repr(value))
            self.assertEqual(r.json()['code'], 'unknown_setting')
        self.assertFalse(OrganisationConfiguration.objects.exists())

    def test_a_refusal_never_disturbs_a_value_already_saved(self):
        # All-or-nothing: the refused write leaves the stored 30 exactly as it was.
        self._auth('oa-a')
        self.client.put(URL, {'values': {KEY: 30}}, format='json')
        self.client.put(URL, {'values': {KEY: 365}}, format='json')
        self.assertEqual(
            OrganisationConfiguration.objects.get(organisation=self.org_a).values, {KEY: 30})

    # ── the fence ────────────────────────────────────────────────────────────
    def test_a_reviewer_may_not_read_or_write(self):
        self._auth('rev-a')
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(
            self.client.put(URL, {'values': {KEY: 30}}, format='json').status_code, 403)

    def test_cross_org_is_404_never_403(self):
        self._auth('oa-a')
        self.assertEqual(self.client.get(f'{URL}?org=beta').status_code, 404)
        # A referral organisation is NOT a tenant and must read as not-found too.
        self.assertEqual(self.client.get(f'{URL}?org=a-school').status_code, 404)

    def test_a_super_must_name_the_organisation_when_two_exist(self):
        self._auth('super-uid')
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'organisation_required')
        # Subset, not equality: migration 0119 seeds a BrightPath tenant into the test DB, so
        # the full list carries more than the two this test created.
        self.assertLessEqual({'alpha', 'beta'}, set(r.json()['organisations']))
        self.assertNotIn('a-school', r.json()['organisations'])
        ok = self.client.get(f'{URL}?org=beta')
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['organisation']['code'], 'beta')

    def test_each_organisation_holds_its_own_row(self):
        self._auth('oa-a')
        self.client.put(URL, {'values': {KEY: 30}}, format='json')
        self._auth('oa-b')
        body = self.client.get(URL).json()
        self.assertIsNone(self._row(body)['value'])

    # ── end to end: the tab's write reaches the sponsor page ─────────────────
    def test_the_saved_window_reaches_the_display_pool(self):
        # Wire a programme + cohort under alpha, fund a student 20 days ago, then set 30 days
        # through the ENDPOINT — the card must come back into the display pool.
        programme = Programme.objects.create(
            code='alpha-gift', organisation=self.org_a, name_en='Alpha Gift')
        cohort = ScholarshipCohort.objects.create(
            code='alpha-2026', name='Alpha 2026', year=2026,
            programme=programme, owning_organisation=self.org_a)
        app = _make_eligible_app(cohort, suffix='e2e')
        app.status = 'awarded'
        app.awarded_at = timezone.now() - timedelta(days=20)
        app.save(update_fields=['status', 'awarded_at'])

        ids = list(pool.display_pool_queryset(ScholarshipApplication)
                   .values_list('id', flat=True))
        self.assertNotIn(app.id, ids)

        self._auth('oa-a')
        r = self.client.put(URL, {'values': {KEY: 30}}, format='json')
        self.assertEqual(r.status_code, 200)

        ids = list(pool.display_pool_queryset(ScholarshipApplication)
                   .values_list('id', flat=True))
        self.assertIn(app.id, ids)
