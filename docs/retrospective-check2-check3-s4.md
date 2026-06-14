# Retrospective — Check-2 / Interview-Stage redesign, Sprint 4 + feature close

**Date:** 2026-06-14 · **Feature:** COMPLETE & LIVE · shipped `f5243a7` → `762b358` on `main`.

## What Was Built (S4 + 3 review rounds)
- **Carry-over:** the Interview Stage agenda lists still-open Outstanding queries as "ask verbally" talking points.
- **Querying lock:** `services.querying_locked()` (status ≥ interviewed OR a submitted interview session) blocks the
  officer raise / Delete / reopen endpoints and the student resolve endpoint; the cockpit hides the controls behind a
  read-only note. Decision time = no more queries/documents.
- **Submit → final profile:** `submit_interview` auto-refines the draft into the final polished profile, gated behind the
  OFF `CHECK2_AUTO_GENERATE` flag, idempotent (skips with no draft / an existing final), best-effort (never blocks submit).
- **Review refinements (live cockpit):** show the actual question (`titleSourceFor`) with inline tags; prominent status
  icons; auto-accept answered queries (no buttons); single Delete on unanswered; merged the request box into the Check-2
  box (two roles); removed the misleading per-item "email the student" path.

## What Went Well
- **Reuse over rebuild.** S3's relocation was a no-op (layout already matched); the auto-draft/auto-finalise reused the
  existing `generate_ready_profile` / `refine_sponsor_profile` + the `CHECK2_AUTO_GENERATE` flag; the "actual question"
  reused `titleSourceFor` — the exact source the student's Action Centre already uses. Little net-new code, low risk.
- **Ship-dark discipline.** Every billable Gemini path (handoff draft, submit finalise) is behind the OFF flag, so the
  whole feature deployed with zero new billable calls; enabling is a one-env-var owner decision.
- **Branch-accumulate, deploy-once intent.** All 4 sprints accumulated on one branch; the merge-to-main happened once the
  feature was whole (then 2 review-round web deploys).

## What Went Wrong
- **Local authenticated smoke wasn't possible — surfaced late.** Symptom: at "test it locally", the worktree had no
  backend `.env` (DB/Supabase), so an authenticated cockpit couldn't run. Root cause: secrets correctly live only in
  Cloud Run, not the repo — I didn't check feasibility before promising a local smoke. Fix: for any "test locally"
  on this stack, check for `halatuju_api/.env` up front; if absent, the real interactive test is a live test-account
  smoke post-deploy (lesson #96) — say so immediately rather than at the testing step.
- **Three deploys for one feature (over the ≤2 guideline).** Symptom: f5243a7 (feature) + 03d0d2f + 762b358 (two review
  rounds). Root cause: the owner reviewed the live cockpit and requested UX changes in rounds — legitimate iteration, but
  each round was a separate web deploy. Mitigation applied: flagged the budget before the 3rd deploy and let the owner
  choose. Lesson: for a "review on live then refine" loop, set the expectation up front that review rounds each cost a
  web deploy, and offer to batch.
- **`main` moved under me three times mid-close** (the course-data agent merging). No conflicts, but each required a
  `git merge origin/main` + full re-verify before the ff-push. Handled cleanly; reinforces the worktree + re-verify
  discipline when sharing `main` with another agent.

## Design Decisions
See `docs/decisions.md` (one querying channel; auto-accept answered + officer-Delete; lock-at-conclusion; ship-dark gating).

## Numbers
1209 scholarship pytest · jest 306 · `next build` clean · i18n parity 2925×3 · 3 web deploys · 0 migrations.
