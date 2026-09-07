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


# ═══ Sprint B — student comms + the deferred sponsor-email card cap ══════════


class TestSprintBRegistry(TestCase):
    """The five Sprint B keys exist, and every default DELEGATES to the platform's live home."""

    SPRINT_B = {
        'sponsor_email_max_cards': ('sponsor_page', 'cards'),
        'query_email_delay_hours': ('student_comms', 'hours'),
        'nudge_auto_delay_minutes': ('student_comms', 'minutes'),
        'nudge_cooldown_hours': ('student_comms', 'hours'),
        'max_clarify_open': ('student_comms', 'questions'),
    }

    def test_every_key_is_registered_with_its_group_and_unit(self):
        for key, (group, unit) in self.SPRINT_B.items():
            spec = org_config.SETTINGS[key]
            self.assertEqual((spec['group'], spec['unit']), (group, unit), key)
            # The full spec shape the endpoint payload builder relies on, for EVERY key.
            self.assertEqual(set(spec), {'group', 'unit', 'min', 'max', 'default'})

    @override_settings(SPONSOR_EMAIL_MAX_CARDS=7, NUDGE_AUTO_DELAY_MINUTES=45,
                       NUDGE_COOLDOWN_HOURS=6)
    def test_defaults_delegate_to_the_live_platform_homes(self):
        # Settings-backed defaults follow an env change with no deploy…
        self.assertEqual(org_config.default('sponsor_email_max_cards'), 7)
        self.assertEqual(org_config.default('nudge_auto_delay_minutes'), 45)
        self.assertEqual(org_config.default('nudge_cooldown_hours'), 6)
        # …and constant-backed defaults read the module constant, the one platform home.
        from apps.scholarship.check2_queries import MAX_CLARIFY
        from apps.scholarship.services import QUERY_EMAIL_DELAY_HOURS
        self.assertEqual(org_config.default('query_email_delay_hours'), QUERY_EMAIL_DELAY_HOURS)
        self.assertEqual(org_config.default('max_clarify_open'), MAX_CLARIFY)


def _org_cohort(code, org):
    """A cohort carrying `owning_organisation` (the source the application copies from)."""
    programme = None
    if org is not None:
        programme = Programme.objects.create(
            code=f'{code}-gift', organisation=org, name_en=f'{code} Gift')
    return ScholarshipCohort.objects.create(
        code=code, name=f'B40 {code}', year=2026,
        programme=programme, owning_organisation=org)


def _configure(org, key, value):
    row, _ = OrganisationConfiguration.objects.get_or_create(organisation=org)
    row.values = {**(row.values or {}), key: value}
    row.save()
    org.refresh_from_db()


class TestPerOrgClarifyCap(TestCase):
    """`max_clarify_open` narrows (or widens) the Check-2 clarify cap PER ORGANISATION."""

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='cc-org', name='Clarify Org')
        cls.cohort = _org_cohort('cc-a', cls.org)
        cls.null_cohort = _org_cohort('cc-null', None)

    def _gappy_app(self, cohort, suffix):
        # The test_check2_queries "force all four gaps" shape: no course pick, legacy-only
        # siblings, no funding device tick → more clarify-able gaps than any cap here.
        from apps.courses.models import StudentProfile
        from apps.scholarship.models import ApplicantDocument
        profile = StudentProfile.objects.create(
            supabase_user_id=f'occ-{suffix}', name='Priya Devi', nric='030101-14-1234',
            household_income=1200, household_size=3)
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='profile_complete',
            profile_completed_at=timezone.now(),
            aspirations='I want to teach.', field_of_study='',
            siblings_in_tertiary=None, siblings_studying_count=2,
            chosen_pathway='stpm', pathway_certainty='sure',
            father_occupation='gov', mother_occupation='homemaker')
        ApplicantDocument.objects.create(
            application=app, doc_type='salary_slip', household_member='father',
            storage_path='x/slip')
        return app

    def _open_clarifies(self, app):
        return app.resolution_items.filter(source='check2', kind='clarify',
                                           status='open').count()

    def test_a_configured_cap_narrows_the_sync_and_feeds_the_overflow_note(self):
        from apps.scholarship.check2_queries import clarify_overflow_count, sync_check2_queries
        app = self._gappy_app(self.cohort, 'k1')
        _configure(self.org, 'max_clarify_open', 1)
        sync_check2_queries(app)
        self.assertEqual(self._open_clarifies(app), 1)
        # The crowded-out gaps surface to the officer against the SAME per-org cap.
        self.assertGreater(clarify_overflow_count(app), 0)

    def test_a_null_org_application_keeps_the_platform_cap(self):
        # One tenant's cap must never ration a NULL-org (or neighbouring) application.
        from apps.scholarship.check2_queries import MAX_CLARIFY, sync_check2_queries
        _configure(self.org, 'max_clarify_open', 1)
        other = self._gappy_app(self.null_cohort, 'k2')
        sync_check2_queries(other)
        self.assertEqual(self._open_clarifies(other), MAX_CLARIFY)


