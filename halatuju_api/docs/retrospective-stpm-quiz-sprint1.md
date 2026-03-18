# Retrospective — STPM Quiz Engine Sprint 1 (2026-03-18)

## What Was Built

Subject-seeded branching STPM quiz engine — a separate quiz for STPM students grounded in Holland's RIASEC, SCCT, SDT, and Super's Career Development Theory. The engine calculates a RIASEC seed from the student's STPM subjects, routes them to a Science/Arts/Mixed branch, generates grade-adaptive confidence questions using actual grades, and enforces cross-domain asymmetry (arts students can't see science-prerequisite options).

**Files created/modified:** 7 (2 new modules, 3 new test files, 2 modified files)

## What Went Well

- **Design doc as spec:** The detailed design document (`docs/plans/2026-03-18-stpm-quiz-design.md`) made implementation straightforward — every question, signal, and branching rule was already defined. Zero ambiguity during coding.
- **Clean separation from SPM quiz:** New files only — `stpm_quiz_data.py` and `stpm_quiz_engine.py` are completely independent of the existing SPM quiz. No risk of breaking existing functionality.
- **Test coverage:** 102 new tests covering seed calculation, branch routing, grade-adaptive Q4, cross-domain Q5 filtering, signal accumulation, API endpoints, and data integrity. All passed on first run.
- **No regressions:** 775 total backend tests pass. Golden masters unchanged (SPM=5319, STPM=2026).
- **3-endpoint API design:** Splitting questions/resolve/submit allows the frontend to progressively fetch questions as the student answers — no need to send all 35 questions upfront.

## What Went Wrong

Nothing significant. The sprint was clean because:
1. The design doc was thorough (no ambiguity to resolve)
2. No model changes were needed (data-only + engine + views)
3. The existing quiz codebase provided clear patterns to follow

## Design Decisions

1. **3 endpoints vs 1:** Chose questions → resolve → submit flow over a single monolithic endpoint. Rationale: the frontend needs Q3/Q4 *after* Q2 is answered (grade-adaptive, branch-dependent). A single endpoint would either send everything upfront (wasteful, confusing) or require the frontend to re-fetch.

2. **Trilingual text in data file, localised in engine:** Question prompts and option texts are stored as `{en, bm, ta}` dicts in `stpm_quiz_data.py`. The engine's `_localise_question()` function extracts the single language before returning to the API. This matches the existing SPM quiz pattern but adds language-dict support.

3. **Q4 threshold at B- (2.67):** Below B- triggers the "weak grade" confidence question. At or above B triggers the "strong grade" variant. B- itself is weak — this is deliberate because B- in STPM is marginal for competitive programmes.

4. **Science students who pick Business/Education in Q2 get arts Q3 variants:** Rather than creating separate Q3 variants, the engine routes science students who express interest in arts-side fields to the existing arts Q3 questions. This keeps the question pool DRY.

## Numbers

| Metric | Value |
|--------|-------|
| Files created | 5 |
| Files modified | 2 |
| New tests | 102 |
| Total backend tests | 775 |
| Test failures | 0 |
| Golden master SPM | 5319 (unchanged) |
| Golden master STPM | 2026 (unchanged) |
| Questions in data file | ~35 (20 unique IDs) |
| Languages | 3 (EN, BM, TA) |
| Signal taxonomy categories | 9 |
