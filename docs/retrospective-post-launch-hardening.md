# Retrospective — Post-Launch Hardening Sprint

**Date:** 2026-03-17
**Duration:** Single session (continuation from identity verification sprint)

## What Was Built

1. **SPM merit subject grouping fix** — `prepare_merit_inputs()` was splitting subjects 5+3+1 (5 core, 3 stream, 1 elective) instead of the correct UPU formula 4+2+2 (4 core, 2 stream, 2 elective). Fixed and documented.
2. **Merit formula documentation** — All 4 formulas (SPM UPU, Matric, STPM mata gred, STPM CGPA) now have "DO NOT CHANGE" documentation blocks with full formula breakdowns in the source code.
3. **Dashboard TOP MATCHES fix** — Backend was splitting into top_5/rest globally before frontend filtered by pathway. Now returns a single ranked list; frontend filters first, then takes top 3.
4. **Rate limiting** — Email verification endpoint throttled to 3 requests/hour per profile.
5. **SPM_CODE_MAP expansion** — From 13 to 121 entries, covering all SPM subject codes for STPM prerequisite matching.
6. **NRIC validation hardening** — Date portion, age 15-23, and state code validation.
7. **Mobile layout fixes** — Header and dashboard card spacing on mobile.
8. **STPM MUET float support** — 65 courses with fractional MUET bands now handled.
9. **IC/verify-email i18n** — Trilingual support for two previously hardcoded pages.

## What Went Well

- **Formula documentation prevents future mistakes.** The matric formula was almost incorrectly modified (grade scale changed from A+=25 to A+=10, subject count from 4 to 10). The attempt was immediately caught and reverted. The "DO NOT CHANGE" blocks now make the intent explicit.
- **Ranking fix was clean.** Changing from top_5/rest to a single ranked list simplified both backend and frontend code (net -24 lines). Frontend now has full control over display logic.
- **Test coverage caught the merit fix.** The existing test expected 90.0 for all-A grades; the corrected formula gives 80.0. The test failure flagged the issue immediately.

## What Went Wrong

1. **Matric formula was nearly broken by pattern-matching.**
   - *Symptom:* When asked to "do the same for matric" (fix merit), the AI changed the matric grade scale and subject count — both of which were already correct.
   - *Root cause:* Applied the same fix pattern (change subject grouping) without verifying the matric formula was actually wrong. The SPM fix was about grouping; the matric system uses a completely different structure.
   - *System change:* Added "DO NOT CHANGE" documentation blocks with explicit formulas to all 4 sacred formula locations. Future sessions must read and respect these before touching any formula code.

2. **Ranking split was a design flaw from the start.**
   - *Symptom:* Dashboard showed fewer than 3 TOP MATCHES cards when filtering by pathway.
   - *Root cause:* The backend decided the display split (top 6 vs rest) when it should only rank. Display decisions belong in the frontend.
   - *System change:* Backend now returns a single sorted list. Frontend applies filters then splits. This is the correct separation of concerns.

## Design Decisions

- **Keep merit formulas documented in-code, not in a separate doc.** The formulas live in 3 files (engine.py, pathways.py, stpm_engine.py). Consolidating them would require a new file that could drift from the actual implementations. In-code documentation with "DO NOT CHANGE" headers is more reliable.
- **Single ranked list over configurable split size.** Could have made the backend accept a `top_n` parameter, but that adds complexity for no benefit. The frontend knows its own layout requirements.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 645 | 654 |
| Frontend tests | 17 | 17 |
| SPM golden master | 5319 | 5319 |
| STPM golden master | 1976 | 2026 |
| Commits | 0 | 9 |
