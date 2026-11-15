"""Sprint M3c (decision D5, 2026-11-15): the new key `scholars.approve` (the senior letters on a scholar's
file, `letters._senior`) is ADDED to every organisation admin row that stores a list, before the code stops
reading that power from the role.

Until M3c `letters._senior` answered "a super or an `org_admin`". M3c reads the key, and the organisation
admin's row stores its keys (migration 0098), so this data step APPENDS `scholars.approve` to the list of
every `org_admin` row whose value is a JSON list that does not hold it — active, revoked, archived or pending
alike (a later Restore must give back what the role gave). Nothing else in the list moves; nothing is taken
away. A NULL row (SQL NULL or a jsonb `null`) is left alone: the new code reads it as the full set
(the v2 catalogue's `org_admin_v2`), which now includes the key. A row whose value is neither NULL nor a
list is left alone too (also read as the full set). Any other role is untouched.

Idempotent: a row that already holds the key is not written and gets no audit row.

ADDITIVE. THE OLD IMAGE IGNORES THE NEW KEY: it reads an organisation admin's stored list strictly through
its own `ORG_ADMIN_V2`, which does not name `scholars.approve`, and `staff_permissions.clean` drops every v2
key, so every page and button answers as before until the new image ships (migrate-first, the 0097 / 0098
precedent). The old image's writers keep the key: Team -> Reviewers Add / Remove keeps every other entry
(`org_admin_list`), and a role change or an invitation writes NULL, which the new code reads as the full set.

⚠ AFTER 0098. 0098's DATA block REPLACES an organisation admin's list. If it is ever re-run (its own window
re-run included), run this DATA block again straight after it, or the key is lost; this step's POST-DEPLOY
CHECK supersedes 0098's equality check from now on (0098's planned lists do not name the key). ⚠ Run this
DATA block again only as part of this release: from M3c a super may take the key from an organisation admin
(People -> a person), and a later re-run would give it back.

THE AUDIT STAYS TRUTHFUL. Each row changed gets one `staff_permission_changes` row: kind 'edit', the list
before and after, `changed_by_email` '' and `changed_by_role` 'migration'. The constants are FROZEN here (a
migration never imports app code); `test_m3c_migration_0099` proves they equal the live ones and pins the
SQL's WHERE text to `plan_row` (the test database cannot run jsonb).

SQL, MIGRATE-FIRST, by hand. Run the PRE-CHECK, then the DATA block (it writes the ledger row in the same
transaction); after the new image carries all the traffic, run the release note's GUARDED copy of the DATA
block (review F2: it skips a row a person changed since the first run) and its POST-DEPLOY CHECK (the
release note, `docs/releases/m3c-granting-release-note-draft.md`, carries them).

PRE-CHECK (read-only): the organisation admin rows by shape and whether they hold the key, and the ledger.
    BEGIN READ ONLY;
    SELECT jsonb_typeof(permissions) AS shape, permissions ? 'scholars.approve' AS has_key, count(*)
      FROM partner_admins WHERE role = 'org_admin' GROUP BY 1, 2 ORDER BY 1, 2;
    SELECT name FROM django_migrations
     WHERE app = 'courses' AND name IN ('0098_store_org_admin_keys', '0099_grant_scholars_approve');
    COMMIT;
Expect 0098 listed and 0099 not.

DATA block (one transaction, the ledger row included; safe to re-run: a row that holds the key is not
written and gets no audit row, and the ledger row is written once):
    BEGIN;
    WITH plan AS (
      SELECT id, email, owning_organisation_id, role, permissions AS base,
             permissions || '["scholars.approve"]'::jsonb AS after
        FROM partner_admins
       WHERE role = 'org_admin'
         AND jsonb_typeof(permissions) = 'array'
         AND NOT permissions ? 'scholars.approve'
    ), audit AS (
      INSERT INTO staff_permission_changes (target_id, target_email, organisation_id, kind, role, before,
                                            after, changed_by_email, changed_by_role, created_at)
      SELECT id, COALESCE(email, ''), owning_organisation_id, 'edit', role, base, after, '', 'migration', now()
        FROM plan
    )
    UPDATE partner_admins p SET permissions = g.after FROM plan g WHERE p.id = g.id;
    INSERT INTO django_migrations (app, name, applied)
    SELECT 'courses', '0099_grant_scholars_approve', now()
     WHERE NOT EXISTS (SELECT 1 FROM django_migrations
                        WHERE app = 'courses' AND name = '0099_grant_scholars_approve');
    COMMIT;

POST-DEPLOY CHECK (read-only, after re-running the DATA block): every organisation admin row that stores a
list without the key. It must return ZERO rows. If not zero, re-run the DATA block only.
    SELECT id FROM partner_admins
     WHERE role = 'org_admin'
       AND jsonb_typeof(permissions) = 'array'
       AND NOT permissions ? 'scholars.approve';

Reverse: only the audit rows this migration wrote (changed_by_role 'migration', no actor, kind 'edit', role
'org_admin', `after` exactly `before` plus the key, and the key not in `before`) are read, and for each row
only the NEWEST of them. A row still holding exactly that row's `after` goes back to its `before`; a row
changed since is left as it is. Only those audit rows go. Safe under either image (the old image ignores the
key; the new one reads a list without it as an organisation admin without the senior letters).
"""
from django.db import migrations

#: FROZEN copies (`test_m3c_migration_0099.FrozenConstants` holds them equal to the live code).
ROLE = 'org_admin'
KEY = 'scholars.approve'
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


def grant_scholars_approve(apps, schema_editor):
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


def take_back_scholars_approve(apps, schema_editor):
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
        ('courses', '0098_store_org_admin_keys'),
    ]

    operations = [
        migrations.RunPython(grant_scholars_approve, take_back_scholars_approve),
    ]
