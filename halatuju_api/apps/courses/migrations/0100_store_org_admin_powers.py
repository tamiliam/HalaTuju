"""Sprint M4a (ACCESS-BY-SWITCHES S2, owner 2026-11-19): the new key `organisation.admin` ("Organisation
admin powers") is ADDED to every organisation admin row that stores a list, before the code stops reading
those powers from the role.

Until M4a the powers an organisation admin holds by being one (manage the team, pay the bill, approve
requests, build and read payment runs, approve a run when nobody else can, vet platform sponsors) were read
from `role == 'org_admin'`. M4a reads them through ONE helper, `staff_permissions.holds_org_admin_powers`,
which asks for this key on a stored list. So this data step APPENDS `organisation.admin` to the list of every
`org_admin` row whose value is a JSON list that does not hold it — active, revoked, archived or pending
alike (a later Restore must give back what the role gave). Nothing else in the list moves; nothing is taken
away. A NULL row (SQL NULL or a jsonb `null`) is left alone: the new code reads it as holding the key
(fail-safe, as `org_admin_v2`). A row whose value is neither NULL nor a list is left alone too (read the same
way). Any other role is untouched.

Idempotent: a row that already holds the key is not written and gets no audit row.

ADDITIVE. THE OLD IMAGE IGNORES THE NEW KEY: `staff_permissions.clean` keeps only `CATALOGUE` keys (it drops
this one), `org_admin_v2` reads only `ORG_ADMIN_V2` keys, `stored_v2` answers none for an organisation admin,
and no live code names `organisation.admin` (`test_m4a_migration_0100` proves both). Every page and button
answers as before until the new image ships (migrate-first, the 0098 / 0099 precedent).

⚠ THE WINDOW. Between this step and the new image carrying all traffic, nobody edits an organisation admin's
card: an old-image save writes `ORG_ADMIN_SET`, which drops the key. Re-run the DATA block ONCE after the new
image carries all traffic, then never again: from M4a a super may untick the key (People -> a person), and a
later re-run would give it back (the 0099 rule). ⚠ AFTER 0098 / 0099: if either is ever re-run, run this
DATA block straight after it.

THE AUDIT STAYS TRUTHFUL. Each row changed gets one `staff_permission_changes` row: kind 'edit', the list
before and after, `changed_by_email` '' and `changed_by_role` 'migration'. The constants are FROZEN here (a
migration never imports app code); `test_m4a_migration_0100` proves they equal the live ones and pins the
SQL's WHERE text to `plan_row` (the test database cannot run jsonb).

SQL, MIGRATE-FIRST, by hand, with the owner's yes. Run the PRE-CHECK, then the DATA block (it writes the
ledger row in the same transaction); after the new image carries all the traffic, run the DATA block once
more and the POST-DEPLOY CHECK.

PRE-CHECK (read-only): the organisation admin rows by shape and whether they hold the key, the ledger, and
the team rows that store `payments.view` (the new image reads it as Payments View, `stored_v2`).
    BEGIN READ ONLY;
    SELECT jsonb_typeof(permissions) AS shape, permissions ? 'organisation.admin' AS has_key, count(*)
      FROM partner_admins WHERE role = 'org_admin' GROUP BY 1, 2 ORDER BY 1, 2;
    SELECT name FROM django_migrations
     WHERE app = 'courses' AND name IN ('0099_grant_scholars_approve', '0100_store_org_admin_powers');
    SELECT count(*) FROM partner_admins
     WHERE role <> 'org_admin' AND jsonb_typeof(permissions) = 'array' AND permissions ? 'payments.view';
    COMMIT;
Expect 0099 listed and 0100 not, and the last count 0 (a team row storing it would gain the Payments page).

DATA block (one transaction, the ledger row included; safe to re-run: a row that holds the key is not
written and gets no audit row, and the ledger row is written once):
    BEGIN;
    WITH plan AS (
      SELECT id, email, owning_organisation_id, role, permissions AS base,
             permissions || '["organisation.admin"]'::jsonb AS after
        FROM partner_admins
       WHERE role = 'org_admin'
         AND jsonb_typeof(permissions) = 'array'
         AND NOT permissions ? 'organisation.admin'
    ), audit AS (
      INSERT INTO staff_permission_changes (target_id, target_email, organisation_id, kind, role, before,
                                            after, changed_by_email, changed_by_role, created_at)
      SELECT id, COALESCE(email, ''), owning_organisation_id, 'edit', role, base, after, '', 'migration', now()
        FROM plan
    )
    UPDATE partner_admins p SET permissions = g.after FROM plan g WHERE p.id = g.id;
    INSERT INTO django_migrations (app, name, applied)
    SELECT 'courses', '0100_store_org_admin_powers', now()
     WHERE NOT EXISTS (SELECT 1 FROM django_migrations
                        WHERE app = 'courses' AND name = '0100_store_org_admin_powers');
    COMMIT;

POST-DEPLOY CHECK (read-only, after re-running the DATA block). Each must return ZERO.
    SELECT count(*) FROM partner_admins
     WHERE role = 'org_admin' AND jsonb_typeof(permissions) = 'array'
       AND NOT permissions ? 'organisation.admin';
    SELECT count(*) FROM partner_admins
     WHERE role <> 'org_admin' AND jsonb_typeof(permissions) = 'array'
       AND permissions ? 'organisation.admin';
    SELECT count(*) FROM partner_admins
     WHERE role = 'org_admin' AND jsonb_typeof(permissions) = 'array'
       AND permissions ?| array['payments_prepare','payments_check','payments_approve','payments.view',
                                'payments.prepare','payments.check','payments.approve','sponsors.check'];

Reverse: only the audit rows this migration wrote (changed_by_role 'migration', no actor, kind 'edit', role
'org_admin', `after` exactly `before` plus the key, and the key not in `before`) are read, and for each row
only the NEWEST of them. A row still holding exactly that row's `after` goes back to its `before`; a row
changed since is left as it is. Only those audit rows go. ⚠ Reverse only under the OLD image: the new image
reading a list without the key takes every organisation admin power away.
"""
from django.db import migrations

