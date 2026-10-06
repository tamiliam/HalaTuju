# Sprint 5 Retrospective — Quiz Frontend

**Date**: 2026-02-17
**Duration**: Single session
**Deliverable**: Interactive quiz page + ranked results on dashboard

## What Was Built

- `/quiz` page — 6-question interactive quiz with step navigation, progress bar, auto-advance on selection, Skip Quiz link
- Quiz API integration in `lib/api.ts` — `getQuizQuestions()`, `submitQuiz()`, `getRankedResults()` with full TypeScript types
- Dashboard "Take Quiz" CTA — gradient banner when quiz not yet taken
- Dashboard ranked results view — top 5 with rank badges and fit reason tags, "Other Eligible Courses" section for the rest
- Quiz completed banner with "Retake Quiz" link
- Signals stored in localStorage (`halatuju_quiz_signals`, `halatuju_signal_strength`)

## What Went Well

- **Backend APIs were ready**. Sprint 3 (quiz) and Sprint 4 (ranking) built clean endpoints with clear request/response contracts. Wiring the frontend was straightforward.
- **Clean build on first try**. No TypeScript errors, no build failures. The Next.js build passed with the new `/quiz` route immediately.
- **No backend changes needed**. Truly a frontend-only sprint — 104 backend tests stayed untouched and passing.
- **React Query made ranking integration simple**. Adding a second query that depends on eligibility data + quiz signals was a natural fit for React Query's `enabled` pattern.

## What Went Wrong

- Nothing significant. The sprint was clean.

## Design Decisions

1. **Quiz as separate page, not modal**: The quiz is a full `/quiz` page rather than a dashboard modal. This gives each question room to breathe and keeps the dashboard focused. The quiz redirects back to dashboard on completion.

2. **Auto-advance on selection**: When a user picks an option, the quiz auto-advances to the next question after 300ms. This reduces clicks and feels more interactive. Users can still navigate back via Previous button or step dots.

3. **localStorage for quiz signals**: Signals are stored client-side rather than in Supabase. This keeps the quiz anonymous-friendly (no auth required) and avoids a database write for every quiz completion. If the user is authenticated, signals could be synced to their profile in a future sprint.

4. **Conditional dashboard rendering**: The dashboard checks for `halatuju_quiz_signals` in localStorage. If present, it calls the ranking API and shows ranked results. If absent, it shows the original flat eligibility list with the Take Quiz CTA. This means both flows coexist cleanly.

5. **Top 5 vs rest split**: The ranking API returns `top_5` and `rest`. The dashboard renders these as distinct sections — top matches get rank badges and fit reason tags, while the rest are shown as standard course cards.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 104 | 104 |
| Golden master | 8280 | 8280 |
| Files created | — | 1 (quiz/page.tsx) |
| Files modified | — | 2 (api.ts, dashboard/page.tsx) |
| Frontend routes | 15 | 16 |
| Migrations | 0 | 0 |
| Deploys | 0 | 0 (pending) |