class TestPerOrgNudgeDelays(TestCase):
    """`nudge_auto_delay_minutes` + `nudge_cooldown_hours` govern the nudge PER ORGANISATION."""

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='nn-org', name='Nudge Org')
        cls.cohort = _org_cohort('nn-a', cls.org)
        cls.null_cohort = _org_cohort('nn-null', None)

    def setUp(self):
        from unittest import mock
        p = mock.patch('apps.scholarship.nudge._has_blockers', return_value=False)
        p.start(); self.addCleanup(p.stop)

    def _consented_app(self, cohort, suffix, *, minutes_ago):
        from apps.courses.models import StudentProfile
        from apps.scholarship.models import Consent
        profile = StudentProfile.objects.create(supabase_user_id=f'onn-{suffix}', name='Janu')
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='shortlisted', notify_email='stu@x.com')
        c = Consent.objects.create(application=app, version='t', granted_by='guardian',
                                   guardian_name='Parent', is_active=True)
        Consent.objects.filter(pk=c.pk).update(
            granted_at=timezone.now() - timedelta(minutes=minutes_ago))
        return app

    def test_nudge_state_reports_the_organisation_s_auto_due_time(self):
        from datetime import datetime
        from apps.scholarship import nudge as nudge_mod
        _configure(self.org, 'nudge_auto_delay_minutes', 60)
        app = self._consented_app(self.cohort, 'd1', minutes_ago=5)
        st = nudge_mod.nudge_state(app)
        due = datetime.fromisoformat(st['available_at'])
        granted = app.consents.get().granted_at
        self.assertAlmostEqual((due - granted).total_seconds(), 3600, delta=5)

    def test_the_cooldown_follows_the_organisation(self):
        from apps.scholarship import nudge as nudge_mod
        _configure(self.org, 'nudge_cooldown_hours', 1)
        app = self._consented_app(self.cohort, 'd2', minutes_ago=300)
        app.nudge_sent_at = timezone.now() - timedelta(hours=2)
        app.save(update_fields=['nudge_sent_at'])
        self.assertTrue(nudge_mod.nudge_state(app)['available'])       # 2h > the org's 1h
        other = self._consented_app(self.null_cohort, 'd3', minutes_ago=300)
        other.nudge_sent_at = timezone.now() - timedelta(hours=2)
        other.save(update_fields=['nudge_sent_at'])
        self.assertFalse(nudge_mod.nudge_state(other)['available'])    # platform 24h holds

    def test_the_auto_sweep_honours_each_organisation_and_the_null_org_trap(self):
        # Configured org waits 120 min; the platform default (30) sweeps everyone else —
        # INCLUDING a NULL-org application (the `~Q(in) | Q(isnull)` spelling, pinned).
        from apps.scholarship import nudge as nudge_mod
        _configure(self.org, 'nudge_auto_delay_minutes', 120)
        waiting = self._consented_app(self.cohort, 's1', minutes_ago=45)
        nullorg = self._consented_app(self.null_cohort, 's2', minutes_ago=45)
        nudge_mod.send_application_nudges()
        waiting.refresh_from_db(); nullorg.refresh_from_db()
        self.assertIsNone(waiting.nudge_sent_at)       # the org's 120-min delay holds
        self.assertIsNotNone(nullorg.nudge_sent_at)    # NULL org = platform default, never dropped


