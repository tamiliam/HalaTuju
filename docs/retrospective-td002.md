# Retrospective — TD-002 Sprint (2026-03-14)

## What Was Built

Eliminated frontend-backend calculation duplication by making the backend the single source of truth for all eligibility formulas. Three new stateless API endpoints replace 596 lines of duplicated frontend TypeScript.

**Endpoints added:**
- `POST /api/v1/calculate/merit/` — UPU merit score from grades
- `POST /api/v1/calculate/cgpa/` — STPM CGPA from grades
- `POST /api/v1/calculate/pathways/` — Pre-U pathway eligibility + fit scores

**Frontend files deleted:** `merit.ts` (63 lines), `stpm.ts` (22 lines), `pathways.ts` (511 lines)

**Tech debt closed:** TD-002, TD-015, TD-017

## What Went Well

- **Subagent-driven execution worked cleanly.** 12 tasks dispatched sequentially, each with focused scope. Fresh context per task prevented confusion. Total of ~10 subagent invocations (some tasks batched).
- **Design-first approach paid off.** The brainstorming session surfaced the `getPathwayFitScore()` gap (TD-017) before implementation began. Without it, we'd have ported pathways to API but left fit scoring frontend-only.
- **Snake-to-camelCase mapping was caught early.** Backend returns `track_id` but frontend uses `trackId`. Identified during plan review, handled in the API client function rather than requiring changes to every frontend page.
- **Zero formula risk.** Moving code, not changing it. Golden master tests unchanged. All existing tests still pass.
- **Clean deletion.** 596 lines removed with zero remaining imports. `npm run build` clean on first try.

## What Went Wrong

1. **Architecture map update was done by subagent without full file read, producing a separate commit.** The subagent updated ARCHITECTURE_MAP.md based on its own assessment rather than being included in sprint close. Root cause: dispatching a doc-update subagent independently instead of doing it during sprint close. Fix: always do doc updates as part of sprint close workflow, not as standalone subagent tasks.

## Design Decisions

- **Backend-only calculations (not shared test vectors).** User pushed for the long-term solution: backend owns formulas, frontend is display-only. This is more robust than shared test vectors because there's only one implementation to maintain.
- **Debounced API calls on grade pages.** 400ms debounce on keystroke-triggered calculations. Prevents API spam while keeping the live merit/CGPA display responsive.
- **Inline CGPA-to-percent on dashboard.** Rather than adding an API call for a trivial formula (`cgpa / 4 * 100`), inlined it as a one-liner. The CGPA value was already computed and stored during onboarding.

## Numbers

| Metric | Value |
|--------|-------|
| Tasks | 12 (all completed) |
| Commits | 12 (10 feature/refactor + 2 docs) |
| Backend tests | 344 passing (+12 new) |
| Frontend build | Clean |
| Lines deleted | 596 |
| Lines added (backend) | ~200 (views, pathways, tests) |
| Lines added (frontend) | ~80 (api.ts types + functions) |
| Net lines | -316 |
| Deploy count | 2 (backend + frontend) |
| Tech debt items resolved | 3 (TD-002, TD-015, TD-017) |
