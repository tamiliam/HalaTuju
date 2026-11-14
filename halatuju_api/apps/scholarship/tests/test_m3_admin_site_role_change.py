"""Sprint M3a review (2026-11-14): a role change on the Django admin screen resets the stored keys.

`role` is editable on `apps/courses/admin.py`'s `PartnerAdminAdmin` while `permissions` is read-only. Since M3a
an organisation admin STORES its keys, so a role change that kept them would carry them to the new role. A save
that changes `role` sets `permissions` to NULL (exactly the pre-M3a reading) and writes one
`staff_permission_changes` row, kind 'role_change', through the editor's own writer.
"""
from unittest import mock

from django.test import TestCase

from apps.courses import staff_activity_hook
from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship.models import StaffPermissionChange
from apps.scholarship.tests.factories import admin_site_role_change, make_admin, make_org


def _reads(a):
    return {'resolve': sp.resolve(a), 'effective_v2': v2.effective_v2(a), 'tables': st.tables(a),
            'doors': {d: st.opens_door(a, d) for d in st.DOOR_KEYS}}


class DemotingAMigratedOrgAdmin(TestCase):
    """Demoted, the row reads as a NULL row of the new role does today: that role's preset, no page key."""

    def setUp(self):
        self.org = make_org()

    def test_to_each_role_gives_that_roles_preset(self):
        for role in ('reviewer', 'admin', 'finance'):
            with self.subTest(role=role):
                lead = make_admin('org_admin', owning_org=self.org, permissions=['review'])
                self.assertEqual(lead.permissions, ['review', *v2.ORG_ADMIN_SET])     # migrated by 0098
                held = [*sp.resolve(lead), *v2.org_admin_v2(lead)]
                after = admin_site_role_change(lead, role)
                self.assertEqual((after.role, after.permissions), (role, None))
                self.assertEqual(sp.resolve(after), sp.preset_for(role))
                self.assertEqual(v2.stored_v2(after), ())
                fresh = make_admin(role, owning_org=self.org, pre_m2b=True)          # a NULL row of the role
                self.assertEqual(_reads(after), _reads(fresh))
                row = StaffPermissionChange.objects.get(target_id=lead.pk)
                self.assertEqual((row.kind, row.role, row.changed_by_role, row.changed_by_email),
                                 ('role_change', role, 'django_admin', 'site-admin@example.test'))
                self.assertEqual((row.before, row.after), (held, list(sp.preset_for(role))))

    def test_the_names_the_old_keys_opened_are_gone(self):
        lead = make_admin('org_admin', owning_org=self.org)
        self.assertTrue({'sponsors.view', 'invitations.view'} <= set(v2.effective_v2(lead)))
        after = admin_site_role_change(lead, 'reviewer')
        self.assertFalse(set(v2.effective_v2(after)) & {'sponsors.view', 'invitations.view'})
        self.assertNotIn('see_all', sp.resolve(after))


class PromotingToOrgAdmin(TestCase):
    """Promoted, a row holding its 0097 list reads as the full organisation-admin set, with no payment seat."""

    def setUp(self):
        self.org = make_org()

    def test_an_admin_or_finance_row_reads_as_the_full_set(self):
        rows = {
            'admin': make_admin('admin', owning_org=self.org,
                                permissions=['see_all', 'scholars', 'spending', 'payments_prepare']),
            'finance': make_admin('finance', owning_org=self.org, permissions=['payments_approve']),
        }
        lead = make_admin('org_admin', owning_org=self.org)                        # the shape 0098 leaves
        for name, row in rows.items():
            with self.subTest(role=name):
                self.assertTrue(row.permissions)                                    # its 0097 list
                after = admin_site_role_change(row, 'org_admin')
                self.assertEqual((after.role, after.permissions), ('org_admin', None))
                self.assertEqual(sp.resolve(after), sp.preset_for('org_admin'))
                self.assertEqual(v2.effective_v2(after), v2.effective_v2(lead))
                self.assertEqual(st.tables(after), st.tables(lead))
                for seat in ('payments_prepare', 'payments_check', 'payments_approve'):
                    self.assertNotIn(seat, sp.resolve(after))
                    self.assertNotIn(after.pk, [h.pk for h in sp.holders(self.org, seat)], seat)
                self.assertEqual(StaffPermissionChange.objects.get(target_id=row.pk).kind, 'role_change')


class OnlyARoleChangeResets(TestCase):

    def test_a_save_that_keeps_the_role_keeps_the_keys_and_writes_nothing(self):
        lead = make_admin('org_admin', owning_org=make_org(), permissions=['review'])
        after = admin_site_role_change(lead, 'org_admin')
        self.assertEqual(after.permissions, ['review', *v2.ORG_ADMIN_SET])
        self.assertFalse(StaffPermissionChange.objects.exists())

    def test_with_no_audit_writer_the_change_is_refused_whole(self):
        lead = make_admin('org_admin', owning_org=make_org())
        with mock.patch.object(staff_activity_hook, 'PERMISSION_RECORDER', None):
            with self.assertRaises(RuntimeError):
                admin_site_role_change(lead, 'reviewer')
        row = PartnerAdmin.objects.get(pk=lead.pk)
        self.assertEqual((row.role, row.permissions), ('org_admin', list(v2.ORG_ADMIN_SET)))
