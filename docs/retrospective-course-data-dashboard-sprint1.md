# Retrospective — Course Data Dashboard Sprint 1 (2026-06-13)

Roadmap: `docs/roadmap-course-data-pipeline.md` (the "Course Data dashboard" track). Owner direction:
**build the tools, then a dashboard that shows status for decisions — no harvesting now.** So this is
the **reporting-only** first cut (no "run" buttons; no ingest).

## What Was Built
- **`CourseDataStatus` model** (`course_data_status` table; migration `0054_coursedatastatus`) — one row
  per source/check (`epanduan_stpm`, `epanduan_spm`, `uptvet`, `emasco`, `link_health`, `audit`), storing
  `last_run_at` + a JSON `summary`. A missing row = "never run".
- **`course_data_status.py`** — `record_status(key, summary, detail)` (best-effort upsert) + `coverage_snapshot()`
  (live have/available/gap from the DB, no stored state; UP_TVET "available" comes from the last stored inventory).
- **Instrumented the 3 LIVE tools** to record status on completion: `refresh_stpm` → `epanduan_stpm`,
  `validate_course_urls` → `link_health`, `audit_data` → `audit`. All wrapped best-effort (telemetry never
  breaks the tool — caught by the no-DB orchestration tests, see below).
- **`AdminCourseDataView`** (`GET /api/v1/admin/course-data/`, any admin role, read-only) → `{statuses, coverage}`,
  every known key present (missing → null). +8 backend tests.
- **`/admin/course-data` page** + nav link (super + admin) + `getCourseDataStatus` client + `admin.courseData.*`
  i18n (en/ms/ta, parity 2600). Freshness strip (4 source cards w/ status dot + "never run" first-class state),
  a coverage table (have/available/gap), link-health + audit cards. Read-only — each card shows the local refresh
  command as a muted hint, no buttons.

## What Went Well
- **Reporting-only scope dissolved the "no harvest" tension** — no UI path can run a scrape/sync, so the dashboard
  is purely a status surface, exactly what was asked.
- **Mirrored existing patterns cleanly** — `PartnerAdminMixin` endpoint like `PartnerDashboardView`; page like the
  admin dashboard; nav like the other links. Small, reviewable diff.
- **All gates green first real run**: next build clean (route 1.75 kB), jest 306, courses pytest 1055 (+8), parity 2600×3.

## What Went Wrong
- **Instrumentation broke `refresh_stpm`'s no-DB orchestration tests.** Those tests run `refresh_stpm` with
  `call_command` mocked and **no database** (SimpleTestCase-style); my added `StpmCourse.objects.count()` (evaluated
  as a `record_status` argument, BEFORE `record_status`'s own try/except) hit the DB and raised. Fix: wrap the whole
  instrumentation block in `try/except` so telemetry is fully best-effort. Lesson: a status/telemetry call added to an
  existing command must be guarded as a unit — guarding only the writer isn't enough when the *arguments* touch the DB.
- Two test-fixture fixes (FieldTaxonomy uses `key` not `field_key`; StpmCourse needs `field_key`) + absolute-count
  asserts failed against a migration-seeded test DB → switched to delta asserts.

## Design Decisions
- **Reporting-only first; triggers later.** Logged in `decisions.md`. Matches "no harvesting now"; the hybrid
  update-triggers are a deliberate later sprint.
- **Freshness via a recorded-run store; coverage computed LIVE.** Counts don't need persistence (compute from the DB);
  freshness/link-health/audit do (a recorded `last_run_at`). UP_TVET available/gap only show once an inventory has run.
- **Empty-state is first-class** (#176) — most sources read "never refreshed" until harvested; that's informative, not broken.

## Carry-forward
- **The SPM + UP_TVET tools aren't instrumented here** (they live on `spm-catalogue` / `uptvet-coverage`). Until those
  branches merge AND their commands call `record_status('epanduan_spm'/'uptvet', …)`, the dashboard shows those two as
  "never refreshed". Wire that when those branches land.
- **Migration `0054` is parallel to `spm-catalogue`'s `0054_course_is_active`** (both children of `0053`). At merge:
  `makemigrations --merge` (or renumber the second). New table → enable RLS at deploy (service-role-only, deny-by-default).

## Numbers
| Metric | Value |
|--------|-------|
| New tests | 8 (record_status ×2, coverage ×3, endpoint ×3) |
| Suite | 1055 courses pytest (1047 baseline off main), 0 failures; jest 306; parity 2600×3 |
| next build | clean (`/admin/course-data` 1.75 kB) |
| Migration | `0054_coursedatastatus` (new table; migrate-first + RLS at deploy) |
| Files | model+migration, status helper, 3 instrumented commands, view, url, FE page+client+nav, i18n×3, test, docs |
