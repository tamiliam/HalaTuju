# Retrospective — v1.25.1 Merit Score Fix (2026-03-09)

## What Was Built

Hotfix for merit score mismatch: the grades page showed 68.88 but course cards showed 56.38 for the same student. Root cause: backend recalculated merit using a different subject grouping (5/3/1) than the frontend's correct UPU formula (4/2/2).

**Fix**: Frontend now sends its pre-computed `student_merit` to the backend via the eligibility payload. Backend uses it directly instead of recalculating.

## What Went Well

- Root cause identified quickly by comparing the two formulas side-by-side
- Simplest possible fix chosen: pass the value through rather than maintaining two formulas
- Backwards-compatible: backend falls back to old calculation if `student_merit` not provided
- No test regressions

## What Went Wrong

- This bug shipped with Sprint 20 (onboarding redesign) and wasn't caught for 2 weeks
- No test existed to verify frontend and backend merit scores match for the same input
- The backend `prepare_merit_inputs()` function silently reorganised grades into a different grouping without any documentation of why

## Design Decisions

- **Pass-through over fix-in-place**: Rather than fixing the backend formula to match, we chose to eliminate the duplicate calculation entirely. The frontend already has the correct value — no reason to recalculate.
- **Kept old code as fallback**: `prepare_merit_inputs()` and `calculate_merit_score()` still exist in `engine.py` for backwards compatibility (API consumers that don't send `student_merit`). Could be removed later.

## Numbers

- Files changed: 5
- Tests: 166 passing (unchanged), 9 pre-existing JWT failures
- Golden master: 8280 (unchanged)
- Deploy: backend rev 33, frontend rev 42
