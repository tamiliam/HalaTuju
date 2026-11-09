"""Sprint S1 (owner 2026-11-09, decision S1-g): the saved-key rows that read Scholars today keep it.

S1 gives Scholars its own key, `scholars` (`apps/courses/staff_permissions.py`). Until S1 the Scholars door
opened on `see_all` (and `review` / `qc`), so a saved list holding `see_all` would lose Scholars at deploy.
This migration adds `scholars` to every SAVED list (`permissions` is not NULL) of a team member (`role` in
admin / finance / qc / reviewer) that holds `see_all` — named, or brought by `qc` (`IMPLIES`) — and lacks
`scholars`. Live, that is 4 rows (read-only count, 2026-11-09). A NULL list is the role's preset, which now
carries the key where S1-a says so: nothing to write. The organisation lead and a super are never stored.

THE AUDIT STAYS TRUTHFUL. Each row changed gets one `staff_permission_changes` row: kind 'edit', the
STORED list before and after, `changed_by_email` '' and `changed_by_role` 'migration' (nobody clicked;
the staff-activity backfill skips a row with no actor). The owner can untick the key on Permissions.

The key is APPENDED to the stored list (readers order it by the catalogue, `staff_permissions.clean`), so
the hand-applied SQL below writes exactly what this code writes. The OLD image drops the unknown key on
read (`clean` keeps catalogue keys only), so the rows are safe before the push.

SQL (MIGRATE-FIRST, by hand, one transaction; the release note carries it with its pre-check):
    BEGIN;
    INSERT INTO staff_permission_changes (target_id, target_email, organisation_id, kind, role, before,
                                          after, changed_by_email, changed_by_role, created_at)
    SELECT id, COALESCE(email, ''), owning_organisation_id, 'edit', role, permissions,
           permissions || '["scholars"]'::jsonb, '', 'migration', now()
      FROM partner_admins
     WHERE role IN ('admin', 'finance', 'qc', 'reviewer') AND jsonb_typeof(permissions) = 'array'
       AND (permissions ? 'see_all' OR permissions ? 'qc') AND NOT permissions ? 'scholars';
    UPDATE partner_admins SET permissions = permissions || '["scholars"]'::jsonb
     WHERE role IN ('admin', 'finance', 'qc', 'reviewer') AND jsonb_typeof(permissions) = 'array'
       AND (permissions ? 'see_all' OR permissions ? 'qc') AND NOT permissions ? 'scholars';
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0095_grant_scholars_key', now());
    COMMIT;

Reverse: the key comes off exactly the rows this migration's audit rows name, and those audit rows go.
"""
from django.db import migrations

TEAM_ROLES = ('admin', 'finance', 'qc', 'reviewer')
KEY = 'scholars'
#: The keys that make a saved list hold `see_all` (`qc` brings it: `staff_permissions.IMPLIES`).
HOLDS_SEE_ALL = ('see_all', 'qc')
BY_ROLE = 'migration'


def _gains(stored):
    return (isinstance(stored, list) and KEY not in stored
            and any(k in stored for k in HOLDS_SEE_ALL))


def grant_scholars(apps, schema_editor):
    """Add `scholars` to each saved list that holds `see_all`, with its audit row. Idempotent. Returns
    the ids changed (for the test)."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    changed = []
    for admin in (PartnerAdmin.objects.filter(role__in=TEAM_ROLES, permissions__isnull=False)
                  .only('id', 'email', 'role', 'owning_organisation_id', 'permissions').order_by('id')):
        before = admin.permissions
        if not _gains(before):
            continue
        after = [*before, KEY]
        PartnerAdmin.objects.filter(pk=admin.pk).update(permissions=after)
        StaffPermissionChange.objects.create(
            target_id=admin.pk, target_email=admin.email or '',
            organisation_id=admin.owning_organisation_id, kind='edit', role=admin.role,
            before=list(before), after=after, changed_by_email='', changed_by_role=BY_ROLE)
        changed.append(admin.pk)
    return changed


def withdraw_scholars(apps, schema_editor):
    """Undo exactly what `grant_scholars` did: take the key off the rows its audit rows name, then delete
    those audit rows. Returns the ids changed (for the test)."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    rows = StaffPermissionChange.objects.filter(changed_by_role=BY_ROLE, changed_by_email='', kind='edit')
    changed = []
    for row in rows.order_by('id'):
        admin = PartnerAdmin.objects.filter(pk=row.target_id).only('id', 'permissions').first()
        if admin is not None and isinstance(admin.permissions, list) and KEY in admin.permissions:
            PartnerAdmin.objects.filter(pk=admin.pk).update(
                permissions=[k for k in admin.permissions if k != KEY])
            changed.append(admin.pk)
    rows.delete()
    return changed


class Migration(migrations.Migration):

    # ⚠ origin/main has courses 0094_drop_partneradmin_is_super_admin, which this branch cannot see: the
    # merge re-points the first dependency to it (sprint S1 report).
    dependencies = [
        ('courses', '0093_retire_partneradmin_is_super_admin'),
        ('scholarship', '0175_staff_permission_changes'),
    ]

    operations = [
        migrations.RunPython(grant_scholars, withdraw_scholars),
    ]
