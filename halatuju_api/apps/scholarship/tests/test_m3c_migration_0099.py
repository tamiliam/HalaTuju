"""Sprint M3c (decision D5, 2026-11-15): courses 0099 appends `scholars.approve` to an organisation admin's list.

Done-when: every `org_admin` row whose value is a list without the key, active, revoked, archived or pending,
gets the key APPENDED and nothing else moves; a NULL row, a non-list row, a row already holding it and every
other role are untouched; each change has one truthful audit row; it is idempotent; it reverses exactly, and
only a row still holding what it wrote, the NEWEST audit row deciding; it sits beside 0098. Run on the live
registry.
"""
from importlib import import_module

from django.apps import apps as live_apps
from django.test import TestCase
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses.models import PartnerAdmin
from apps.scholarship.models import StaffPermissionChange
from apps.scholarship.tests.factories import ORG_ADMIN_PRE_M4A, make_admin, make_org

M = import_module('apps.courses.migrations.0099_grant_scholars_approve')
M0098 = import_module('apps.courses.migrations.0098_store_org_admin_keys')
FULL_0098, REVIEWING_0098 = M0098.PLANNED
FULL = [*FULL_0098, M.KEY]
REVIEWING = [*REVIEWING_0098, M.KEY]


class FrozenConstants(TestCase):
    def test_they_equal_the_live_code(self):
        self.assertEqual(M.ROLE, sp.LEAD_ROLE)
        self.assertIn(M.KEY, v2.ORG_ADMIN_V2)
        self.assertIn(M.KEY, v2.CATALOGUE_V2)
        self.assertEqual(set((*M0098.V2_KEYS, M.KEY)), set(v2.ORG_ADMIN_V2))
        self.assertEqual(len((*M0098.V2_KEYS, M.KEY)), len(v2.ORG_ADMIN_V2))
        self.assertEqual(set(FULL), set(v2.ORG_ADMIN_SET))
        self.assertEqual(tuple(FULL), ORG_ADMIN_PRE_M4A)   # M4a: 0100 appends after

    def test_the_key_is_grantable_and_not_held_by_role(self):
        self.assertIn(M.KEY, v2.GRANTABLE_V2)
        self.assertNotIn(M.KEY, v2.NEVER_GRANTABLE)
        for key in (*sp.LEAD_BY_ROLE, *v2.LEAD_BY_ROLE_V2, *v2.ALIAS_V2):
            self.assertNotEqual(key, M.KEY)

    def test_the_module_imports_no_app_code(self):
        source = open(M.__file__).read()
        self.assertNotIn('staff_permissions_v2', source)
        body = source.split('"""', 2)[2]
        self.assertNotIn('from apps', body)
        self.assertNotIn('import apps', body)


class HandSql(TestCase):
    """The test database cannot run jsonb, so the hand SQL's text is pinned to `plan_row`."""

    def setUp(self):
        self.flat = ''.join(M.__doc__.split())

    def test_the_where_matches_plan_row_in_the_data_block_and_the_check(self):
        where = (f"WHERErole='{M.ROLE}'ANDjsonb_typeof(permissions)='array'"
                 f"ANDNOTpermissions?'{M.KEY}'")
        self.assertEqual(self.flat.count(where), 2)
        self.assertIn(f"permissions||'[\"{M.KEY}\"]'::jsonbASafter", self.flat)

    def test_the_audit_row_matches_the_python(self):
        self.assertIn(f"'{M.KIND}',role,base,after,'','{M.BY_ROLE}',now()", self.flat)
        self.assertIn("COALESCE(email,'')", self.flat)

    def test_the_ledger_row_is_written_in_the_data_blocks_own_transaction(self):
        data = self.flat.split('DATAblock(onetransaction', 1)[1].split('POST-DEPLOYCHECK(read-only', 1)[0]
        body = data.split('BEGIN;', 1)[1].split('COMMIT;', 1)[0]
        self.assertIn('UPDATEpartner_adminsp', body)
        self.assertIn('INSERTINTOstaff_permission_changes', body)
        self.assertIn('INSERTINTOdjango_migrations', body)
        self.assertEqual(self.flat.count('INSERTINTOdjango_migrations'), 1)

    def test_the_ledger_and_the_check_are_safe_to_re_run(self):
        self.assertIn('WHERENOTEXISTS(SELECT1FROMdjango_migrations', self.flat)
        self.assertIn("'courses','0099_grant_scholars_approve'", self.flat)
        self.assertNotIn('VALUES(', self.flat)
        self.assertIn('ItmustreturnZEROrows', self.flat)
        self.assertIn('Ifnotzero,re-runtheDATAblockonly.', self.flat)

    def test_the_pre_check_is_read_only_and_names_both_migrations(self):
        pre = self.flat.split('PRE-CHECK(read-only)', 1)[1].split('DATAblock', 1)[0]
        self.assertIn('BEGINREADONLY;', pre)
        self.assertIn("'0098_store_org_admin_keys','0099_grant_scholars_approve'", pre)
        self.assertNotIn('UPDATE', pre)
        self.assertNotIn('INSERT', pre)

    def test_the_warnings_are_carried(self):
        for words in ('AFTER0098', 'THEOLDIMAGEIGNORESTHENEWKEY', 'NEWEST', 'asupermaytakethekey'):
            with self.subTest(words=words):
                self.assertIn(words, self.flat.replace('`', ''))


