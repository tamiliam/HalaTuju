"""Sprint M4a (ACCESS-BY-SWITCHES S2): courses 0100 appends `organisation.admin` to an organisation admin's list.

Done-when: every `org_admin` row whose value is a list without the key, active, revoked, archived or pending,
gets the key APPENDED and nothing else moves; a NULL row, a non-list row, a row already holding it and every
other role are untouched; each change has one truthful audit row; it is idempotent; it reverses exactly, and
only a row still holding what it wrote, the NEWEST audit row deciding; it sits beside 0098 and 0099; and the
readers the OLD image uses answer the same for a keyed row as for an unkeyed one (migrate-first is safe).
Run on the live registry.
"""
from importlib import import_module
from pathlib import Path

from django.apps import apps as live_apps
from django.test import TestCase
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses.models import PartnerAdmin
from apps.scholarship.models import StaffPermissionChange
from apps.scholarship.tests.factories import ORG_ADMIN_MIGRATED, ORG_ADMIN_PRE_M4A, make_admin, make_org

M = import_module('apps.courses.migrations.0100_store_org_admin_powers')
M0098 = import_module('apps.courses.migrations.0098_store_org_admin_keys')
M0099 = import_module('apps.courses.migrations.0099_grant_scholars_approve')
BEFORE = list(ORG_ADMIN_PRE_M4A)                    # a live list after 0098 + 0099
REVIEWING_BEFORE = ['review', *BEFORE]
FULL = [*BEFORE, M.KEY]
REVIEWING = [*REVIEWING_BEFORE, M.KEY]
APPS = Path(__file__).resolve().parents[2]


class FrozenConstants(TestCase):
    def test_they_equal_the_live_code(self):
        self.assertEqual(M.ROLE, sp.LEAD_ROLE)
        self.assertEqual(M.KEY, sp.ORG_ADMIN_KEY)
        self.assertEqual(M.KEY, v2.ORG_ADMIN_KEY)
        self.assertEqual(tuple(FULL), ORG_ADMIN_MIGRATED)
        # What an invitation stores from M4a: the same keys (catalogue order; 0099 appended its key), ours last.
        self.assertEqual(set(FULL), set(v2.ORG_ADMIN_FULL))
        self.assertEqual(len(FULL), len(v2.ORG_ADMIN_FULL))
        self.assertEqual(v2.ORG_ADMIN_FULL[-1], M.KEY)

    def test_the_key_is_no_page_key_and_no_switch(self):
        """Outside the catalogue: never grantable to a team row, never an old key, never in the org admin set."""
        self.assertIn(M.KEY, v2.V2_KEYS)
        for keys in (v2.CATALOGUE_V2, v2.GRANTABLE_V2, v2.ORG_ADMIN_V2, v2.ORG_ADMIN_SET, sp.CATALOGUE):
            self.assertNotIn(M.KEY, keys)

    def test_the_module_imports_no_app_code(self):
        source = open(M.__file__).read()
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
        self.assertIn("'courses','0100_store_org_admin_powers'", body)

    def test_the_ledger_is_safe_to_re_run(self):
        self.assertIn('WHERENOTEXISTS(SELECT1FROMdjango_migrations', self.flat)
        self.assertNotIn('VALUES(', self.flat)

    def test_the_pre_check_is_read_only_and_names_both_migrations(self):
        pre = self.flat.split('PRE-CHECK(read-only)', 1)[1].split('DATAblock', 1)[0]
        self.assertIn('BEGINREADONLY;', pre)
        self.assertIn("'0099_grant_scholars_approve','0100_store_org_admin_powers'", pre)
        self.assertNotIn('UPDATE', pre)
        self.assertNotIn('INSERT', pre)

    def test_the_post_deploy_check_has_the_three_zero_counts(self):
        post = self.flat.split('POST-DEPLOYCHECK(read-only', 1)[1].split('Reverse:', 1)[0]
        self.assertEqual(post.count('SELECTcount(*)FROMpartner_admins'), 3)
        self.assertIn(f"WHERErole<>'{M.ROLE}'", post)
        for key in ('payments_prepare', 'payments_check', 'payments_approve', 'payments.view',
                    'payments.prepare', 'payments.check', 'payments.approve', 'sponsors.check'):
            self.assertIn(f"'{key}'", post)
        self.assertNotIn('UPDATE', post)

    def test_the_warnings_are_carried(self):
        for words in ('AFTER0098/0099', 'THEOLDIMAGEIGNORESTHENEWKEY', 'NEWEST', 'asupermayuntickthekey',
                      'THEWINDOW', 'ReverseonlyundertheOLDimage'):
            with self.subTest(words=words):
                self.assertIn(words, self.flat.replace('`', ''))


