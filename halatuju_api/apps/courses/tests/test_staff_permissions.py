"""Request #39 Sprint 1 — `apps/courses/staff_permissions.py`, `PartnerAdmin.permission_set` / `has_perm`,
and what `/admin/role/` serves.

The golden table (`test_permission_presets.py`) proves the PRESETS reproduce today's gates. This file
holds the module's own rules: NULL is the preset, a stored list is read fail-closed, the lead tier and
the platform roles are not editable, a typo raises, and `holders` counts members, never a super.
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses import staff_permissions as sp
from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.tests.factories import make_admin

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


class Resolve(TestCase):
    def test_null_is_the_preset_of_the_role(self):
        for role, preset in sp.PRESETS.items():
            with self.subTest(role=role):
                a = PartnerAdmin(role=role)
                self.assertIsNone(a.permissions)
                self.assertEqual(set(a.permission_set), set(preset))
                self.assertFalse(sp.is_custom(a))

    def test_a_stored_list_replaces_the_preset(self):
        # Rohini's combination (Sprint 4 will make it through the screen; S3 by a reviewed update).
        a = PartnerAdmin(role='reviewer', permissions=['review', 'spending'])
        self.assertEqual(a.permission_set, ('review', 'spending'))
        self.assertTrue(a.has_perm('spending'))
        self.assertFalse(a.has_perm('see_all'))
        self.assertTrue(sp.is_custom(a))

    def test_an_empty_stored_list_holds_nothing(self):
        a = PartnerAdmin(role='admin', permissions=[])
        self.assertEqual(a.permission_set, ())
        self.assertTrue(sp.is_custom(a))

    def test_a_stored_list_is_read_fail_closed(self):
        a = PartnerAdmin(role='reviewer', permissions=[
            'review', 'review', 'bogus', 7, 'manage_team', 'qc'])
        # unknown and non-string dropped; manage_team is never granted; qc without see_all dropped
        self.assertEqual(a.permission_set, ('review',))

    def test_qc_with_see_all_is_kept(self):
        a = PartnerAdmin(role='reviewer', permissions=['qc', 'see_all'])
        self.assertEqual(a.permission_set, ('see_all', 'qc'))

    def test_a_non_list_is_read_as_nothing(self):
        for junk in ({'review': True}, 'review', 5):
            with self.subTest(junk=str(junk)):
                self.assertEqual(PartnerAdmin(role='reviewer', permissions=junk).permission_set, ())

    def test_the_lead_tier_ignores_a_stored_list(self):
        a = PartnerAdmin(role='org_admin', permissions=['review'])
        self.assertEqual(set(a.permission_set), set(sp.LEAD_TIER))
        self.assertFalse(sp.is_custom(a))
        self.assertTrue(sp.is_lead_tier(a))

    def test_a_super_holds_every_key_by_flag_or_by_role(self):
        for a in (PartnerAdmin(role='reviewer', is_super_admin=True), PartnerAdmin(role='super')):
            with self.subTest(role=a.role):
                self.assertEqual(a.permission_set, sp.CATALOGUE)
                self.assertFalse(sp.is_lead_tier(a))
                self.assertFalse(sp.is_custom(a))

    def test_a_partner_holds_nothing_whatever_is_stored(self):
        a = PartnerAdmin(role='partner', permissions=['review', 'see_all'])
        self.assertEqual(a.permission_set, ())
        self.assertFalse(sp.is_custom(a))

    def test_an_unknown_key_raises(self):
        with self.assertRaises(KeyError):
            PartnerAdmin(role='super').has_perm('reveiw')

    def test_none_holds_nothing(self):
        self.assertEqual(sp.resolve(None), ())
        self.assertFalse(sp.is_custom(None))
        self.assertFalse(sp.is_lead_tier(None))

    def test_the_catalogue_is_eight_keys_and_presets_use_only_them(self):
        self.assertEqual(len(sp.CATALOGUE), 8)
        for preset in list(sp.PRESETS.values()) + [sp.LEAD_TIER]:
            self.assertTrue(set(preset) <= set(sp.CATALOGUE))
        # no team preset holds a lead-tier-only key, and every preset keeps qc => see_all
        for role, preset in sp.PRESETS.items():
            self.assertFalse(set(preset) & sp.LEAD_TIER_ONLY, role)
            if 'qc' in preset:
                self.assertIn('see_all', preset, role)


class TheDjangoAdminCannotEditThem(TestCase):
    def test_permissions_is_read_only_until_the_sprint_4_editor(self):
        # A hand edit in /admin/ would skip every rule the editor enforces (review fix 4).
        from django.contrib import admin as django_admin
        self.assertIn('permissions', django_admin.site._registry[PartnerAdmin].readonly_fields)


class Holders(TestCase):
    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='h-org', name='H')
        self.other = PartnerOrganisation.objects.create(code='h-other', name='Other')

    def test_counts_active_members_of_this_organisation_only(self):
        fin = make_admin('finance', owning_org=self.org)
        make_admin('finance', owning_org=self.org, is_active=False)
        make_admin('finance', owning_org=self.other)
        self.assertEqual(sp.holders(self.org, 'payments_check'), [fin])

    def test_a_super_is_never_a_holder_even_when_bound_to_the_organisation(self):
        make_admin('super', super_admin=True, owning_org=self.org)
        make_admin('admin', super_admin=True, owning_org=self.org)
        self.assertEqual(sp.holders(self.org, 'payments_check'), [])

    def test_a_stored_grant_counts(self):
        a = make_admin('admin', owning_org=self.org, permissions=['payments_check'])
        self.assertEqual(sp.holders(self.org, 'payments_check'), [a])

    def test_the_lead_tier_holds_its_bundle(self):
        oa = make_admin('org_admin', owning_org=self.org)
        self.assertEqual(sp.holders(self.org, 'payments_approve'), [oa])
        self.assertEqual(sp.holders(self.org, 'payments_check'), [])

    def test_no_organisation_and_unknown_key(self):
        self.assertEqual(sp.holders(None, 'review'), [])
        with self.assertRaises(KeyError):
            sp.holders(self.org, 'nope')


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TheRoleEndpointServesThem(TestCase):
    """`GET /admin/role/` adds `permissions` (always RESOLVED, never null), `preset` and `custom`;
    `role` stays, so a bundle from before this change keeps working."""

    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='r-org', name='R')
        self.client = APIClient()

    def _get(self, a):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(a.supabase_user_id)}')
        r = self.client.get('/api/v1/admin/role/')
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_every_role_is_served_its_resolved_set(self):
        cases = {
            'reviewer': make_admin('reviewer', owning_org=self.org),
            'admin': make_admin('admin', owning_org=self.org),
            'finance': make_admin('finance', owning_org=self.org),
            'qc': make_admin('qc', owning_org=self.org),
            'org_admin': make_admin('org_admin', owning_org=self.org),
            'partner': make_admin('partner'),
            'super': make_admin('super', super_admin=True),
        }
        for role, a in cases.items():
            with self.subTest(role=role):
                body = self._get(a)
                self.assertEqual(body['role'], role)
                self.assertEqual(body['preset'], role)
                self.assertEqual(body['permissions'], list(sp.resolve(a)))
                self.assertIs(body['custom'], False)

    def test_a_custom_set_is_served_resolved_and_marked(self):
        a = make_admin('reviewer', owning_org=self.org, permissions=['spending', 'review', 'bogus'])
        body = self._get(a)
        self.assertEqual(body['permissions'], ['review', 'spending'])
        self.assertEqual(body['preset'], 'reviewer')
        self.assertIs(body['custom'], True)
