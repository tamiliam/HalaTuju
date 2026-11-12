"""Sprint M2b (decision D10, 2026-11-12): what the `admin` / `finance` LABELS opened by themselves becomes
STORED v2 page keys, before the code stops reading the labels.

Until M2b the label `admin` opened the admin work pages and seated its holder at the Admins table (which
opens the organisation read pages); `finance` seated its holder at Admins. M2b reads stored keys instead,
so this data step writes, for each row ACTIVE OR REVOKED (architect, 2026-11-12, superseding D10's "inactive
untouched": a later Restore, a bare `is_active=True`, then gives back what the label opened):

  role `admin`               the stored list, or the admin preset materialised when it is NULL, plus every
                             key of ADMIN_PRESET below it lacks (the organisation read + admin work pages);
  role `finance`, a list     plus every key of ORG_READ it lacks (what the Admins seat opened, nothing more);
  role `finance`, NULL       untouched: its preset key `payments_approve` already seats it at Admins, so the
                             same pages open with no write (and no "Custom" chip appears);
  the row with id ROW_ID,    (a reviewer or QC the owner confirmed, who sits at Admins through an old key)
  when ACTIVE
                             its list (or its preset) plus every key of ADMIN_PRESET it lacks — the one
                             person whose pages GROW (owner ruling O8);
  anything else              untouched: the lead tier, a super, a partner, a mentor login.

Live (read-only count, 2026-11-12): 2 active admin rows and 1 active finance row, all with a stored list;
the row ROW_ID stored; 0 revoked admin or finance rows. Idempotent: a key already held is never added again, and a row that gains nothing
is not written and gets no audit row.

THE OLD IMAGE IGNORES THE NEW KEYS: `staff_permissions.clean` keeps catalogue keys only, so a list holding
v2 keys reads exactly as before until the new image ships (migrate-first, the 0095 precedent).

THE AUDIT STAYS TRUTHFUL. Each row changed gets one `staff_permission_changes` row: kind 'edit', the
list before (the preset when the row was NULL) and after, `changed_by_email` '' and `changed_by_role`
'migration'. The keys are APPENDED, in catalogue order, so the hand-applied SQL below writes exactly what
this code writes. The constants are FROZEN here (a migration never imports app code);
`test_m2b_migration_0097` proves they equal the live ones.

SQL (MIGRATE-FIRST, by hand, one transaction; the release note carries it with its pre-check):
    BEGIN;
    WITH plan AS (
      SELECT id, email, owning_organisation_id, role,
             COALESCE(permissions, (CASE role WHEN 'admin' THEN '["see_all","scholars","spending","payments_prepare"]'
                                              WHEN 'finance' THEN '["payments_approve"]'
                                              WHEN 'qc' THEN '["see_all","qc"]'
                                              ELSE '["review"]' END)::jsonb) AS base,
             (CASE WHEN role = 'admin' OR id = 9
                   THEN '["invitations.view","team.view","sources.view","sources.edit","sponsors.view",
                          "sponsors.edit","announcements.view","announcements.edit","surveys.view",
                          "surveys.edit","development.view","development.edit","mentoring.view",
                          "mentoring.edit"]'
                   ELSE '["invitations.view","team.view","sponsors.view"]' END)::jsonb AS adds
        FROM partner_admins
       WHERE role IN ('admin', 'finance', 'qc', 'reviewer')
         AND (permissions IS NULL OR jsonb_typeof(permissions) = 'array')
         AND (role = 'admin' OR (id = 9 AND is_active) OR (role = 'finance' AND permissions IS NOT NULL))
    ), grown AS (
      SELECT plan.*, base || COALESCE((SELECT jsonb_agg(k ORDER BY n)
                                         FROM jsonb_array_elements_text(adds) WITH ORDINALITY AS a(k, n)
                                        WHERE NOT base ? k), '[]'::jsonb) AS after
        FROM plan
    ), audit AS (
      INSERT INTO staff_permission_changes (target_id, target_email, organisation_id, kind, role, before,
                                            after, changed_by_email, changed_by_role, created_at)
      SELECT id, COALESCE(email, ''), owning_organisation_id, 'edit', role, base, after, '', 'migration', now()
        FROM grown WHERE after <> base
    )
    UPDATE partner_admins p SET permissions = g.after FROM grown g WHERE p.id = g.id AND g.after <> g.base;
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0097_store_admin_v2_keys', now());
    COMMIT;

Reverse: only the audit rows this migration wrote (changed_by_role 'migration', kind 'edit', no actor, and
what `after` adds to `before` is a non-empty set of ADMIN_PRESET keys — 0095's rows add `scholars`) are
read. Exactly the keys each one added come off the row it names; a list left equal to its role's preset
goes back to NULL (the editor's own rule: a preset is stored as NULL). Only those audit rows go.
"""
from django.db import migrations

