"""Sprint M2b (decisions D7-D9, 2026-11-12): the Permissions editor and the table moves write v2 page keys.

- `asked_set` stores grantable v2 keys; refuses NEVER_GRANTABLE (`never_grantable`), any other lead-only
  key (`lead_tier`, until M3), a key an old key already means (`alias_permission`) and an unknown key.
- NULL only when the old part is the role's preset AND no v2 key is held; an Admin on its preset on both
  parts is not "Custom"; a save that changes nothing writes nothing.
- A tab opened before M2b (no `v2: true`) keeps the stored v2 keys; the GET draws them by group.
- Add to Admins applies ADMIN_PRESET_V2; leaving Admins strips every v2 key; Change role into `admin`
  stores ADMIN_PRESET_V2.
"""
from django.test import TestCase, override_settings

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.scholarship import staff_tables_admin as sta
from apps.scholarship.models import StaffPermissionChange
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org

ADMIN = list(sp.preset_for('admin'))


def _url(target):
    return f'/api/v1/admin/admins/{target.pk}/permissions/'


def _patch(who, target, keys, **extra):
    return authed_client(who).patch(_url(target), {'permissions': keys, **extra}, format='json')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class Save(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def fresh(self, a):
        a.refresh_from_db()
        return a

    def test_a_v2_key_is_stored_with_its_view_and_seats_at_admins(self):
        rev = make_admin('reviewer', owning_org=self.org)
        r = _patch(self.lead, rev, ['review', 'surveys.edit'], v2=True)
        self.assertEqual(r.status_code, 200, r.content[:300])
        body = r.json()
        self.assertEqual((body['permissions'], body['v2_held'], body['custom']),
                         (['review'], ['surveys.view', 'surveys.edit'], True))
        self.assertEqual(self.fresh(rev).permissions, ['review', 'surveys.view', 'surveys.edit'])
        self.assertEqual(st.tables(rev), ('admins', 'reviewers'))
        self.assertTrue(st.opens(rev, 'surveys.edit'))
        row = StaffPermissionChange.objects.get(target=rev)
        self.assertEqual((row.before, row.after), (['review'], ['review', 'surveys.view', 'surveys.edit']))

    def test_each_refusal_has_its_code_and_writes_nothing(self):
        rev = make_admin('reviewer', owning_org=self.org)
        for asked, code in ((['review', 'billing.edit'], 'never_grantable'),
                            (['review', 'requests.approve'], 'never_grantable'),
                            (['review', 'settings.edit'], 'lead_tier'),
                            (['review', 'invitations.edit'], 'lead_tier'),
                            (['review', 'manage_team'], 'lead_tier'),
                            (['review', 'students.view'], 'alias_permission'),
                            (['review', 'payments.approve'], 'alias_permission'),
                            (['review', 'team.nonsense'], 'unknown_permission')):
            with self.subTest(asked=asked):
                r = _patch(self.lead, rev, asked, v2=True)
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
        self.assertEqual(_patch(self.lead, rev, ['billing.edit'], v2=True).json()['keys'], ['billing.edit'])
        self.assertIsNone(self.fresh(rev).permissions)
        self.assertFalse(StaffPermissionChange.objects.exists())

    def test_null_only_for_the_old_preset_with_no_v2_key(self):
        a = make_admin('admin', owning_org=self.org, pre_m2b=True)          # a NULL row
        _patch(self.lead, a, [*ADMIN, 'team.view'], v2=True)
        self.assertEqual(self.fresh(a).permissions, [*ADMIN, 'team.view'])
        _patch(self.lead, a, ADMIN, v2=True)
        self.assertIsNone(self.fresh(a).permissions)

    def test_the_admin_preset_on_both_parts_is_not_custom_and_an_unchanged_save_writes_nothing(self):
        a = make_admin('admin', owning_org=self.org)                        # the post-0097 shape
        self.assertFalse(sp.is_custom(a))
        self.assertEqual(sp.preset_diff(a), ([], []))
        r = _patch(self.lead, a, [*ADMIN, *v2.ADMIN_PRESET_V2], v2=True)
        self.assertEqual((r.json()['changed'], r.json()['custom']), (False, False))
        self.assertFalse(StaffPermissionChange.objects.exists())

    def test_saves_are_idempotent(self):
        rev = make_admin('reviewer', owning_org=self.org)
        for _ in range(2):
            r = _patch(self.lead, rev, ['review', 'team.view', 'mentoring.edit'], v2=True)
        self.assertFalse(r.json()['changed'])
        self.assertEqual(StaffPermissionChange.objects.filter(target=rev).count(), 1)
        self.assertEqual(self.fresh(rev).permissions, ['review', 'team.view', 'mentoring.view', 'mentoring.edit'])

    def test_a_tab_without_the_v2_flag_keeps_the_stored_v2_keys(self):
        a = make_admin('admin', owning_org=self.org)
        r = _patch(self.lead, a, ['see_all', 'scholars', 'payments_prepare'])          # Spending off
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json()['permissions'], ['see_all', 'scholars', 'payments_prepare'])
        self.assertEqual(self.fresh(a).permissions,
                         ['see_all', 'scholars', 'payments_prepare', *v2.ADMIN_PRESET_V2])
        self.assertTrue(st.may_do_admin_work(a))
        _patch(self.lead, a, ['see_all', 'scholars', 'payments_prepare'], v2=True)    # the M2b screen
        self.assertEqual(self.fresh(a).permissions, ['see_all', 'scholars', 'payments_prepare'])
        self.assertFalse(st.may_do_admin_work(a))
        self.assertTrue(st.may_read_org(a))                                          # the see_all seat

    def test_custom_and_the_chips_weigh_each_part_against_its_own_preset(self):
        a = make_admin('admin', owning_org=self.org, pre_m2b=True,      # as saved: 0097 already ran
                       permissions=[*ADMIN, *(k for k in v2.ADMIN_PRESET_V2 if k != 'surveys.edit')])
        self.assertTrue(sp.is_custom(a))
        self.assertEqual(sp.preset_diff(a), ([], ['surveys.edit']))
        fin = make_admin('finance', owning_org=self.org, permissions=['payments_approve'])   # + ORG_READ (0097)
        self.assertEqual(sp.preset_diff(fin), ([], []))
        rev = make_admin('reviewer', owning_org=self.org, permissions=['review', 'team.view'])
        self.assertEqual(sp.preset_diff(rev), (['team.view'], []))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class Get(TestCase):
    def test_the_v2_keys_by_group_with_reasons(self):
        org = make_org()
        lead = make_admin('org_admin', owning_org=org)
        a = make_admin('admin', owning_org=org, first_seen_at=None)
        body = authed_client(lead).get(_url(a)).json()
        self.assertEqual([g['group'] for g in body['v2_keys']], list(v2.GROUPS))
        keys = {k['key']: k for g in body['v2_keys'] for k in g['keys']}
        self.assertEqual(list(keys), list(v2.CATALOGUE_V2))
        self.assertEqual(keys['billing.edit'] | {}, {'key': 'billing.edit', 'page': 'billing', 'level': 'edit',
                                                    'grantable': False, 'reason': 'never_grantable',
                                                    'held': False})
        self.assertEqual((keys['settings.edit']['reason'], keys['students.view']['reason']), ('lead_only', 'alias'))
        self.assertTrue(keys['students.view']['held'])                 # through `see_all`
        self.assertTrue(keys['team.view']['grantable'] and keys['team.view']['held'])
        self.assertEqual(body['v2_held'], list(v2.ADMIN_PRESET_V2))
        self.assertEqual(body['v2_preset'], list(v2.ADMIN_PRESET_V2))
        self.assertEqual(body['permissions'], ADMIN)
        self.assertFalse(body['custom'])
        self.assertEqual(body['table_presets']['admins'][-len(v2.ADMIN_PRESET_V2):], list(v2.ADMIN_PRESET_V2))


