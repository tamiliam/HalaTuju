"""Sprint M2b (the one principle, 2026-11-12): on ship day NOBODY's pages change — except the one row the
owner named by id (O8), who gains the admin work pages.

Each live row shape is made as it stood BEFORE M2b (`pre_m2b=True`), read with a hand-written copy of the
OLD rule (the `admin` / `finance` labels seated their holder at Admins; the `admin` label opened the admin
work pages), then put through migration 0097's `plan_row` and read with the NEW code (stored keys only).
The tables, the v2 page keys and every door in `staff_tables.DOOR_KEYS` must answer the same.
"""
from importlib import import_module

from django.test import TestCase

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship.tests.factories import make_admin, make_org

M = import_module('apps.courses.migrations.0097_store_admin_v2_keys')


def _old_in_admins(a):
    """`staff_tables.in_admins` as it stood before M2b (main 4728cc534)."""
    if a is None or not a.is_active:
        return False
    if a.is_super or sp.is_lead_tier(a):
        return True
    if not st._team_member(a):
        return False
    return a.role in ('admin', 'finance') or bool(st.admin_keys(a))


def _old_effective(a):
    """`staff_permissions_v2.effective_v2` as it stood before M2b: the `admin` label granted the admin work
    pages (`LABEL_GRANTS`) and the label-or-key Admins seat granted the organisation read pages."""
    if a.is_super or not a.is_active or a.role == sp.LEAD_ROLE or a.role not in sp.TEAM_ROLES:
        return v2.effective_v2(a)                  # unchanged by M2b: no stored-key branch reached
    held = set(v2.through_aliases(sp.resolve(a)))
    if _old_in_admins(a):
        held.update(v2.ORG_READ_V2)
    if a.role == 'admin':
        held.update(v2.ADMIN_WORK_V2)
    return v2.with_implied_views(held)


def _old_tables(a):
    return tuple(t for t, rule in ((st.ADMINS, _old_in_admins), (st.REVIEWERS, st.in_reviewers),
                                   (st.MENTORS, st.in_mentors)) if rule(a))


def _doors(held):
    return {door: all(k in held for k in keys) for door, keys in st.DOOR_KEYS.items()}


class NobodyChanges(TestCase):
    @classmethod
    def setUpTestData(cls):
        org = make_org()

        def shape(role, keys=None, **kw):
            return make_admin(role, owning_org=org, pre_m2b=True, permissions=keys, **kw)
        cls.shapes = {
            'admin, stored (the live shape)': shape('admin', ['see_all', 'scholars', 'spending', 'payments_prepare']),
            'admin, stored, no admin key': shape('admin', ['review']),
            'admin, NULL': shape('admin'),
            'finance, stored': shape('finance', ['payments_approve']),
            'finance, stored, no admin key': shape('finance', ['review']),
            'finance, NULL': shape('finance'),
            'reviewer with admin keys (not the named row)': shape('reviewer', ['review', 'see_all', 'spending']),
            'reviewer, NULL': shape('reviewer'),
            'qc, NULL': shape('qc'),
            'qc, stored': shape('qc', ['qc', 'see_all']),
            'org_admin': shape('org_admin'),
            'org_admin, stored [review] (a lead added to Reviewers)': shape('org_admin', ['review']),
            'super': make_admin('admin', owning_org=org, super_admin=True),
            'inactive admin': shape('admin', ['see_all'], is_active=False),
            'partner': shape('partner'),
        }
        cls.named = shape('reviewer', ['review', 'see_all', 'spending'])

    def migrate(self, a, *, row_id=None):
        plan = M.plan_row(a.pk, a.role, a.is_active, a.permissions, row_id=row_id)
        if plan is not None:
            PartnerAdmin.objects.filter(pk=a.pk).update(permissions=plan[1])
        return PartnerAdmin.objects.get(pk=a.pk)

    def test_every_shape_keeps_its_tables_its_keys_and_every_door(self):
        for name, before in self.shapes.items():
            with self.subTest(shape=name):
                old_tables, old_keys = _old_tables(before), _old_effective(before)
                after = self.migrate(before)
                self.assertEqual(st.tables(after), old_tables)
                self.assertEqual(v2.effective_v2(after), old_keys)
                self.assertEqual(st.page_keys(after), tuple(old_keys) if after.is_active else ())
                self.assertEqual({d: st.opens_door(after, d) for d in st.DOOR_KEYS}, _doors(set(old_keys)))
                self.assertEqual(sp.resolve(after), sp.resolve(before))       # the old part: untouched

    def test_the_label_alone_no_longer_seats_anyone(self):
        # the reason the data step is REQUIRED: unmigrated, the label-only admin loses Admins
        unmigrated = self.shapes['admin, stored, no admin key']
        self.assertEqual(_old_tables(unmigrated), (st.ADMINS, st.REVIEWERS))
        self.assertEqual(st.tables(unmigrated), (st.REVIEWERS,))

    def test_only_the_named_row_gains_and_it_gains_the_admin_work_pages(self):
        old = set(_old_effective(self.named))
        self.assertTrue(set(v2.ORG_READ_V2) <= old)                             # it sat at Admins by a key
        after = self.migrate(self.named, row_id=self.named.pk)
        new = set(v2.effective_v2(after))
        self.assertEqual(new - old, set(v2.ADMIN_WORK_V2) - set(v2.ORG_READ_V2))
        self.assertFalse(old - new)
        self.assertTrue(st.may_do_admin_work(after))
        self.assertEqual(st.tables(after), _old_tables(self.named))
