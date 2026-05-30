# Sprint retrospective — Phase C + supporting work (2026-05-30)

Covers everything shipped on 2026-05-30 since the S19 close (4 merges):
TD-063, TD-061+062, **Phase C (the headline)**, and the branded-entry refresh.
Versions 2.12.0 → 2.16.0.

## What Was Built

1. **TD-063 — explicit stream subjects (v2.13.0, `ceb002f`).** The merit engine
   now trusts the student's own stream/aliran selection (`prepare_merit_inputs(grades,
   stream_subjects=None)`); the FE/BE stream pools become fallback-only, so the
   S18 missing-from-pool mis-score is impossible for labelled data. New
   `StudentProfile.stream_subjects`. Golden master unchanged (5319) + a
   differential audit captured as 6 unit tests.
2. **TD-061 + TD-062 (v2.14.0, `5dc7c29`).** Dropped 4 dead columns
   (`family_income`/`siblings`/`phone`/`siblings_studying`) under expand-contract;
   fixed a latent `/profile` bug (household income/size edits were silently
   dropped). Added `cleanup_orphan_blobs` management command (TD-062).
3. **Phase C — post-shortlist handoff + interview layer (v2.15.0, `c671b3e`).**
   The headline. New funnel `shortlisted → profile_complete → interviewing →
   interviewed → accepted`. Explicit "Confirm & submit" (`confirm_profile`,
   stamps `profile_completed_at`, emails admin); **hard accept-gate** on
   incomplete profiles (no override); **request-more-docs**; `PartnerAdmin.role`
   {super,reviewer,viewer}; `assigned_to` FK + filters; `InterviewSession`
   (findings keyed to anomaly codes + 1–5 rubric) + capture UI extending the
   Pre-interview-flags card. Completion is **not** a freeze — the student keeps
   uploading. +21 tests.
4. **Branded entry + sponsor-interest (v2.16.0, `a4398f4`).** Header "Log in"
   dropdown (Student/Sponsor/Partner) + "Sign Up" → `/get-started` chooser;
   `/sponsor/register-interest` → public `SponsorInterest` lead capture + admin
   email. Browse-first **preserved** (NRIC gate behaviour unchanged). +6 tests.

## What Went Well

- **The handoff-flaw discovery was the highest-leverage moment of the sprint.**
  Before building the Phase C interview layer, an Explore pass found the
  submit→admin handoff was unsound (silent completion, no admin signal, ungated
  accept) — exactly what bites when a batch completes Step 4. Building the
  hardening *first* (and forward-safe) meant the urgent risk was closed before the
  larger build, not after.
- **Critically evaluating the auth proposal instead of implementing it literally.**
  The Funding-Societies-style "register to enter" model would have closed the
  open course guide. Pushing back (browse-first is the product) + reframing
  sponsor as "register interest" (because sponsor login had no destination) turned
  a multi-sprint overhaul into a safe, bounded ship.
- **Migrate-first via Supabase MCP held across four destructive/additive
  migrations** (column drops, new `interview_sessions` + `sponsor_interests`
  tables, choices changes) with zero downtime and verified pre-drop data safety.
- **Golden masters never moved** (SPM 5319 / STPM 2026) across the whole sprint
  despite touching the merit engine (TD-063) — the differential-audit + golden
  master combo gave real confidence.

## What Went Wrong

1. **Phase C shipped without an interactive end-to-end run.**
   - *Symptom:* The whole post-shortlist funnel (confirm → admin sees → assign →
     interview → submit → accept) was verified by test-equivalence + health
     checks (401-not-500), never a real browser click-through, even though real
     students are imminent.
   - *Root cause:* No "drive the live flow as a human (or via Playwright MCP)"
     step in the deploy checklist; test-green was treated as ship-confidence for a
     multi-screen stateful flow.
   - *System change:* For any multi-screen stateful flow facing imminent real
     users, add an explicit **interactive smoke** (Playwright MCP against the live
     test account) to the deploy step — not just endpoint health checks. (Flagged
     to the user as the recommended next action.)

2. **"Build it all together" (Phase C) outran the <24h batch window.**
   - *Symptom:* The user chose to build the full Phase C in one effort; a complete
     interview layer is not a <24h build, so the imminent batch could reach Step 4
     before the admin side was fully exercised.
   - *Root cause:* The urgency (handoff) and the larger build (interview layer)
     were bundled by the "together" decision.
   - *System change:* Mitigated by *ordering* the work handoff-first + forward-safe
     so Steps 1–2 could deploy alone if needed. Lesson: when a "build together"
     choice collides with a hard deadline, still sequence the deadline-critical
     slice first and keep it independently shippable. (Done this sprint.)

3. **The sprint sprawled across 5 versions / 4 merges without an interim close.**
   - *Symptom:* TD cleanup + Phase C + entry refresh all landed in one session;
     "one coherent deliverable per sprint" (workspace rule) was exceeded.
   - *Root cause:* Momentum — each ship enabled the next, and the user kept
     directing new work in-session.
   - *System change:* Acceptable here (all related to the post-shortlist push), but
     CHANGELOG/decisions/lessons were updated *inline per ship* so this close is a
     consolidation, not a reconstruction. Keep doing inline doc updates so a
     multi-ship session is always close-ready.

## Design Decisions

See `docs/decisions.md` (this sprint: hard accept-gate with no override;
`profile_complete` status + timestamp + explicit confirm; completion-is-not-a-
freeze via `POST_SHORTLIST_EDITABLE`; `PartnerAdmin.role` expand-contract; browse-
first preserved; sponsor = register-interest until a portal exists). TD-063's
explicit-stream decision was logged at its own ship.

## Numbers

- 4 merges, 5 versions (2.12.0–2.16.0).
- Backend **1276** pytest + **155** jest = **1431** tests; 0 failures.
- Golden masters: SPM **5319**, STPM **2026** — unchanged all sprint.
- Migrations: `courses/0049–0051`, `scholarship/0021–0024` (all migrate-first via
  Supabase MCP; 2 new tables with RLS).
- i18n parity **1442 × en/ms/ta** (Tamil first-drafts queued).
- TDs resolved: **TD-061, TD-062, TD-063**.

## Carried forward

- **Validate Phase C interactively** (recommended next — real funnel run).
- **Phase D** (Gemini v2 refines the sponsor profile with interview findings) —
  cheap, contained, but its consumer (sponsor) is gated on Phase E.
- **Phase E** (real sponsor portal) / **Phase F** (mentor) — future.
- **Tamil refine** — now ~11 batches incl. all Phase C + entry strings; especially
  the consent text before the lawyer meeting.
