# Release-note draft — sprint S1, a Scholars permission of its own (2026-11-09)

**DRAFT. Not applied anywhere but the local test database. The owner says yes before any step below runs.**
Decisions: `docs/decisions.md` (2026-11-09, S1). Brief: `docs/plans/2026-11-09-s1-scholars-access.md`.

## What changes for people

- **New permission "Scholars"** (`scholars`): reads and works every scholar's file in the organisation. The admin
  preset and the organisation admin hold it; reviewers and QC do not.
- **"See all students" now reads "Applications".** Same key (`see_all`), same reach, minus Scholars.
- **Reviewers and QC no longer open Scholars.** They keep their applications in the cockpit.
- **Results work moves.** Semester-result review on the **53 awarded cases** now falls to **6 people**: the
  **2 admins**, the **2 people in both groups** (Admins and Reviewers) and the **2 organisation admins**. Tell
  them before the deploy.
- **Mentors** see Scholars in their menu: the full file of their current students only, read-only, ending when the
  mentoring ends. This is a deliberate widening (documents, money, family data) by the owner.

## Migration — MIGRATE-FIRST, by hand, before the push

`courses` `0095_grant_scholars_key` (data only, reversible). ⚠ On this branch it depends on `courses` 0093 and
`scholarship` 0175; main has `courses` 0094, so the merge author re-points the first dependency to
`0094_drop_partneradmin_is_super_admin` before the push. The ledger row name below is unchanged by that.

The rule: an ACTIVE team member (`is_active`) whose SAVED list NAMES `see_all` and lacks `scholars`. A `qc`-only
list does not gain it (owner ruling 2026-11-10: Quality check carries no Scholars role), nor does a deactivated
row. The pre-check and the apply use the same WHERE, word for word.

### 1. Pre-check (read-only). Expect exactly 4 rows. Any other number: STOP and ask.

```sql
BEGIN READ ONLY;
SELECT count(*)
  FROM partner_admins
 WHERE role IN ('admin', 'finance', 'qc', 'reviewer') AND is_active
   AND jsonb_typeof(permissions) = 'array' AND permissions ? 'see_all' AND NOT permissions ? 'scholars';
SELECT count(*) FROM django_migrations WHERE app = 'courses' AND name = '0095_grant_scholars_key';   -- expect 0
COMMIT;
```

### 2. Apply (one transaction)

```sql
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
```

Expect `INSERT 0 4`, `UPDATE 4`, `INSERT 0 1`. The old image drops the unknown key on read
(`staff_permissions.clean`), so it is safe to apply before the push.

### 3. Afterwards

- A migrated list may now read as "custom" on People; the owner can untick Scholars on the Permissions tab.
- Run the Supabase Security Advisor (no schema change, so expect no new finding).

## Strings for ms / ta review

The Applications and Scholars permission labels and descriptions (`admin.perm.see_all`, `admin.perm.scholars`),
`qcBrings`, `myStudents.needSeeAll`, the Add-to-Admins hint (`addIntro.admins`), `inviteAdminNote`,
`files_widened_all` and `becomesMentor`: new ms and ta wording, written by the builder.