class TableMoves(TestCase):
    """D8: Add to Admins applies ADMIN_PRESET_V2; leaving Admins strips every v2 key; the old keys move as
    they did before M2b."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def test_add_to_admins_applies_the_preset_and_says_it_opens_the_admin_pages(self):
        rev = make_admin('reviewer', owning_org=self.org)
        _, dry = sta.change(rev.pk, sta.ADMINS, 'add', by=self.lead, dry_run=True)
        self.assertTrue(dry['opens_admin_pages'])
        target, _ = sta.change(rev.pk, sta.ADMINS, 'add', by=self.lead)
        target.refresh_from_db()
        self.assertEqual(target.permissions, ['review', 'see_all', 'scholars', *v2.ADMIN_PRESET_V2])

    def test_remove_from_admins_strips_every_v2_key_and_moves_the_old_ones_as_before(self):
        rev = make_admin('reviewer', owning_org=self.org,
                         permissions=['review', 'see_all', 'spending', *v2.ADMIN_PRESET_V2])
        target, plan = sta.change(rev.pk, sta.ADMINS, 'remove', by=self.lead)
        target.refresh_from_db()
        self.assertEqual((target.role, target.permissions), ('reviewer', None))
        self.assertEqual(st.tables(target), ('reviewers',))
        self.assertFalse(plan['opens_admin_pages'])

    def test_a_reviewer_seated_only_by_v2_keys_can_leave_admins(self):
        rev = make_admin('reviewer', owning_org=self.org, permissions=['review', 'team.view'])
        target, _ = sta.change(rev.pk, sta.ADMINS, 'remove', by=self.lead)
        target.refresh_from_db()
        self.assertEqual((target.permissions, st.tables(target)), (None, ('reviewers',)))

    def test_add_to_reviewers_keeps_the_v2_part(self):
        a = make_admin('admin', owning_org=self.org)
        target, plan = sta.change(a.pk, sta.REVIEWERS, 'add', by=self.lead)
        target.refresh_from_db()
        self.assertEqual(target.permissions, ['review', *ADMIN, *v2.ADMIN_PRESET_V2])
        self.assertFalse(plan['opens_admin_pages'])

    def test_an_admin_leaving_admins_becomes_a_reviewer_with_no_v2_key(self):
        a = make_admin('admin', owning_org=self.org, permissions=['review', 'see_all'])
        target, _ = sta.change(a.pk, sta.ADMINS, 'remove', by=self.lead)
        target.refresh_from_db()
        self.assertEqual((target.role, target.permissions), ('reviewer', None))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ChangeRole(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def switch(self, target, role):
        return authed_client(self.lead).patch(f'/api/v1/admin/admins/{target.pk}/role/', {'role': role},
                                              format='json')

    def test_finance_to_admin_stores_the_admin_preset_and_records_it(self):
        fin = make_admin('finance', owning_org=self.org, permissions=['payments_approve'])
        self.assertEqual(self.switch(fin, 'admin').status_code, 200)
        fin.refresh_from_db()
        self.assertEqual(fin.permissions, ['payments_approve', *v2.ADMIN_PRESET_V2])
        self.assertEqual(sp.resolve(fin), ('payments_approve',))
        row = StaffPermissionChange.objects.get(target=fin, kind='role_change')
        self.assertEqual((row.before, row.after),
                         (['payments_approve', *v2.ORG_READ_V2], ['payments_approve', *v2.ADMIN_PRESET_V2]))

    def test_qc_to_reviewer_keeps_its_v2_keys(self):
        qc = make_admin('qc', owning_org=self.org, permissions=['see_all', 'qc', 'team.view'])
        self.assertEqual(self.switch(qc, 'reviewer').status_code, 200)
        qc.refresh_from_db()
        self.assertEqual((qc.role, qc.permissions), ('reviewer', ['see_all', 'qc', 'team.view']))
        self.assertFalse(StaffPermissionChange.objects.filter(target=qc).exists())
