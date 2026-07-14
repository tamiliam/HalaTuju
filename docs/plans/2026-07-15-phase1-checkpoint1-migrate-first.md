# Phase 1 Checkpoint 1 — prod migrate-first runbook (Sprints 2 + 3a)

**Run via the Supabase MCP (`execute_sql`) BEFORE pushing the S2/S3a/S3b commits.**
Deploys do not migrate; additive-first keeps live code working. The deployed code's
`ScholarshipApplication.save()` reads `owning_organisation_id` and queries
`scholarship_cohorts.owning_organisation_id`, so **these columns MUST exist before the
push** or every application save 500s. Hand-written Postgres DDL (never `sqlmigrate` —
it renders SQLite). Index names are hand-chosen; Django never re-introspects them.

Four migrations, all additive: `scholarship/0099` (+0100 data) and `courses/0062`
(+0063 data). `scholarship/0099` also carries an AlterField that only changes a
cohort help_text — metadata only, no DDL; the migration row is still recorded.

## Pre-checks (run first, abort if any fails)

```sql
-- 1. Right tables? (legacy-table trap): the real tables carry a known column.
SELECT
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='scholarship_applications' AND column_name='cohort_id')   AS app_ok,
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='partner_admins' AND column_name='is_super_admin')        AS admin_ok,
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='partner_organisations' AND column_name='module_payout')  AS org_ok,
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='scholarship_cohorts' AND column_name='owning_organisation_id') AS cohort_ok;
-- expect: 1 | 1 | 1 | 1  (org/cohort cols prove Sprint 1 is already applied)

-- 2. BrightPath org exists (Sprint 1 seed) — the backfills bind to it.
SELECT id, code FROM partner_organisations WHERE code='brightpath';
-- expect 1 row

-- 3. These migrations not already applied (a parallel session may have run it first).
SELECT name FROM django_migrations
WHERE name IN ('0099_application_owning_organisation',
               '0100_backfill_application_owning_organisation',
               '0062_partneradmin_owning_organisation',
               '0063_backfill_partneradmin_owning_organisation');
-- expect 0 rows (if any appear, skip that step — already applied)

-- 4. Columns not already present (idempotence).
SELECT
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='scholarship_applications' AND column_name='owning_organisation_id') AS app_col,
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='partner_admins' AND column_name='owning_organisation_id')          AS admin_col;
-- expect: 0 | 0
```

## Step 1 — scholarship/0099 (FK column on scholarship_applications; cohort help_text = no DDL)

```sql
BEGIN;
ALTER TABLE scholarship_applications
  ADD COLUMN owning_organisation_id bigint NULL
  REFERENCES partner_organisations(id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX scholarship_applications_owning_organisation_id_idx
  ON scholarship_applications (owning_organisation_id);
INSERT INTO django_migrations (app, name, applied)
VALUES ('scholarship', '0099_application_owning_organisation', now());
COMMIT;
```

## Step 2 — scholarship/0100 (backfill applications from their cohort)

```sql
BEGIN;
UPDATE scholarship_applications a
SET owning_organisation_id = c.owning_organisation_id
FROM scholarship_cohorts c
WHERE a.cohort_id = c.id
  AND a.owning_organisation_id IS NULL
  AND c.owning_organisation_id IS NOT NULL;
INSERT INTO django_migrations (app, name, applied)
VALUES ('scholarship', '0100_backfill_application_owning_organisation', now());
COMMIT;
```

## Step 3 — courses/0062 (FK column on partner_admins)

```sql
BEGIN;
ALTER TABLE partner_admins
  ADD COLUMN owning_organisation_id bigint NULL
  REFERENCES partner_organisations(id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX partner_admins_owning_organisation_id_idx
  ON partner_admins (owning_organisation_id);
INSERT INTO django_migrations (app, name, applied)
VALUES ('courses', '0062_partneradmin_owning_organisation', now());
COMMIT;
```

## Step 4 — courses/0063 (bind existing B40 staff to BrightPath)

```sql
BEGIN;
UPDATE partner_admins
SET owning_organisation_id = (SELECT id FROM partner_organisations WHERE code='brightpath')
WHERE role IN ('admin','reviewer','qc')
  AND is_active = true
  AND is_super_admin = false
  AND owning_organisation_id IS NULL;
INSERT INTO django_migrations (app, name, applied)
VALUES ('courses', '0063_backfill_partneradmin_owning_organisation', now());
COMMIT;
```

## Post-checks

```sql
-- Columns landed on the RIGHT tables.
SELECT
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='scholarship_applications' AND column_name='owning_organisation_id') AS app_col,
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='partner_admins' AND column_name='owning_organisation_id')          AS admin_col;
-- expect: 1 | 1

-- Zero un-owned applications (every one inherited its cohort's org = BrightPath).
SELECT count(*) FROM scholarship_applications WHERE owning_organisation_id IS NULL;
-- expect 0

-- Staff binding: active non-super admin/reviewer/qc → BrightPath; super/partner NULL.
SELECT role, is_super_admin,
       (owning_organisation_id IS NULL) AS org_null, count(*)
FROM partner_admins
WHERE is_active = true
GROUP BY role, is_super_admin, org_null
ORDER BY role;
-- expect: admin/reviewer/qc (non-super) → org_null=false; super + partner → org_null=true

-- The four migration rows recorded.
SELECT app, name FROM django_migrations
WHERE name IN ('0099_application_owning_organisation',
               '0100_backfill_application_owning_organisation',
               '0062_partneradmin_owning_organisation',
               '0063_backfill_partneradmin_owning_organisation')
ORDER BY app, name;
-- expect 4 rows
```

## Then and only then
`git push` (triggers the api + web deploy) → match the build by SHORT_SHA in
`gcloud builds list` → live smoke:
1. student flow loads (web 200);
2. reviewer/QC cockpit — the B40 application **list** and a **detail** open (org-scoped
   query returns today's rows, since BrightPath is the only org);
3. a QC action succeeds on an awaiting-QC case.
Zero new error logs. Then interim close notes → Sprint 4 (no migration).

**Rollback:** the DDL is additive; reverting the code leaves the unused columns
harmless. If a step must be undone: `ALTER TABLE … DROP COLUMN owning_organisation_id;`
+ delete the corresponding `django_migrations` row (do the two data steps' rows too).
