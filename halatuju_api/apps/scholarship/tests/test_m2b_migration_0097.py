"""Sprint M2b (decision D10, 2026-11-12): courses 0097 stores, as v2 page keys, what the `admin` / `finance`
labels opened by themselves.

Done-when: each `admin` row, active or revoked, gains ADMIN_PRESET_V2 (a NULL row's preset materialised
first); each `finance` row with a list, active or revoked, gains ORG_READ_V2; a NULL `finance` row, the lead
tier, a super and a non-team login are untouched; the one row the owner named by id (O8) gains
ADMIN_PRESET_V2 while active;
every change has one truthful audit row; it is idempotent; it reverses exactly, NULLing a list left equal
to its preset, and never touches 0095's audit rows (nor 0095's reverse its). Run on the live app registry.
"""
from importlib import import_module
from unittest import mock

from django.apps import apps as live_apps
from django.test import TestCase

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses.models import PartnerAdmin
from apps.scholarship.models import StaffPermissionChange
from apps.scholarship.tests.factories import make_admin, make_org

M = import_module('apps.courses.migrations.0097_store_admin_v2_keys')
M0095 = import_module('apps.courses.migrations.0095_grant_scholars_key')
ADMIN = list(sp.preset_for('admin'))


class FrozenConstants(TestCase):
    def test_they_equal_the_live_code(self):
        self.assertEqual(M.PRESETS, {r: tuple(sp.preset_for(r)) for r in ('admin', 'finance', 'qc', 'reviewer')})
        self.assertEqual(M.ORG_READ, tuple(v2.ORG_READ_V2))
        self.assertEqual(M.ADMIN_PRESET, tuple(v2.ADMIN_PRESET_V2))

    def test_the_hand_sql_spells_the_same_lists_and_imports_no_app_code(self):
        doc = M.__doc__
        flat = ''.join(doc.split())
        self.assertIn('[' + ','.join(f'"{k}"' for k in M.ADMIN_PRESET) + ']', flat)
        self.assertIn('[' + ','.join(f'"{k}"' for k in M.ORG_READ) + ']', flat)
        for role, keys in M.PRESETS.items():
            self.assertIn(f"'{role}'THEN'[" + ','.join(f'"{k}"' for k in keys) + "]'"
                          if role != 'reviewer' else 'ELSE\'["review"]\'', flat)
        self.assertIn(f'id={M.ROW_ID}', flat)
        self.assertNotIn('staff_permissions_v2', open(M.__file__).read().split('"""', 2)[2])


class PlanRow(TestCase):
    """The pure rule, for each row shape (no database)."""

    def test_each_shape(self):
        P = M.ADMIN_PRESET
        cases = (
            ((1, 'admin', True, None), (ADMIN, [*ADMIN, *P])),
            ((1, 'admin', True, ['see_all']), (['see_all'], ['see_all', *P])),
            ((1, 'admin', True, ['see_all', 'team.view']),
             (['see_all', 'team.view'], ['see_all', 'team.view', *(k for k in P if k != 'team.view')])),
            ((1, 'admin', True, [*ADMIN, *P]), None),                                # already done
            ((1, 'finance', True, ['payments_approve']),
             (['payments_approve'], ['payments_approve', *M.ORG_READ])),
            ((1, 'finance', True, None), None),                                      # NULL finance
            ((1, 'admin', False, ['see_all']), (['see_all'], ['see_all', *P])),      # revoked: the same
            ((1, 'admin', False, None), (ADMIN, [*ADMIN, *P])),
            ((1, 'finance', False, ['payments_approve']),
             (['payments_approve'], ['payments_approve', *M.ORG_READ])),
            ((1, 'finance', False, None), None),
            ((1, 'reviewer', True, ['review', 'see_all']), None),
            ((1, 'qc', True, None), None),
            ((M.ROW_ID, 'reviewer', True, ['review', 'see_all', 'spending']),
             (['review', 'see_all', 'spending'], ['review', 'see_all', 'spending', *P])),
            ((M.ROW_ID, 'reviewer', True, None), (['review'], ['review', *P])),
            ((M.ROW_ID, 'reviewer', False, ['review']), None),
            ((M.ROW_ID, 'org_admin', True, None), None),
            ((1, 'org_admin', True, None), None),
            ((1, 'org_admin', True, ['review']), None),                              # a lead on Reviewers
            ((1, 'super', True, None), None),
            ((1, 'partner', True, None), None),
            ((1, 'admin', True, {'see_all': True}), None),                           # not a list
        )
        for args, expected in cases:
            with self.subTest(args=args):
                got = M.plan_row(*args)
                self.assertEqual(got, None if expected is None else (list(expected[0]), list(expected[1])))

    def test_the_factory_never_applies_the_row_id_grant(self):
        self.assertIsNone(M.plan_row(M.ROW_ID, 'reviewer', True, ['review'], row_id=None))