#: FROZEN copies (`test_m2b_migration_0097.FrozenConstants` holds them equal to the live code).
#: `staff_permissions.PRESETS` for the team roles.
PRESETS = {
    'admin': ('see_all', 'scholars', 'spending', 'payments_prepare'),
    'finance': ('payments_approve',),
    'qc': ('see_all', 'qc'),
    'reviewer': ('review',),
}
TEAM_ROLES = tuple(PRESETS)
#: `ORG_READ_V2` — what the Admins table seat opens.
ORG_READ = ('invitations.view', 'team.view', 'sponsors.view')
#: `ADMIN_PRESET_V2` — ORG_READ plus the admin work pages, in catalogue order.
ADMIN_PRESET = ('invitations.view', 'team.view', 'sources.view', 'sources.edit', 'sponsors.view',
                'sponsors.edit', 'announcements.view', 'announcements.edit', 'surveys.view', 'surveys.edit',
                'development.view', 'development.edit', 'mentoring.view', 'mentoring.edit')
#: The one reviewer the owner confirmed, by id only (O8). Never a name.
ROW_ID = 9
BY_ROLE = 'migration'


def plan_row(pk, role, is_active, stored, *, row_id=ROW_ID):
    """``(before, after)`` lists for one row, or None when this migration leaves it alone. Pure: the
    forward step and the test factory (`row_id=None`) both read it."""
    if role not in TEAM_ROLES:                     # active or revoked alike (architect, 2026-11-12)
        return None
    if stored is not None and not isinstance(stored, list):
        return None
    if role == 'admin' or (is_active and row_id is not None and pk == row_id):
        adds = ADMIN_PRESET
    elif role == 'finance' and stored is not None:
        adds = ORG_READ
    else:
        return None
    before = list(stored) if stored is not None else list(PRESETS[role])
    new = [k for k in adds if k not in before]
    if not new:
        return None
    return before, [*before, *new]


def _ours(row):
    """An audit row this migration wrote: it added ADMIN_PRESET keys, and nothing else."""
    if not (isinstance(row.before, list) and isinstance(row.after, list)):
        return False
    added = [k for k in row.after if k not in row.before]
    return (bool(added) and set(added) <= set(ADMIN_PRESET)
            and row.after[:len(row.before)] == row.before)


def store_v2_keys(apps, schema_editor):
    """Forward: the writes the module docstring lists, one audit row per changed row. Idempotent.
    Returns the ids changed (for the test)."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    changed = []
    for admin in (PartnerAdmin.objects.filter(role__in=TEAM_ROLES)
                  .only('id', 'email', 'role', 'is_active', 'owning_organisation_id', 'permissions')
                  .order_by('id')):
        plan = plan_row(admin.pk, admin.role, admin.is_active, admin.permissions)
        if plan is None:
            continue
        before, after = plan
        PartnerAdmin.objects.filter(pk=admin.pk).update(permissions=after)
        StaffPermissionChange.objects.create(
            target_id=admin.pk, target_email=admin.email or '',
            organisation_id=admin.owning_organisation_id, kind='edit', role=admin.role,
            before=before, after=after, changed_by_email='', changed_by_role=BY_ROLE)
        changed.append(admin.pk)
    return changed


def remove_v2_keys(apps, schema_editor):
    """Reverse: take off exactly the keys each of this migration's audit rows added, NULL a list left
    equal to its role's preset, then delete only those audit rows. Returns the ids changed."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    candidates = StaffPermissionChange.objects.filter(
        changed_by_role=BY_ROLE, changed_by_email='', kind='edit')
    rows = [row for row in candidates.order_by('id') if _ours(row)]
    changed = []
    for row in rows:
        added = {k for k in row.after if k not in row.before}
        admin = PartnerAdmin.objects.filter(pk=row.target_id).only('id', 'role', 'permissions').first()
        if admin is None or not isinstance(admin.permissions, list) or not added & set(admin.permissions):
            continue
        kept = [k for k in admin.permissions if k not in added]
        PartnerAdmin.objects.filter(pk=admin.pk).update(
            permissions=None if tuple(kept) == PRESETS.get(admin.role) else kept)
        changed.append(admin.pk)
    StaffPermissionChange.objects.filter(pk__in=[row.pk for row in rows]).delete()
    return changed


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0096_partneradmin_archive_member'),
        ('scholarship', '0175_staff_permission_changes'),
    ]

    operations = [
        migrations.RunPython(store_v2_keys, remove_v2_keys),
    ]
