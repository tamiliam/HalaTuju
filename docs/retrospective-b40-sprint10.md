# B40 Redesign — Sprint 10 Retrospective (2026-05-24)

The second half of the apply form — **My Plans + My Support** + verifying the post-submit "received" screen.
Frontend only, branch `feature/b40-redesign`, not deployed.

## What Was Built
- **My Plans**: intends-tertiary gate checkbox; pathways-considering multi-select chips; UPU/destination radio with
  an inline amber note when IPTS is picked; field-of-study dropdown (field taxonomy); **top-3 course choices from the
  student's saved courses** (ranked by tap order, max 3, friendly empty-state); other-scholarships chips + free text.
- **My Support**: two optional help radios (Yes/No/Not sure), "anything else" free text, required consent.
- `scholarship.ts` plans/support form state + payload (`top_choices` ranked by array order) + option constants;
  apply page fetches saved courses (exam-type aware) + field taxonomy on mount. EN/MS/TA i18n (35 keys).
- Replaced the single `intended_pathway` select with `pathways_considered` (multi) and `notes` with `anything_else`;
  kept `intends_tertiary_2026` (engine hard gate) as an explicit checkbox.

## What Went Well
- **The backend was already done.** S7's "add every intake field up front" meant `ApplicationCreateSerializer`
  already accepted all nine plans/support fields — S10 needed **zero backend changes, no migration, no backend test
  edits**. The upfront-schema bet paid off cleanly.
- **Top-3 from saved courses** (the user's call) kept this to one session: a single `getSavedCourses` call instead of
  mirroring the dashboard's heavy two-step eligibility+ranking flow with quiz-signal prep.
- The post-submit **"Application received"** screen needed no work — S8's silent-score already keeps status
  `submitted`, so the application page shows the neutral received card and never auto-advances. Verified the copy only.

## What Went Wrong
- **`next dev` on port 3007 from the previous (S9) session was still running**, causing `EADDRINUSE` when I started
  the S10 screenshot server. *Symptom:* "Failed to start server: address already in use :::3007". *Root cause:* the
  S9 cleanup used `pkill -f "next dev"`, which on Windows didn't kill the detached `next-server` child — it survived
  across turns. *Fix → lessons.md:* kill background dev servers **by listening port** (`netstat -ano | findstr :PORT`
  → `taskkill /F /PID`) before restarting, and don't assume `pkill -f` reaped a Windows node child. (Also: a stale
  server serves the OLD bundle, so a screenshot taken against it would silently be wrong — always confirm the restart.)

## Design Decisions
- Top-3 sourced from the student's **saved courses** (not a fresh eligibility recompute) — see `docs/decisions.md`.

## Numbers
- Frontend jest **49**; backend unchanged (**1095**); i18n **1087 keys × 3** (parity); `next build` clean. ~6 files
  (scholarship.ts, its test, apply page, 3 i18n). **No migration, no backend change.**
