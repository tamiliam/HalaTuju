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
never again: from S4 an org admin may switch Manage off and a later re-run would give it back. ⚠ AFTER 0099 /
0100: a re-run of either loses nothing here (they touch only organisation admin lists).

THE RE-RUN IS BOUNDED BY THE CUTOVER (S4a review S3). The first run sets `cut` to NULL (every row). The re-run
sets it to the CUTOVER: the moment the new image first took traffic. Then a row touched since is SKIPPED: one
created since (an invite, or a never-seen re-invite), one not signed in before it (`first_seen_at` NULL or
later: a pending invite, or a Restore, which clears `first_seen_at`), or one with any `staff_permission_changes`
row since (an edit or a role switch on the new image). Under the new image those rows mean Manage OFF (Q-E:
invites, Restore and a role switch use the preset, which holds no Manage), and a re-run must not undo that.
The RE-RUN PRE-CHECK lists them first: each is expected to be skipped. The forward step below takes the same
bound (`cutover`); `migrate` runs it once, unbounded, as the first run.

THE AUDIT STAYS TRUTHFUL. Each row changed gets one `staff_permission_changes` row: kind 'edit' (or
'edit_null'), the list before and after, `changed_by_email` '' and `changed_by_role` 'migration'. The
constants are FROZEN here (a migration never imports app code); `test_s4_migration_0101` proves they equal
the live ones and pins the SQL's text to `plan_row` (the test database cannot run jsonb).

SQL, by hand, with the owner's yes. Run the PRE-CHECK, then the DATA block with `cut` NULL (it writes the ledger
row in the same transaction); publish; after the new image carries all the traffic, run the RE-RUN PRE-CHECK
and the DATA block once more with `cut` set to the cutover, then the POST-DEPLOY CHECK with the same cutover.

PRE-CHECK (read-only): the rows the DATA block will write, by whether active, and the ledger. Expect 4 active
list rows, no NULL admin row, no organisation admin list holding `scholars` without the key; 0100 listed, 0101 not.
    BEGIN READ ONLY;
    SELECT 'list' AS shape, is_active, count(*) FROM partner_admins
     WHERE role IN ('admin','finance','qc','reviewer') AND jsonb_typeof(permissions) = 'array'
       AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve' GROUP BY 1, 2 ORDER BY 1, 2;
    SELECT 'null_admin' AS shape, is_active, count(*) FROM partner_admins
     WHERE role = 'admin' AND (permissions IS NULL OR jsonb_typeof(permissions) = 'null') GROUP BY 1, 2;
    SELECT 'org_admin_without_manage' AS shape, count(*) FROM partner_admins
     WHERE role = 'org_admin' AND jsonb_typeof(permissions) = 'array'
       AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve';
    SELECT name FROM django_migrations
     WHERE app = 'courses' AND name IN ('0100_store_org_admin_powers', '0101_grant_scholars_manage');
    COMMIT;

