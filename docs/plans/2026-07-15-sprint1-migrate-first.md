# Platform Sprint 1 — prod migrate-first runbook

**Run via the Supabase MCP (`execute_sql`) BEFORE pushing the Sprint-1 commit** (deploys do not
migrate; additive-first keeps live code working). Hand-written Postgres DDL per lessons — never
`sqlmigrate` output (it renders SQLite).

## Pre-checks (run first, abort if any fails)

```sql
-- 1. Right table? (legacy-table trap): partner_organisations must have contact_person
SELECT column_name FROM information_schema.columns
WHERE table_name='partner_organisations' AND column_name IN ('contact_person','code');
-- expect 2 rows

-- 2. scholarship_cohorts is the cohort table (custom db_table)
SELECT column_name FROM information_schema.columns
WHERE table_name='scholarship_cohorts' AND column_name='query_response_sla_days';
-- expect 1 row

-- 3. Migrations not already applied
SELECT name FROM django_migrations WHERE name LIKE '0061_partner%' OR name LIKE '009%owning%' OR name LIKE '0098_seed%';
-- expect 0 rows
```

## Step 1 — courses/0061 (19 additive columns on partner_organisations)

```sql
BEGIN;
ALTER TABLE partner_organisations
  ADD COLUMN programme_name_en varchar(200) NOT NULL DEFAULT '',
  ADD COLUMN programme_name_ms varchar(200) NOT NULL DEFAULT '',
  ADD COLUMN programme_name_ta varchar(200) NOT NULL DEFAULT '',
  ADD COLUMN logo_url varchar(500) NOT NULL DEFAULT '',
  ADD COLUMN brand_colour varchar(20) NOT NULL DEFAULT '',
  ADD COLUMN persona_name_en varchar(100) NOT NULL DEFAULT '',
  ADD COLUMN persona_name_ms varchar(100) NOT NULL DEFAULT '',
  ADD COLUMN persona_name_ta varchar(100) NOT NULL DEFAULT '',
  ADD COLUMN team_signoff_en varchar(200) NOT NULL DEFAULT '',
  ADD COLUMN team_signoff_ms varchar(200) NOT NULL DEFAULT '',
  ADD COLUMN team_signoff_ta varchar(200) NOT NULL DEFAULT '',
  ADD COLUMN email_from varchar(254) NOT NULL DEFAULT '',
  ADD COLUMN email_reply_to varchar(254) NOT NULL DEFAULT '',
  ADD COLUMN email_support varchar(254) NOT NULL DEFAULT '',
  ADD COLUMN frontend_url varchar(200) NOT NULL DEFAULT '',
  ADD COLUMN module_scholarship boolean NOT NULL DEFAULT false,
  ADD COLUMN module_sponsor_pool boolean NOT NULL DEFAULT false,
  ADD COLUMN module_comms_whatsapp boolean NOT NULL DEFAULT false,
  ADD COLUMN module_payout boolean NOT NULL DEFAULT false;
-- Django keeps defaults app-side:
ALTER TABLE partner_organisations
  ALTER COLUMN programme_name_en DROP DEFAULT, ALTER COLUMN programme_name_ms DROP DEFAULT,
  ALTER COLUMN programme_name_ta DROP DEFAULT, ALTER COLUMN logo_url DROP DEFAULT,
  ALTER COLUMN brand_colour DROP DEFAULT, ALTER COLUMN persona_name_en DROP DEFAULT,
  ALTER COLUMN persona_name_ms DROP DEFAULT, ALTER COLUMN persona_name_ta DROP DEFAULT,
  ALTER COLUMN team_signoff_en DROP DEFAULT, ALTER COLUMN team_signoff_ms DROP DEFAULT,
  ALTER COLUMN team_signoff_ta DROP DEFAULT, ALTER COLUMN email_from DROP DEFAULT,
  ALTER COLUMN email_reply_to DROP DEFAULT, ALTER COLUMN email_support DROP DEFAULT,
  ALTER COLUMN frontend_url DROP DEFAULT, ALTER COLUMN module_scholarship DROP DEFAULT,
  ALTER COLUMN module_sponsor_pool DROP DEFAULT, ALTER COLUMN module_comms_whatsapp DROP DEFAULT,
  ALTER COLUMN module_payout DROP DEFAULT;
INSERT INTO django_migrations (app, name, applied)
VALUES ('courses', '0061_partnerorganisation_brand_colour_and_more', now());
COMMIT;
```

## Step 2 — scholarship/0097 (FK column on scholarship_cohorts)

```sql
BEGIN;
ALTER TABLE scholarship_cohorts
  ADD COLUMN owning_organisation_id bigint NULL
  REFERENCES partner_organisations(id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX scholarship_cohorts_owning_organisation_id_idx
  ON scholarship_cohorts (owning_organisation_id);
INSERT INTO django_migrations (app, name, applied)
VALUES ('scholarship', '0097_scholarshipcohort_owning_organisation', now());
COMMIT;
```

## Step 3 — scholarship/0098 (seed BrightPath + backfill)

```sql
BEGIN;
INSERT INTO partner_organisations
  (code, name, contact_email, contact_person, phone, is_active, created_at,
   programme_name_en, programme_name_ms, programme_name_ta, logo_url, brand_colour,
   persona_name_en, persona_name_ms, persona_name_ta,
   team_signoff_en, team_signoff_ms, team_signoff_ta,
   email_from, email_reply_to, email_support, frontend_url,
   module_scholarship, module_sponsor_pool, module_comms_whatsapp, module_payout)
SELECT
  'brightpath', 'BrightPath Bursary', 'help@halatuju.xyz', '', '', true, now(),
  'BrightPath Bursary', 'Bursari BrightPath', 'BrightPath Bursary', '', '#137fec',
  'Cikgu Gopal', 'Cikgu Gopal', 'Cikgu Gopal',
  'The BrightPath Bursary Team', '', '',
  'info@halatuju.xyz', 'help@halatuju.xyz', 'help@halatuju.xyz', 'https://halatuju.xyz',
  true, true, true, false
WHERE NOT EXISTS (SELECT 1 FROM partner_organisations WHERE code='brightpath');

UPDATE scholarship_cohorts
SET owning_organisation_id = (SELECT id FROM partner_organisations WHERE code='brightpath')
WHERE owning_organisation_id IS NULL;

INSERT INTO django_migrations (app, name, applied)
VALUES ('scholarship', '0098_seed_brightpath_organisation', now());
COMMIT;
```

## Post-checks

```sql
-- Columns landed on the RIGHT table (sanity: known column present alongside a new one)
SELECT count(*) FROM information_schema.columns
WHERE table_name='partner_organisations' AND column_name IN ('contact_person','module_payout');
-- expect 2

SELECT code, programme_name_ms, module_scholarship FROM partner_organisations WHERE code='brightpath';
-- expect: brightpath | Bursari BrightPath | t

SELECT count(*) FROM scholarship_cohorts WHERE owning_organisation_id IS NULL;
-- expect 0

SELECT app, name FROM django_migrations ORDER BY id DESC LIMIT 3;
-- expect the three rows just inserted
```

**Then and only then:** `git push` (triggers deploy) → live smoke (student flow loads; cockpit lists
applicants) → close the sprint.
