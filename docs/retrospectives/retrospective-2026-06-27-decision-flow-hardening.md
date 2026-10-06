# Retrospective — Decision-flow & verification hardening (2026-06-27)

Worktree `.worktrees/wa-comms`. Commits `2410f25d`, `791a5828`, `badda56d`, `f2059d1c`,
`435ba2ef`, `3d0b4f27` (interleaved with the other agent's #66 / doc-recognition work on `main`).
All shipped + deployed incrementally; no migration.

## What Was Built

1. **BC / guardianship relationship rows: name-primary matching.** A birth-certificate / letter
   IC number is AI-read off green JPN security paper, so a one-digit OCR slip (76‑08→76‑09) was
   flipping the Mother/Guardian row to a hard red "Doesn't match" even when the name matched and
   the parent's own IC was separately verified (#12). Now the NAME is the primary proof and the
   IC number is corroboration: name-match + IC clash → amber **"check the IC number"**, or
   **"differs by one digit (likely a scan misread)"** when exactly one digit differs
   (`vision.nric_close`); red is reserved for a real name mismatch. `income_engine._combine_relationship`.
2. **Upload orphan-row guard.** #80's Mother's EPF showed a dead view link — the `bursary`… no:
   the `bursary_agreements`… no — the DOC row existed but its blob was missing from Storage
   (signing returned HTTP 400). A one-time sweep of all 603 docs found exactly 1 orphan (deleted).
   Hardened: `storage.object_exists` (tri-state) + the upload-create endpoint rejects a
   CONFIRMED-missing blob (`400 upload_incomplete`) before the stale-sweep, so a reject never
   harms the existing copy.
3. **api memory 1 GiB → 2 GiB.** Interview "Propose times" intermittently failed with "Could not
   save" (#90) — the container was OOM-killed mid-request (1047 MiB used vs the 1 GiB cap).
   Config-only bump; OOM kills stopped.
4. **Reopen returns an accepted case to the decision point.** Reopen now moves status
   `accepted` → `interviewed` (was a side-flag only) + clears any pending decline; cancel-reopen
   restores `accepted`. A decline after reopen is therefore bucketed **`interview`** (not
   `contractual`); `contractual` is reserved for genuinely post-award (`sponsored`). Decline
   emails are now **HTML** (the interview bucket thanks the student for their time + documents).
5. **Decline = immediate decision, embargoed email.** The rejection flips to `rejected` at once
   (cockpit/records reflect it); only the student EMAIL is embargoed for the cool-off and sent by
   the release cron. The student does not see the rejection during the embargo —
   `ApplicationReadSerializer.status` masks an email-embargoed rejection as `interviewed`;
   `cancel_pending_decline` reverses it before the student is told.
6. **Bursary-agreement cockpit panel gated behind `BURSARY_AGREEMENT_ENABLED`.** The dark feature's
   panel was rendering on prod and showing false Student/Guarantor ✓ ticks (a `bursary ? … : true`
   default; `bursary_agreements` empty). Now gated on a flag exposed via the admin serializer.
7. **Ops/data:** #11 & #12 recategorised `contractual` → `interview`; #12 set `rejected` (email
   embargoed to 7/4); two mislabelled accepted+pending-decline cases (#12, #62) moved to
   `interviewed`. B40 invite campaign **batch 8** (27 new SPM merit+need, never-contacted) sent +
   **Group A reminder** (6 only-invited). Supabase MCP wired into this CLI session.

## What Went Well
- Live data pulled straight from the officer cockpit screenshots avoided guesswork on #12/#80/#90.
- The state-machine fix (reopen→interviewed) fixed three of the owner's 5-point requirements with a
  single backend change — the existing frontend (`doSave`, `decisionLocked`, cancel-reopen) did the rest.

## What Went Wrong
- **Cool-off conflated decision-finality with notification-timing → #11/#12 showed "Accepted".**
  *Symptom:* a reviewer-declined student (after reopen) displayed as Accepted in the cockpit.
  *Root cause:* the original cool-off held the whole decision silently (status unflipped) until
  release, AND reopen used a side-flag instead of a real status transition — so a declined case sat
  at its pre-decision status. *Fix:* split the two concerns — immediate `rejected` + embargoed
  email; reopen moves the status; +tests (`test_decision_cooloff`, `test_decision_reopen`).
- **A dark feature leaked to prod because the panel was gated on status, not the flag.** *Symptom:*
  the Bursary-agreement panel showed false "signed" ticks for every accepted applicant.
  *Root cause:* the render condition checked only `status`, while a code comment *claimed*
  "flag-gated; dark by default" — a comment is not a check; the backend never exposed the flag to
  the frontend. *Fix:* expose `bursary_agreement_enabled` on the admin serializer + gate the panel
  on it. (Lesson added.)
- **Two wasted Cloud Run job runs: a multi-line `a.save()` write silently didn't persist.**
  *Symptom:* the #12 backfill "ran" but the row was unchanged (reads worked, the write didn't).
  *Root cause:* a multi-line Python script passed via `gcloud run jobs execute --args="^@^…"`
  intermittently mis-parses and aborts before the save; only `print` source lines surfaced in logs.
  *Fix:* used the now-connected Supabase MCP `execute_sql` with a `RETURNING` clause to apply +
  confirm the write in one shot. (Lesson added.)

## Design Decisions (logged in decisions.md)
- Decline cool-off = immediate rejection + embargoed student email (not silent-until-release).
- Reopen moves status `accepted` → `interviewed` (a real transition, not a side-flag).
- Relationship matching: NAME is the primary proof of the link; the AI-read IC number is
  corroboration (amber, never a hard red, on a one-digit OCR slip).

## Numbers
- Backend: see MEMORY.md registry (full suite re-run at close). jest 371. `next build` clean.
- 6 code commits, no migration; 3 data fixes; batch-8 invite (27) + 6 reminders.
