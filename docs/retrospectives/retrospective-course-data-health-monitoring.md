# Retrospective — Course-Data Health Monitoring (2026-06-13)

Roadmap: `docs/roadmap-course-data-pipeline.md` (Course Data dashboard track, "Sprint A"). Owner intent:
**watch freshness + link health, READ-ONLY, no update/overwrite; periodic cron + a manual option.**

## What Was Built
- **`validate_course_urls --workers N`** — a concurrent (`ThreadPoolExecutor`) path for the ~650 catalogue URLs
  (read-only GETs parallelise safely; `check_url` unchanged → existing tests hold). ~650 URLs now finish in well
  under a minute instead of minutes, so the check fits in a single Cloud Run request (cron OR button) — no Cloud
  Run Job needed.
- **`course_data_check`** — read-only orchestrator: `audit_data` + `validate_course_urls --workers 20` (NO `--fix`,
  NO scrape, NO catalogue writes); each records its dashboard status (`audit`, `link_health`).
- **Weekly cron** — `'course-data-check'` added to `CronRunView.JOBS`; Cloud Scheduler `halatuju-course-data-check`
  (Mon 03:00 Asia/KL) POSTs the cron endpoint (`X-Cron-Secret`, mirrors the existing schedulers).
- **Manual trigger** — `POST /api/v1/admin/course-data/check/` (`AdminCourseDataCheckView`, **super/admin only**)
  runs the same command synchronously and returns the refreshed payload; a "Run health check now" button on
  `/admin/course-data` with a checking state. Read-only — issues link checks + audit, never writes.

## What Went Well
- **Concurrency dissolved the timeout problem cleanly.** A read-only sized spike (652 distinct URLs) showed sequential
  checking would exceed the request timeout for both cron and button; parallelising the GETs (the obvious property of a
  read-only check) made a Cloud Run Job unnecessary — far less infra than the alternative.
- **Reuse over rebuild** — the two reporters already recorded dashboard status from the dashboard sprint; this sprint
  just runs them on a schedule + on demand. Small, coherent diff. No migration.
- **All gates green**: 1100 courses pytest (+7), cron tests pass, next build clean (1.96 kB), jest 306, parity 2603×3.

## What Went Wrong
- **Absolute-count test asserts (again).** Two `course_data_check` tests asserted `alive == 1` / `dead == 1`, but the
  test DB carries migration-seeded catalogue URLs (16), so the link check counts those too. Fixed to `>= 1` + assert MY
  seeded dead link survives (read-only). Same migration-seeded-DB trap as the dashboard sprint — should be a reflex by now.

## Design Decisions
- **Read-only monitoring, no writes — by construction.** The cron + button run only `audit_data` + `validate_course_urls`
  **without `--fix`**; the catalogue scrapes (which need a browser) stay manual/local and only ever dry-run. There is no
  UI/cron path that mutates the catalogue. Logged in `decisions.md`.
- **Concurrency, not a Cloud Run Job.** A concurrent in-request check (~650 URLs in <1 min) keeps the whole feature inside
  the existing CronRunView + a synchronous admin endpoint — no new Job/infra. Revisit only if the URL set grows ~10×.
- **Manual trigger gated super/admin** (not viewer) — it issues ~650 outbound requests; the dashboard nav already shows
  only to super/admin.

## Numbers
| Metric | Value |
|--------|-------|
| New tests | 7 (concurrency ×2; course_data_check command ×2; admin check endpoint ×3) |
| Suite | 1100 courses pytest (+7), 0 failures; cron tests pass; jest 306; parity 2603×3; next build clean |
| Migration | none |
| Ops | Cloud Scheduler `halatuju-course-data-check` (weekly Mon 03:00 Asia/KL) created at deploy |
| Files | validate_course_urls (+workers), course_data_check (new), CronRunView, views_admin, urls, FE page+client, i18n×3, 2 tests, docs |
