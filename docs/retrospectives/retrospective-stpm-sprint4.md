# STPM Sprint 4 Retrospective — Search + Detail Pages

**Date:** 2026-03-13
**Branch:** `feature/stpm-entrance`

## What Was Built

1. **STPM search API** (`GET /api/v1/stpm/search/`) — Text, university, and stream filters with cursor-based pagination (20 per page). Returns filter metadata (distinct universities, streams) for dropdown population.

2. **STPM programme detail API** (`GET /api/v1/stpm/programmes/<id>/`) — Full programme data including human-readable subject labels, SPM prerequisite labels, CGPA/MUET thresholds, and boolean flags (interview, colorblind, medical, Malaysian-only, bumiputera-only).

3. **Frontend API client + i18n** — `searchStpmProgrammes()` and `getStpmProgrammeDetail()` in `lib/api.ts` with typed interfaces. 33 new i18n keys across EN/BM/TA for search and detail pages.

4. **STPM search page** (`/stpm/search`) — Debounced text search, university/stream dropdown filters via URL params, responsive 3-column card grid, load-more pagination. Dashboard "Browse All Programmes" link added.

5. **STPM programme detail page** (`/stpm/[id]`) — Breadcrumb navigation, header with stream badge, STPM subjects (blue pills), SPM prerequisites (green pills), sidebar with quick facts and requirement flags.

## What Went Well

- **Subagent-driven execution**: All 5 implementation tasks completed via fresh subagents. Each produced clean, working code on first run with no debugging needed.
- **i18n done inline**: Tasks 3 (API client + i18n) was small enough to implement directly, saving context vs. spawning a subagent.
- **Test-first approach**: Backend tests (12 new) all passed on first run. Both golden masters unchanged.
- **Correct i18n pattern**: Search page subagent correctly adapted from `useTranslation()` to the project's actual `useT()` pattern without being told.

## What Went Wrong

- **Nothing significant**. Clean sprint — all tasks passed on first attempt, frontend build clean, no rework needed.

## Design Decisions

- **URL-based filter state** for search page: Filters are stored in URL search params rather than React state. This makes search results linkable/shareable and survives page refreshes.
- **Human-readable labels in detail API**: The backend maps internal subject codes to display names (e.g., `pengajian_am` → `Pengajian Am`) rather than requiring the frontend to maintain a mapping table. Keeps the frontend thin.

## Numbers

| Metric | Value |
|--------|-------|
| Tests collected | 319 |
| Tests passing | 286 |
| Tests added | 12 (8 search + 4 detail) |
| SPM golden master | 8283 (unchanged) |
| STPM golden master | 1811 (unchanged) |
| i18n keys added | 33 × 3 languages = 99 |
| Commits | 5 (search API, detail API, API client+i18n, search page, detail page) |
