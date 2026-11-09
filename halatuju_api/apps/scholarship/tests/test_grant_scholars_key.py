"""Sprint S1 (decision S1-g): courses 0095 adds `scholars` to every ACTIVE saved list that NAMES `see_all`.

Done-when: it adds the key to every such row — not a `qc`-only list (owner ruling 2026-11-10: Quality
check carries no Scholars role), not a deactivated row — touches nothing else, keeps the permission-change
audit truthful, and reverses cleanly, touching no audit row it did not write. Run on the live app registry
(the functions take `apps`).
"""
from importlib import import_module

from django.apps import apps as live_apps
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import StaffPermissionChange
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org

MIGRATION = import_module('apps.courses.migrations.0095_grant_scholars_key')


class GrantScholarsKey(TestCase):
    @classmethod
    def setUpTestData(cls):
        org = make_org()

        def person(role, keys=None, **kw):
            return make_admin(role, owning_org=org, permissions=keys, **kw) if keys is not None \
                else make_admin(role, owning_org=org, **kw)
        cls.gain = {
            'admin_see_all': person('admin', ['see_all', 'spending']),
            'reviewer_see_all': person('reviewer', ['review', 'see_all', 'spending']),
            'finance_see_all': person('finance', ['payments_approve', 'see_all']),
            'qc_see_all': person('qc', ['qc', 'see_all']),        # names `see_all`: it gains
        }
        cls.keep = {
            'preset_admin': person('admin'),                       # NULL: the preset carries the key
            'preset_reviewer': person('reviewer'),
            'review_only': person('reviewer', ['review']),
            'spending_only': person('admin', ['spending']),
            'already': person('admin', ['see_all', 'scholars']),
            'qc_alone': person('qc', ['qc']),                      # `qc` implies `see_all`, never Scholars
            'reviewer_qc': person('reviewer', ['review', 'qc']),
            'inactive_see_all': person('admin', ['see_all', 'spending'], is_active=False),
            'lead': person('org_admin'),
            'super': make_admin('super', super_admin=True),
        }
        # the lead is never stored or read from `permissions`: a stray list on that row is not touched
        PartnerAdmin.objects.filter(pk=cls.keep['lead'].pk).update(permissions=['see_all'])

    def _stored(self):
        return dict(PartnerAdmin.objects.values_list('pk', 'permissions'))

    def test_every_saved_see_all_row_gains_the_key_and_nothing_else_moves(self):
        before = self._stored()
        changed = MIGRATION.grant_scholars(live_apps, None)
        after = self._stored()
        self.assertEqual(sorted(changed), sorted(p.pk for p in self.gain.values()))
        for name, person in self.gain.items():
            with self.subTest(name):
                self.assertEqual(after[person.pk], [*before[person.pk], 'scholars'])
                person.refresh_from_db()
                self.assertTrue(person.has_perm('scholars'))
        self.assertEqual({pk: v for pk, v in after.items() if pk not in changed},
                         {pk: v for pk, v in before.items() if pk not in changed})
        self.assertEqual(MIGRATION.grant_scholars(live_apps, None), [])          # idempotent

    def test_the_audit_names_each_addition(self):
        changed = MIGRATION.grant_scholars(live_apps, None)
        rows = StaffPermissionChange.objects.filter(changed_by_role='migration')
        self.assertEqual(sorted(rows.values_list('target_id', flat=True)), sorted(changed))
        row = rows.get(target_id=self.gain['admin_see_all'].pk)
        self.assertEqual((row.kind, row.role, row.before, row.after, row.changed_by_email),
                         ('edit', 'admin', ['see_all', 'spending'], ['see_all', 'spending', 'scholars'], ''))
        self.assertEqual(row.organisation_id, self.gain['admin_see_all'].owning_organisation_id)

    def test_it_reverses_cleanly(self):
        before = self._stored()
        audit_before = StaffPermissionChange.objects.count()
        MIGRATION.grant_scholars(live_apps, None)
        undone = MIGRATION.withdraw_scholars(live_apps, None)
        self.assertEqual(sorted(undone), sorted(p.pk for p in self.gain.values()))
        self.assertEqual(self._stored(), before)
        self.assertEqual(StaffPermissionChange.objects.count(), audit_before)
        self.assertEqual(self._stored()[self.keep['already'].pk], ['see_all', 'scholars'])  # not its key

    def test_the_reverse_leaves_every_other_migration_row_alone(self):
        other = StaffPermissionChange.objects.create(        # `before` already held the key: not 0095's
            target_id=self.keep['already'].pk, target_email='', organisation_id=None, kind='edit',
            role='admin', before=['see_all', 'scholars'], after=['see_all', 'scholars'],
            changed_by_email='', changed_by_role='migration')
        unrelated = StaffPermissionChange.objects.create(
            target_id=self.keep['spending_only'].pk, target_email='', organisation_id=None, kind='edit',
            role='admin', before=['see_all'], after=['spending'], changed_by_email='',
            changed_by_role='migration')
        MIGRATION.grant_scholars(live_apps, None)
        undone = MIGRATION.withdraw_scholars(live_apps, None)
        self.assertEqual(sorted(undone), sorted(p.pk for p in self.gain.values()))
        self.assertEqual(StaffPermissionChange.objects.filter(pk__in=[other.pk, unrelated.pk]).count(), 2)
        self.assertEqual(self._stored()[self.keep['already'].pk], ['see_all', 'scholars'])

    @override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_the_persons_changes_say_a_migration_made_it(self):
        MIGRATION.grant_scholars(live_apps, None)
        target = self.gain['admin_see_all']
        res = authed_client(self.keep['lead']).get(f'/api/v1/admin/admins/{target.pk}/permissions/')
        self.assertEqual(res.status_code, 200, res.content)
        row = res.json()['history'][0]
        self.assertEqual((row['by'], row['by_super'], row['by_migration'], row['added']),
                         ('', False, True, ['scholars']))