class PlanRow(TestCase):
    """The pure rule, for each row shape (no database)."""

    def test_each_shape(self):
        cases = (
            (('org_admin', list(BEFORE)), (BEFORE, FULL)),                            # after 0099
            (('org_admin', list(REVIEWING_BEFORE)), (REVIEWING_BEFORE, REVIEWING)),
            (('org_admin', []), ([], [M.KEY])),
            (('org_admin', ['review']), (['review'], ['review', M.KEY])),
            (('org_admin', list(FULL)), None),                                          # already done
            (('org_admin', [M.KEY, 'review']), None),
            (('org_admin', None), None),                                                # read as holding it
            (('org_admin', {'see_all': True}), None),
            (('org_admin', 'see_all'), None),
            (('admin', ['see_all', 'payments_prepare']), None),
            (('admin', None), None),
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

        def lead(keys, **kw):
            a = make_admin('org_admin', owning_org=org, pre_m4a=True, **kw)
            PartnerAdmin.objects.filter(pk=a.pk).update(permissions=keys)
            return a
        cls.lead_full = lead(list(BEFORE))
        cls.lead_reviewing = lead(list(REVIEWING_BEFORE))
        cls.lead_revoked = lead(list(BEFORE), is_active=False)
        cls.lead_archived = lead(list(BEFORE))
        PartnerAdmin.objects.filter(pk=cls.lead_archived.pk).update(archived_at=timezone.now())
        cls.lead_pending = lead(list(BEFORE))
        PartnerAdmin.objects.filter(pk=cls.lead_pending.pk).update(first_seen_at=None)
        cls.lead_null = lead(None)
        cls.lead_dict = lead({'see_all': True})
        cls.lead_done = lead(list(FULL))
        cls.admin = make_admin('admin', owning_org=org, permissions=['see_all', 'payments_prepare'])
        cls.finance = make_admin('finance', owning_org=org, permissions=['payments_approve'])
        cls.reviewer = make_admin('reviewer', owning_org=org, permissions=['review'])
        cls.super = make_admin('super', super_admin=True)
        cls.leads = (cls.lead_full, cls.lead_reviewing, cls.lead_revoked, cls.lead_archived, cls.lead_pending)
        cls.untouched = (cls.lead_null, cls.lead_dict, cls.lead_done, cls.admin, cls.finance, cls.reviewer,
                         cls.super)

    def perms(self, a):
        return PartnerAdmin.objects.get(pk=a.pk).permissions

    def snapshot(self):
        return {a.pk: self.perms(a) for a in (*self.leads, *self.untouched)}

    def test_forward_appends_the_key_with_one_truthful_audit_row(self):
        untouched = {a.pk: self.perms(a) for a in self.untouched}
        changed = M.store_org_admin_powers(live_apps, None)
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
                         ('edit', 'org_admin', '', 'migration', REVIEWING_BEFORE, REVIEWING,
                          self.lead_reviewing.owning_organisation_id))
        self.assertEqual(row.target_email, self.lead_reviewing.email or '')

    def test_after_it_every_organisation_admin_holds_the_powers_and_nobody_else_does(self):
        before = {a.pk: sp.holds_org_admin_powers(PartnerAdmin.objects.get(pk=a.pk)) for a in self.leads}
        self.assertEqual(set(before.values()), {False})              # a list without the key: no powers
        M.store_org_admin_powers(live_apps, None)
        for a in (*self.leads, self.lead_null, self.lead_dict, self.lead_done):
            self.assertTrue(sp.holds_org_admin_powers(PartnerAdmin.objects.get(pk=a.pk)), a.pk)
        for a in (self.admin, self.finance, self.reviewer, self.super):
            self.assertFalse(sp.holds_org_admin_powers(PartnerAdmin.objects.get(pk=a.pk)), a.role)

    def test_it_is_idempotent(self):
        M.store_org_admin_powers(live_apps, None)
        after = self.snapshot()
        self.assertEqual(M.store_org_admin_powers(live_apps, None), [])
        self.assertEqual(self.snapshot(), after)
        self.assertEqual(StaffPermissionChange.objects.count(), len(self.leads))

    def test_backwards_restores_every_row_exactly_and_removes_only_its_audit_rows(self):
        before = self.snapshot()
        other = StaffPermissionChange.objects.create(
            target_id=self.reviewer.pk, organisation_id=self.reviewer.owning_organisation_id, kind='edit',
            role='org_admin', before=['review'], after=['review', M.KEY],
            changed_by_email='lead@example.test', changed_by_role='super')
        M.store_org_admin_powers(live_apps, None)
        restored = M.take_back_org_admin_powers(live_apps, None)
        self.assertEqual(sorted(restored), sorted(a.pk for a in self.leads))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(StaffPermissionChange.objects.values_list('pk', flat=True)), [other.pk])

    def test_backwards_leaves_a_row_changed_since_as_it_is(self):
        M.store_org_admin_powers(live_apps, None)
        PartnerAdmin.objects.filter(pk=self.lead_full.pk).update(permissions=['review', *FULL])   # edited
        PartnerAdmin.objects.filter(pk=self.lead_reviewing.pk).update(role='admin')             # role changed
        M.take_back_org_admin_powers(live_apps, None)
        self.assertEqual(self.perms(self.lead_full), ['review', *FULL])
        self.assertEqual(self.perms(self.lead_reviewing), REVIEWING)
        self.assertEqual(self.perms(self.lead_revoked), BEFORE)
        self.assertFalse(StaffPermissionChange.objects.filter(changed_by_role='migration').exists())

    def test_forward_reverse_forward_reverse_is_exact(self):
        before = self.snapshot()
        for _ in range(2):
            M.store_org_admin_powers(live_apps, None)
            M.take_back_org_admin_powers(live_apps, None)
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(StaffPermissionChange.objects.exists())

    def test_with_two_audit_rows_the_newest_decides(self):
        # The DATA block, then a super unticks the key, then the block re-run gives it back: the reverse
        # puts back what the NEWEST row found, never the older row's list.
        M.store_org_admin_powers(live_apps, None)
        PartnerAdmin.objects.filter(pk=self.lead_full.pk).update(permissions=['see_all'])
        self.assertEqual(M.store_org_admin_powers(live_apps, None), [self.lead_full.pk])
        self.assertEqual(StaffPermissionChange.objects.filter(target_id=self.lead_full.pk).count(), 2)
        M.take_back_org_admin_powers(live_apps, None)
        self.assertEqual(self.perms(self.lead_full), ['see_all'])
        self.assertEqual(self.perms(self.lead_revoked), BEFORE)
        self.assertFalse(StaffPermissionChange.objects.exists())


