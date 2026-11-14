"""Sprint M3a (decision A1, 2026-11-14): courses 0098 stores an organisation admin's powers as keys.

Done-when: every `org_admin` row, active, revoked, archived or pending, has its list REPLACED by
['review' if held] + ORG_ADMIN_KEYS + ORG_ADMIN_V2; a leftover key (a payment key kept from a team role) is
gone; a row whose value is not a list is left alone; every other role is untouched; each change has one
truthful audit row (kind NULL_KIND for a NULL row, before = ORG_ADMIN_KEYS); it is idempotent; it reverses
exactly, and only a row still holding what it wrote; it sits beside 0097 and 0095. Run on the live registry.
"""
from importlib import import_module

from django.apps import apps as live_apps
from django.test import TestCase
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses.models import PartnerAdmin
from apps.scholarship.models import StaffPermissionChange
from apps.scholarship.tests.factories import make_admin, make_org

M = import_module('apps.courses.migrations.0098_store_org_admin_keys')
M0097 = import_module('apps.courses.migrations.0097_store_admin_v2_keys')
M0095 = import_module('apps.courses.migrations.0095_grant_scholars_key')
OLD = list(sp.ORG_ADMIN_KEYS)
FULL = [*sp.ORG_ADMIN_KEYS, *v2.ORG_ADMIN_V2]
REVIEWING = ['review', *FULL]


def _lst(keys):
    return '[' + ','.join(f'"{k}"' for k in keys) + ']'


class FrozenConstants(TestCase):
    def test_they_equal_the_live_code(self):
        self.assertEqual(M.ROLE, sp.LEAD_ROLE)
        self.assertEqual(M.REVIEW, sp.LEAD_MAY_ADD)
        self.assertEqual(M.OLD_KEYS, tuple(sp.ORG_ADMIN_KEYS))
        self.assertEqual(M.V2_KEYS, tuple(v2.ORG_ADMIN_V2))
        self.assertEqual(M.PLANNED, (FULL, REVIEWING))
        self.assertEqual(list(v2.ORG_ADMIN_SET), FULL)

    def test_nothing_held_by_role_or_an_alias_is_written(self):
        for key in (*sp.LEAD_BY_ROLE, *v2.LEAD_BY_ROLE_V2, *v2.LEAD_MONEY_UNTIL_M4, *v2.ALIAS_V2):
            self.assertNotIn(key, REVIEWING, key)

    def test_the_module_imports_no_app_code(self):
        self.assertNotIn('staff_permissions_v2', open(M.__file__).read())
        body = open(M.__file__).read().split('"""', 2)[2]
        self.assertNotIn('from apps', body)
        self.assertNotIn('import apps', body)


