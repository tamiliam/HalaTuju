"""Sprint S1 (owner 2026-11-09, decision S1-g): the saved-key rows that read Scholars today keep it.

S1 gives Scholars its own key, `scholars` (`apps/courses/staff_permissions.py`). Until S1 the Scholars door
opened on `see_all` (and `review` / `qc`), so a saved list holding `see_all` would lose Scholars at deploy.
This migration adds `scholars` to every SAVED list (`permissions` is not NULL) of an ACTIVE team member
(`role` in admin / finance / qc / reviewer, `is_active` true) that NAMES `see_all` and lacks `scholars`.
Live, that is 4 rows (read-only count, 2026-11-09). Not a list that holds `qc` alone: `qc` implies
`see_all` for Applications, but the owner ruled (2026-11-10) that Quality check carries no Scholars role.
Not a deactivated row: nobody reads Scholars through it, and the owner ticks the key if one comes back.
A NULL list is the role's preset, which now carries the key where S1-a says so: nothing to write. The
organisation lead and a super are never stored.

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
     WHERE role IN ('admin', 'finance', 'qc', 'reviewer') AND is_active
       AND jsonb_typeof(permissions) = 'array' AND permissions ? 'see_all' AND NOT permissions ? 'scholars';
    UPDATE partner_admins SET permissions = permissions || '["scholars"]'::jsonb
     WHERE role IN ('admin', 'finance', 'qc', 'reviewer') AND is_active
       AND jsonb_typeof(permissions) = 'array' AND permissions ? 'see_all' AND NOT permissions ? 'scholars';
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0095_grant_scholars_key', now());
    COMMIT;

Reverse: only the audit rows this migration wrote (changed_by_role 'migration', kind 'edit', no actor,
`after` holds `scholars` and `before` lacks it) are read; the key comes off exactly the rows they name,
and only those audit rows go. Any other 'migration' row is left alone.
"""
from django.db import migrations

TEAM_ROLES = ('admin', 'finance', 'qc', 'reviewer')
KEY = 'scholars'
#: The key a saved list must NAME to gain `scholars` (`qc` alone does not: owner ruling, 2026-11-10).
SEE_ALL = 'see_all'
BY_ROLE = 'migration'


def _gains(stored):
    return isinstance(stored, list) and KEY not in stored and SEE_ALL in stored


def _ours(row):
    """An audit row this migration wrote: it added `scholars` and nothing else wrote it that way."""
    return (isinstance(row.after, list) and KEY in row.after
            and not (isinstance(row.before, list) and KEY in row.before))


def grant_scholars(apps, schema_editor):
    """Add `scholars` to each active saved list that names `see_all`, with its audit row. Idempotent.
    Returns the ids changed (for the test)."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    changed = []
    for admin in (PartnerAdmin.objects.filter(role__in=TEAM_ROLES, is_active=True, permissions__isnull=False)
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
    """Undo exactly what `grant_scholars` did: take the key off the rows its own audit rows name, then
    delete only those audit rows. Returns the ids changed (for the test)."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    candidates = StaffPermissionChange.objects.filter(
        changed_by_role=BY_ROLE, changed_by_email='', kind='edit')
    rows = [row for row in candidates.order_by('id') if _ours(row)]
    changed = []
    for row in rows:
        admin = PartnerAdmin.objects.filter(pk=row.target_id).only('id', 'permissions').first()
        if admin is not None and isinstance(admin.permissions, list) and KEY in admin.permissions:
            PartnerAdmin.objects.filter(pk=admin.pk).update(
                permissions=[k for k in admin.permissions if k != KEY])
            changed.append(admin.pk)
    StaffPermissionChange.objects.filter(pk__in=[row.pk for row in rows]).delete()
    return changed


class Migration(migrations.Migration):

    # Re-pointed from 0093 to main's 0094 at the merge with `activity-release` (one courses leaf). This
    # migration never reads `is_super_admin` (0094 dropped it): it filters and loads by `role` only.
    dependencies = [
        ('courses', '0094_drop_partneradmin_is_super_admin'),
        ('scholarship', '0175_staff_permission_changes'),
    ]

    operations = [
        migrations.RunPython(grant_scholars, withdraw_scholars),
    ]