class PlanRow(TestCase):
    """The pure rule, for each row shape (no database)."""

    def test_each_shape(self):
        cases = (
            (('org_admin', list(FULL_0098)), (FULL_0098, FULL)),                       # after 0098
            (('org_admin', list(REVIEWING_0098)), (REVIEWING_0098, REVIEWING)),
            (('org_admin', []), ([], [M.KEY])),
            (('org_admin', ['review']), (['review'], ['review', M.KEY])),
            (('org_admin', list(FULL)), None),                                          # already done
            (('org_admin', [M.KEY, 'review']), None),
            (('org_admin', None), None),                                                # read as full
            (('org_admin', {'see_all': True}), None),
            (('org_admin', 'see_all'), None),
            (('admin', ['see_all', 'scholars']), None),
            (('admin', None), None),
            (('reviewer', ['review']), None),
            (('finance', ['payments_approve']), None),
            (('qc', None), None),
            (('super', None), None),
            (('partner', None), None),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertEqual(M.plan_row(*args), expected)

    def test_the_before_is_a_copy(self):
        stored = ['review']
        before, _ = M.plan_row('org_admin', stored)
        before.append('x')
        self.assertEqual(stored, ['review'])


class ForwardAndBack(TestCase):
    @classmethod
    def setUpTestData(cls):
        org = make_org()

        def lead(keys, **kw):
            a = make_admin('org_admin', owning_org=org, pre_m3=True, **kw)
            PartnerAdmin.objects.filter(pk=a.pk).update(permissions=keys)
            return a
        cls.lead_full = lead(list(FULL_0098))
        cls.lead_reviewing = lead(list(REVIEWING_0098))
        cls.lead_revoked = lead(list(FULL_0098), is_active=False)
        cls.lead_archived = lead(list(FULL_0098))
        PartnerAdmin.objects.filter(pk=cls.lead_archived.pk).update(archived_at=timezone.now())
        cls.lead_pending = lead(list(FULL_0098))
        PartnerAdmin.objects.filter(pk=cls.lead_pending.pk).update(first_seen_at=None)
        cls.lead_null = lead(None)
        cls.lead_dict = lead({'see_all': True})
        cls.lead_done = lead(list(FULL))
        cls.admin = make_admin('admin', owning_org=org, permissions=['see_all', 'scholars'])
        cls.reviewer = make_admin('reviewer', owning_org=org, permissions=['review'])
        cls.super = make_admin('super', super_admin=True)
        cls.leads = (cls.lead_full, cls.lead_reviewing, cls.lead_revoked, cls.lead_archived, cls.lead_pending)
        cls.untouched = (cls.lead_null, cls.lead_dict, cls.lead_done, cls.admin, cls.reviewer, cls.super)

    def perms(self, a):
        return PartnerAdmin.objects.get(pk=a.pk).permissions

    def snapshot(self):
        return {a.pk: self.perms(a) for a in (*self.leads, *self.untouched)}

    def test_forward_appends_the_key_with_one_truthful_audit_row(self):
        untouched = {a.pk: self.perms(a) for a in self.untouched}
        changed = M.grant_scholars_approve(live_apps, None)
        self.assertEqual(sorted(changed), sorted(a.pk for a in self.leads))
        for a in (self.lead_full, self.lead_revoked, self.lead_archived, self.lead_pending):
            self.assertEqual(self.perms(a), FULL)
        self.assertEqual(self.perms(self.lead_reviewing), REVIEWING)
        for a in self.untouched:
            self.assertEqual(self.perms(a), untouched[a.pk], a.role)
        rows = {r.target_id: r for r in StaffPermissionChange.objects.all()}
        self.assertEqual(set(rows), set(changed))
        row = rows[self.lead_reviewing.pk]
        self.assertEqual((row.kind, row.role, row.changed_by_email, row.changed_by_role, row.before, row.after,
                          row.organisation_id),
                         ('edit', 'org_admin', '', 'migration', REVIEWING_0098, REVIEWING,
                          self.lead_reviewing.owning_organisation_id))
        self.assertEqual(row.target_email, self.lead_reviewing.email or '')

    def test_it_is_idempotent(self):
        M.grant_scholars_approve(live_apps, None)
        after = self.snapshot()
        self.assertEqual(M.grant_scholars_approve(live_apps, None), [])
        self.assertEqual(self.snapshot(), after)
        self.assertEqual(StaffPermissionChange.objects.count(), len(self.leads))

    def test_backwards_restores_every_row_exactly_and_removes_only_its_audit_rows(self):
        before = self.snapshot()
        other = StaffPermissionChange.objects.create(
            target_id=self.reviewer.pk, organisation_id=self.reviewer.owning_organisation_id, kind='edit',
            role='org_admin', before=['review'], after=['review', M.KEY],
            changed_by_email='lead@example.test', changed_by_role='org_admin')
        M.grant_scholars_approve(live_apps, None)
        restored = M.take_back_scholars_approve(live_apps, None)
        self.assertEqual(sorted(restored), sorted(a.pk for a in self.leads))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(StaffPermissionChange.objects.values_list('pk', flat=True)), [other.pk])

    def test_backwards_leaves_a_row_changed_since_as_it_is(self):
        M.grant_scholars_approve(live_apps, None)
        PartnerAdmin.objects.filter(pk=self.lead_full.pk).update(permissions=['review', *FULL])   # edited
        PartnerAdmin.objects.filter(pk=self.lead_reviewing.pk).update(role='admin')             # role changed
        M.take_back_scholars_approve(live_apps, None)
        self.assertEqual(self.perms(self.lead_full), ['review', *FULL])
        self.assertEqual(self.perms(self.lead_reviewing), REVIEWING)
        self.assertEqual(self.perms(self.lead_revoked), FULL_0098)
        self.assertFalse(StaffPermissionChange.objects.filter(changed_by_role='migration').exists())

    def test_forward_reverse_forward_reverse_is_exact(self):
        before = self.snapshot()
        for _ in range(2):
            M.grant_scholars_approve(live_apps, None)
            M.take_back_scholars_approve(live_apps, None)
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(StaffPermissionChange.objects.exists())

    def test_with_two_audit_rows_the_newest_decides(self):
        # The DATA block, then a super takes the key away, then the block re-run gives it back: the reverse
        # puts back what the NEWEST row found, never the older row's list.
        M.grant_scholars_approve(live_apps, None)
        PartnerAdmin.objects.filter(pk=self.lead_full.pk).update(permissions=['see_all'])
        self.assertEqual(M.grant_scholars_approve(live_apps, None), [self.lead_full.pk])
        self.assertEqual(StaffPermissionChange.objects.filter(target_id=self.lead_full.pk).count(), 2)
        M.take_back_scholars_approve(live_apps, None)
        self.assertEqual(self.perms(self.lead_full), ['see_all'])
        self.assertEqual(self.perms(self.lead_revoked), FULL_0098)
        self.assertFalse(StaffPermissionChange.objects.exists())