class HandSql(TestCase):
    """The test database cannot run jsonb, so the hand SQL's text is pinned to `plan_row`."""

    def setUp(self):
        self.flat = ''.join(M.__doc__.split())

    def test_the_planned_list_and_the_where_appear_in_the_data_block_and_the_check(self):
        planned = (f"(CASEWHENpermissions?'{M.REVIEW}'THEN'[\"{M.REVIEW}\"]'ELSE'[]'END)::jsonb"
                   f"||'{_lst(M.OLD_KEYS + M.V2_KEYS)}'::jsonb")
        self.assertEqual(self.flat.count(planned), 2)
        where = (f"WHERErole='{M.ROLE}'"
                 "AND(permissionsISNULLORjsonb_typeof(permissions)IN('array','null'))")
        self.assertEqual(self.flat.count(where), 2)
        self.assertNotIn("jsonb_typeof(permissions)='array')", self.flat)

    def test_a_null_row_is_based_on_the_old_keys_and_audited_with_the_null_kind(self):
        self.assertIn(f"COALESCE(NULLIF(permissions,'null'::jsonb),'{_lst(M.OLD_KEYS)}'::jsonb)ASbase", self.flat)
        self.assertIn(f"CASEWHENwas_nullTHEN'{M.NULL_KIND}'ELSE'edit'END", self.flat)
        self.assertEqual(self.flat.count('was_nullORafter<>base'), 1)
        self.assertIn('(g.was_nullORg.after<>g.base)', self.flat)
        self.assertIn(f"'','{M.BY_ROLE}',now()", self.flat)

    def test_a_stored_json_null_is_read_as_null_as_the_python_reads_it(self):
        # Django reads a jsonb `null` as None, so `plan_row` treats it as NULL; the SQL must too, in the
        # data block's `was_null` and in the post-deploy check's.
        self.assertEqual(self.flat.count("(permissionsISNULLORpermissions='null'::jsonb)ASwas_null"), 2)
        self.assertEqual(M.plan_row(M.ROLE, None), (OLD, FULL))

    def test_the_ledger_row_is_written_in_the_data_blocks_own_transaction(self):
        data = self.flat.split('DATAblock(onetransaction', 1)[1].split('POST-DEPLOYCHECK(read-only', 1)[0]
        body = data.split('BEGIN;', 1)[1].split('COMMIT;', 1)[0]
        self.assertIn('UPDATEpartner_adminsp', body)
        self.assertIn("INSERTINTOdjango_migrations", body)
        self.assertEqual(self.flat.count('INSERTINTOdjango_migrations'), 1)
        self.assertNotIn('LEDGERblock', self.flat)

    def test_the_window_and_the_reverse_carry_their_warnings(self):
        for words in ('100%ofthetraffic', 'donotuseTeam->ReviewersAdd/Removeonanorganisationadmin',
                      'ONLYAFTERtheimageisrolledback', 'mustsetpermissions=NULL', 'NEWEST'):
            with self.subTest(words=words):
                self.assertIn(words, self.flat.replace('`', ''))

    def test_the_ledger_and_the_check_are_safe_to_re_run(self):
        self.assertIn("WHERENOTEXISTS(SELECT1FROMdjango_migrations", self.flat)
        self.assertIn("'courses','0098_store_org_admin_keys'", self.flat)
        self.assertNotIn('VALUES(', self.flat)
        self.assertIn('ISDISTINCTFROM', self.flat)
        self.assertIn('Ifnotzero,re-runtheDATAblockonly.', self.flat)


