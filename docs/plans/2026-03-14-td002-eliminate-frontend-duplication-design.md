# TD-002 + TD-017: Eliminate Frontend Calculation Duplication — Design

## Goal

Move all eligibility formulas and scoring logic to the backend. Frontend becomes display-only — it calls API endpoints instead of computing locally. Closes TD-002 (duplicated logic) and TD-017 (pre-U fit scoring frontend-only).

## Architecture

Backend owns every formula. Frontend calls lightweight API endpoints and displays results. The same pattern the rest of the app already follows.

### New API Endpoints

| Endpoint | Method | Input | Output | Replaces |
|----------|--------|-------|--------|----------|
| `/api/v1/calculate/merit/` | POST | `{grades, coq_score}` | `{academic_merit, final_merit}` | `merit.ts` |
| `/api/v1/calculate/cgpa/` | POST | `{stpm_grades}` | `{cgpa, merit_percent}` | `stpm.ts` |
| `/api/v1/calculate/pathways/` | POST | `{grades, coq_score, signals?}` | `{pathways: [{id, name, eligible, merit/mata_gred, fit_score}]}` | `pathways.ts` |

All endpoints are public (no auth required) — they're pure calculation, no user data stored.

### Frontend Changes

| Page | Current | After |
|------|---------|-------|
| `/onboarding/grades/` | Calls `calculateMeritScore()` locally on submit | Calls `/calculate/merit/` API |
| `/onboarding/stpm-grades/` | Calls `calculateStpmCgpa()` locally | Calls `/calculate/cgpa/` API |
| `/pathway/matric/` | Calls `checkAllPathways()` locally | Calls `/calculate/pathways/` API |
| `/pathway/stpm/` | Calls `checkAllPathways()` locally | Calls `/calculate/pathways/` API |
| `/dashboard/` | Calls `cgpaToMeritPercent()` locally | Uses value from `/calculate/cgpa/` (already fetched during onboarding, stored in localStorage) |

### Files Deleted

- `halatuju-web/src/lib/merit.ts` (63 lines)
- `halatuju-web/src/lib/stpm.ts` (22 lines)
- `halatuju-web/src/lib/pathways.ts` (511 lines)

Total: ~596 lines of duplicated frontend logic removed.

### Files Modified

**Backend (new endpoints):**
- `halatuju_api/apps/courses/views.py` — add 3 view classes
- `halatuju_api/apps/courses/urls.py` — add 3 URL patterns

**Backend (move getPathwayFitScore to backend):**
- `halatuju_api/apps/courses/pathways.py` — add `get_pathway_fit_score()` function (port from pathways.ts lines 326-490)

**Frontend (replace local calls with API calls):**
- `halatuju-web/src/app/onboarding/grades/page.tsx` — replace `calculateMeritScore()` with API call
- `halatuju-web/src/app/onboarding/stpm-grades/page.tsx` — replace `calculateStpmCgpa()` with API call
- `halatuju-web/src/app/pathway/matric/page.tsx` — replace `checkAllPathways()` with API call
- `halatuju-web/src/app/pathway/stpm/page.tsx` — replace `checkAllPathways()` with API call
- `halatuju-web/src/app/dashboard/page.tsx` — remove `cgpaToMeritPercent()` import, use stored value
- `halatuju-web/src/lib/api.ts` — add `calculateMerit()`, `calculateCgpa()`, `calculatePathways()` functions

### UX Handling

- Grades pages: call API on form submit (not on every keystroke). Merit/CGPA appears after submit, same as current flow.
- Pathway pages: call API on page load with grades from localStorage. Show loading skeleton while waiting.
- Debounce not needed since calls happen on submit/page-load, not live typing.

### What Stays the Same

- `engine.py` (golden master) — untouched
- `stpm_engine.py` — untouched (CGPA calculation already there)
- `pathways.py` — existing functions stay, `get_pathway_fit_score()` added
- All eligibility results, merit scores, pathway scores — identical outputs
- Subject key mapping — frontend still sends UI keys, serializer still maps (TD-013 separate)

### Testing

- Backend: add tests for 3 new endpoints (input/output contract)
- Backend: add tests for `get_pathway_fit_score()` (port existing frontend logic)
- Frontend: no new tests needed (deleted code = deleted test surface)
- Golden master: unchanged (these endpoints don't affect eligibility engine)

### Risk

- **Zero formula risk** — moving code, not changing it
- **Latency**: ~200ms per API call. Acceptable for submit-time / page-load calculations
- **Offline**: Students without internet can't calculate merit. But they already can't use the app offline (all data comes from API).

## Tech Debt Closed

| ID | Title | Status |
|----|-------|--------|
| TD-002 | Client-side eligibility logic duplicated | Closed |
| TD-017 | Pre-U fit scoring exists only on frontend | Closed |

## Out of Scope

- TD-013 (subject key naming split) — separate issue, lower risk
- TD-003 (zero frontend tests) — partially addressed by removing testable frontend logic
- TD-015 (frontend/backend merit may disagree) — eliminated by single source of truth
