# Retrospective — STPM Quiz Engine Sprint 2 (2026-03-18)

## What Was Built

Data enrichment for quiz-informed STPM ranking. Three new fields on StpmCourse (`riasec_type`, `difficulty_level`, `efficacy_domain`) and one on FieldTaxonomy (`riasec_primary`). A deterministic management command (`enrich_stpm_riasec`) classifies courses based on their `field_key` using mappings derived from the design document's RIASEC-to-FieldTaxonomy table (Section 10).

**Files created/modified:** 4 (1 migration, 1 command, 1 test file, 1 modified model)

## What Went Well

- **Design doc as single source of truth:** The RIASEC → field_key mapping in Section 10 of the design doc was directly invertible to field_key → RIASEC. No guesswork needed for the classifier.
- **Deterministic classification:** No AI/Gemini needed. Every field_key maps to exactly one RIASEC type, difficulty level, and efficacy domain. 37/37 leaf field_keys covered. Only `umum` (catch-all) is intentionally unmapped.
- **Mapping consistency tests:** The test suite enforces that all three maps (RIASEC, difficulty, efficacy) cover the exact same set of field_keys. If someone adds a field_key to one map but forgets another, the test fails.
- **No regressions:** 829 total backend tests pass. Golden masters unchanged (SPM=5319, STPM=2026).
- **Fast sprint:** Model changes + migration + command + 40 tests completed in one pass.

## What Went Wrong

Nothing significant. One minor issue:

1. **Local SQLite has stale field_key data.** The dry run showed only 1/1,113 courses would be updated because local SQLite has 1,112 courses with `field_key='umum'` — the real field_key backfill was done directly in Supabase. Root cause: local DB doesn't stay in sync with Supabase after direct SQL backfills. Fix: this is a known limitation (not worth syncing), but the command must be run against Supabase (`DATABASE_URL` pointed at production) to classify the full 1,113 courses. Noted in the Next Sprint section of CLAUDE.md.

## Design Decisions

1. **Deterministic over AI classification:** The field_key → RIASEC mapping is fully deterministic because the design doc already defines the relationship. AI classification (mentioned in the design doc) is unnecessary — every STPM course already has a `field_key`, and every `field_key` maps to exactly one RIASEC type. This is simpler, cheaper, and 100% reproducible.

2. **Three separate maps in one command:** RIASEC, difficulty, and efficacy are classified together in a single management command rather than three separate ones. Rationale: they share the same input (`field_key`) and the same execution pattern (iterate courses, look up mapping, save). Splitting would triple the boilerplate.

3. **Parent FieldTaxonomy groups don't get riasec_primary:** The 10 top-level groups (engineering, it, business, etc.) are intentionally left without RIASEC mapping. Courses link to leaf nodes, not groups, so the parent mapping would never be used.

4. **`umum` intentionally unmapped:** The catch-all field_key has no meaningful RIASEC type. Courses with `field_key='umum'` will get no RIASEC bonus in ranking — this is correct behaviour.

## Numbers

| Metric | Value |
|--------|-------|
| Files created | 3 |
| Files modified | 1 |
| New tests | 40 |
| Total backend tests | 829 |
| Test failures | 0 |
| Golden master SPM | 5319 (unchanged) |
| Golden master STPM | 2026 (unchanged) |
| Field keys mapped | 37 (all except umum) |
| RIASEC types used | 6 (R, I, A, S, E, C) |
| Difficulty levels | 3 (low, moderate, high) |
| Efficacy domains | 4 (quantitative, scientific, verbal, practical) |
| FieldTaxonomy entries enriched | 28 (leaf nodes) |
