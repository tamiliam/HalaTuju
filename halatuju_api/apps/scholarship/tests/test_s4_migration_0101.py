"""Sprint S4 (ACCESS-BY-SWITCHES SCHOLARS-SPLIT): courses 0101 gives "Manage scholar files" to every team member
whose stored list holds "View scholars" (`scholars`), whatever the stored role label, and removes nothing.

Done-when: a team row (any of the four team labels) whose list holds `scholars` and not the key gains
`scholars.approve`, appended, and nothing else moves; a NULL `admin` row is materialised (kind 'edit_null');
organisation admins, supers, a row holding a withdraw key without `scholars`, other shapes and rows without
`scholars` are untouched; active, revoked, archived and pending alike; one truthful audit row each;
idempotent; an exact reverse that never takes back 0099's rows; the hand SQL is pinned to `plan_row`.
"""
from importlib import import_module

from django.apps import apps as live_apps
from django.test import TestCase
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship.models import StaffPermissionChange
from apps.scholarship.tests.factories import make_admin, make_org

M = import_module('apps.courses.migrations.0101_grant_scholars_manage')
PRESET = ['see_all', 'scholars', 'spending', 'payments_prepare', *v2.ADMIN_PRESET_V2]
REVIEWING = ['review', 'scholars', *v2.ADMIN_PRESET_V2]          # a member of Admins and Reviewers, by shape
REVIEWING_VIEW = ['review', 'scholars']                           # View scholars and a Reviewers switch
WITHDRAW_ONLY = ['payments_approve', 'award_withdraw_approve']    # a withdraw switch without View: untouched


class FrozenConstants(TestCase):
    def test_they_equal_the_live_code(self):
        self.assertEqual(M.KEY, 'scholars.approve')
        self.assertIn(M.KEY, v2.CATALOGUE_V2)
        self.assertEqual(v2.ALIASES[M.VIEW], ('scholars.view',))
        self.assertEqual(M.TEAM_ROLES, sp.TEAM_ROLES)
        self.assertEqual(M.ADMIN_PRESET, sp.PRESETS['admin'])
        self.assertEqual(M.ADMIN_PRESET_V2, v2.ADMIN_PRESET_V2)
        self.assertNotIn(M.KEY, v2.ADMIN_PRESET_V2)                  # Q-E: a new Admin starts with Manage off

    def test_the_module_imports_no_app_code(self):
        body = open(M.__file__).read().split('"""', 2)[2]
        self.assertNotIn('from apps', body)
        self.assertNotIn('import apps', body)


class HandSql(TestCase):
    """The test database cannot run jsonb, so the hand SQL's text is pinned to the frozen constants."""

    def setUp(self):
        self.flat = ''.join(M.__doc__.split())

    def test_the_where_matches_plan_row_in_the_pre_check_the_data_block_and_the_post_check(self):
        roles = ','.join(f"'{r}'" for r in M.TEAM_ROLES)
        where = (f"WHEREroleIN({roles})ANDjsonb_typeof(permissions)='array'"
                 f"ANDpermissions?'{M.VIEW}'ANDNOTpermissions?'{M.KEY}'")
        self.assertEqual(self.flat.count(where), 3)
        self.assertEqual(self.flat.count("WHERErole='admin'AND(permissionsISNULLORjsonb_typeof(permissions)='null')"), 3)
        self.assertNotIn("'org_admin'", self.flat.split('PRE-CHECK(read-only)', 1)[1].split('Reverse:', 1)[0])

    def test_the_writes_match_plan_row_and_nothing_is_removed(self):
        self.assertIn(f"permissions||'[\"{M.KEY}\"]'::jsonbASafter", self.flat)
        base = '[' + ','.join(f'"{k}"' for k in M.ADMIN_PRESET) + ']'
        after = '[' + ','.join(f'"{k}"' for k in M.MATERIALISED) + ']'
        self.assertIn(f"'{M.NULL_KIND}'ASkind,'{base}'::jsonbASbase,'{after}'::jsonbASafter", self.flat)
        self.assertNotIn("permissions-'", self.flat)

    def test_the_audit_row_and_the_ledger(self):
        self.assertIn(f"kind,role,base,after,'','{M.BY_ROLE}',now()", self.flat)
        data = self.flat.split('DATAblock(onetransaction', 1)[1].split('POST-DEPLOYCHECK(read-only', 1)[0]
        body = data.split('BEGIN;', 1)[1].split('COMMIT;', 1)[0]
        for words in ('UPDATEpartner_adminsp', 'INSERTINTOstaff_permission_changes', 'INSERTINTOdjango_migrations',
                      "'courses','0101_grant_scholars_manage'", 'WHERENOTEXISTS(SELECT1FROMdjango_migrations'):
            self.assertIn(words, body)
        self.assertEqual(self.flat.count('INSERTINTOdjango_migrations'), 1)

    def test_the_checks_are_read_only(self):
        pre = self.flat.split('PRE-CHECK(read-only)', 1)[1].split('DATAblock(onetransaction', 1)[0]
        post = self.flat.split('POST-DEPLOYCHECK(read-only', 1)[1].split('Reverse:', 1)[0]
        self.assertIn('BEGINREADONLY;', pre)
        for part in (pre, post):
            self.assertNotIn('UPDATE', part)
            self.assertNotIn('INSERT', part)
        self.assertEqual(post.count('SELECTcount(*)'), 3)

    def test_the_warnings_are_carried(self):
        for words in ('NOTINVISIBLETOTHEOLDIMAGE', 'ORGANISATIONADMINROWSARENOTTOUCHED', 'NEWEST',
                      'ReverseonlyundertheOLDimage', 'ADMIN_PRESET_V2)doesNOTgainthekey', 'REMOVESNOTHING'):
            with self.subTest(words=words):
                self.assertIn(words, self.flat.replace('`', ''))


