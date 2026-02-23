# Sprint 20 Retrospective — Onboarding Redesign + Merit Calculator

**Date**: 2026-02-23
**Branch**: `feature/v1.1-stream-logic`
**Versions**: v1.22.0, v1.22.1

## What Was Built

### Onboarding Redesign (v1.22.0)
- New `/onboarding/exam-type` page — SPM (active) + STPM (coming soon)
- Merged stream selection into grades page (compact pill buttons)
- Core subjects: button grid with green checkmark, 5+5 mobile layout
- Stream/elective subjects: compact dropdown + grade badge + remove
- Profile page: single compact card (Negeri, Nationality, Jantina, Keperluan Khas)
- ProgressStepper component across all 3 screens
- Deleted old `/onboarding/stream` page

### Merit Calculator + CoQ (v1.22.1)
- Co-curricular score input (0-10, decimal like 5.50, 7.85) on profile page
- Live merit score panel on grades page (Academic /90 + CoQ /10 = Total /100)
- Client-side `lib/merit.ts` — TypeScript port of `engine.py` formula
- Backend now accepts `coq_score` from request (was hardcoded 5.0)
- Fixed stream subject pre-population bug on first visit

## What Went Well

1. **Design decisions document** — Having Sprint 20 design decisions pre-confirmed from the previous session eliminated all back-and-forth. We went straight to building.
2. **Clean build on first try** — Both v1.22.0 and v1.22.1 built with 0 errors on first attempt.
3. **Faithful merit port** — Porting `engine.py` to TypeScript was straightforward. The formula is pure arithmetic, no external dependencies.
4. **Backward-compatible API** — `coq_score` defaults to 5.0 if not sent, so existing clients (including production) are unaffected.

## What Went Wrong

1. **Stream subject pre-population bug** — The `useEffect` loaded saved aliran from localStorage but didn't set defaults from the stream pool on first visit. First-time users saw empty stream subject dropdowns. Caught during review, not by testing.
2. **i18n interpolation assumption** — Initially assumed `t()` supported interpolation (it doesn't). Had to use separate keys for the progress stepper. This was caught from Sprint 20 part 1.
3. **Git push auth timeout** — `git push` hung waiting for authentication in the CLI environment. Had to ask user to push manually.
4. **Roadmap drift** — The master roadmap (Sprints 18-20) was stale — actual sprints diverged significantly from planned content. Sprints 18-20 in the roadmap said "i18n, filters, cleanup" but we actually did "header/footer, images, onboarding redesign".

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| CoQ as direct number input, not proxy selector | User corrected: "The students actually know their coq scores" — no need for a 4-level proxy |
| CoQ on profile page, not grades page | CoQ is not a grade — it's a profile attribute. Keeps grades page focused on SPM results |
| Merit panel on grades page, not a separate screen | Live feedback as grades are entered. Academic merit updates in real time |
| Client-side merit calculation | Pure arithmetic, no API call needed. Enables instant feedback |
| Merit formula faithfully ported (including C+ exclusion) | Engine is golden master — port must be exact, even if logic seems odd |

## Numbers

| Metric | Value |
|--------|-------|
| Files created | 2 (merit.ts, exam-type page) |
| Files modified | 11 |
| Files deleted | 1 (old stream page) |
| Lines added | ~770 (across both commits) |
| Lines deleted | ~350 |
| Frontend build | 20 routes, 0 errors |
| Backend tests | 142 pass (golden master included), 13 auth failures (pre-existing env issue) |
| Translation keys added | ~21 (across en, ms, ta) |
| Deploys | 1 (v1.22.0), v1.22.1 pending push |
