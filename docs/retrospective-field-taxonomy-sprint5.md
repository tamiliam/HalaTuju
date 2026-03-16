# Retrospective — Field Taxonomy Sprint 5: Cleanup & Legacy Removal

**Date:** 2026-03-16
**Sprint:** Field Taxonomy Sprint 5 (Final)

---

## What Was Built

1. **`field_key` non-nullable** — Migration 0027 makes `field_key` non-nullable on both `Course` and `StpmCourse`. All 1,503 courses already had values; RunPython step backfills any stragglers to `umum`.

2. **`frontend_label` removed** — Migration 0028 drops the column from `Course`. Removed from `CourseSerializer`, `CourseAdmin`, all test fixtures. Was the original SPM field grouping (9 Malay labels) — fully replaced by `field_key`.

3. **`category` removed** — Migration 0029 drops the column from `StpmCourse`. Was an AI-generated field from Gemini classification, never used in any frontend or API logic.

4. **Frontend field fallbacks replaced** — All `course.field` / `data.field` references in 5 frontend files replaced with `getFieldName(course.field_key)` from `useFieldTaxonomy` hook. Field labels are now trilingual everywhere.

5. **TypeScript types cleaned** — `frontend_label` removed from `Course` interface. `field` marked as legacy. `SearchParams.field` removed (only `field_key` sent).

---

## What Went Well

- **Zero breakage** — 530 tests pass, golden masters unchanged (SPM=5319, STPM=1811). Frontend build clean.
- **Clean removal** — 3 columns removed with proper migrations. No backward-compatibility shims needed.
- **Images already existed** — Both `farmasi.png` and `undang-undang.png` were already in Supabase Storage from earlier image generation runs.

---

## What Went Wrong

Nothing significant. Straightforward column removal sprint.

---

## Design Decisions

- **Keep `field` column in DB** — Still present on both models for audit/debugging. Removed from serializer output but not from the database. Can be dropped in a future migration if needed.
- **`umum` as fallback** — The RunPython migration step sets any NULL `field_key` to `umum` (catch-all) before making the column non-nullable. In practice, no rows had NULL values.

---

## Numbers

| Metric | Value |
|--------|-------|
| Files modified | 27 |
| Migrations created | 3 (0027, 0028, 0029) |
| Columns removed | 2 (frontend_label, category) |
| Columns altered | 2 (field_key non-nullable on both models) |
| Backend tests | 530 |
| Frontend tests | 17 |
| Golden master | SPM=5319, STPM=1811 (unchanged) |

---

## Field Taxonomy Series Summary

| Sprint | Focus | Key Deliverable |
|--------|-------|-----------------|
| 1 | Model + SPM backfill | FieldTaxonomy table (47 entries), 390 SPM courses classified |
| 2 | STPM classification + API | 1,113 STPM courses classified, `/api/v1/fields/` endpoint |
| 3 | Ranking engine | field_key-based interest matching, shared FIELD_KEY_MAP |
| 4 | Frontend integration | useFieldTaxonomy hook, CourseCard rewrite, trilingual search filter |
| 5 | Cleanup | field_key non-nullable, legacy columns removed, frontend fallbacks replaced |

**Total across 5 sprints:** 47 taxonomy entries, 1,503 courses classified, 3 legacy columns removed, unified trilingual field system across SPM + STPM.