class ForwardAndBack(TestCase):
    @classmethod
    def setUpTestData(cls):
        org = make_org()

        def person(role, keys=None, **kw):
            return make_admin(role, owning_org=org, pre_m2b=True, permissions=keys, **kw)
        cls.admin_list = person('admin', ['see_all', 'scholars', 'spending'])
        cls.admin_null = person('admin')
        cls.fin_list = person('finance', ['payments_approve', 'see_all'])
        cls.fin_null = person('finance')
        cls.reviewer = person('reviewer', ['review', 'see_all'])
        cls.qc = person('qc')
        cls.revoked_admin = person('admin', ['see_all'], is_active=False)
        cls.revoked_fin = person('finance', ['payments_approve', 'see_all'], is_active=False)  # not the preset
        cls.lead = person('org_admin')
        cls.lead_reviewing = person('org_admin', ['review'])
        cls.untouched = (cls.fin_null, cls.reviewer, cls.qc, cls.lead, cls.lead_reviewing)

    def _before(self):
        return {a.pk: PartnerAdmin.objects.get(pk=a.pk).permissions
                for a in (self.admin_list, self.admin_null, self.fin_list, self.revoked_admin, self.revoked_fin,
                          *self.untouched)}

    def perms(self, a):
        return PartnerAdmin.objects.get(pk=a.pk).permissions

    def test_forward_writes_each_shape_with_one_truthful_audit_row(self):
        changed = M.store_v2_keys(live_apps, None)
        self.assertEqual(sorted(changed), sorted([self.admin_list.pk, self.admin_null.pk, self.fin_list.pk,
                                                  self.revoked_admin.pk, self.revoked_fin.pk]))
        self.assertEqual(self.perms(self.revoked_admin), ['see_all', *v2.ADMIN_PRESET_V2])
        self.assertEqual(self.perms(self.revoked_fin), ['payments_approve', 'see_all', *v2.ORG_READ_V2])
        self.assertEqual(self.perms(self.admin_list), ['see_all', 'scholars', 'spending', *v2.ADMIN_PRESET_V2])
        self.assertEqual(self.perms(self.admin_null), [*ADMIN, *v2.ADMIN_PRESET_V2])
        self.assertEqual(self.perms(self.fin_list), ['payments_approve', 'see_all', *v2.ORG_READ_V2])
        for a in self.untouched:
            self.assertEqual(self.perms(a), a.permissions, a.role)
        rows = {r.target_id: r for r in StaffPermissionChange.objects.all()}
        self.assertEqual(set(rows), set(changed))
        null_row = rows[self.admin_null.pk]
        self.assertEqual((null_row.kind, null_row.role, null_row.changed_by_email, null_row.changed_by_role,
                          null_row.before, null_row.after),
                         ('edit', 'admin', '', 'migration', ADMIN, [*ADMIN, *v2.ADMIN_PRESET_V2]))
        self.assertEqual(null_row.target_email, self.admin_null.email or '')

    def test_it_is_idempotent(self):
        M.store_v2_keys(live_apps, None)
        after = self._before()
        self.assertEqual(M.store_v2_keys(live_apps, None), [])
        self.assertEqual(self._before(), after)
        self.assertEqual(StaffPermissionChange.objects.count(), 5)

    def test_backwards_restores_every_row_and_removes_only_its_audit_rows(self):
        before = self._before()
        other = StaffPermissionChange.objects.create(
            target_id=self.reviewer.pk, organisation_id=self.reviewer.owning_organisation_id, kind='edit',
            role='reviewer', before=['review'], after=['review', 'see_all'],
            changed_by_email='lead@example.test', changed_by_role='org_admin')
        M.store_v2_keys(live_apps, None)
        M.remove_v2_keys(live_apps, None)
        self.assertEqual(self._before(), before)                     # the NULL admin is NULL again
        self.assertEqual(list(StaffPermissionChange.objects.values_list('pk', flat=True)), [other.pk])

    def test_backwards_keeps_a_key_a_lead_added_since_and_leaves_a_custom_list_custom(self):
        M.store_v2_keys(live_apps, None)
        PartnerAdmin.objects.filter(pk=self.admin_null.pk).update(
            permissions=[*ADMIN, *v2.ADMIN_PRESET_V2, 'sources.view'])  # already there: no change
        PartnerAdmin.objects.filter(pk=self.fin_list.pk).update(
            permissions=['payments_approve', 'see_all', 'team.view', 'sponsors.view'])   # one v2 key removed
        M.remove_v2_keys(live_apps, None)
        self.assertIsNone(self.perms(self.admin_null))
        self.assertEqual(self.perms(self.fin_list), ['payments_approve', 'see_all'])

    def test_the_named_row_gains_the_admin_preset(self):
        # The live row's id is ROW_ID; here the rule is pointed at a test row's id (plan_row's own
        # default is pinned in PlanRow). The forward step reads `plan_row` from the module.
        row = make_admin('reviewer', owning_org=self.lead.owning_organisation, pre_m2b=True,
                         permissions=['review', 'see_all'])
        real = M.plan_row
        with mock.patch.object(M, 'plan_row', lambda *a, **k: real(*a, row_id=row.pk)):
            changed = M.store_v2_keys(live_apps, None)
        self.assertIn(row.pk, changed)
        self.assertEqual(self.perms(row), ['review', 'see_all', *v2.ADMIN_PRESET_V2])
        self.assertEqual(self.perms(self.reviewer), ['review', 'see_all'])   # any other reviewer: untouched
        M.remove_v2_keys(live_apps, None)
        self.assertEqual(self.perms(row), ['review', 'see_all'])