DATA block (one transaction, the ledger row included; a row holding the key is not written again and gets no
audit row, and the ledger row is written once). `cut`: NULL on the first run; on the re-run the cutover, e.g.
`TIMESTAMPTZ '2026-11-25 11:00:00+08'`:
    BEGIN;
    WITH cut AS (SELECT NULL::timestamptz AS at),
    eligible AS (
      SELECT a.* FROM partner_admins a, cut
       WHERE cut.at IS NULL
          OR (a.created_at < cut.at AND a.first_seen_at < cut.at
              AND NOT EXISTS (SELECT 1 FROM staff_permission_changes c
                               WHERE c.target_id = a.id AND c.created_at >= cut.at))
    ), plan AS (
      SELECT id, email, owning_organisation_id, role, 'edit' AS kind, permissions AS base,
             permissions || '["scholars.approve"]'::jsonb AS after
        FROM eligible
       WHERE role IN ('admin','finance','qc','reviewer') AND jsonb_typeof(permissions) = 'array'
         AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve'
      UNION ALL
      SELECT id, email, owning_organisation_id, role, 'edit_null' AS kind,
             '["see_all","scholars","spending","payments_prepare"]'::jsonb AS base,
             '["see_all","scholars","spending","payments_prepare","invitations.view","team.view","sources.view","sources.edit","sponsors.view","sponsors.edit","announcements.view","announcements.edit","surveys.view","surveys.edit","development.view","development.edit","mentoring.view","mentoring.edit","scholars.approve"]'::jsonb AS after
        FROM eligible WHERE role = 'admin' AND (permissions IS NULL OR jsonb_typeof(permissions) = 'null')
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

RE-RUN PRE-CHECK (read-only, before the re-run; `cut` = the cutover). The rows touched since the cutover, by id
(no name), each EXPECTED TO BE SKIPPED: they keep Manage off (Q-E). Both shapes the DATA block writes: a list,
and a NULL `admin` row (S4a review round 2: e.g. a Django-admin role switch, which stores NULL and writes a
`role_change` audit row, or a pending invite the old image stored as NULL).
    BEGIN READ ONLY;
    WITH cut AS (SELECT TIMESTAMPTZ '2026-11-25 11:00:00+08' AS at)
    SELECT a.id, a.role, a.is_active,
           CASE WHEN jsonb_typeof(permissions) = 'array' THEN 'list' ELSE 'null_admin' END AS shape,
           a.created_at >= cut.at AS created_since,
           a.first_seen_at IS NULL OR a.first_seen_at >= cut.at AS not_seen_before,
           EXISTS (SELECT 1 FROM staff_permission_changes c
                    WHERE c.target_id = a.id AND c.created_at >= cut.at) AS changed_since
      FROM partner_admins a, cut
     WHERE ((role IN ('admin','finance','qc','reviewer') AND jsonb_typeof(permissions) = 'array'
             AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve')
            OR (role = 'admin' AND (permissions IS NULL OR jsonb_typeof(permissions) = 'null')))
       AND NOT (a.created_at < cut.at AND a.first_seen_at < cut.at
                AND NOT EXISTS (SELECT 1 FROM staff_permission_changes c
                                 WHERE c.target_id = a.id AND c.created_at >= cut.at))
     ORDER BY a.id;
    COMMIT;

POST-DEPLOY CHECK (read-only, after the re-run; `cut` = the same cutover). Queries 1 to 3 must each return
ZERO (1 and 2 count only the rows not touched since the cutover: the skipped rows are the RE-RUN PRE-CHECK's list).
Query 4 is INFORMATIONAL: Manage scholar files without View scholars is a legal shape (Manage implies View).
    BEGIN READ ONLY;
    WITH cut AS (SELECT TIMESTAMPTZ '2026-11-25 11:00:00+08' AS at)
    SELECT count(*) FROM partner_admins a, cut
     WHERE role IN ('admin','finance','qc','reviewer') AND jsonb_typeof(permissions) = 'array'
       AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve'
       AND a.created_at < cut.at AND a.first_seen_at < cut.at
       AND NOT EXISTS (SELECT 1 FROM staff_permission_changes c
                        WHERE c.target_id = a.id AND c.created_at >= cut.at);
    WITH cut AS (SELECT TIMESTAMPTZ '2026-11-25 11:00:00+08' AS at)
    SELECT count(*) FROM partner_admins a, cut
     WHERE role = 'admin' AND (permissions IS NULL OR jsonb_typeof(permissions) = 'null')
       AND a.created_at < cut.at AND a.first_seen_at < cut.at
       AND NOT EXISTS (SELECT 1 FROM staff_permission_changes c
                        WHERE c.target_id = a.id AND c.created_at >= cut.at);
    SELECT count(*) FROM partner_admins
     WHERE role = 'org_admin' AND jsonb_typeof(permissions) = 'array'
       AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve';
    SELECT 'informational' AS note, count(*) FROM partner_admins
     WHERE jsonb_typeof(permissions) = 'array' AND permissions ? 'scholars.approve' AND NOT permissions ? 'scholars';
    COMMIT;

Reverse: only the audit rows this migration wrote (changed_by_role 'migration', no actor, a team role, kind
'edit' with `after` exactly `before` plus the key and `scholars` in `before`, or kind 'edit_null' with the
materialised list) are read, and for each row only the NEWEST of them. A row still holding exactly that row's
`after` goes back to its `before` (an 'edit_null' row back to NULL); a row changed since is left as it is,
and so are its audit rows. Only the audit rows of the rows put back go (S4a review N2). ⚠ Reverse only under the OLD image: the new image reading a list without the key
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


def touched_since(admin, cutover, changed_since):
    """The re-run's bound (the DATA block's `eligible`): created at or after the cutover, not signed in before
    it, or holding an audit row since (``changed_since``: those target ids). Pure."""
    seen = admin.first_seen_at
    return (admin.created_at >= cutover or seen is None or seen >= cutover or admin.pk in changed_since)


def grant_scholars_manage(apps, schema_editor, cutover=None):
    """Forward: the writes the module docstring lists, one audit row per changed row. Idempotent.
    ``cutover`` None is the first run (`migrate`); a time is the bounded re-run, which skips every row
    `touched_since` it. Returns the ids changed (for the test)."""
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    StaffPermissionChange = apps.get_model('scholarship', 'StaffPermissionChange')
    changed_since = (set() if cutover is None else set(
        StaffPermissionChange.objects.filter(created_at__gte=cutover).values_list('target_id', flat=True)))
    changed = []
    for admin in (PartnerAdmin.objects.filter(role__in=TEAM_ROLES)
                  .only('id', 'email', 'role', 'owning_organisation_id', 'permissions', 'created_at',
                        'first_seen_at').order_by('id')):
        plan = plan_row(admin.role, admin.permissions)
        if plan is None or (cutover is not None and touched_since(admin, cutover, changed_since)):
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
    wrote, then delete this migration's audit rows OF THE ROWS PUT BACK only (a row left alone keeps its
    history). Returns the ids changed."""
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
    put_back = set(changed)
    StaffPermissionChange.objects.filter(pk__in=[row.pk for row in rows if row.target_id in put_back]).delete()
    return changed


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0100_store_org_admin_powers'),
    ]

    operations = [
        migrations.RunPython(grant_scholars_manage, take_back_scholars_manage),
    ]