class PlanRow(TestCase):
    """The pure rule, for each row shape (no database)."""

    def test_each_shape(self):
        cases = (
            (('org_admin', None), (OLD, FULL)),                                     # live shape 1
            (('org_admin', ['review']), (['review'], REVIEWING)),                   # live shape 2
            (('org_admin', []), ([], FULL)),
            (('org_admin', ['payments_approve', 'see_all']), (['payments_approve', 'see_all'], FULL)),
            (('org_admin', ['review', 'payments_check']), (['review', 'payments_check'], REVIEWING)),
            (('org_admin', ['see_all', 'manage_team', 'review']),
             (['see_all', 'manage_team', 'review'], REVIEWING)),
            (('org_admin', list(FULL)), None),                                      # already done
            (('org_admin', list(REVIEWING)), None),
            (('org_admin', list(reversed(FULL))), (list(reversed(FULL)), FULL)),   # order is exact
            (('org_admin', {'see_all': True}), None),                               # not a list
            (('org_admin', 'see_all'), None),
            (('admin', None), None),
            (('admin', ['see_all', 'scholars']), None),
            (('finance', ['payments_approve']), None),
            (('reviewer', ['review']), None),
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

        def person(role, keys=None, **kw):
            return make_admin(role, owning_org=org, pre_m3=True, permissions=keys, **kw)
        cls.lead_null = person('org_admin')
        cls.lead_reviewing = person('org_admin', ['review'])
        cls.lead_leftover = person('org_admin', ['payments_approve', 'see_all'])
        cls.lead_revoked = person('org_admin', is_active=False)
        cls.lead_archived = person('org_admin', ['review'], is_active=False)
        PartnerAdmin.objects.filter(pk=cls.lead_archived.pk).update(archived_at=timezone.now())
        cls.lead_pending = person('org_admin')
        PartnerAdmin.objects.filter(pk=cls.lead_pending.pk).update(first_seen_at=None)
        cls.lead_dict = person('org_admin')
        PartnerAdmin.objects.filter(pk=cls.lead_dict.pk).update(permissions={'see_all': True})
        cls.admin = person('admin', ['see_all', 'scholars', 'spending'])
        cls.finance = person('finance', ['payments_approve'])
        cls.reviewer = person('reviewer', ['review'])
        cls.super = make_admin('super', super_admin=True, pre_m3=True)
        cls.leads = (cls.lead_null, cls.lead_reviewing, cls.lead_leftover, cls.lead_revoked, cls.lead_archived,
                     cls.lead_pending)
        cls.untouched = (cls.lead_dict, cls.admin, cls.finance, cls.reviewer, cls.super)

    def perms(self, a):
        return PartnerAdmin.objects.get(pk=a.pk).permissions

    def snapshot(self):
        return {a.pk: self.perms(a) for a in (*self.leads, *self.untouched)}

    def test_forward_replaces_every_org_admin_list_with_one_truthful_audit_row(self):
        untouched = {a.pk: self.perms(a) for a in self.untouched}
        changed = M.store_org_admin_keys(live_apps, None)
        self.assertEqual(sorted(changed), sorted(a.pk for a in self.leads))
        self.assertEqual(self.perms(self.lead_null), FULL)
        self.assertEqual(self.perms(self.lead_reviewing), REVIEWING)
        self.assertEqual(self.perms(self.lead_leftover), FULL)          # the payment key is gone
        self.assertEqual(self.perms(self.lead_revoked), FULL)
        self.assertEqual(self.perms(self.lead_archived), REVIEWING)
        self.assertEqual(self.perms(self.lead_pending), FULL)
        for a in self.untouched:
            self.assertEqual(self.perms(a), untouched[a.pk], a.role)
        rows = {r.target_id: r for r in StaffPermissionChange.objects.all()}
        self.assertEqual(set(rows), set(changed))
        null_row = rows[self.lead_null.pk]
        self.assertEqual((null_row.kind, null_row.role, null_row.changed_by_email, null_row.changed_by_role,
                          null_row.before, null_row.after, null_row.organisation_id),
                         (M.NULL_KIND, 'org_admin', '', 'migration', OLD, FULL,
                          self.lead_null.owning_organisation_id))
        self.assertEqual(null_row.target_email, self.lead_null.email or '')
        rev_row = rows[self.lead_reviewing.pk]
        self.assertEqual((rev_row.kind, rev_row.before, rev_row.after), ('edit', ['review'], REVIEWING))

    def test_it_is_idempotent(self):
        M.store_org_admin_keys(live_apps, None)
        after = self.snapshot()
        self.assertEqual(M.store_org_admin_keys(live_apps, None), [])
        self.assertEqual(self.snapshot(), after)
        self.assertEqual(StaffPermissionChange.objects.count(), len(self.leads))

    def test_backwards_restores_every_row_exactly_and_removes_only_its_audit_rows(self):
        before = self.snapshot()
        other = StaffPermissionChange.objects.create(
            target_id=self.reviewer.pk, organisation_id=self.reviewer.owning_organisation_id, kind='edit',
            role='reviewer', before=['review'], after=['review', 'see_all'],
            changed_by_email='lead@example.test', changed_by_role='org_admin')
        M.store_org_admin_keys(live_apps, None)
        restored = M.restore_org_admin_lists(live_apps, None)
        self.assertEqual(sorted(restored), sorted(a.pk for a in self.leads))
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(self.perms(self.lead_null))                   # NULL again, not OLD
        self.assertEqual(list(StaffPermissionChange.objects.values_list('pk', flat=True)), [other.pk])

    def test_backwards_leaves_a_row_changed_since_as_it_is(self):
        M.store_org_admin_keys(live_apps, None)
        PartnerAdmin.objects.filter(pk=self.lead_null.pk).update(permissions=REVIEWING)   # joined Reviewers
        PartnerAdmin.objects.filter(pk=self.lead_reviewing.pk).update(role='admin')       # role changed
        M.restore_org_admin_lists(live_apps, None)
        self.assertEqual(self.perms(self.lead_null), REVIEWING)
        self.assertEqual(self.perms(self.lead_reviewing), REVIEWING)
        self.assertIsNone(self.perms(self.lead_revoked))
        self.assertFalse(StaffPermissionChange.objects.filter(changed_by_role='migration').exists())

    def test_forward_reverse_forward_reverse_is_exact(self):
        before = self.snapshot()
        for _ in range(2):
            M.store_org_admin_keys(live_apps, None)
            M.restore_org_admin_lists(live_apps, None)
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(StaffPermissionChange.objects.exists())

    def test_with_two_audit_rows_the_newest_decides(self):
        # A window write, then the DATA block re-run: the first run took NULL to FULL, an old-image writer
        # stored [], the re-run took [] to FULL. Both rows end at FULL; the reverse puts back what the
        # NEWEST one found ([]), never the older row's NULL.
        M.store_org_admin_keys(live_apps, None)
        PartnerAdmin.objects.filter(pk=self.lead_null.pk).update(permissions=[])
        self.assertEqual(M.store_org_admin_keys(live_apps, None), [self.lead_null.pk])
        self.assertEqual(StaffPermissionChange.objects.filter(target_id=self.lead_null.pk).count(), 2)
        M.restore_org_admin_lists(live_apps, None)
        self.assertEqual(self.perms(self.lead_null), [])
        self.assertIsNone(self.perms(self.lead_revoked))                  # one row: as before
        self.assertFalse(StaffPermissionChange.objects.exists())


class AlongsideEarlierMigrations(TestCase):
    @classmethod
    def setUpTestData(cls):
        org = make_org()
        cls.admin = make_admin('admin', owning_org=org, pre_m2b=True, permissions=['see_all', 'spending'])
        cls.lead = make_admin('org_admin', owning_org=org, pre_m2b=True)

    def perms(self, a):
        return PartnerAdmin.objects.get(pk=a.pk).permissions

    def test_each_reverse_touches_only_its_own_rows(self):
        M0095.grant_scholars(live_apps, None)
        M0097.store_v2_keys(live_apps, None)
        M.store_org_admin_keys(live_apps, None)
        self.assertEqual(self.perms(self.lead), FULL)
        self.assertEqual(self.perms(self.admin), ['see_all', 'spending', 'scholars', *v2.ADMIN_PRESET_V2])
        self.assertEqual(StaffPermissionChange.objects.count(), 3)
        M.restore_org_admin_lists(live_apps, None)                       # Django's order: 0098 first
        self.assertIsNone(self.perms(self.lead))
        self.assertEqual(self.perms(self.admin), ['see_all', 'spending', 'scholars', *v2.ADMIN_PRESET_V2])
        self.assertEqual(StaffPermissionChange.objects.count(), 2)
        M0097.remove_v2_keys(live_apps, None)
        M0095.withdraw_scholars(live_apps, None)
        self.assertEqual(self.perms(self.admin), ['see_all', 'spending'])
        self.assertFalse(StaffPermissionChange.objects.exists())

    def test_0097_never_reads_this_steps_audit_rows(self):
        M.store_org_admin_keys(live_apps, None)
        M0097.remove_v2_keys(live_apps, None)
        self.assertEqual(self.perms(self.lead), FULL)
        self.assertEqual(StaffPermissionChange.objects.count(), 1)
