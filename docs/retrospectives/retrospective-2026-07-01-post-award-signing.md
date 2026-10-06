# Retrospective — Post-award contract-signing flow (5 sprints, DARK)

**Date:** 2026-07-01 · **Branch:** `feat/award-comprehension` (worktree `.worktrees/award-quiz`)
**Commits:** `013effe3` (S2) · `3e7b69c6` (S3) · `429679b8` (S4) · `5abae484` (S5) · `f7cc7300` (S6)
**Flag:** everything behind `BURSARY_AGREEMENT_ENABLED` (default OFF). Not yet flipped on prod.

## What Was Built

The wiring that takes an **awarded** student end to end — from a follow-up email through to a
fully executed bursary agreement — without landing them in the student portal until everyone has
signed. The signing *engine* (`bursary.py`, the 4-party state machine, PDF/SHA snapshot, the
`parent_ic` identity gate, the in-session signing page, the admin countersign/witness endpoints)
already existed; this work is the orchestration around it.

- **S2 — comprehension quiz.** Ported the owner-approved 8-checkpoint "Understand" prototype into a
  wired React component (`AwardComprehensionQuiz.tsx` + `awardComprehension.ts`, en/ms/ta). It gates
  the signing form; the pass is persisted (`comprehension_passed_at`, migration `0083`).
- **S3 — parent PIN gate.** The guarantor signature now requires a fresh SMS PIN to the
  guardian's **locked** phone (read from `profile.guardians`; `guarantor_phone`/
  `guarantor_phone_verified_at`, migration `0084`; freshness TTL). Endpoints
  `…/award/guarantor/verify-phone/{send,check}/` reuse Twilio Verify; `sign_agreement` raises
  `guarantor_phone_missing`/`_unverified`. FE PIN block in the guarantor section.
- **S4 — notify-and-sign chain.** After the guarantor signs: partner witness (if a referring org
  with a contact email) → else Foundation directly (graceful) → on witness, Foundation nudge → on
  countersign+execute, student "in effect" email. `foundation_notify_emails()` =
  `FOUNDATION_NOTIFY_EMAIL` → super admins → `ADMIN_NOTIFY_EMAIL`. Owner-sent "ready to sign"
  follow-up command. Panel gated away from the portal until executed.
- **S5 — cockpit signer UX.** Fixed **TD-144** (real agreement surfaced on the admin detail GET →
  accurate four-party ticks; buttons disabled until an agreement exists). Provisioning doc.
- **S6 — SLA + local E2E + go-live.** Daily reminder cron (`*_reminded_at` stamps, migration `0085`);
  `manage.py bursary_e2e` walks the whole chain with every external seam mocked; go-live playbook.

## What Went Well

- **Reused the engine, wired the edges.** A 5-parallel-agent investigation up front established the
  signing engine was ~80% built; the work became orchestration + one prototype port, not greenfield.
- **Each sprint shipped tested + build-clean** behind the flag; 1849 scholarship pytest at close.
- **The local E2E driver** turns "we hope the chain works" into a one-command, repeatable proof —
  both the with-partner and no-org (graceful) paths print green, with no real Twilio/email/storage.

## What Went Wrong

1. **Built a redundant S1 Action-Centre "sign" task before checking what already existed.**
   *Symptom:* a whole task + endpoint + FE component, discarded unpushed. *Root cause:* started
   building the entry point before confirming the existing `awardPanel` already routed awarded
   students to `/scholarship/award` — the prior sprint's embargo note (`AWARD_ACCEPTANCE_ENABLED`)
   was the clue. *Fix:* the investigation-first habit is already in `lessons.md`
   (`feedback_verify_shipped_before_rebuild`); reinforced — check the embargoed/flagged surfaces
   before assuming a feature is missing.
2. **New docs landed in `halatuju_api/docs/` instead of the canonical root `docs/`.**
   *Symptom:* provisioning + playbook docs in the wrong tree, moved at sprint-close. *Root cause:*
   assumed docs sit beside the app; the repo keeps retrospectives/specs/tech-debt at the worktree
   root `docs/`. *Fix:* note in `lessons.md` — bursary/scholarship docs go in root `docs/scholarship/`.
3. **A 5-commit divergence from `origin/main` surfaced only at sprint-close.** The owner pushed a
   parallel STR-proof series + an award-email reword touching the same files. *Symptom:* a late merge
   with overlap in `emails.py` + i18n. *Root cause:* worked a long branch without periodically
   merging `origin/main`. It auto-merged cleanly (1849 pass, build clean), but the risk was real.
   *Fix:* on a multi-sprint branch, merge `origin/main` in at each sprint boundary, not just at close.

## Design Decisions

See `docs/decisions.md`: in-house e-signature (no DocuSign); same-session parent PIN on a locked
phone; graceful/non-blocking witness; parent gets the PIN, not an email.

## Numbers

- 5 sprints; ~3 migrations (`0083`/`0084`/`0085`, all additive); 1849 scholarship pytest; web build clean.
- New: 1 comprehension quiz, 1 parent-PIN gate (2 endpoints), 4 chain emails, 3 owner/SLA commands,
  1 local E2E driver, 2 ops docs. Everything dark.
