"""Sprint M3a (decision A1, 2026-11-14): an organisation admin's powers become STORED keys, before the code
stops reading them as a fixed tier.

Until M3a an `org_admin` row's `permissions` list was never read except for `review` (Team -> Reviewers):
`staff_permissions.resolve` answered the fixed lead tier and the v2 module's `lead_v2` every v2 key.
M3a reads the stored list, so this data step REPLACES (never merges) the list of every `org_admin` row,
active, revoked, archived or pending alike (a later Restore must give back what the role gave), with:

  `review`, only when the row's list holds it today (Team -> Reviewers);
  the old keys ORG_ADMIN_KEYS (the lead tier less `manage_team`, which the role gives: owner O15);
  the v2 page keys ORG_ADMIN_V2 (every catalogue key that is neither never-grantable nor an alias).

Not written, on purpose: `manage_team`, `billing.edit` and `requests.approve` (held by role, O15); the
aliases `students.view`, `scholars.view`, `spending.*` (the old keys mean them); `payments.*` and
`sponsors.check` (held by role until M4, TD-620). Why replace: a row appointed after holding a team role may
keep an old key such as `payments_approve`; reading it would give that organisation admin a payment seat,
which is M4's. Replacing writes exactly what the lead tier meant. A row whose value is neither NULL nor a
list is left alone (the new code reads it as the full set, as it reads NULL). Any other role is untouched.

Live (read-only count, 2026-11-14): 2 `org_admin` rows, both active and signed in; one stores NULL, one
`["review"]`. Idempotent: a row already equal to its planned list is not written and gets no audit row.

THE OLD IMAGE IGNORES THE NEW KEYS: it reads an organisation admin's list for `review` only, and `review` is
kept, so every page and button answers as before until the new image ships (migrate-first, the 0097
precedent). ⚠ Between this step and the deploy, do not change an organisation admin's role or Team ->
Reviewers seat: the old image's writers overwrite the list (`["review"]` or NULL). NULL reads safely as the
full set; the POST-DEPLOY re-run below rewrites either.

THE AUDIT STAYS TRUTHFUL. Each row changed gets one `staff_permission_changes` row: the list before (for a
NULL row, ORG_ADMIN_KEYS — what the NULL stood for, in keys a row can store) and after, `changed_by_email`
'' and `changed_by_role` 'migration'. Its kind is NULL_KIND ('edit_null') for a NULL row and 'edit' for a
stored list, so the reverse is EXACT. The constants are FROZEN here (a migration never imports app code);
`test_m3_migration_0098` proves they equal the live ones and pins the SQL's CASE and WHERE text to
`plan_row` (the test database cannot run jsonb).

SQL, MIGRATE-FIRST, by hand. Run the DATA block, then the LEDGER block; after the deploy, re-run the DATA
block and run the POST-DEPLOY CHECK (the release note carries them with the pre-check).

DATA block (one transaction; safe to re-run: a row already equal to its planned list is not written and
gets no audit row):
    BEGIN;
    WITH plan AS (
      SELECT id, email, owning_organisation_id, role, (permissions IS NULL) AS was_null,
             COALESCE(permissions, '["see_all","scholars","qc","spending","award_withdraw_approve"]'::jsonb) AS base,
             (CASE WHEN permissions ? 'review' THEN '["review"]' ELSE '[]' END)::jsonb
             || '["see_all","scholars","qc","spending","award_withdraw_approve","invitations.view",
                  "invitations.edit","team.view","sources.view","sources.edit","sponsors.view","sponsors.edit",
                  "sponsors.approve","billing.view","requests.view","requests.edit","settings.edit",
                  "students.edit","students.approve","contracts.view","contracts.edit","programmes.edit",
                  "announcements.view","announcements.edit","surveys.view","surveys.edit","development.view",
                  "development.edit","mentoring.view","mentoring.edit"]'::jsonb AS after
        FROM partner_admins
       WHERE role = 'org_admin'
         AND (permissions IS NULL OR jsonb_typeof(permissions) = 'array')
    ), audit AS (
      INSERT INTO staff_permission_changes (target_id, target_email, organisation_id, kind, role, before,
                                            after, changed_by_email, changed_by_role, created_at)
      SELECT id, COALESCE(email, ''), owning_organisation_id, CASE WHEN was_null THEN 'edit_null' ELSE 'edit' END,
             role, base, after, '', 'migration', now()
        FROM plan WHERE was_null OR after <> base
    )
    UPDATE partner_admins p SET permissions = g.after FROM plan g WHERE p.id = g.id AND (g.was_null OR g.after <> g.base);
    COMMIT;

LEDGER block (safe to re-run):
    INSERT INTO django_migrations (app, name, applied)
    SELECT 'courses', '0098_store_org_admin_keys', now()
     WHERE NOT EXISTS (SELECT 1 FROM django_migrations
                        WHERE app = 'courses' AND name = '0098_store_org_admin_keys');

POST-DEPLOY CHECK (read-only, after re-running the DATA block): every organisation admin row that is NULL or
whose list is not exactly its planned list. It must return ZERO rows. If not zero, re-run the DATA block only.
    SELECT id, (permissions IS NULL) AS was_null FROM partner_admins
     WHERE role = 'org_admin'
       AND (permissions IS NULL OR jsonb_typeof(permissions) = 'array')
       AND permissions IS DISTINCT FROM ((CASE WHEN permissions ? 'review' THEN '["review"]' ELSE '[]' END)::jsonb
             || '["see_all","scholars","qc","spending","award_withdraw_approve","invitations.view",
                  "invitations.edit","team.view","sources.view","sources.edit","sponsors.view","sponsors.edit",
                  "sponsors.approve","billing.view","requests.view","requests.edit","settings.edit",
                  "students.edit","students.approve","contracts.view","contracts.edit","programmes.edit",
                  "announcements.view","announcements.edit","surveys.view","surveys.edit","development.view",
                  "development.edit","mentoring.view","mentoring.edit"]'::jsonb);

Reverse: only the audit rows this migration wrote (changed_by_role 'migration', no actor, kind 'edit' or
NULL_KIND, role 'org_admin', and `after` exactly one of the two planned lists) are read. A row still holding
exactly that `after` goes back to its `before` (NULL for NULL_KIND); a row changed since is left as it is.
Only those audit rows go. ⚠ Django reverses this step before 0097 and 0095; 0095's reverse would also read
an audit row here that adds `scholars`, so never run 0095's reverse by hand while this step is applied.
"""
from django.db import migrations