class AlongsideMigration0095(TestCase):
    @classmethod
    def setUpTestData(cls):
        org = make_org()
        cls.admin = make_admin('admin', owning_org=org, pre_m2b=True, permissions=['see_all', 'spending'])

    def test_each_reverse_touches_only_its_own_rows(self):
        M0095.grant_scholars(live_apps, None)
        M.store_v2_keys(live_apps, None)
        self.assertEqual(PartnerAdmin.objects.get(pk=self.admin.pk).permissions,
                         ['see_all', 'spending', 'scholars', *v2.ADMIN_PRESET_V2])
        self.assertEqual(StaffPermissionChange.objects.count(), 2)
        M.remove_v2_keys(live_apps, None)
        self.assertEqual(PartnerAdmin.objects.get(pk=self.admin.pk).permissions, ['see_all', 'spending', 'scholars'])
        self.assertEqual(StaffPermissionChange.objects.count(), 1)
        M.store_v2_keys(live_apps, None)
        M0095.withdraw_scholars(live_apps, None)
        self.assertEqual(PartnerAdmin.objects.get(pk=self.admin.pk).permissions,
                         ['see_all', 'spending', *v2.ADMIN_PRESET_V2])
        self.assertEqual(StaffPermissionChange.objects.get().changed_by_role, 'migration')
