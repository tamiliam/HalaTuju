"""Sprint S4 (ACCESS-BY-SWITCHES SCHOLARS-SPLIT, owner rulings 25 Nov): from S4 the Scholars switch `scholars`
("View scholars") only READS a scholar's file; every write (and the suspension and termination letters) asks
`scholars.approve` ("Manage scholar files"). Owner Q3: today's file writers keep their write power. So this
data step APPENDS `scholars.approve` to every team member's row whose value is a JSON list holding `scholars`
and not the key, WHATEVER its stored role label (the label decides nothing: there are no permanent reviewers
or admins, owner 25 Nov: a group offers switches and a member holds some of them; a switch never places
anyone in a group). Active, revoked, archived and pending alike: a later Restore gives back what was held. It REMOVES
NOTHING. Live (25 Nov): the 4 team members in Admins who hold View scholars gain Manage scholar files, and with it the suspension and
termination letters and withdrawing a letter (named in the phone check by count only, never a name).

A NULL `admin` row reads its preset (which holds `scholars`); it is MATERIALISED as the admin preset, 0097's v2
preset and the key, audit kind 'edit_null' (expected 0). Other NULL team rows (their presets hold no
`scholars`), a row whose value is neither NULL nor a list, a row holding the key without `scholars` (live: 1
team member holding `award_withdraw_approve` only, untouched), supers, partners and any other role are left
alone. ORGANISATION ADMIN ROWS ARE NOT TOUCHED: they already hold the key (0099 stored it; a NULL row reads the
full set; live: both hold it). Leaving them out also keeps 0099's own audit rows (the same key appended) out
of this migration's reverse.

Idempotent: a row holding the key, or without `scholars`, is not written and gets no audit row. The admin
preset (`ADMIN_PRESET_V2`) does NOT gain the key (Q-E: a team member newly invited to Admins starts with Manage
OFF; an org admin switches it on).

NOT INVISIBLE TO THE OLD IMAGE. The live image already reads a stored `scholars.approve` on a team row (the
senior letters, door `senior_letters`). So run the DATA block in the S4 publish window, straight before the
publish, and do the phone check then. Re-run the DATA block ONCE after the new image carries all traffic, then
never again: from S4 an org admin may switch Manage off and a re-run would give it back. ⚠ AFTER 0099 / 0100:
a re-run of either loses nothing here (they touch only organisation admin lists).

THE AUDIT STAYS TRUTHFUL. Each row changed gets one `staff_permission_changes` row: kind 'edit' (or
'edit_null'), the list before and after, `changed_by_email` '' and `changed_by_role` 'migration'. The
constants are FROZEN here (a migration never imports app code); `test_s4_migration_0101` proves they equal
the live ones and pins the SQL's text to `plan_row` (the test database cannot run jsonb).

SQL, by hand, with the owner's yes. Run the PRE-CHECK, then the DATA block (it writes the ledger row in the
same transaction); after the new image carries all the traffic, run the DATA block once more and the
POST-DEPLOY CHECK.

PRE-CHECK (read-only): the rows the DATA block will write, by whether active, and the ledger. Expect 4 active
list rows, no NULL admin row; 0100 listed, 0101 not.
    BEGIN READ ONLY;
    SELECT 'list' AS shape, is_active, count(*) FROM partner_admins
     WHERE role IN ('admin','finance','qc','reviewer') AND jsonb_typeof(permissions) = 'array'
       AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve' GROUP BY 1, 2 ORDER BY 1, 2;
    SELECT 'null_admin' AS shape, is_active, count(*) FROM partner_admins
     WHERE role = 'admin' AND (permissions IS NULL OR jsonb_typeof(permissions) = 'null') GROUP BY 1, 2;
    SELECT name FROM django_migrations
     WHERE app = 'courses' AND name IN ('0100_store_org_admin_powers', '0101_grant_scholars_manage');
    COMMIT;

DATA block (one transaction, the ledger row included; safe to re-run: a row holding the key is not written
again and gets no audit row, and the ledger row is written once):
    BEGIN;
    WITH plan AS (
      SELECT id, email, owning_organisation_id, role, 'edit' AS kind, permissions AS base,
             permissions || '["scholars.approve"]'::jsonb AS after
        FROM partner_admins
       WHERE role IN ('admin','finance','qc','reviewer') AND jsonb_typeof(permissions) = 'array'
         AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve'
      UNION ALL
      SELECT id, email, owning_organisation_id, role, 'edit_null' AS kind,
             '["see_all","scholars","spending","payments_prepare"]'::jsonb AS base,
             '["see_all","scholars","spending","payments_prepare","invitations.view","team.view","sources.view","sources.edit","sponsors.view","sponsors.edit","announcements.view","announcements.edit","surveys.view","surveys.edit","development.view","development.edit","mentoring.view","mentoring.edit","scholars.approve"]'::jsonb AS after
        FROM partner_admins WHERE role = 'admin' AND (permissions IS NULL OR jsonb_typeof(permissions) = 'null')
    ), audit AS (
      INSERT INTO staff_permission_changes (target_id, target_email, organisation_id, kind, role, before,
                                            after, changed_by_email, changed_by_role, created_at)
      SELECT id, COALESCE(email, ''), owning_organisation_id, kind, role, base, after, '', 'migration', now()
        FROM plan
    )
    UPDATE partner_admins p SET permissions = g.after FROM plan g WHERE p.id = g.id;
    INSERT INTO django_migrations (app, name, applied)
    SELECT 'courses', '0101_grant_scholars_manage', now()
     WHERE NOT EXISTS (SELECT 1 FROM django_migrations
                        WHERE app = 'courses' AND name = '0101_grant_scholars_manage');
    COMMIT;

POST-DEPLOY CHECK (read-only, after re-running the DATA block). Each must return ZERO.
    SELECT count(*) FROM partner_admins
     WHERE role IN ('admin','finance','qc','reviewer') AND jsonb_typeof(permissions) = 'array'
       AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve';
    SELECT count(*) FROM partner_admins
     WHERE role = 'admin' AND (permissions IS NULL OR jsonb_typeof(permissions) = 'null');
    SELECT count(*) FROM partner_admins
     WHERE jsonb_typeof(permissions) = 'array' AND permissions ? 'scholars.approve' AND NOT permissions ? 'scholars';

Reverse: only the audit rows this migration wrote (changed_by_role 'migration', no actor, a team role, kind
'edit' with `after` exactly `before` plus the key and `scholars` in `before`, or kind 'edit_null' with the
materialised list) are read, and for each row only the NEWEST of them. A row still holding exactly that row's
`after` goes back to its `before` (an 'edit_null' row back to NULL); a row changed since is left as it is.
Only those audit rows go. ⚠ Reverse only under the OLD image: the new image reading a list without the key
shuts every file write.
"""
from django.db import migrations

