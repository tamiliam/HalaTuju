"""A1.10b / TD-064: `role` is the ONLY super marker; the legacy `is_super_admin` flag is retired.

Every row here is a super by ROLE ALONE — the shape the new code writes (it no longer sets the flag).
Before TD-064 the doors below read the flag directly, so a role-only super was refused on them. Each
door is a matrix: the super is allowed, an organisation admin and a reviewer are refused.
"""
from django.db import connection
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org,
)

ROLE = '/api/v1/admin/role/'
ORGS = '/api/v1/admin/orgs/'
STUDENT = '/api/v1/admin/students/td064-no-such-student/'
STAFF = '/api/v1/admin/admins/'


class TheFlagIsGone(TestCase):
    def test_the_model_has_no_flag_and_is_super_reads_the_role(self):
        names = {f.name for f in PartnerAdmin._meta.get_fields()}
        self.assertNotIn('is_super_admin', names)
        self.assertTrue(PartnerAdmin(role='super').is_super)
        for role in ('org_admin', 'admin', 'reviewer', 'qc', 'finance', 'partner'):
            with self.subTest(role=role):
                self.assertFalse(PartnerAdmin(role=role).is_super)

    def test_a_new_row_inserts_while_the_column_is_still_in_the_database(self):
        """Step 1 keeps the column (the old image reads it); the migration gives it a DB default,
        so an INSERT that no longer names it passes its NOT NULL."""
        with connection.cursor() as cur:
            cols = [c.name for c in connection.introspection.get_table_description(cur, 'partner_admins')]
        self.assertIn('is_super_admin', cols)
        a = PartnerAdmin.objects.create(email='td064-new@x.com', name='New', role='reviewer')
        with connection.cursor() as cur:
            cur.execute('SELECT is_super_admin FROM partner_admins WHERE id = %s', [a.pk])
            self.assertFalse(cur.fetchone()[0])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class RoleOnlySuperDoors(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.super = make_admin('super')
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)

    def _status(self, admin, method, url):
        return getattr(authed_client(admin), method)(url).status_code

    def test_referral_partners_dropdown(self):
        self.assertEqual(self._status(self.super, 'get', ORGS), 200)
        self.assertEqual(self._status(self.org_admin, 'get', ORGS), 403)
        self.assertEqual(self._status(self.reviewer, 'get', ORGS), 403)

    def test_student_delete_is_super_only(self):
        # The super passes the door and meets the missing student; the others never reach it.
        self.assertEqual(self._status(self.super, 'delete', STUDENT), 404)
        self.assertEqual(self._status(self.org_admin, 'delete', STUDENT), 403)
        self.assertEqual(self._status(self.reviewer, 'delete', STUDENT), 403)

    def test_role_answer_carries_the_super_marker_from_the_role(self):
        self.assertIs(authed_client(self.super).get(ROLE).json()['is_super_admin'], True)
        self.assertIs(authed_client(self.org_admin).get(ROLE).json()['is_super_admin'], False)
        self.assertIs(authed_client(self.reviewer).get(ROLE).json()['is_super_admin'], False)

    def test_people_list_marks_the_super_by_role(self):
        rows = authed_client(self.super).get(STAFF).json()
        rows = rows.get('admins', rows) if isinstance(rows, dict) else rows
        by_id = {r['id']: r for r in rows}
        self.assertIs(by_id[self.super.pk]['is_super_admin'], True)
        self.assertIs(by_id[self.reviewer.pk]['is_super_admin'], False)

    def test_a_super_is_never_revoked(self):
        other = make_admin('super')
        res = authed_client(self.super).patch(f'{STAFF}{other.pk}/revoke/', {'action': 'revoke'},
                                             format='json')
        self.assertEqual(res.status_code, 400)
        other.refresh_from_db()
        self.assertTrue(other.is_active)
        # ...while a reviewer in reach is revocable by the same caller.
        res = authed_client(self.super).patch(f'{STAFF}{self.reviewer.pk}/revoke/', {'action': 'revoke'},
                                             format='json')
        self.assertEqual(res.status_code, 200, res.content)
