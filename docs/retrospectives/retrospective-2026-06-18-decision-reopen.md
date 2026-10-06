# Retrospective — Reverse a recorded decision ("Reopen") + cockpit Q&A presentation (2026-06-18)

Migration `scholarship/0062` (migrate-first). Worked in worktree `.worktrees/sched` / `feat/interview-scheduling`.
Five owner-requested cockpit changes from a live-review pass; one (Reopen) is a real feature, four are presentation.

## What Was Built

1. **Reverse a recorded decision — "Reopen" (the consequential one).** The Decision panel's cosmetic "Edit" (which only
   unlocked the form in the browser) became **Reopen** with real backend consequences, super-only:
   - **Reopen** → holds the student's profile from the sponsor pool (`anon_published=False`), opens a `DecisionReopen`
     audit row attributed to the **assigned reviewer**, stamps `decision_reopened_at` (so the reopened state survives a
     reload), unlocks the panel + the reviewer dropdown, and shows a "held from sponsors" banner. A **reason is required**
     (a reopen asserts a reviewer error).
   - **Cancel reopen** → restores the prior published state exactly (re-publishes iff it was published before), re-locks,
     closes the audit row with `resulted_in_change=False` (no correction).
   - **Re-save** (Approve/Decline via the existing record-verdict / reject paths) → closes the audit row with
     `resulted_in_change=True`, regenerates + republishes per the new decision (decline stays unpublished).
   - **Corrections count (model B):** a reopen counts against the reviewer **only when it leads to a saved change** —
     an exploratory reopen that's cancelled does not. The count is `COUNT(resulted_in_change=True)` over the audit log
     (derived, never a bare counter), surfaced internally in the assign panel — never on a sponsor/student surface.
   - New `decision_reopened_at` column + `decision_reopens` table (migration `0062`); service module `reopen.py`;
     endpoints `reopen-decision/` + `cancel-reopen/`.

2. **Assign-reviewer panel** — heading "Reviewer assigned" + "Reviewer: {name}" when assigned; the dropdown **locks**
   once a decision is recorded and only unlocks on Reopen (it's a finished case). Shows the reviewer's corrections tally.

3. **Interview Stage record → Check-2 card style** — each answered question renders with a green ✓ tick + bold
   "Question:" + the finding under a "Reviewer's finding" header (label above the box, not inside).

4. **Removed the redundant top "Submitted" pill** on the Interview Stage (the "Submitted on …" line at the foot stays).

5. **"Conclusion" (Decision) and "Findings" (Interview) labels → headers above their boxes** (presentation, as before).

## What Went Well
- **Investigated the publish pipeline before designing.** An Explore pass mapped exactly how a profile reaches the pool
  (`anon_published` + active share consent, `pool.eligible_pool_queryset`) and that the existing "Edit" did nothing to
  it — so the design wired reopen to the real gate instead of duplicating publish logic.
- **Reused the existing finalise/publish path** for re-publish-on-resave rather than re-implementing it; the reopen
  service only opens/closes the audit row + holds/restores the publish flag.
- **Migrate-first, additive** (new nullable column + new table) — `makemigrations --check` clean, applied to prod ahead
  of the code push so old code kept working.

## What Went Wrong
- **The counting rule was genuinely ambiguous** — "we reopen only when there's an error" points at counting every
  reopen (A), but that would penalise a reviewer for an exploratory reopen the super then cancels. *Root cause:* the
  metric attributes blame, so the trigger point matters. *Fix (process):* surfaced the A-vs-B fork to the owner with a
  recommendation rather than guessing; the owner chose B (count only on a saved change). When a feature writes a
  per-person quality metric, confirm the increment trigger with the owner before coding it.

## Design Decisions (see docs/decisions.md)
- Reopen reverses a decision by holding the profile from the pool + an audit row, restoring on cancel and re-publishing
  on re-save; corrections counted on saved-change only (model B); count derived from the audit log, not a bare counter.

## Numbers
- Tests: **2488 backend pytest** (1324 scholarship incl. +10 new in `test_decision_reopen.py`; 1164 courses/reports)
  + **327 jest**. i18n en/ms/ta parity + the `admin.scholarship` orphan guardrail green. `next build` clean.
- Migration `scholarship/0062` (1 nullable column + 1 new table; migrate-first via Supabase MCP; RLS on the new table).
- No new flag — Reopen is a super-only cockpit action; the presentation changes are unconditional.
