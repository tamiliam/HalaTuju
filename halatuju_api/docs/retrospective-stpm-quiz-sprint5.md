# Retrospective — STPM Quiz Sprint 5: Deploy & Validate (2026-03-18)

## What Was Built

Production deployment of all STPM quiz engine work (Sprints 1-4). Applied 4 pending database migrations to Supabase, ran RIASEC enrichment against production data, deployed backend and frontend to Cloud Run, and smoke tested the full quiz flow.

## What Went Well

- **Parallel deploys**: Backend and frontend deployed simultaneously to Cloud Run, saving ~10 minutes wall time.
- **Raw SQL migration bypass**: The `InconsistentMigrationHistory` error (migration 0017/0018 ordering) has blocked `manage.py migrate` for weeks. Applying DDL via Supabase MCP `execute_sql` and recording in `django_migrations` manually was a clean workaround.
- **Enrichment ran cleanly**: `enrich_stpm_riasec --apply` updated 867/1,112 courses and 28/47 taxonomy entries on first run. 8 unmapped field_keys (edge cases like `umum`, `sains-data`) are known and documented.
- **Security Advisor clean**: No new RLS or security issues from 4 schema changes.

## What Went Wrong

1. **Migration 0043 assumed `address` column existed.**
   - *Symptom*: First `execute_sql` batch failed with `column "address" of relation "student_profiles" does not exist`.
   - *Root cause*: Migration 0010 (which adds `address`) was never applied to Supabase, even though later migrations (0031-0041) were recorded. The migration history is inconsistent — some early migrations were skipped during initial Supabase setup.
   - *Fix*: Changed the SQL to `ADD COLUMN IF NOT EXISTS address text` (final type) instead of `ALTER COLUMN`. For future migrations that alter existing columns, always verify the column exists in production first.

2. **Smoke test used wrong API field names.**
   - *Symptom*: Eligibility endpoint returned 0 courses with `grades` field; returned error with wrong field name.
   - *Root cause*: The STPM eligibility API requires `stpm_grades` (uppercase keys like `PHYSICS`), `spm_grades`, and `cgpa` — different from what the quiz API uses (lowercase keys). No single reference doc maps all endpoint schemas.
   - *Fix*: Checked test files for correct request format. Not a code issue — just operator error during manual smoke testing.

## Design Decisions

1. **Raw SQL over Django migrate**: Used Supabase MCP `execute_sql` to apply DDL directly, bypassing Django's migration runner. This avoids the `InconsistentMigrationHistory` error that has accumulated from months of ad-hoc migration application. Trade-off: migration state must be manually recorded in `django_migrations` table.

2. **Address column created as final type**: Migration 0043 originally did AddField(CharField) then AlterField(TextField). Since migration 0010 was never applied, we created `address` directly as `text` (the final desired type), skipping the intermediate CharField state.

## Numbers

| Metric | Value |
|--------|-------|
| Migrations applied | 4 (0042-0045) |
| Courses enriched | 867 |
| Taxonomy entries enriched | 28 |
| Unmapped field_keys | 8 |
| Backend revision | halatuju-api-00131-p7l |
| Frontend revision | halatuju-web-00160-rql |
| Backend tests | 888 (unchanged) |
| Frontend tests | 17 (unchanged) |
| Security Advisor issues | 0 new |
