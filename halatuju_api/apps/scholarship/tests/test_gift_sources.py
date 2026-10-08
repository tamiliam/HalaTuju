"""Per-gift referral sources, Sprint 1 (owner, 2026-10-08) — each gift chooses its own sources.

What is pinned here:

1. **The seed** (`0172.seed_programme_sources`) on a PRODUCTION-SHAPED fixture: two active gifts
   and one inactive, seven active sources (one carrying the old single-gift FK), two switched-off
   sources, and two TENANT rows — one with `show_in_apply` off and one with it ON, to prove a
   tenant is never seeded as a source even when its flag says so.
2. **The gift's Configuration endpoint** lists only ACTIVE non-tenant sources with `on`, and its
   PUT validates the whole request (items AND sources) before writing anything, writes only what
   changed, and audits each change. Cross-org is 404. A new gift lists every source OFF.
3. **The Sources list** counts each source's gifts in ONE query, and the PATCH refuses the
   retired `programme_id`.
"""
from importlib import import_module

from django.apps import apps as live_apps
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.courses.models import PartnerOrganisation
from apps.scholarship import gift_sources
from apps.scholarship.models import (
    ApplicationItem, Programme, ProgrammeApplicationItem, ProgrammeReferralSource,
)
from apps.scholarship.tests.contract_helpers import brightpath_org, flagship
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_programme,
)

CONFIG = '/api/v1/admin/scholarship/programme/configuration/'
SOURCES = '/api/v1/admin/scholarship/sources/'
AUDIT_LOGGER = 'apps.scholarship.views_admin'

SEED = import_module('apps.scholarship.migrations.0172_programme_referral_sources')


def _source(code, name=None, show=True, active=True, **kw):
    return PartnerOrganisation.objects.create(
        code=code, name=name or code.upper(), show_in_apply=show, is_active=active, **kw)


def _links(programme):
    return set(ProgrammeReferralSource.objects.filter(programme=programme)
               .values_list('source__code', flat=True))


