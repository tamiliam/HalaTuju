# Retrospective — v1.32.2 (Unified Pre-U Scoring & Pathway Fixes)

**Date**: 2026-03-11
**Duration**: ~1 session

## What Was Built

1. **Unified pre-U scoring system** — Asasi, Matric, and STPM all use the same scoring philosophy: prestige bonus + academic bonus + field preference + signal adjustment. Replaces ad-hoc generic course-tag matching for Asasi.
2. **STPM progress bar fix** — Full 3-27 mata gred range with raw value display ("You: 4 | Need: 18") instead of confusing 0-100 conversion.
3. **STPM Social Science "Fair" label** — 13-18 range changed from "Low" to "Fair" after reading the STPM guidebook and identifying the Autonomi Pengetua appeal process.
4. **Pathway card link fix** — Cards now pass track/stream query params instead of defaulting to Science.
5. **Non-auth pathway cards** — Matric/STPM synthetic entries now appear in the flat course list (without quiz).

## What Went Well

- **Design doc first**: Writing the pre-U scoring design doc (`docs/plans/2026-03-11-pre-u-scoring-design.md`) before coding helped catch threshold inconsistencies early.
- **User domain knowledge**: Reading the STPM guidebook PDF (68 pages) revealed the appeal process — a key insight for the "Fair" label that wouldn't have been found from code alone.
- **Parallel frontend/backend**: Frontend pathway scoring (pathways.ts) and backend Asasi scoring (ranking_engine.py) were implemented in parallel with consistent logic.

## What Went Wrong

- **Two rendering paths**: Dashboard has two code paths (ranked with quiz, flat without quiz) that both need synthetic pathway entries. The flat path was missed initially, causing cards to disappear for non-authenticated users.
- **Multiple user corrections needed**: Academic bonus thresholds, display values, and chance labels all needed user correction — should have asked for specifications upfront rather than guessing.
- **7 frontend deploys**: Too many incremental deploys. Could have batched changes better.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Prestige order: Asasi > Matric > STPM | Reflects real-world selectivity and competition for places |
| Asasi prestige = 12 (vs Matric 8, STPM 5) | Asasi is the most competitive pre-U pathway with merit cutoffs 77-95 |
| Raw mata gred display | Users found 0-100 converted values confusing — "4" is more meaningful than "96" |
| "Fair" instead of "Low" for SocSci 13-18 | Autonomi Pengetua appeal process means these students have a real chance |
| Separate `displayStudent`/`displayCutoff` props | Allows progress bar to use normalised values while showing raw values in text |

## Numbers

- **Files changed**: 9 (7 frontend, 1 backend, 1 design doc)
- **Lines**: +420, -141
- **Deploys**: 7 frontend, 1 backend
- **Tests**: 212 collected, 203 passing (unchanged)
- **Golden master**: 8245 (unchanged)
