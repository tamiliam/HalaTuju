# Retrospective — STPM Sprint 7: Unified Explore Page

**Date:** 2026-03-13
**Branch:** `feature/stpm-entrance`
**Duration:** Single session

## What Was Built

Merged the separate SPM and STPM browse experiences into a single `/search` page. Students can now toggle between SPM, STPM, or All courses using qualification filter buttons. The old `/stpm/search` page redirects to `/search?qualification=STPM`.

Key deliverables:
- Unified `CourseSearchView` querying both `Course` (SPM) and `StpmCourse` (STPM) tables
- STPM→CourseCard field mapping for consistent UI rendering
- Bumiputera-only programme exclusion at runtime
- Eligible toggle dual-check (calls both eligibility APIs, merges IDs)
- AI metadata enrichment: 1,113 STPM courses classified with field/category/description via Gemini 2.0 Flash
- 3 new DB columns on `StpmCourse` (field, category, description) synced to Supabase
- 12 new unified search tests + 2 metadata model tests

## What Went Well

- **Subagent-driven development** worked smoothly — fresh subagent per task kept context clean, spec compliance and code quality reviews caught issues before they compounded.
- **Design-first approach** — the design doc and 9-task implementation plan meant zero ambiguity during execution.
- **Smart filter skipping** — level/source_type/state filters intelligently skip the irrelevant qualification, avoiding confusing empty results.
- **Gemini enrichment** classified all 1,113 courses in ~45 batches with only 1 JSON parse failure (re-ran 25 with `--only-empty`).

## What Went Wrong

1. **Gemini API key not found by management command**
   - *Symptom:* `enrich_stpm_metadata` command printed "GEMINI_API_KEY not set" and exited.
   - *Root cause:* The command used `os.environ.get('GEMINI_API_KEY')` but Django doesn't load `.env` files into the environment by default. The key was in the root `.env` but only accessible through `django.conf.settings`.
   - *Fix:* Changed to `settings.GEMINI_API_KEY or os.environ.get('GEMINI_API_KEY')`. Also documented manual `export` workaround. **System change:** Management commands should always read config from `settings` first, environment second.

2. **Gemini returned 207 unique field values instead of ~30**
   - *Symptom:* The field filter dropdown has far too many options (e.g. "Actuarial Science", "Forensic Chemistry" instead of broader categories like "Sains & Matematik").
   - *Root cause:* The prompt asked Gemini to use existing SPM categories first but "add new ones if none fits". Gemini interpreted this too liberally, creating hyper-specific fields for many courses.
   - *Fix:* Not blocking — filtering still works. Deferred to a data normalisation pass. **System change:** For taxonomy classification, future prompts should use a closed set (no "add new" option) or include a two-pass approach: classify first, then review outliers.

3. **Supabase batch sync consumed significant context**
   - *Symptom:* 23 SQL batch files needed to be executed one at a time via MCP, consuming context window.
   - *Root cause:* Same issue as Sprint 3 and Sprint 6 — large batch data operations don't fit in the main context window.
   - *Fix:* Delegated to a background subagent. **System change:** Already captured in lessons.md. Reinforces that >500 rows should use `psql` or a management command, not MCP batches.

## Design Decisions

- **Unified endpoint over separate APIs:** Extending `CourseSearchView` to handle both qualifications (with smart filter skipping) rather than keeping `/search` and `/stpm/search` as separate endpoints. Simpler frontend, single source of truth for course browsing.
- **Redirect over deletion:** `/stpm/search` redirects to `/search?qualification=STPM` rather than being deleted. Preserves bookmarks and any external links.
- **AI enrichment as one-time command:** `enrich_stpm_metadata` is a management command, not a scheduled job. The classification only needs to run once per data load. No ongoing cost.

## Numbers

| Metric | Value |
|--------|-------|
| Tests collected | 338 |
| Tests passing | 307 |
| Pre-existing failures | 9 (JWT auth) |
| New tests added | 14 (12 unified search + 2 metadata) |
| SPM golden master | 8,283 |
| STPM golden master | 1,811 |
| STPM courses enriched | 1,113 / 1,113 |
| Unique field values | 207 (needs normalisation) |
| Commits | 10 |
| Files changed | ~15 |
