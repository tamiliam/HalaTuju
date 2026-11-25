# Release-note draft — sprint S4a, View scholars and Manage scholar files (2026-11-25)

**DRAFT. Branch access-s4-scholars, local, not pushed. The owner says yes before it goes live.**
Brief: `docs/plans/2026-11-24-s4-scholars-split-brief.md`. Decisions: `docs/decisions.md` (2026-11-25, sprint S4a).
Debt: TD-597 (closed, accepted), TD-598 (closed). The screens follow in S4b (web).

## What changes for people

- **The Scholars switch becomes two.** "View scholars" opens the Scholars page and every scholar's file to read.
  "Manage scholar files" changes a file: results review, activity, the reporting date, the maintenance stage,
  closing a file, and every letter, suspension and termination included.
- **Nobody who changes files today loses anything.** The data step gives Manage scholar files to every team member who
  holds View scholars (4 people today). With it they gain the suspension and termination letters and withdrawing a
  letter, which until now only an organisation admin had.
- **Someone newly invited to Admins starts with View scholars on and Manage scholar files off.** An organisation
  admin switches Manage on when they want that person to change files.
- **Money on a scholar's file after the award** (a tranche, a disbursement, putting a scholar on hold or lifting it)
  asks View scholars plus Payments: Prepare, as before. Manage scholar files is never a second key to money.
- Groups do not change: holding a switch never puts anyone in a group.

## Not changed

- No new table or column; no environment variable; no web change in this half.
- Organisation admins already hold Manage scholar files (migration 0099); their rows are not touched.
- Surveys and Development keep their own switches (owner Q-A).

## Deploy

Services: api. Migration: `courses/0101_grant_scholars_manage` (additive data step). Run it **by hand in the publish
window, straight before the publish** (the live image already reads a stored `scholars.approve` for the senior
letters, so it is not invisible to the old image). The full SQL, including the reverse, is in the migration's
docstring; it is copied here.

### 1. PRE-CHECK (read-only)

Expect 4 active list rows, no NULL admin row, no organisation admin list holding `scholars` without
`scholars.approve`; 0100 listed, 0101 not.

```sql
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
```

**Before (read-only count, 25 Nov):** 4 team rows hold `scholars` without `scholars.approve`; 0 NULL admin rows.

### 2. DATA block (one transaction, the ledger row included)

First run: `cut` is NULL (every row), straight before the publish.

```sql
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
```

Then publish the api. Note the **cutover**: the moment the new image first took traffic.

### 3. The re-run, bounded by the cutover (once, after the new image carries all the traffic; then never again)

A row touched since the cutover is skipped: invited since, not signed in before it (a pending invite, or a
Restore, which clears the first sign-in), or with any permission change since (an edit or a role switch). Under
the new image those people start with Manage scholar files off, and the re-run must not switch it on. First list
them (each is expected to be skipped). Both shapes the DATA block writes are listed: a list, and a NULL `admin` row
(e.g. a Django-admin role switch, which stores NULL and writes a `role_change` audit row, or a pending invite the
old image stored as NULL):

```sql
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
```

Then run the DATA block again with its first line set to the cutover, e.g.
`WITH cut AS (SELECT TIMESTAMPTZ '2026-11-25 11:00:00+08' AS at),`. From S4 an organisation admin may switch
Manage off, so the DATA block is never run a third time.

### 4. POST-DEPLOY CHECK (read-only, after the re-run, with the same cutover)

Queries 1 to 3 must each return ZERO (1 and 2 count only rows untouched since the cutover). Query 4 is informational:
Manage scholar files without View scholars is a legal shape (Manage implies View).

```sql
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
```

**After (expected):** 0 team rows untouched since the cutover hold `scholars` without `scholars.approve`; 4 audit
rows in `staff_permission_changes` with `changed_by_role = 'migration'` from this step.

### Reverse

Only under the OLD image (the new image reading a list without the key shuts every file write). The migration's
reverse puts back only rows still holding exactly what this step wrote, then deletes only this step's audit rows
of the rows it put back (a row changed since keeps its history).

## Phone check (owner, after live)

1. As an organisation admin, open a funded scholar's file: change the reporting date and preview a suspension letter;
   both work.
2. As one of the 4 team members who hold View scholars: open the same file; you can still change it, and a suspension
   letter can now be previewed.
3. As a team member newly invited to Admins (View on, Manage off): the file opens to read; any change is refused.
4. As a team member holding View scholars and Payments: Prepare but not Manage scholar files: put a funded scholar
   on hold and lift it back to on track; both work. Moving the stage to probation is refused.