#: FROZEN copies (`test_m3_migration_0098.FrozenConstants` holds them equal to the live code).
ROLE = 'org_admin'
#: `staff_permissions.LEAD_MAY_ADD` — the key Team -> Reviewers adds.
REVIEW = 'review'
#: `staff_permissions.ORG_ADMIN_KEYS` — the lead tier less `manage_team`, in catalogue order.
OLD_KEYS = ('see_all', 'scholars', 'qc', 'spending', 'award_withdraw_approve')
#: The v2 module's `ORG_ADMIN_V2`, in catalogue order.
V2_KEYS = ('invitations.view', 'invitations.edit', 'team.view', 'sources.view', 'sources.edit',
           'sponsors.view', 'sponsors.edit', 'sponsors.approve', 'billing.view', 'requests.view',
           'requests.edit', 'settings.edit', 'students.edit', 'students.approve', 'contracts.view',
           'contracts.edit', 'programmes.edit', 'announcements.view', 'announcements.edit', 'surveys.view',
           'surveys.edit', 'development.view', 'development.edit', 'mentoring.view', 'mentoring.edit')
#: The two lists a row can be given.
PLANNED = ([*OLD_KEYS, *V2_KEYS], [REVIEW, *OLD_KEYS, *V2_KEYS])
BY_ROLE = 'migration'
#: The audit kind for a row that was NULL before; a stored list's row is kind 'edit' (as 0097).
NULL_KIND = 'edit_null'


def plan_row(role, stored):
    """``(before, after)`` lists for one row, or None when this migration leaves it alone. Pure: the
    forward step and the test factory both read it."""
    if role != ROLE:
        return None
    if stored is not None and not isinstance(stored, list):
        return None
    after = [REVIEW, *OLD_KEYS, *V2_KEYS] if stored is not None and REVIEW in stored else [*OLD_KEYS, *V2_KEYS]
    if stored == after:
        return None
    return (list(stored) if stored is not None else list(OLD_KEYS)), after


def _ours(row):
    """An audit row this migration wrote: an organisation admin's, to one of the two planned lists."""
    return row.role == ROLE and isinstance(row.after, list) and row.after in PLANNED


def store_org_admin_keys(apps, schema_editor):
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
            kind=NULL_KIND if admin.permissions is None else 'edit', role=admin.role,
            before=before, after=after, changed_by_email='', changed_by_role=BY_ROLE)
        changed.append(admin.pk)
    return changed


def restore_org_admin_lists(apps, schema_editor):
    """Reverse: put back each row this migration wrote that still holds what it wrote — its `before`, or
    NULL for a row that was NULL — then delete only this migration's audit rows. Returns the ids changed."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    candidates = StaffPermissionChange.objects.filter(
        changed_by_role=BY_ROLE, changed_by_email='', kind__in=('edit', NULL_KIND), role=ROLE)
    rows = [row for row in candidates.order_by('id') if _ours(row)]
    changed = []
    for row in rows:
        admin = PartnerAdmin.objects.filter(pk=row.target_id).only('id', 'role', 'permissions').first()
        if admin is None or admin.role != ROLE or admin.permissions != row.after:
            continue
        PartnerAdmin.objects.filter(pk=admin.pk).update(
            permissions=None if row.kind == NULL_KIND else list(row.before))
        changed.append(admin.pk)
    StaffPermissionChange.objects.filter(pk__in=[row.pk for row in rows]).delete()
    return changed


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0097_store_admin_v2_keys'),
        ('scholarship', '0175_staff_permission_changes'),
    ]

    operations = [
        migrations.RunPython(store_org_admin_keys, restore_org_admin_lists),
    ]
