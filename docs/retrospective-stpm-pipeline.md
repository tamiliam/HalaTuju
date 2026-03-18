# Retrospective — STPM Pipeline Completion Sprint (2026-03-18)

## What Was Built

Made the STPM data pipeline production-ready with 4 features:

1. **Course deactivation mechanism** — `is_active` BooleanField on StpmCourse (default True). All 8 query sites in `stpm_engine.py` and `views.py` filter by `is_active=True`. Detail view and saved courses intentionally unfiltered (user should still see courses they saved or linked to).

2. **Sync command deactivation** — `sync_stpm_mohe --apply` now deactivates removed courses and reactivates returned ones. Reports inactive count, splits removed into active-will-deactivate vs already-inactive.

3. **STPM audit sections** — `audit_data` now reports STPM courses (active/inactive, description, headline, MOHE URL, merit, institution FK, career links), requirements (coverage, subject group stats), and career mappings (M2M link count).

4. **MOHE scraper fix** — Rewrote `_parse_cards()` for redesigned ePanduan DOM. Old selectors returned 0 results. New ones use `.executive-data-label`/`.executive-data-value` classes. Changed page load from `networkidle` (hung) to `domcontentloaded` + explicit selector wait. Added `Set` deduplication. Verified: 1,002 Science programmes scraped across 101 pages.

5. **Workflow doc update** — `stpm-requirements-update.md` updated with current test count (888+), added Stage 5 (deactivation), added `scrape_mohe_stpm.py` and `sync_stpm_mohe.py` to tool inventory, added deactivation failure mode.

## What Went Well

- **Subagent-driven development worked cleanly** — 6 tasks dispatched sequentially, each with spec compliance review. No rework needed on any task.
- **Exhaustive query audit upfront** — listing all 15 `StpmCourse.objects` call sites in the plan prevented missed filtering. The split into "must filter" vs "no filter" was the right framing.
- **Live scraper test caught real breakage** — MOHE had redesigned their DOM. Without testing against the live site, the scraper would have failed silently during the annual refresh.

## What Went Wrong

1. **Stray commit from another session slipped in** — `c953fff` (STPM quiz Sprint 3) was committed by a subagent during Task 5's long scraper run. The subagent completed other work while waiting for Playwright.
   - Root cause: The subagent ran in the same workspace without branch isolation, and the concurrent session committed to `main`.
   - Fix: For long-running tasks (scraper, deploy), either use a worktree or verify `git log` before and after to catch unexpected commits.

2. **Scraper required iterative DOM investigation** — took 4 rounds of Playwright inspection to understand the new DOM structure (heading, card container, data labels, badges).
   - Root cause: No DOM documentation from the scraper's original author; the JavaScript was opaque inline code.
   - Fix: Added comments to the new JS explaining each selector. Future DOM changes will be easier to debug.

## Design Decisions

- **`is_active` on StpmCourse only, not StpmRequirement** — Requirements are 1:1 with courses (cascade delete). Filtering at the course level is sufficient. No need for a redundant flag on requirements.
- **Detail view NOT filtered** — Users who have a direct link to a deactivated course should still see it (e.g. from saved courses or shared links). The search and eligibility are filtered.
- **Reactivation is automatic** — If a course reappears in MOHE after being deactivated, `sync_stpm_mohe --apply` reactivates it. No manual intervention needed.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 829 | 888 |
| New test files | — | `test_stpm_sync.py` (7 tests) |
| Updated test files | — | `test_stpm_models.py` (+2), `test_stpm_engine.py` (+1), `test_stpm_search.py` (+2) |
| Golden masters | SPM=5319, STPM=2026 | Unchanged |
| Files changed | — | 7 (model, migration, engine, views, sync, audit, scraper) |
| MOHE programmes scraped | 0 (broken) | 1,002 (Science) |
