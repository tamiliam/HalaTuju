"""Sprint M2b (decisions D2-D6, 2026-11-12): v2 page keys are STORED in `PartnerAdmin.permissions`.

Pinned here: the admin preset is derived (no money, no lead-only key); exactly the preset is grantable;
`stored_v2` reads only grantable keys; the OLD readers (`clean`, `resolve`, `holders`, `team_holding`,
the payment chain) never see a v2 key, so the old image is safe on rows 0097 has written; the label
seats nobody by itself, so an `admin` row the data step has not reached LOSES Admins (the step is
required).
"""
from importlib import import_module

from django.test import TestCase

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship.tests.factories import make_admin, make_org
_M0097 = import_module('apps.courses.migrations.0097_store_admin_v2_keys')   # M2b: same app


class AdminPreset(TestCase):
    def test_it_is_the_two_door_sets_in_catalogue_order(self):
        self.assertEqual(set(v2.ADMIN_PRESET_V2), {*v2.ORG_READ_V2, *v2.ADMIN_WORK_V2})
        self.assertEqual(v2.ADMIN_PRESET_V2, v2.v2_order(v2.ADMIN_PRESET_V2))
        self.assertEqual(len(v2.ADMIN_PRESET_V2), len(set(v2.ADMIN_PRESET_V2)))

    def test_it_holds_no_money_no_lead_only_and_no_never_grantable_key(self):
        for key in v2.ADMIN_PRESET_V2:
            with self.subTest(key=key):
                group, _page, _tier, lead_only = v2.CATALOGUE_V2[key]
                self.assertNotEqual(group, v2.MONEY)
                self.assertFalse(lead_only)
                self.assertNotIn(key, v2.NEVER_GRANTABLE)
                self.assertNotIn(key, v2.ALIAS_V2)

    def test_exactly_the_preset_is_grantable(self):
        self.assertEqual(v2.GRANTABLE_V2, v2.ADMIN_PRESET_V2)

    def test_the_label_presets(self):
        self.assertEqual(v2.V2_PRESETS, {'admin': v2.ADMIN_PRESET_V2, 'finance': v2.ORG_READ_V2})

    def test_the_label_grant_and_the_label_seat_are_gone(self):
        self.assertFalse(hasattr(v2, 'LABEL_GRANTS'))
        self.assertFalse(hasattr(st, 'ADMIN_ROLES'))

    def test_an_invited_admin_starts_with_it(self):
        self.assertEqual(st.invite_permissions('admin'), ['see_all', 'scholars', *v2.ADMIN_PRESET_V2])
        self.assertIsNone(st.invite_permissions('reviewer'))


class Refusals(TestCase):
    def test_never_grantable_keys_are_catalogue_keys_and_lead_only(self):
        self.assertEqual(set(v2.NEVER_GRANTABLE), {'billing.edit', 'requests.approve'})
        for key in v2.NEVER_GRANTABLE:
            self.assertTrue(v2.CATALOGUE_V2[key][3], key)

    def test_every_catalogue_key_has_one_answer(self):
        for key, (_g, _p, _t, lead_only) in v2.CATALOGUE_V2.items():
            with self.subTest(key=key):
                reason = v2.refusal_reason(key)
                if key in v2.NEVER_GRANTABLE:
                    self.assertEqual(reason, 'never_grantable')
                elif lead_only:
                    self.assertEqual(reason, 'lead_only')
                elif key in v2.ALIAS_V2:
                    self.assertEqual(reason, 'alias')
                else:
                    self.assertIsNone(reason)
                    self.assertIn(key, v2.GRANTABLE_V2)

    def test_the_aliases_are_what_an_old_key_already_means(self):
        meant = {k for keys in v2.ALIASES.values() for k in keys}
        self.assertEqual(set(v2.ALIAS_V2), meant & set(v2.CATALOGUE_V2))
        self.assertIn('students.view', v2.ALIAS_V2)
        self.assertIn('payments.approve', v2.ALIAS_V2)


