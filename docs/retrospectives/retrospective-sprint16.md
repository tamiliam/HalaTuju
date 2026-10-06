# Sprint 16 Retrospective — Registration Gate

**Date**: 2026-02-22
**Duration**: 2 sessions (first hit context limit mid-frontend, second completed + pushed)

## What Was Built

- `AuthProvider` + `useAuth()` hook (`lib/auth-context.tsx`) — wraps Supabase session, provides token, auth state, and auth gate controls
- `AuthGateModal` component (`components/AuthGateModal.tsx`) — 3-step inline modal: login (phone OTP + Google OAuth) → OTP verification → profile (name + school)
- `ProfileSyncView` — POST `/api/v1/profile/sync/` bulk-pushes localStorage data (grades, gender, quiz signals, name, school) to backend after first login
- `name` + `school` CharField on `StudentProfile` model (migration 0008)
- Dashboard gating: save/report/quiz CTAs always visible, gate on auth when clicked
- Quiz page gating: inline sign-in prompt for unauthenticated visitors
- Resume actions after auth: localStorage-based handoff for save/report actions
- Google OAuth edge case: pending action stored before redirect, detected on mount
- 21 i18n keys × 3 locales (EN/BM/TA)
- 4 new backend tests (profile sync CRUD + auth), 6 existing tests updated

## What Went Well

- **AuthContext pattern worked cleanly**: Following the existing `I18nProvider` pattern for `AuthProvider` meant the architecture was consistent. The `useAuth()` hook made gating trivial — one-line checks across dashboard and quiz.
- **Inline modal UX**: Keeping login inside a modal (not a redirect to `/login`) preserved user context. Students see exactly where they were when they dismiss the modal.
- **Resume action pattern**: Using localStorage (`halatuju_resume_action`) to resume save/report after auth avoided stale closure issues. The dashboard picks up the pending action via useEffect when token becomes available.
- **Google OAuth handled gracefully**: The `PENDING_ACTION_KEY` in localStorage bridges the OAuth redirect gap. AuthProvider detects it on mount and re-opens the modal at the profile step.
- **Backend was minimal**: Only 2 new files (migration + sync view), ~50 lines of backend code. The heavy lifting was all frontend.

## What Went Wrong

- **Context exhaustion**: The sprint spanned two sessions because the first session ran out of context partway through the frontend work. Backend was done but AuthGateModal, dashboard gating, and quiz gating had to be completed in a continuation session.
- **Set spread TypeScript error**: Used `new Set([...prev, courseId])` which failed because the tsconfig target doesn't support Set iteration with the spread operator. Had to refactor to explicit `Set.add()`. This is a known TypeScript gotcha that should be remembered.
- **File-not-read error**: The Write tool requires reading the file first in the same conversation turn. Two files failed on first write attempt and had to be read then rewritten.
- **`nul` artifact**: A Windows `nul` file from a previous session is still untracked in the repo. Needs cleanup.

## Design Decisions

1. **Modal, not page redirect**: Inline auth in a modal keeps the student on their current page. Dismissing returns them exactly where they were.
2. **Three-step modal flow**: Login → OTP → Profile. The profile step (name + school) appears after auth to collect data while the student is engaged, without blocking the initial sign-in.
3. **Always-visible CTAs**: Save, report, and quiz buttons show for all users. Gating happens on click, not on render. This lets guest users discover features before being asked to sign in.
4. **ProfileSyncView as bulk endpoint**: One POST pushes everything (grades, profile, quiz signals, name, school) instead of separate calls. Reduces round trips and simplifies the frontend.
5. **Quiz page inline prompt (not modal)**: For the quiz page specifically, showing a full-page sign-in prompt (not a modal overlay) made more sense since the quiz is the entire page content.

## Numbers

| Metric | Value |
|--------|-------|
| Tests | 166 (+10 from Sprint 15's 156) |
| Golden master | 8280 (unchanged) |
| i18n keys added | 21 × 3 locales = 63 |
| New endpoint | 1 (POST /api/v1/profile/sync/) |
| New migration | 1 (0008) |
| New components | 2 (AuthGateModal, AuthProvider) |
| Files modified | ~14 |
| Sessions | 2 (context limit in first) |