class AlongsideMigration0098(TestCase):
    @classmethod
    def setUpTestData(cls):
        org = make_org()
        cls.lead_null = make_admin('org_admin', owning_org=org, pre_m3=True)
        cls.lead_reviewing = make_admin('org_admin', owning_org=org, pre_m3=True, permissions=['review'])

    def perms(self, a):
        return PartnerAdmin.objects.get(pk=a.pk).permissions

    def test_each_reverse_touches_only_its_own_rows(self):
        start = (self.perms(self.lead_null), self.perms(self.lead_reviewing))
        M0098.store_org_admin_keys(live_apps, None)
        M.grant_scholars_approve(live_apps, None)
        self.assertEqual((self.perms(self.lead_null), self.perms(self.lead_reviewing)), (FULL, REVIEWING))
        self.assertEqual(StaffPermissionChange.objects.count(), 4)
        M.take_back_scholars_approve(live_apps, None)                    # Django's order: 0099 first
        self.assertEqual((self.perms(self.lead_null), self.perms(self.lead_reviewing)),
                         (FULL_0098, REVIEWING_0098))
        self.assertEqual(StaffPermissionChange.objects.count(), 2)
        M0098.restore_org_admin_lists(live_apps, None)
        self.assertEqual((self.perms(self.lead_null), self.perms(self.lead_reviewing)), start)
        self.assertFalse(StaffPermissionChange.objects.exists())

    def test_0098_never_reads_this_steps_audit_rows(self):
        M0098.store_org_admin_keys(live_apps, None)
        M.grant_scholars_approve(live_apps, None)
        M0098.restore_org_admin_lists(live_apps, None)
        # 0098's newest row wrote FULL_0098; the row now holds FULL, so 0098 leaves it (changed since).
        self.assertEqual(self.perms(self.lead_null), FULL)
        self.assertEqual(StaffPermissionChange.objects.filter(changed_by_role='migration').count(), 2)
