# Contract Go-Live Transition T2 — prod cutover SQL (migrate-first)

Applied to prod (Supabase `pbrrlyoyyiftckqvzvvo`, HalaTuju) via the Supabase MCP BEFORE the
single deploy, per the migrate-first convention (deploys do NOT run `migrate`). These are the two
migrations authored in T1 but not applied then (T1 was branch-only). Hand-written Postgres DDL
(`sqlmigrate` renders SQLite) grounded in the live schema: `partner_organisations.id`,
`scholarship_applications.id`, `api_student_profiles.referred_by_org_id` are all `bigint`.

Pre-state verified 2026-07-19: `show_in_apply` absent, `witness_org_id` absent; `courses` at
`0064`, `scholarship` at `0103`.

## courses/0065 — PartnerOrganisation.show_in_apply (+ data seed)

```sql
ALTER TABLE partner_organisations
  ADD COLUMN show_in_apply boolean NOT NULL DEFAULT false;

-- Data-driven seed (T1 RunPython): activate every org that has ANY referring student.
-- On prod this is 7 orgs (cumig, smc, pptm, ewrf, mhm, hss, hyo) — the plan's "6" was the
-- 32-student live-cohort subset; the apply-form source list wants every real referral source.
UPDATE partner_organisations SET show_in_apply = true
  WHERE id IN (SELECT DISTINCT referred_by_org_id
               FROM api_student_profiles WHERE referred_by_org_id IS NOT NULL);

INSERT INTO django_migrations (app, name, applied)
  VALUES ('courses', '0065_partnerorganisation_show_in_apply', now());
```

## scholarship/0104 — ScholarshipApplication.witness_org (FK)

```sql
ALTER TABLE scholarship_applications
  ADD COLUMN witness_org_id bigint NULL
  CONSTRAINT scholarship_applications_witness_org_id_fk
  REFERENCES partner_organisations (id) DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX scholarship_applications_witness_org_id_idx
  ON scholarship_applications (witness_org_id);

INSERT INTO django_migrations (app, name, applied)
  VALUES ('scholarship', '0104_scholarshipapplication_witness_org', now());
```

**Constraint/index naming caveat** (same as E1a/E2a/E3/0103): the FK constraint + index are named
explicitly here, which differs from Django's hashed names. Harmless — a future migration that
alters/drops either by Django's expected name would need the real name (query
`information_schema` / `pg_indexes`). No RLS change: both tables are pre-existing (RLS already
configured); `ADD COLUMN` does not alter it.
