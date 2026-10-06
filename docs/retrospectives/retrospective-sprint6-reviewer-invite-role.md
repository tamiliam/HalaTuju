# Retrospective — B40 Phase E/F Sprint 6: Reviewer invite role selector (F5)

**Date:** 2026-06-09
**Branch:** `main` (held local, not pushed — deploy owner-gated, batched for go-live)
**Migration:** none (the `PartnerAdmin.role` field already existed from Phase C)

## What Was Built

A super admin now sets the new admin's role at invite time, and the role is visible in the admin list.

- **`AdminInviteView`** accepts `role` (`super`/`reviewer`/`viewer`); unspecified or invalid → `reviewer` (the safe
  workhorse default). When `role=super`, the legacy `is_super_admin` flag is set in lockstep (several call sites still
  gate on it directly). Response echoes the chosen `role`.
- **`AdminListView`** returns each admin's effective role (`'super' if a.is_super else a.role`).
- **`/admin/invite`** gains a role `<select>` (reviewer default) with a one-line hint per role; the admin-list table
  gains a colour-coded role badge column (purple/blue/grey). Trilingual `admin.role.*` + `admin.roleHint.*`.

## What Went Well

- **Zero schema churn.** The role model + `has_role()` bridge already existed (Phase C), so F5 was pure wiring —
  one request field on the way in, one serialized field on the way out, plus a select + badge on the FE.
- **Tested the real endpoint, not just existence.** Replaced the existence-only invite test with HTTP tests (JWT +
  APIClient) that mock the Supabase invite call and assert role-on-create, the super legacy-flag lockstep, the
  invalid-role fallback, the non-super 403, and the list serialization.
- **Concurrency-safe under a parallel agent.** With another agent on the same tree, I checked `git status` (only my
  files present, shared docs clean) and committed with explicit paths — never `git add -A`.

## What Went Wrong

- **Nothing of note.** The one judgement call was scope: the roadmap's secondary "prompt reviewer-profile completion
  on first sign-in" was deferred (logged as TD-099) to keep the sprint small as the roadmap labelled it — a conscious
  cut, not a miss.

## Numbers

- **Backend:** 1936 pytest (892 scholarship + 1044 courses/reports; +7 new) green; no migration.
- **Frontend:** `next build` clean (`/admin/invite` 4.44 kB); 276 jest green (page is render-only).
- **i18n:** parity 2333 × en/ms/ta (+8: `roleLabel`, `roleHeader`, 3 `role.*`, 3 `roleHint.*`).
- **Files touched:** 7 (2 BE incl. test; 5 FE: api-client + page + 3 message files).
- **Deploys:** 0 (held; owner-gated batch). **Carried:** TD-099 (first-sign-in profile-completion nudge).