#: FROZEN copies (`test_m4a_migration_0100.FrozenConstants` holds them equal to the live code).
ROLE = 'org_admin'
KEY = 'organisation.admin'
BY_ROLE = 'migration'
KIND = 'edit'


def plan_row(role, stored):
    """``(before, after)`` lists for one row, or None when this migration leaves it alone. Pure: the
    forward step and the tests both read it."""
    if role != ROLE or not isinstance(stored, list) or KEY in stored:
        return None
    return list(stored), [*stored, KEY]


def _ours(row):
    """An audit row this migration wrote: an organisation admin's list, with the key appended."""
    before, after = row.before, row.after
    return (row.role == ROLE and isinstance(before, list) and isinstance(after, list)
            and KEY not in before and after == [*before, KEY])


def store_org_admin_powers(apps, schema_editor):
    """Forward: the writes the module docstring lists, one audit row per changed row. Idempotent.
    Returns the ids changed (for the test)."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    changed = []
    for admin in (PartnerAdmin.objects.filter(role=ROLE)
                  .only('id', 'email', 'role', 'owning_organisation_id', 'permissions').order_by('id')):
        plan = plan_row(admin.role, admin.permissions)
        if plan is None:
            continue
        before, after = plan
        PartnerAdmin.objects.filter(pk=admin.pk).update(permissions=after)
        StaffPermissionChange.objects.create(
            target_id=admin.pk, target_email=admin.email or '', organisation_id=admin.owning_organisation_id,
            kind=KIND, role=admin.role, before=before, after=after, changed_by_email='',
            changed_by_role=BY_ROLE)
        changed.append(admin.pk)
    return changed


def take_back_org_admin_powers(apps, schema_editor):
    """Reverse: put back each row this migration wrote that still holds what its NEWEST audit row here
    wrote, then delete only this migration's audit rows. Returns the ids changed."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    candidates = StaffPermissionChange.objects.filter(
        changed_by_role=BY_ROLE, changed_by_email='', kind=KIND, role=ROLE)
    rows = [row for row in candidates.order_by('id') if _ours(row)]
    newest = {}
    for row in rows:                       # ascending ids: the last one seen per row is the newest
        newest[row.target_id] = row
    changed = []
    for row in newest.values():
        admin = PartnerAdmin.objects.filter(pk=row.target_id).only('id', 'role', 'permissions').first()
        if admin is None or admin.role != ROLE or admin.permissions != row.after:
            continue
        PartnerAdmin.objects.filter(pk=admin.pk).update(permissions=list(row.before))
        changed.append(admin.pk)
    StaffPermissionChange.objects.filter(pk__in=[row.pk for row in rows]).delete()
    return changed


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0099_grant_scholars_approve'),
    ]

    operations = [
        migrations.RunPython(store_org_admin_powers, take_back_org_admin_powers),
    ]
