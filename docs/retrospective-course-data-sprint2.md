# Retrospective — Course-Data Pipeline Sprint 2 (2026-06-13)

Roadmap: `docs/roadmap-course-data-pipeline.md`. Catalogue-wide link health + audit freshness section.

## What Was Built
- **`validate_course_urls`** — reachability check over the distinct external URLs on `Institution.url` +
  `CourseInstitution.hyperlink` (deduped), with a lightweight HTTP GET via **stdlib `urllib`** (no new dep, no browser).
  Classifies alive / dead (404/410/5xx) / error (timeout/DNS/SSL — transient, never auto-fixed). `--fix` clears
  **confirmed-dead** URLs only; `--limit` / `--timeout`. Pure `check_url(url)` for testability.
- **`audit_data` LINK HEALTH section** — distinct external URL counts per catalogue + how to verify liveness. The
  audit-derived freshness signal (no per-row `last_verified` — option A).
- Complements the Selenium STPM validator: `validate_course_urls` = "is the link reachable", `validate_stpm_urls` =
  "does MOHE still list this programme". Documented that HTTP status can't detect a portal that 200s on a dead page.

## What Went Well
- **Worktree isolation, second time, frictionless** — built in `.worktrees/course-urls`; the other agent pushed
  `cf5ad79` to `main` mid-sprint and the merge was still clean (no overlap, courses-only change).
- **Zero new dependency** — chose stdlib `urllib` over `requests`/`httpx`, so no `requirements.txt` churn and no extra
  install at deploy (L78 avoided by design).
- **Honest scoping up front** — explicitly bounded this to *reachability* (not portal-content), and chose option (A)
  (no migration) to keep it genuinely low-complexity, with the `last_verified` field as a documented optional follow-up.

## What Went Wrong
- Nothing notable. The sprint was small, the plan held, tests passed first run, no regressions, one clean deploy.

## Design Decisions
- **Option (A): no `last_verified` field/migration.** Freshness is audit-run-derived ("run the checker, read the
  report"). Avoids a migration on Course/StpmCourse for a low-value-now persisted date. Revisit if persisted per-row
  freshness dates become worth a migration (logged in the roadmap).
- **Reachability via HTTP status, deliberately NOT content-aware.** Catches the common rot (dead domains, 404s,
  timeouts); the deeper "portal lists nothing" check stays with the STPM Selenium validator (per-portal markers).

## Numbers
| Metric | Value |
|--------|-------|
| New tests | 10 (check_url classification ×5, report counts, dry-run vs --fix, fix-clears-dead-only, limit, audit section) |
| Suite | 1044 (courses), 0 failures |
| Deploys | 1 API build | 
| Files | 5 (1 new command, audit_data, 1 test, CHANGELOG, roadmap) |
| Migration | none |