@override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestPerOrgQueryEmailDelay(TestCase):
    """`query_email_delay_hours` holds the "a few questions" email PER ORGANISATION."""

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='qq-org', name='Query Org')
        cls.cohort = _org_cohort('qq-a', cls.org)
        cls.null_cohort = _org_cohort('qq-null', None)

    def _submitted_app(self, cohort, suffix, *, hours_ago):
        # The gappy shape guarantees ≥1 open clarify, so the sweep has something to announce.
        from apps.courses.models import StudentProfile
        profile = StudentProfile.objects.create(
            supabase_user_id=f'oqq-{suffix}', name='Priya Devi',
            household_income=1200, household_size=3)
        return ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='profile_complete',
            notify_email='stu@x.com',
            profile_completed_at=timezone.now() - timedelta(hours=hours_ago),
            aspirations='I want to teach.', field_of_study='',
            siblings_in_tertiary=0, siblings_in_school=0,
            chosen_pathway='stpm', pathway_certainty='sure',
            father_occupation='gov', mother_occupation='homemaker')

    def test_the_sweep_honours_each_organisation_and_the_null_org_trap(self):
        from apps.scholarship import services
        _configure(self.org, 'query_email_delay_hours', 8)
        held = self._submitted_app(self.cohort, 'q1', hours_ago=3)     # 3h < the org's 8h
        due = self._submitted_app(self.null_cohort, 'q2', hours_ago=3)  # 3h > the platform 2h
        services.send_due_query_emails()
        held.refresh_from_db(); due.refresh_from_db()
        self.assertIsNone(held.query_raised_notified_at)
        self.assertIsNotNone(due.query_raised_notified_at)             # NULL org never dropped
        # Once the org's own delay HAS passed, the held student is announced too.
        ScholarshipApplication.objects.filter(pk=held.pk).update(
            profile_completed_at=timezone.now() - timedelta(hours=9))
        held.refresh_from_db()
        services.send_due_query_emails()
        held.refresh_from_db()
        self.assertIsNotNone(held.query_raised_notified_at)


class TestPerOrgSponsorEmailCap(TestCase):
    """`sponsor_email_max_cards` — ONE value drives BOTH sponsor-email render sites."""

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='sc-org', name='Cap Org')

    @staticmethod
    def _cards(n):
        return [{'id': i, 'ref': f'S-{i:06d}', 'course': 'Course', 'amount': '3000'}
                for i in range(n)]

    def test_the_template_block_caps_per_organisation_and_says_so(self):
        from apps.scholarship import sponsor_comms
        _configure(self.org, 'sponsor_email_max_cards', 2)
        _html, text = sponsor_comms.student_cards_blocks(self._cards(5), organisation=self.org)
        self.assertIn('and 3 more', text)
        # No organisation in hand → the platform default (5) — nothing dropped here.
        _html, text = sponsor_comms.student_cards_blocks(self._cards(5))
        self.assertNotIn('more waiting', text)

    def test_the_pre_template_sender_caps_per_organisation(self):
        from django.core import mail
        from apps.scholarship.emails import send_sponsor_new_student_email
        _configure(self.org, 'sponsor_email_max_cards', 2)
        send_sponsor_new_student_email('s@x.com', self._cards(4), lang='en',
                                       organisation=self.org)
        body = mail.outbox[-1].body
        self.assertIn('S-000001', body)
        self.assertNotIn('S-000002', body)     # the third card is beyond the org's cap of 2

    def test_the_batch_organisation_is_derived_only_when_it_is_sole(self):
        from apps.scholarship.sponsor_notifications import _sole_batch_organisation

        class _App:
            def __init__(self, org):
                self.owning_organisation = org
                self.owning_organisation_id = getattr(org, 'id', None)

        other = PartnerOrganisation.objects.create(code='sc-org-2', name='Cap Org 2')
        self.assertEqual(_sole_batch_organisation([_App(self.org), _App(self.org)]), self.org)
        self.assertIsNone(_sole_batch_organisation([_App(self.org), _App(other)]))
        # A NULL-org application makes the batch UNKNOWN, never "the other apps' org".
        self.assertIsNone(_sole_batch_organisation([_App(self.org), _App(None)]))


# ─── Sprint C: reviewers & staff ─────────────────────────────────────────────

class TestSprintCRegistry(TestCase):
    """The five Sprint C keys exist, and every default DELEGATES to the platform's live home."""

    SPRINT_C = ('review_sla_days', 'review_nudge_soon_days', 'review_escalate_grace_days',
                'temp_password_ttl_days', 'admin_dormant_days')

    def test_every_key_is_registered_with_its_group_and_unit(self):
        for key in self.SPRINT_C:
            spec = org_config.SETTINGS[key]
            self.assertEqual((spec['group'], spec['unit']), ('reviewers_staff', 'days'), key)
            self.assertEqual(set(spec), {'group', 'unit', 'min', 'max', 'default'})

    @override_settings(REVIEW_SLA_DAYS=12, REVIEW_NUDGE_SOON_DAYS=3,
                       REVIEW_ESCALATE_GRACE_DAYS=5, PARTNER_TEMP_PASSWORD_TTL_DAYS=9,
                       ADMIN_DORMANT_DAYS=120)
    def test_defaults_delegate_to_the_live_platform_settings(self):
        self.assertEqual(org_config.default('review_sla_days'), 12)
        self.assertEqual(org_config.default('review_nudge_soon_days'), 3)
        self.assertEqual(org_config.default('review_escalate_grace_days'), 5)
        self.assertEqual(org_config.default('temp_password_ttl_days'), 9)
        self.assertEqual(org_config.default('admin_dormant_days'), 120)