class AlongsideMigrations0098And0099(TestCase):
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
        M0099.grant_scholars_approve(live_apps, None)
        M.store_org_admin_powers(live_apps, None)
        self.assertEqual((self.perms(self.lead_null), self.perms(self.lead_reviewing)), (FULL, REVIEWING))
        self.assertEqual(StaffPermissionChange.objects.count(), 6)
        M.take_back_org_admin_powers(live_apps, None)                    # Django's order: 0100 first
        self.assertEqual((self.perms(self.lead_null), self.perms(self.lead_reviewing)),
                         (BEFORE, REVIEWING_BEFORE))
        self.assertEqual(StaffPermissionChange.objects.count(), 4)
        M0099.take_back_scholars_approve(live_apps, None)
        M0098.restore_org_admin_lists(live_apps, None)
        self.assertEqual((self.perms(self.lead_null), self.perms(self.lead_reviewing)), start)
        self.assertFalse(StaffPermissionChange.objects.exists())


class TheOldImageIgnoresTheKey(TestCase):
    """Migrate-first is safe: the readers the image LIVE TODAY uses for an organisation admin's row
    (`staff_permissions.clean` in `resolve`, `org_admin_v2` in `effective_v2`, `stored_v2`) answer the same
    for a keyed row as for the same row without the key, and no non-test code on today's image names the
    key (git grep over origin/main, run by the builder: zero hits; this test pins the readers)."""

    @classmethod
    def setUpTestData(cls):
        org = make_org()
        cls.plain = make_admin('org_admin', owning_org=org, pre_m4a=True)       # the live list today
        cls.keyed = make_admin('org_admin', owning_org=org)                     # after 0100

    def test_the_rows_differ_only_by_the_key(self):
        self.assertEqual(self.keyed.permissions, [*self.plain.permissions, M.KEY])

    def test_clean_drops_the_key(self):
        self.assertEqual(sp.clean(self.keyed.permissions), sp.clean(self.plain.permissions))
        self.assertNotIn(M.KEY, sp.clean(self.keyed.permissions))

    def test_org_admin_v2_and_stored_v2_ignore_the_key(self):
        self.assertEqual(v2.org_admin_v2(self.keyed), v2.org_admin_v2(self.plain))
        self.assertEqual(v2.stored_v2(self.keyed), ())
        self.assertEqual(v2.stored_v2(self.plain), ())

    def test_a_team_row_storing_the_key_reads_nothing_from_it(self):
        team = make_admin('admin', permissions=['see_all', M.KEY])
        self.assertNotIn(M.KEY, sp.clean(team.permissions))
        self.assertNotIn(M.KEY, v2.stored_v2(team))
        self.assertFalse(sp.holds_org_admin_powers(team))
        self.assertNotIn(M.KEY, v2.effective_v2(team))

    def test_only_the_one_helper_reads_the_key_in_non_test_code(self):
        """The key is read in ONE place (`holds_org_admin_powers`); the rest name it to store, list or
        order it. A new reader must come through the helper."""
        readers = []
        for path in APPS.rglob('*.py'):
            rel = path.relative_to(APPS).as_posix()
            if '/tests/' in rel or '/migrations/' in rel:
                continue
            text = path.read_text(encoding='utf-8')
            if "'organisation.admin'" in text:
                readers.append(rel)
        self.assertEqual(readers, ['courses/staff_permissions.py'])