class TestTheSeed(TestCase):
    """The migration's data step, run against the live models on production's shape."""

    @classmethod
    def setUpTestData(cls):
        cls.bp = brightpath_org()                       # the tenant (owns the active gifts)
        cls.flag = flagship()                           # active, seeded by 0119
        cls.sabah = make_programme(organisation=cls.bp, code='bpb-sabah-2026', is_active=True)
        cls.testing = make_programme(organisation=cls.bp, code='testing', is_active=False)
        cls.active_codes = ['cumig', 'ewrf', 'hss', 'hyo', 'mhm', 'pptm']
        for code in cls.active_codes:
            _source(code)
        # The one source whose old single-gift FK is set: it goes on THAT gift only.
        _source('smc', programme=cls.sabah)
        _source('sathya_sai', show=False)                # switched off in Sources
        _source('tara', show=False)
        _source('suspended', show=True, active=False)    # flag on, but the org is suspended
        # A SECOND tenant with show_in_apply ON — still never a source. Tenant by its active
        # org_admin (no gift of its own), the other half of `tenants()`.
        cls.t2 = _source('tenant-two', show=True)
        make_admin('org_admin', owning_org=cls.t2)

    def test_the_fixture_is_productions_shape(self):
        # Preconditions, so a later migration that seeds another gift reads as a red here, not as
        # a mysteriously different count below.
        self.assertEqual(set(Programme.objects.filter(is_active=True).values_list('code', flat=True)),
                         {'brightpath-flagship', 'bpb-sabah-2026'})
        self.assertFalse(self.bp.show_in_apply)
        self.assertFalse(ProgrammeReferralSource.objects.exists())

    def test_every_active_gift_gets_every_active_source_and_the_set_gift_keeps_its_one(self):
        SEED.seed_programme_sources(live_apps, None)
        self.assertEqual(_links(self.flag), set(self.active_codes))
        self.assertEqual(_links(self.sabah), set(self.active_codes) | {'smc'})
        self.assertEqual(_links(self.testing), set())     # an inactive gift gets nothing
        self.assertEqual(ProgrammeReferralSource.objects.count(), 13)

    def test_no_tenant_switched_off_or_suspended_source_is_seeded(self):
        SEED.seed_programme_sources(live_apps, None)
        seeded = set(ProgrammeReferralSource.objects.values_list('source__code', flat=True))
        for code in ('brightpath', 'tenant-two', 'sathya_sai', 'tara', 'suspended'):
            self.assertNotIn(code, seeded)

    def test_it_is_idempotent_and_the_reverse_clears_it(self):
        SEED.seed_programme_sources(live_apps, None)
        SEED.seed_programme_sources(live_apps, None)
        self.assertEqual(ProgrammeReferralSource.objects.count(), 13)
        SEED.unseed_programme_sources(live_apps, None)
        self.assertFalse(ProgrammeReferralSource.objects.exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _ConfigBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_application_catalogue', verbosity=0)
        cls.org = make_org('gs-org')
        cls.gift = make_programme(organisation=cls.org, code='gs-gift', is_active=True)
        cls.other_org = make_org('gs-other')
        cls.foreign = make_programme(organisation=cls.other_org, code='gs-foreign', is_active=True)
        cls.oa = make_admin('org_admin', owning_org=cls.org)
        cls.smc = _source('smc', 'Sri Murugan Centre')
        cls.cumig = _source('cumig', 'Concerned UM Indian Graduates')
        cls.off = _source('tara', 'Tara Foundation', show=False)
        cls.suspended = _source('gone', 'Gone Org', active=False)
        ProgrammeReferralSource.objects.create(programme=cls.gift, source=cls.smc)

    def _get(self, query=''):
        return authed_client(self.oa).get(CONFIG + query)

    def _put(self, body, query=''):
        return authed_client(self.oa).put(CONFIG + query, body, format='json')


class TestTheConfigurationLists(_ConfigBase):
    def test_only_active_non_tenant_sources_by_name_with_on(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['sources'], [
            {'code': 'cumig', 'name': 'Concerned UM Indian Graduates', 'on': False},
            {'code': 'smc', 'name': 'Sri Murugan Centre', 'on': True},
        ])

    def test_a_tenant_is_never_offered_even_with_its_flag_on(self):
        PartnerOrganisation.objects.filter(pk=self.org.pk).update(show_in_apply=True)
        codes = [s['code'] for s in self._get().json()['sources']]
        self.assertNotIn('gs-org', codes)
        self.assertNotIn('gs-other', codes)
        self.assertEqual(codes, ['cumig', 'smc'])

    def test_a_new_gift_lists_every_source_OFF(self):
        """Owner: a new gift starts with NO sources — the form then shows only the defaults."""
        fresh = make_programme(organisation=self.org, code='gs-fresh', is_active=False)
        rows = self._get('?programme=gs-fresh').json()['sources']
        self.assertEqual([r['on'] for r in rows], [False, False])
        self.assertFalse(ProgrammeReferralSource.objects.filter(programme=fresh).exists())

    def test_a_cross_org_gift_is_404(self):
        self.assertEqual(self._get('?programme=gs-foreign').status_code, 404)


class TestTheConfigurationSaves(_ConfigBase):
    def test_switching_on_and_off_writes_only_the_change_and_audits_each(self):
        with self.assertLogs(AUDIT_LOGGER, 'INFO') as logs:
            resp = self._put({'sources': {'cumig': True, 'smc': False}})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(_links(self.gift), {'cumig'})
        lines = [r.getMessage() for r in logs.records if 'programme_source_set' in r.getMessage()]
        self.assertEqual(len(lines), 2)
        self.assertIn('AUDIT programme_source_set programme=gs-gift source=cumig was=off now=on',
                      lines[0] + lines[1])
        self.assertIn('source=smc was=on now=off', lines[0] + lines[1])
        self.assertEqual({r['code']: r['on'] for r in resp.json()['sources']},
                         {'cumig': True, 'smc': False})

    def test_a_row_already_in_that_state_is_neither_rewritten_nor_audited(self):
        before = ProgrammeReferralSource.objects.get(programme=self.gift, source=self.smc).pk
        with self.assertLogs(AUDIT_LOGGER, 'INFO') as logs:
            self._put({'sources': {'smc': True, 'cumig': False}})
            # assertLogs needs one line; a harmless marker keeps it honest about "none of ours".
            import logging
            logging.getLogger(AUDIT_LOGGER).info('marker')
        self.assertFalse([r for r in logs.records if 'programme_source_set' in r.getMessage()])
        self.assertEqual(
            ProgrammeReferralSource.objects.get(programme=self.gift, source=self.smc).pk, before)

    def test_items_and_sources_save_together(self):
        resp = self._put({'items': [{'kind': 'document', 'code': 'water_bill', 'state': 'required'}],
                          'sources': {'cumig': True}})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(_links(self.gift), {'smc', 'cumig'})
        self.assertTrue(ProgrammeApplicationItem.objects.filter(
            programme=self.gift, item__code='water_bill', state='required').exists())

    def test_a_bad_source_refuses_the_WHOLE_request_and_writes_nothing(self):
        for bad, code in (('nope', 'unknown_source'),        # no such code
                          ('tara', 'unknown_source'),        # switched off in Sources
                          ('gone', 'unknown_source'),        # suspended
                          ('gs-org', 'unknown_source')):     # a tenant
            with self.subTest(source=bad):
                resp = self._put({
                    'items': [{'kind': 'document', 'code': 'water_bill', 'state': 'required'}],
                    'sources': {'cumig': True, bad: True}})
                self.assertEqual(resp.status_code, 400, resp.content)
                self.assertEqual(resp.json()['code'], code)
                self.assertEqual(resp.json()['source'], bad)
                self.assertEqual(_links(self.gift), {'smc'})
                self.assertFalse(ProgrammeApplicationItem.objects.filter(
                    programme=self.gift, item__code='water_bill').exists())

    def test_a_non_boolean_or_a_non_map_is_refused(self):
        resp = self._put({'sources': {'cumig': 'yes'}})
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'bad_source_value'))
        resp = self._put({'sources': ['cumig']})
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'bad_sources'))
        self.assertEqual(_links(self.gift), {'smc'})

    def test_a_body_with_neither_items_nor_sources_is_refused(self):
        self.assertEqual(self._put({}).json()['code'], 'bad_items')

    def test_a_cross_org_gift_is_404_and_untouched(self):
        resp = self._put({'sources': {'cumig': True}}, '?programme=gs-foreign')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(ProgrammeReferralSource.objects.filter(programme=self.foreign).exists())

    def test_a_plain_admin_is_refused(self):
        admin = make_admin('admin', owning_org=self.org)
        resp = authed_client(admin).put(CONFIG, {'sources': {'cumig': True}}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(_links(self.gift), {'smc'})

    def test_the_catalogue_is_untouched_by_a_sources_only_save(self):
        n = ApplicationItem.objects.count()
        self._put({'sources': {'cumig': True}})
        self.assertEqual(ApplicationItem.objects.count(), n)
        self.assertFalse(ProgrammeApplicationItem.objects.filter(programme=self.gift).exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheSourcesPageCounts(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org('sc-org')
        cls.a = make_programme(organisation=cls.org, code='sc-a', is_active=True)
        cls.b = make_programme(organisation=cls.org, code='sc-b', is_active=True)
        cls.draft = make_programme(organisation=cls.org, code='sc-draft', is_active=False)
        cls.foreign = make_programme(code='sc-foreign', is_active=True)
        cls.oa = make_admin('org_admin', owning_org=cls.org)
        cls.smc = _source('smc', 'Sri Murugan Centre')
        cls.cumig = _source('cumig', 'Concerned UM Indian Graduates')
        for gift in (cls.a, cls.b, cls.draft, cls.foreign):
            ProgrammeReferralSource.objects.create(programme=gift, source=cls.smc)

    def _rows(self, client=None):
        resp = (client or authed_client(self.oa)).get(SOURCES)
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json(), {s['code']: s for s in resp.json()['sources']}

    def test_each_source_counts_its_ACTIVE_gifts_inside_the_callers_scope(self):
        _body, rows = self._rows()
        # The draft gift and another tenant's gift are not counted, and not in the total.
        self.assertEqual((rows['smc']['gift_count'], rows['smc']['gift_total']), (2, 2))
        self.assertEqual((rows['cumig']['gift_count'], rows['cumig']['gift_total']), (0, 2))

    def test_the_retired_single_gift_fields_are_gone(self):
        body, rows = self._rows()
        self.assertNotIn('programmes', body)
        self.assertNotIn('programme_id', rows['smc'])
        self.assertNotIn('programme_name', rows['smc'])

    def test_the_count_costs_ONE_query_whatever_the_number_of_sources(self):
        """The count is an annotation, never a query per row: more sources, same queries."""
        def queries():
            with CaptureQueriesContext(connection) as ctx:
                self._rows()
            return len(ctx.captured_queries)
        few = queries()
        for i in range(4):
            src = _source(f'extra{i}')
            ProgrammeReferralSource.objects.create(programme=self.a, source=src)
        self.assertEqual(queries(), few)

    def test_the_patch_refuses_programme_id_and_writes_nothing(self):
        resp = authed_client(self.oa).patch(
            f'{SOURCES}{self.cumig.id}/', {'programme_id': self.a.id, 'phone': '0123'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['code'], 'programme_id_retired')
        self.cumig.refresh_from_db()
        self.assertIsNone(self.cumig.programme_id)
        self.assertEqual(self.cumig.phone, '')

    def test_a_patch_answers_with_the_counted_row(self):
        resp = authed_client(self.oa).patch(
            f'{SOURCES}{self.smc.id}/', {'show_in_apply': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual((resp.json()['gift_count'], resp.json()['gift_total']), (2, 2))

    def test_a_new_source_joins_no_gift(self):
        resp = authed_client(self.oa).post(
            SOURCES, {'code': 'newsrc', 'name': 'New Source', 'show_in_apply': True},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual((resp.json()['gift_count'], resp.json()['gift_total']), (0, 2))
        self.assertFalse(ProgrammeReferralSource.objects.filter(source__code='newsrc').exists())


class TestTheHelpers(TestCase):
    def test_deleting_a_gift_takes_its_choices_and_keeps_the_sources(self):
        gift = make_programme(code='hp-gift')
        src = _source('hp-src')
        ProgrammeReferralSource.objects.create(programme=gift, source=src)
        gift.delete()
        self.assertFalse(ProgrammeReferralSource.objects.filter(source=src).exists())
        self.assertTrue(PartnerOrganisation.objects.filter(pk=src.pk).exists())

    def test_resolve_with_no_map_is_no_change(self):
        self.assertEqual(gift_sources.resolve_changes(None), {})