@override_settings(REVIEW_NUDGES_ENABLED=True)
class TestPerOrgReviewClocks(TestCase):
    """`review_sla_days` / `review_nudge_soon_days` / `review_escalate_grace_days` — the three
    verdict clocks are computed PER ORGANISATION, and the three read sites (the nudge sweep, the
    assignment email, the interview reminder) all state the SAME due date."""

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='rc-org', name='Review Org')
        cls.cohort = _org_cohort('rc-a', cls.org)
        cls.null_cohort = _org_cohort('rc-null', None)
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rc-rev', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Reviewer RC', email='rc-rev@x.com')

    def _assigned_app(self, cohort, suffix, *, days_ago):
        from apps.courses.models import StudentProfile
        profile = StudentProfile.objects.create(supabase_user_id=f'orc-{suffix}', name='Kavi')
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='profile_complete',
            notify_email='stu@x.com', assigned_to=self.reviewer)
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            assigned_at=timezone.now() - timedelta(days=days_ago))
        app.refresh_from_db()
        return app

    def _run(self):
        from django.core.management import call_command
        call_command('send_review_nudges')

    def test_the_sweep_uses_the_organisations_sla_and_grace(self):
        # Org: due at day 5, escalate at day 6 → an app assigned 8 days ago is overdue AND
        # escalated. NULL org: platform SLA 10 → the same age is not even due yet.
        _configure(self.org, 'review_sla_days', 5)
        _configure(self.org, 'review_escalate_grace_days', 1)
        ours = self._assigned_app(self.cohort, 'a1', days_ago=8)
        theirs = self._assigned_app(self.null_cohort, 'a2', days_ago=8)
        self._run()
        ours.refresh_from_db(); theirs.refresh_from_db()
        self.assertIsNotNone(ours.review_nudged_overdue_at)
        self.assertIsNotNone(ours.review_escalated_at)
        self.assertIsNone(theirs.review_nudged_overdue_at)   # platform clock, untouched
        self.assertIsNone(theirs.review_escalated_at)

    def test_the_soon_window_follows_the_organisation(self):
        # Org SLA 5, soon window 2 → an app assigned 4 days ago is due in 1 day → "due soon".
        # NULL org at the same age: due in 6 days on the platform's 10 → silence.
        _configure(self.org, 'review_sla_days', 5)
        soon = self._assigned_app(self.cohort, 'b1', days_ago=4)
        quiet = self._assigned_app(self.null_cohort, 'b2', days_ago=4)
        self._run()
        soon.refresh_from_db(); quiet.refresh_from_db()
        self.assertIsNotNone(soon.review_nudged_soon_at)
        self.assertIsNone(quiet.review_nudged_soon_at)

    def test_the_assignment_email_states_the_organisations_review_by_date(self):
        from unittest import mock
        from apps.scholarship import services
        _configure(self.org, 'review_sla_days', 5)
        app = self._assigned_app(self.cohort, 'c1', days_ago=0)
        other = PartnerAdmin.objects.create(
            supabase_user_id='rc-rev2', role='reviewer', is_active=True,
            owning_organisation=self.org, name='Reviewer Two', email='rc-rev2@x.com')
        superadmin = PartnerAdmin.objects.create(
            supabase_user_id='rc-super', is_super_admin=True, is_active=True,
            name='Super', email='rc-super@x.com')
        with mock.patch('apps.scholarship.emails.send_reviewer_assigned_email') as sent:
            services.assign_reviewer(app, reviewer=other, by_admin=superadmin)
        expected = (timezone.now() + timedelta(days=5)).date().strftime('%d %b %Y')
        self.assertEqual(sent.call_args.kwargs['review_by'], expected)

    @override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
    def test_the_interview_reminder_names_the_same_due_date(self):
        from unittest import mock
        from django.core.management import call_command
        _configure(self.org, 'review_sla_days', 5)
        app = self._assigned_app(self.cohort, 'd1', days_ago=1)
        now = timezone.now()
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            interview_status='booked', interview_start=now + timedelta(minutes=30),
            interview_booked_at=now - timedelta(hours=3))
        with mock.patch('apps.scholarship.emails.send_interview_reminder_email'), \
                mock.patch('apps.scholarship.emails'
                           '.send_reviewer_interview_reminder_email') as rev:
            call_command('send_interview_reminders')
        app.refresh_from_db()
        expected = (app.assigned_at + timedelta(days=5)).date().strftime('%d %b %Y')
        self.assertEqual(rev.call_args.kwargs['verdict_due'], expected)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestPerOrgStaffClocks(TestCase):
    """`temp_password_ttl_days` + `admin_dormant_days` — the staff clocks, per organisation.

    ⚠ ONE TTL, several readers: the invitation's own expiry, the rotate-dead cron and the login
    gate (which reads the number SERVED on the role payload) must all move together when an
    organisation tunes it — a screen saying "still valid" about a password the cron already
    rotated dead is the exact drift the shared derivation exists to prevent."""

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='sc-org', name='Staff Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='sc-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OrgAdmin SC', email='sc-oa@x.com')
        cls.rev = PartnerAdmin.objects.create(
            supabase_user_id='sc-rev', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Reviewer SC', email='sc-rev@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_a_staff_invitations_expiry_follows_the_organisations_ttl(self):
        from apps.scholarship import invitations
        _configure(self.org, 'temp_password_ttl_days', 3)
        inv = invitations.create_or_refresh(
            audience='staff', email='new@x.com', name='New', role='reviewer',
            organisation=self.org)
        self.assertAlmostEqual(
            (inv.expires_at - timezone.now()).total_seconds(), 3 * 86400, delta=10)
        # No organisation → the platform's 7 days, untouched.
        bare = invitations.create_or_refresh(
            audience='staff', email='bare@x.com', name='Bare', role='reviewer',
            organisation=None)
        self.assertAlmostEqual(
            (bare.expires_at - timezone.now()).total_seconds(), 7 * 86400, delta=10)

    def test_the_role_payload_serves_the_callers_resolved_ttl(self):
        _configure(self.org, 'temp_password_ttl_days', 3)
        self._auth('sc-rev')
        body = self.client.get('/api/v1/admin/role/').json()
        self.assertEqual(body['temp_password_ttl_days'], 3)

    def test_the_staff_list_serves_dormant_days_per_row(self):
        _configure(self.org, 'admin_dormant_days', 30)
        self._auth('sc-oa')
        body = self.client.get('/api/v1/admin/admins/').json()
        rows = {r['email']: r for r in body['admins']}
        self.assertEqual(rows['sc-rev@x.com']['dormant_days'], 30)

    @override_settings(SUPABASE_URL='https://sb.test', SUPABASE_SERVICE_ROLE_KEY='sk')
    def test_the_expiry_cron_rotates_on_the_organisations_clock(self):
        # Org TTL 1 day: a 3-day-old unchanged temp password rotates (both sc-org accounts).
        # The SAME age under the platform's 7 days (a NULL-org admin) is left alone.
        from unittest import mock
        from django.core.management import call_command
        _configure(self.org, 'temp_password_ttl_days', 1)
        PartnerAdmin.objects.create(
            supabase_user_id='sc-null', role='reviewer', is_active=True,
            owning_organisation=None, name='Platform Rev', email='sc-null@x.com')
        issued = (timezone.now() - timedelta(days=3)).isoformat()
        meta = {'must_change_password': True, 'temp_password_issued_at': issued}
        get = mock.Mock(status_code=200, json=lambda: {'user_metadata': dict(meta)})
        put = mock.Mock(status_code=200)
        with mock.patch('apps.courses.management.commands.expire_temp_passwords'
                        '.http_requests.get', return_value=get), \
                mock.patch('apps.courses.management.commands.expire_temp_passwords'
                           '.http_requests.put', return_value=put) as put_call:
            call_command('expire_temp_passwords')
        rotated_urls = [c.args[0] for c in put_call.call_args_list]
        self.assertEqual(len(rotated_urls), 2)
        self.assertTrue(any('sc-oa' in u for u in rotated_urls))
        self.assertTrue(any('sc-rev' in u for u in rotated_urls))
        self.assertFalse(any('sc-null' in u for u in rotated_urls))