#: FROZEN copies (`test_s4_migration_0101.FrozenConstants` holds them equal to the live code).
KEY = 'scholars.approve'
VIEW = 'scholars'
TEAM_ROLES = ('admin', 'finance', 'qc', 'reviewer')
#: `staff_permissions.PRESETS['admin']` and 0097's `ADMIN_PRESET` (= `ADMIN_PRESET_V2`).
ADMIN_PRESET = ('see_all', 'scholars', 'spending', 'payments_prepare')
ADMIN_PRESET_V2 = ('invitations.view', 'team.view', 'sources.view', 'sources.edit', 'sponsors.view',
                   'sponsors.edit', 'announcements.view', 'announcements.edit', 'surveys.view', 'surveys.edit',
                   'development.view', 'development.edit', 'mentoring.view', 'mentoring.edit')
MATERIALISED = (*ADMIN_PRESET, *ADMIN_PRESET_V2, KEY)
BY_ROLE = 'migration'
KIND = 'edit'
NULL_KIND = 'edit_null'


def plan_row(role, stored):
    """``(kind, before, after)`` for one row, or None when this migration leaves it alone. Pure: the forward
    step and the tests both read it."""
    if role == 'admin' and stored is None:
        return NULL_KIND, list(ADMIN_PRESET), list(MATERIALISED)
    if role not in TEAM_ROLES or not isinstance(stored, list) or VIEW not in stored or KEY in stored:
        return None
    return KIND, list(stored), [*stored, KEY]


def _ours(row):
    """An audit row this migration wrote: a team row's list with the key appended, or a materialisation."""
    before, after = row.before, row.after
    if row.role not in TEAM_ROLES or not (isinstance(before, list) and isinstance(after, list)):
        return False
    if row.kind == NULL_KIND:
        return row.role == 'admin' and before == list(ADMIN_PRESET) and after == list(MATERIALISED)
    return VIEW in before and KEY not in before and after == [*before, KEY]


def grant_scholars_manage(apps, schema_editor):
    """Forward: the writes the module docstring lists, one audit row per changed row. Idempotent.
    Returns the ids changed (for the test)."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    changed = []
    for admin in (PartnerAdmin.objects.filter(role__in=TEAM_ROLES)
                  .only('id', 'email', 'role', 'owning_organisation_id', 'permissions').order_by('id')):
        plan = plan_row(admin.role, admin.permissions)
        if plan is None:
            continue
        kind, before, after = plan
        PartnerAdmin.objects.filter(pk=admin.pk).update(permissions=after)
        StaffPermissionChange.objects.create(
            target_id=admin.pk, target_email=admin.email or '', organisation_id=admin.owning_organisation_id,
            kind=kind, role=admin.role, before=before, after=after, changed_by_email='',
            changed_by_role=BY_ROLE)
        changed.append(admin.pk)
    return changed


def take_back_scholars_manage(apps, schema_editor):
    """Reverse: put back each row this migration wrote that still holds what its NEWEST audit row here
    wrote, then delete only this migration's audit rows. Returns the ids changed."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    candidates = StaffPermissionChange.objects.filter(
        changed_by_role=BY_ROLE, changed_by_email='', kind__in=(KIND, NULL_KIND), role__in=TEAM_ROLES)
    rows = [row for row in candidates.order_by('id') if _ours(row)]
    newest = {}
    for row in rows:                       # ascending ids: the last one seen per row is the newest
        newest[row.target_id] = row
    changed = []
    for row in newest.values():
        admin = PartnerAdmin.objects.filter(pk=row.target_id).only('id', 'role', 'permissions').first()
        if admin is None or admin.role != row.role or admin.permissions != row.after:
            continue
        back = None if row.kind == NULL_KIND else list(row.before)
        PartnerAdmin.objects.filter(pk=admin.pk).update(permissions=back)
        changed.append(admin.pk)
    StaffPermissionChange.objects.filter(pk__in=[row.pk for row in rows]).delete()
    return changed


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0100_store_org_admin_powers'),
    ]

    operations = [
        migrations.RunPython(grant_scholars_manage, take_back_scholars_manage),
    ]
