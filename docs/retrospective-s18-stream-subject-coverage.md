# Retrospective — S18: SPM Stream Subject Coverage (2026-05-29)

## What Was Built

A user reported that the SPM apply-form stream dropdowns (the "stream subjects" step, which carries 30% merit weight) offered far fewer subjects than the official SPM list. Investigation showed:

- The Arts stream pool listed **9** subjects; the official non-Islamic list has **38**. `SUBJECT_NAMES` already carried labels for ~26 of the missing ones — they were simply never added to the selectable pool.
- The Technical stream pool listed **8**; the official Science-Technology-Vocational grouping has **16**.
- The backend merit engine kept its **own** hardcoded copy of these pools, used to compute the 30% stream weight (Sec2). A subject selectable in the dropdown but absent from the backend pool would silently score on the 10% elective weight (Sec3) instead.

Delivered:
- `subjects.ts`: model change `category` (single) → `streams` (list), so a subject can sit in multiple stream pools while staying electable. Arts 9→38, Technical 8→16. Two new keys (`bahasa_punjabi`, `bible_knowledge`). `Multimedia` moved to elective-only. Derived export names/shapes preserved → zero page edits.
- `engine.py`: `ARTS_POOL`/`TECHNICAL_POOL` expanded to mirror the frontend exactly, lifted to module-level constants for testability, with a comment linking the two definitions.
- Tests: `subjects.test.ts` (12) and `test_merit_pools.py` (7).

## What Went Well

- **The mechanical grep (lessons L24) paid off before any code.** It proved the two consuming pages only use the *derived* exports, never `.category` directly — so the model change was contained entirely to `subjects.ts` with no page edits. The file list in the plan was accurate.
- **The golden master prediction held.** Reasoned up front that the new keys aren't held by the 50 baseline students and that the science/technical pool overlap resolves the tie to Science by ordering (so pure-science merit is identical), then *verified* with the 5319 baseline rather than assuming.
- Single deploy-worth of changes, under the file budget, first-try green on the full suite.

## What Went Wrong

1. **A new test used a fragile heuristic that false-positived.** The first version of the "every subject has a label" test asserted `getSubjectName(id,'en') !== humanise(id)`. `bible_knowledge` resolves to "Bible Knowledge", which is *identical* to its humanised fallback — so the test failed even though the label exists.
   - *Root cause:* I tested label presence indirectly (via a value that can coincide with the fallback) instead of directly (key membership).
   - *Fix:* Exported `SUBJECT_NAMES` and asserted `SUBJECT_NAMES[id]` is defined — the precise property. Caught on the first local run, cost ~one edit.

2. **Briefly created a duplicate label key.** Added `produksi_seni_persembahan` before noticing an existing `produksi_seni` covered the same source subject; removed it and relabelled the existing key.
   - *Root cause:* Didn't scan `SUBJECT_NAMES` for an existing near-match before adding.
   - *Fix (procedural):* When adding a label key, grep `SUBJECT_NAMES` for the BM stem first. No system change warranted beyond noting it.

## Design Decisions

- **Multi-stream subject model + mirrored backend pools** (logged in `decisions.md`). Chose a `streams` list over single-category + overlap-map or cross-language codegen. The FE/BE pool duplication is accepted debt (TD-063), mitigated by a linking comment + paired count tests.

## Numbers

- Backend: **1231** pytest (1224 + 7 new), golden master **5319** unchanged, STPM golden master untouched.
- Frontend: **154** jest (+12 new), `next build` clean (exit 0).
- Files touched: `subjects.ts`, `engine.py`, 2 new test files, CHANGELOG, decisions, lessons, technical-debt, this retrospective, CLAUDE.md. No migration, no backfill.
- Arts pool 9→38, Technical pool 8→16.
