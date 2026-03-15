# Retrospective — Field Taxonomy Sprint 2: STPM Classification + API Integration

**Date:** 2026-03-16
**Sprint:** Field Taxonomy Sprint 2

---

## What Was Built

1. **Deterministic STPM classifier** (`classify_stpm_fields.py`)
   - `classify_stpm_course()` maps `category + field + course_name` to taxonomy key
   - `_classify_spm_matching()` helper for 10 SPM-matching categories (702/1,113 courses)
   - Handles ~170 unique category values across 29 taxonomy keys
   - Management command with `--save` flag and distribution summary

2. **API integration**
   - `FieldTaxonomySerializer` with recursive `children` field
   - `GET /api/v1/fields/` endpoint (10 groups with nested children)
   - `?field_key=` backwards-compatible filter on search endpoints
   - `field_key` added to SPM search, STPM search, and STPM detail responses

3. **Supabase backfill**
   - All 1,113/1,113 STPM courses classified (0 unclassified)
   - Distribution healthy: 29 of 37 keys used

4. **Tests**
   - 57 STPM classifier tests + 4 API endpoint tests
   - Total: 118 in test_field_taxonomy.py, 542 across all test files

---

## What Went Well

- **Category data was clean enough for deterministic matching** — the original plan called for Gemini AI classification, but STPM category values turned out to be consistent BM labels. Deterministic matching is faster, cheaper, more testable, and reproducible.
- **Reusing `match_any()` from SPM classifier** — the shared utility reduced code duplication and kept the matching style consistent.
- **Test coverage was thorough** — 57 STPM tests covering all 10 SPM-matching categories, ~40 STPM-specific categories, edge cases (Lain-lain variants), and sub-classification paths.

---

## What Went Wrong

1. **STPM `field` == `category` (aggregate value) caused false matches when delegating to SPM classifier**
   - *Symptom:* 99 IT courses mapped to 'multimedia', 63 civil courses to 'senibina', 21 aero to 'minyak-gas' — all wrong.
   - *Root cause:* SPM's `classify_course()` checks keywords in the `field` parameter. For SPM, `field` is a specific sub-discipline (e.g. "Teknologi Maklumat"). For STPM, `field` equals the aggregate `category` string (e.g. "Komputer, IT & Multimedia"), so keyword matches like 'multimedia' hit the aggregate string instead of the course's actual sub-discipline.
   - *Fix:* Created `_classify_spm_matching()` that ignores `field` entirely and uses `course_name` for sub-classification. Added a comment explaining why SPM's `classify_course()` cannot be reused for STPM.
   - *Prevention:* When reusing a classifier across data sources, always verify the semantics of each input column — same column name does not mean same data granularity.

2. **"Bahasa & Komunikasi" misclassified as 'multimedia' instead of 'umum'**
   - *Symptom:* Language courses were being classified under Communication & Media.
   - *Root cause:* The Communication & Media check (`komunikasi` keyword) came before the Language & Humanities check (`bahasa` keyword) in the classifier. The category "Bahasa & Komunikasi" contains both keywords — order determined which matched first.
   - *Fix:* Reordered Language & Humanities check BEFORE Communication & Media check.
   - *Prevention:* When building keyword classifiers with overlapping terms, always test compound categories and document the ordering rationale with comments.

3. **Supabase column name `field_key` vs `field_key_id`**
   - *Symptom:* First batch of UPDATE statements failed with `column "field_key" of relation "stpm_courses" does not exist`.
   - *Root cause:* Django adds `_id` suffix to FK columns in the database. The Python attribute is `field_key`, but the actual DB column is `field_key_id`.
   - *Fix:* Changed all SQL to use `field_key_id`.
   - *Prevention:* Already captured in lessons.md — always check `class Meta: db_table` and FK column naming before writing raw SQL.

---

## Design Decisions

- **Deterministic over AI**: Chose keyword matching over Gemini classification because category data quality was high enough. This is cheaper ($0), faster, reproducible, and testable without API mocking.
- **Separate `_classify_spm_matching()` helper**: Rather than patching `classify_course()` to handle STPM's aggregate field values, created a clean separation. This avoids coupling STPM quirks into the SPM classifier.
- **Backwards-compatible `?field_key=` filter**: Added alongside existing `?field=` parameter so frontend can adopt in Sprint 4 without breaking current behaviour.

---

## Numbers

| Metric | Value |
|--------|-------|
| STPM courses classified | 1,113/1,113 |
| Taxonomy keys used | 29/37 |
| New tests | 61 |
| Total tests | 542 |
| Files created | 2 (classifier, SQL reference) |
| Files modified | 4 (serializers, views, urls, tests) |
| Tech debt resolved | TD-051 |
| Remaining tech debt | 3/52 |