class PlanRow(TestCase):
    def test_each_shape(self):
        cases = (
            (('admin', list(PRESET)), ('edit', PRESET, [*PRESET, M.KEY])),
            (('reviewer', list(REVIEWING)), ('edit', REVIEWING, [*REVIEWING, M.KEY])),
            (('reviewer', list(REVIEWING_VIEW)), ('edit', REVIEWING_VIEW, [*REVIEWING_VIEW, M.KEY])),
            (('qc', ['qc', 'see_all', 'scholars']), ('edit', ['qc', 'see_all', 'scholars'],
                                                     ['qc', 'see_all', 'scholars', M.KEY])),
            (('finance', ['scholars', 'award_withdraw_request']),
             ('edit', ['scholars', 'award_withdraw_request'], ['scholars', 'award_withdraw_request', M.KEY])),
            (('admin', ['scholars']), ('edit', ['scholars'], ['scholars', M.KEY])),
            (('admin', None), ('edit_null', list(M.ADMIN_PRESET), list(M.MATERIALISED))),
            (('admin', [*PRESET, M.KEY]), None),                      # already holds it
            (('admin', ['see_all', 'payments_prepare']), None),         # no `scholars`
            (('finance', list(WITHDRAW_ONLY)), None),
            (('reviewer', None), None), (('qc', None), None), (('finance', None), None),
            (('admin', {'scholars': True}), None),
            (('org_admin', ['see_all', 'scholars']), None),             # 0099 gave the organisation admins the key
            (('org_admin', None), None),
            (('super', ['scholars']), None), (('partner', ['scholars']), None),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                got = M.plan_row(*args)
                self.assertEqual(got if got is None else (got[0], got[1], got[2]),
                                 expected if expected is None else (expected[0], list(expected[1]),
                                                                    list(expected[2])))


class ForwardAndBack(TestCase):
    @classmethod
    def setUpTestData(cls):
        org = make_org()

        def row(role, keys, **kw):
            a = make_admin(role, owning_org=org, **kw)
            PartnerAdmin.objects.filter(pk=a.pk).update(permissions=keys)
            return a
        cls.admin = row('admin', list(PRESET))
        cls.admin_revoked = row('admin', list(PRESET), is_active=False)
        cls.admin_archived = row('admin', list(PRESET))
        PartnerAdmin.objects.filter(pk=cls.admin_archived.pk).update(archived_at=timezone.now())
        cls.admin_pending = row('admin', list(PRESET))
        PartnerAdmin.objects.filter(pk=cls.admin_pending.pk).update(first_seen_at=None)
        cls.reviewing = row('reviewer', list(REVIEWING))
        cls.reviewing_view = row('reviewer', list(REVIEWING_VIEW))
        cls.admin_null = row('admin', None)
        cls.granted = (cls.admin, cls.admin_revoked, cls.admin_archived, cls.admin_pending, cls.reviewing,
                       cls.reviewing_view)
        cls.untouched = (row('admin', [*PRESET, M.KEY]), row('reviewer', ['review']), row('finance', None),
                         row('finance', list(WITHDRAW_ONLY)),
                         row('org_admin', ['see_all', 'scholars', M.KEY]), row('org_admin', ['see_all', 'scholars']),
                         row('org_admin', None), make_admin('super', super_admin=True))
        cls.changed = (*cls.granted, cls.admin_null)

    def perms(self, a):
        return PartnerAdmin.objects.get(pk=a.pk).permissions

    def snapshot(self):
        return {a.pk: self.perms(a) for a in (*self.changed, *self.untouched)}

    def test_forward_grants_and_materialises_with_one_truthful_audit_row_each(self):
        untouched = {a.pk: self.perms(a) for a in self.untouched}
        changed = M.grant_scholars_manage(live_apps, None)
        self.assertEqual(sorted(changed), sorted(a.pk for a in self.changed))
        for a in self.granted[:4]:
            self.assertEqual(self.perms(a), [*PRESET, M.KEY])
        self.assertEqual(self.perms(self.reviewing), [*REVIEWING, M.KEY])
        self.assertEqual(self.perms(self.reviewing_view), [*REVIEWING_VIEW, M.KEY])
        self.assertEqual(self.perms(self.admin_null), [*M.ADMIN_PRESET, *M.ADMIN_PRESET_V2, M.KEY])
        for a in self.untouched:
            self.assertEqual(self.perms(a), untouched[a.pk], a.role)
        rows = {r.target_id: r for r in StaffPermissionChange.objects.all()}
        self.assertEqual(set(rows), set(changed))
        one = rows[self.reviewing_view.pk]
        self.assertEqual((one.kind, one.role, one.changed_by_email, one.changed_by_role, one.before, one.after),
                         ('edit', 'reviewer', '', 'migration', REVIEWING_VIEW, [*REVIEWING_VIEW, M.KEY]))
        self.assertEqual(rows[self.admin_null.pk].kind, 'edit_null')

    def test_after_it_every_view_holder_manages_and_keeps_every_group(self):
        groups = {a.pk: st.tables(PartnerAdmin.objects.get(pk=a.pk)) for a in self.changed}
        M.grant_scholars_manage(live_apps, None)
        for a in (self.admin, self.reviewing, self.reviewing_view, self.admin_null):
            fresh = PartnerAdmin.objects.get(pk=a.pk)
            self.assertTrue(st.opens(fresh, M.KEY), a.pk)
            self.assertTrue(st.in_admins(fresh), a.pk)
        for a in self.changed:                                     # today's stopgap group read (keys, until S6) moves for nobody
            self.assertEqual(st.tables(PartnerAdmin.objects.get(pk=a.pk)), groups[a.pk], a.pk)

    def test_it_is_idempotent(self):
        M.grant_scholars_manage(live_apps, None)
        after = self.snapshot()
        self.assertEqual(M.grant_scholars_manage(live_apps, None), [])
        self.assertEqual(self.snapshot(), after)
        self.assertEqual(StaffPermissionChange.objects.count(), len(self.changed))

    def test_backwards_is_exact_and_never_takes_back_0099s_rows(self):
        before = self.snapshot()
        lead = self.untouched[4]
        m0099 = StaffPermissionChange.objects.create(        # the shape 0099 wrote: the same key appended
            target_id=lead.pk, organisation_id=lead.owning_organisation_id, kind='edit', role='org_admin',
            before=['see_all', 'scholars'], after=['see_all', 'scholars', M.KEY], changed_by_email='',
            changed_by_role='migration')
        M.grant_scholars_manage(live_apps, None)
        restored = M.take_back_scholars_manage(live_apps, None)
        self.assertEqual(sorted(restored), sorted(a.pk for a in self.changed))
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(self.perms(self.admin_null))
        self.assertEqual(list(StaffPermissionChange.objects.values_list('pk', flat=True)), [m0099.pk])

    def test_backwards_leaves_a_row_changed_since_and_the_newest_row_decides(self):
        M.grant_scholars_manage(live_apps, None)
        PartnerAdmin.objects.filter(pk=self.admin.pk).update(permissions=['see_all', 'scholars'])  # switched off
        self.assertEqual(M.grant_scholars_manage(live_apps, None), [self.admin.pk])          # re-run gives it back
        PartnerAdmin.objects.filter(pk=self.reviewing.pk).update(permissions=['review'])      # edited since
        M.take_back_scholars_manage(live_apps, None)
        self.assertEqual(self.perms(self.admin), ['see_all', 'scholars'])
        self.assertEqual(self.perms(self.reviewing), ['review'])
        self.assertEqual(self.perms(self.reviewing_view), REVIEWING_VIEW)
        self.assertFalse(StaffPermissionChange.objects.filter(changed_by_role='migration').exists())
