"""Sources and referral partners, Sprint D (2026-10-19) — the clean-up.

1. **The sources' old rows are switched off, never deleted** (courses 0081): a `partner_organisations`
   row with a twin in `referral_sources` (same id AND code) that is neither the referral partner
   nor a tenant. CUMIG's row, the tenant, a partner without a twin, a row whose id is shared by a
   source of ANOTHER code — untouched. Idempotent.
2. **The expand / contract order**: 0081 gives `show_in_apply` a database default (the new image
   inserts without naming it) and 0082, after the deploy, drops it and `StudentProfile.source`.
3. **The bursary answer never reaches the partner logins' Source column**: a `?ref=cumig` student
   who then names SMC on the bursary form shows `cumig` to CUMIG's login, never `smc`.
4. **Referral partners — list, mark, unmark — super only**, with the refusals.
"""
from importlib import import_module

from django.apps import apps as live_apps
from django.test import TestCase, override_settings

from apps.courses import referral_links
from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship.models import ProgrammeReferralSource
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_cohort, make_org, make_programme,
    make_shortlistable_student, make_source, make_student,
)

EXPAND = import_module('apps.courses.migrations.0081_retire_old_source_rows')
CONTRACT = import_module('apps.courses.migrations.0082_drop_retired_source_columns')
LIST = '/api/v1/admin/referral-partners/'
PARTNER_LIST = '/api/v1/admin/students/'


def _row(code, **kw):
    kw.setdefault('name', code.upper())
    return PartnerOrganisation.objects.create(code=code, **kw)


