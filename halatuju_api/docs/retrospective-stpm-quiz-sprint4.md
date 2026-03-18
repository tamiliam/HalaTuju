# Retrospective — STPM Quiz Engine Sprint 4 (2026-03-18)

## What Was Built

Frontend STPM quiz page with branching UI, wired to the 3 backend API endpoints from Sprint 1. Card-based question interface (same pattern as SPM quiz) with dynamic Q3/Q4 resolution after Q2 is answered. Dashboard updated to show quiz-informed result framing (confirmatory/guided/discovery headings) and route quiz CTA to `/stpm/quiz`. Trilingual labels added (EN/BM/TA).

**Files created:** 1 (`src/app/stpm/quiz/page.tsx`)
**Files modified:** 7 (api.ts, storage.ts, subjects.ts, dashboard/page.tsx, en.json, ms.json, ta.json)

## What Went Well

- **Backend was ready:** All 3 STPM quiz API endpoints were built and tested in Sprint 1 (102 tests). The ranking formula with framing was done in Sprint 3. Frontend just needed to wire to existing endpoints — no backend changes needed.
- **SPM quiz as template:** The existing SPM quiz page (`/quiz/page.tsx`) provided a proven pattern for card-based UI, progress tracking, auto-advance, and auth gating. The STPM quiz follows the same UX patterns with additions for branching.
- **Clean build on first attempt:** Next.js compiled successfully with no TypeScript errors on the first build.
- **Separation of concerns:** STPM quiz signals stored under `KEY_STPM_QUIZ_SIGNALS` (not reusing `KEY_QUIZ_SIGNALS`), preventing SPM/STPM signal contamination.

## What Went Wrong

Nothing. The sprint was clean because:
1. Backend API endpoints were already tested and stable (Sprint 1)
2. Frontend patterns were well-established from the SPM quiz
3. No model changes or migrations needed
4. The subject-to-API key mapping was straightforward (1:1 from design doc)

## Design Decisions

1. **Separate storage key for STPM quiz signals:** Used `KEY_STPM_QUIZ_SIGNALS` instead of reusing `KEY_QUIZ_SIGNALS`. This prevents a student who switches between SPM and STPM from having their SPM quiz signals incorrectly fed into STPM ranking (different signal taxonomies). The dashboard falls back to `KEY_QUIZ_SIGNALS` only if no STPM-specific signals exist.

2. **Dynamic Q3/Q4 resolution via API call:** After Q2 is answered, the frontend calls `/stpm/quiz/resolve/` to get Q3 and Q4 questions (which depend on the Q2 field choice and the student's actual grades). This adds one extra API call mid-quiz but avoids shipping all Q3 variants to the frontend (35 question variants would bloat the initial payload).

3. **Adaptive grid layout:** Questions with 3 or fewer options use a single-column layout (horizontal cards); questions with 4+ options use the 2x2 grid. This matches the design doc's principle of "one question per screen" while keeping the UI clean for questions that have only 3 choices.

4. **No quiz-to-onboarding redirect:** The STPM grades onboarding flow still routes to `/onboarding/profile` → dashboard. The quiz is accessed from the dashboard CTA, matching the SPM quiz pattern (quiz is optional, not required).

## Numbers

| Metric | Value |
|--------|-------|
| Files created | 1 |
| Files modified | 7 |
| Frontend build | Clean (0 errors) |
| Backend tests | 888 (unchanged) |
| Frontend tests | 17 (unchanged) |
| i18n keys added | 7 per language (21 total) |
| API functions added | 3 |
| Storage keys added | 2 |
| Subject mappings | 20 |