class StoredV2(TestCase):
    def _row(self, role, permissions):
        return PartnerAdmin(role=role, permissions=permissions, is_active=True)

    def test_null_and_non_list_store_none(self):
        self.assertEqual(v2.stored_v2(self._row('admin', None)), ())
        self.assertEqual(v2.stored_v2(self._row('admin', {'team.view': True})), ())
        self.assertEqual(v2.stored_v2(None), ())

    def test_only_grantable_keys_in_catalogue_order(self):
        row = self._row('reviewer', ['mentoring.edit', 'review', 'team.view', 'billing.edit',
                                     'students.view', 'manage_team', 'nonsense', 7])
        self.assertEqual(v2.stored_v2(row), ('team.view', 'mentoring.edit'))

    def test_a_stored_page_key_opens_its_page_view_and_counts(self):
        row = self._row('reviewer', ['review', 'surveys.edit'])
        held = set(v2.effective_v2(row))
        self.assertTrue({'surveys.edit', 'surveys.view'} <= held)


class OldReadersIgnoreV2(TestCase):
    """The old image's compat (migrate-first, the 0095 precedent): v2 keys in a list change nothing it reads."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def test_clean_drops_every_v2_key(self):
        self.assertEqual(sp.clean([*v2.CATALOGUE_V2, 'see_all']), ('see_all',))
        self.assertEqual(sp.clean(list(v2.ADMIN_PRESET_V2)), ())

    def test_resolve_reads_the_old_part_only(self):
        a = make_admin('admin', owning_org=self.org)          # the post-0097 shape
        self.assertEqual(sp.resolve(a), sp.preset_for('admin'))
        self.assertTrue(set(v2.ADMIN_PRESET_V2) <= set(a.permissions))

    def test_holders_and_team_holding_ignore_v2(self):
        only_v2 = make_admin('reviewer', owning_org=self.org, permissions=['review', *v2.ADMIN_PRESET_V2])
        for key in sp.CATALOGUE:
            if key == 'review':
                continue
            with self.subTest(key=key):
                self.assertNotIn(only_v2, sp.holders(self.org, key))
        self.assertFalse(PartnerAdmin.objects.filter(sp.team_holding(['see_all', 'spending']),
                                                     pk=only_v2.pk).exists())
        self.assertTrue(PartnerAdmin.objects.filter(sp.team_holding(['review']), pk=only_v2.pk).exists())

    def test_the_payment_chain_ignores_v2(self):
        fin = make_admin('finance', owning_org=self.org, permissions=['payments_approve'])
        self.assertTrue(set(v2.ORG_READ_V2) <= set(fin.permissions))   # 0097's finance shape
        self.assertEqual([a.pk for a in sp.holders(self.org, 'payments_approve')], [fin.pk])
        self.assertFalse(any(fin.has_perm(k) for k in ('payments_prepare', 'payments_check', 'spending')))


class TheLabelSeatsNobody(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def test_an_unmigrated_admin_with_no_admin_key_loses_admins(self):
        # PINNED: the data step is required. Before M2b this row sat at Admins by its label alone.
        a = make_admin('admin', owning_org=self.org, permissions=['review'], pre_m2b=True)
        self.assertEqual(st.tables(a), ('reviewers',))
        self.assertFalse(st.may_read_org(a))
        self.assertFalse(st.may_do_admin_work(a))
        before, after = _M0097.plan_row(a.pk, a.role, a.is_active, a.permissions, row_id=None)
        PartnerAdmin.objects.filter(pk=a.pk).update(permissions=after)
        a.refresh_from_db()
        self.assertEqual(st.tables(a), ('admins', 'reviewers'))
        self.assertTrue(st.may_read_org(a) and st.may_do_admin_work(a))

    def test_a_stored_v2_key_seats_at_admins_and_an_unstorable_one_does_not(self):
        rev = make_admin('reviewer', owning_org=self.org, permissions=['review', 'sponsors.view'])
        self.assertTrue(st.in_admins(rev))
        bad = make_admin('reviewer', owning_org=self.org, permissions=['review', 'billing.edit'])
        self.assertFalse(st.in_admins(bad))
        self.assertNotIn('billing.edit', v2.effective_v2(bad))

    def test_an_inactive_row_sits_nowhere(self):
        a = make_admin('admin', owning_org=self.org, is_active=False,
                       permissions=['see_all', *v2.ADMIN_PRESET_V2])
        self.assertEqual(st.tables(a), ())