class TestTheOldSourceRowsAreSwitchedOff(TestCase):
    """Production's shape after Sprint B: one tenant; CUMIG the referral partner with a source twin;
    SMC and EWRF old rows with twins (SATHYA already off); a referral partner with no twin; a loose
    row with no twin; a row sharing an id with a source of another code."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = make_org('sd-tenant')
        make_admin('org_admin', owning_org=cls.tenant)
        cls.cumig = _row('cumig', is_referral_partner=True)
        cls.smc = _row('smc')
        cls.ewrf = _row('ewrf')
        cls.sathya = _row('sathya_sai', is_active=False)
        cls.partner = _row('ptwo', is_referral_partner=True)
        cls.loose = _row('loose')
        cls.stranger = _row('stranger')
        for row in (cls.cumig, cls.smc, cls.ewrf, cls.sathya):
            make_source(cls.tenant, row.code, pk=row.pk)
        make_source(cls.tenant, 'not-stranger', pk=cls.stranger.pk)     # same id, another code
        # A tenant that also has a twin (it should never, but the rule must still leave it on).
        make_source(cls.tenant, cls.tenant.code, pk=cls.tenant.pk)

    def _active(self):
        return dict(PartnerOrganisation.objects.values_list('code', 'is_active'))

    def test_only_the_sources_old_rows_go_off(self):
        before = self._active()
        retired = EXPAND.retire_old_source_rows(live_apps, None)
        self.assertEqual(sorted(retired), sorted([self.smc.pk, self.ewrf.pk]))
        after = self._active()
        for code in ('smc', 'ewrf'):
            self.assertEqual((before[code], after[code]), (True, False), code)
        for code in ('cumig', 'ptwo', 'loose', 'stranger', 'sd-tenant', 'sathya_sai'):
            self.assertEqual(after[code], before[code], code)
        self.assertEqual(PartnerOrganisation.objects.count(), len(before))   # nothing deleted

    def test_it_is_idempotent_and_the_referral_partner_still_links(self):
        EXPAND.retire_old_source_rows(live_apps, None)
        self.assertEqual(EXPAND.retire_old_source_rows(live_apps, None), [])
        self.assertEqual(set(referral_links.referral_partners().values_list('code', flat=True)),
                         {'cumig', 'ptwo'})


class TestTheExpandContractOrder(TestCase):
    def test_the_expand_gives_show_in_apply_a_database_default(self):
        """The image without the field inserts `partner_organisations` rows without naming the
        column; until 0082 drops it, the database default must answer (it had none)."""
        alter = [op for op in EXPAND.Migration.operations
                 if getattr(op, 'name', None) == 'show_in_apply']
        self.assertEqual(len(alter), 1)
        self.assertIs(alter[0].field.db_default, False)

    def test_the_contract_follows_the_expand_and_drops_both_columns(self):
        self.assertIn(('courses', '0081_retire_old_source_rows'), CONTRACT.Migration.dependencies)
        self.assertEqual({(op.model_name, op.name) for op in CONTRACT.Migration.operations},
                         {('partnerorganisation', 'show_in_apply'), ('studentprofile', 'source')})
        self.assertNotIn('source', {f.name for f in StudentProfile._meta.fields})
        self.assertNotIn('show_in_apply', {f.name for f in PartnerOrganisation._meta.fields})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _World(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = make_org('sd-house')
        make_admin('org_admin', owning_org=cls.tenant)
        cls.gift = make_programme(organisation=cls.tenant, code='sd-gift', is_active=True)
        make_cohort(programme=cls.gift, code='sd-gift-2026', is_open=True, is_active=True)
        cls.cumig = _row('cumig', is_referral_partner=True)
        cls.login = make_admin('partner', org=cls.cumig)
        cls.smc = make_source(cls.tenant, 'smc')
        ProgrammeReferralSource.objects.create(programme=cls.gift, source=cls.smc)
        cls.super = make_admin('super', super_admin=True)


class TestTheBursaryAnswerNeverReachesThePartnerList(_World):
    def test_the_partner_login_sees_the_ref_code_never_the_bursary_answer(self):
        student = make_shortlistable_student()
        self.assertEqual(authed_client(student).post(
            '/api/v1/profile/sync/', {'referral_source': 'cumig'}, format='json').status_code, 200)
        self.assertEqual(authed_client(student).post('/api/v1/scholarship/applications/', {
            'household_income': 2500, 'receives_str': True, 'consent_to_contact': True,
            'programme_code': 'sd-gift', 'referral_source': 'smc'}, format='json').status_code, 201)
        body = authed_client(self.login).get(PARTNER_LIST).json()
        rows = [r for r in body['students'] if r['supabase_user_id'] == student.supabase_user_id]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['referral_source'], 'cumig')
        self.assertEqual(body['source_options'], ['cumig'])


class TestReferralPartnersAreMarkedBySuperOnly(_World):
    def _patch(self, admin, org, value):
        return authed_client(admin).patch(f'{LIST}{org.pk}/', {'is_referral_partner': value},
                                          format='json')

    def test_only_a_super_may_list_or_change(self):
        loose = _row('sd-loose')
        for role, kw in (('org_admin', {'owning_org': self.tenant}), ('admin', {'owning_org': self.tenant}),
                         ('partner', {'org': self.cumig}), ('reviewer', {})):
            with self.subTest(role=role):
                admin = make_admin(role, **kw)
                self.assertEqual(authed_client(admin).get(LIST).status_code, 403)
                self.assertEqual(self._patch(admin, loose, True).status_code, 403)
        loose.refresh_from_db()
        self.assertFalse(loose.is_referral_partner)

    def test_the_list_is_every_non_tenant_row_with_its_logins(self):
        _row('sd-off', is_active=False)
        body = authed_client(self.super).get(LIST).json()['organisations']
        by_code = {r['code']: r for r in body}
        self.assertNotIn('sd-house', by_code)                      # a tenant is another category
        self.assertEqual(by_code['cumig'], {'id': self.cumig.pk, 'code': 'cumig', 'name': 'CUMIG',
                                            'is_active': True, 'is_referral_partner': True,
                                            'partner_logins': 1})
        self.assertEqual(by_code['sd-off']['is_active'], False)
        self.assertEqual(body[0]['code'], 'cumig')                 # marked rows first

    def test_marking_makes_its_ref_link_collect_and_is_audited(self):
        loose = _row('sd-new')
        with self.assertLogs('apps.courses.views_referral_partners', 'INFO') as logs:
            resp = self._patch(self.super, loose, True)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['is_referral_partner'])
        self.assertIn(f'AUDIT referral_partner_marked org_id={loose.pk} by_admin={self.super.pk}',
                      logs.output[0])
        student = make_student()
        self.assertIn('referred_by_org', referral_links.apply_ref_code(student, 'sd-new'))

    def test_the_refusals(self):
        _row('other')                                              # a fixed form code
        off = _row('sd-retired', is_active=False)                  # a retired source row
        cases = ((self.tenant, True, 'org_is_tenant'),
                 (PartnerOrganisation.objects.get(code='other'), True, 'code_reserved'),
                 (off, True, 'org_inactive'),
                 (self.cumig, False, 'has_partner_logins'))
        for org, value, code in cases:
            with self.subTest(code=code):
                resp = self._patch(self.super, org, value)
                self.assertEqual(resp.status_code, 400, resp.content)
                self.assertEqual(resp.json()['code'], code)
                self.assertEqual(resp.json()['error'], referral_links.MARK_REFUSALS[code])
                org.refresh_from_db()
                self.assertEqual(org.is_referral_partner, not value)
        self.assertEqual(self._patch(self.super, off, 'yes').status_code, 400)
        self.assertEqual(authed_client(self.super).patch(
            f'{LIST}999999/', {'is_referral_partner': True}, format='json').status_code, 404)

    def test_unmarking_once_its_logins_are_revoked_stops_new_links_and_keeps_old_ones(self):
        linked = make_student(referred_by_org=self.cumig)
        self.login.is_active = False
        self.login.save(update_fields=['is_active'])
        resp = self._patch(self.super, self.cumig, False)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['partner_logins'], 0)
        self.assertEqual(referral_links.apply_ref_code(make_student(), 'cumig'), ['referral_source'])
        linked.refresh_from_db()
        self.assertEqual(linked.referred_by_org_id, self.cumig.pk)  # an existing link is kept
