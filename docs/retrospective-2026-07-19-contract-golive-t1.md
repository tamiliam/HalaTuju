# Retrospective — Contract Go-Live Transition, Sprint T1 (backend)

**Date:** 2026-07-19 · **Branch:** `feat/contract-golive-transition` · **Not deployed** (single deploy is T2)
**Plan:** `docs/plans/2026-07-19-contract-golive-transition-plan.md`

## What Was Built

The backend half of the switch from the grandfather arrangement to contract mode, all behind the
still-OFF flags:

1. **Contract-mode award email** — `emails.send_award_offer_sign_email` + a flag branch in
   `sponsorship.release_award_offer_emails`. Flag-ON: review-&-sign email (`/scholarship/award`),
   no Vircle, no setup task. Flag-OFF: byte-identical to before.
2. **Vircle bootstrap at execution** — `bursary.send_vircle_setup_at_execution` on the
   `distribute_executed_agreement` seam; grandfather-skips (task exists / non-blank `vircle_id`) and
   is idempotent.
3. **Maintenance flip on the payment run** — `payments.complete` flips `active → maintenance` on the
   first released item (reusing `disbursement._flip_to_maintenance`).
4. **Offer-lapse rework** — armed-at-sign-invitation clock (`arm_sign_deadline`,
   `SIGN_ACCEPT_DEADLINE_DAYS` default 30), cleared at bind; `lapse_expired_offers` lapses only
   armed-and-expired offers and refuses paid apps (returns `{'lapsed', 'flagged'}`).
5. **Sources model + witness assignment** — `PartnerOrganisation.show_in_apply` (+ migration seed of
   the live referral orgs), `ScholarshipApplication.witness_org` override FK, witness resolution
   override → referral → none, and `_AdminBase`-fenced (super/org_admin) Sources + witness endpoints.
6. **29 tests** in `test_contract_golive_t1.py` covering the plan's full T1 acceptance block.

## What Went Well

- The plan's acceptance block mapped cleanly onto a unit-test matrix; the end-to-end `bursary_e2e`
  command (both org + no-org paths) confirmed the execution-time Vircle invite fires live and the
  signing chain is intact.
- Reusing `disbursement._flip_to_maintenance` in `payments.complete` kept the flip semantics
  single-sourced rather than a second copy.

## What Went Wrong

- **The plan's "Verified facts" claimed PartnerOrganisation had no phone field; it does, and an
  existing endpoint edits it.** Symptom: the plan named a new `contact_phone` column. Root cause: the
  plan-authoring pass didn't grep the model + its editors, so a factual error was locked into an
  otherwise-authoritative section. Fix: reused the existing `phone`; added the cross-cutting lesson
  "re-verify each load-bearing plan-fact against the running code" to `lessons.md`, and documented the
  deviation in CHANGELOG + decisions so the plan-to-code mismatch is traceable.
- **A concurrent agent was editing the same working tree (sponsor funding-bar / pool) uncommitted.**
  Symptom: `git status` on the new branch showed ~9 files I never touched. Root cause: no worktree
  isolation between two agents on one repo. Fix (this sprint): staged only my explicit paths, never
  `git add -A`. Systemic fix already exists (`parallel-work-isolation.md` / git worktrees) — worth
  using proactively when two agents share `Production/HalaTuju`.
- **`send_sign_invitation_email` mock initially targeted the wrong binding.** Symptom: the
  failed-send test armed the deadline anyway. Root cause: the management command binds the name at
  import (`from … import send_sign_invitation_email`), so patching `emails.send_sign_invitation_email`
  didn't intercept it. Fix: patched the command module's bound reference. (Recurring Python-mock
  gotcha; already known but re-bit here.)

## Design Decisions

See `docs/decisions.md` (2026-07-19): reuse-`phone`-not-`contact_phone`; maintenance-flip-in-complete;
armed-clock lapse rework.

## Numbers

- Files touched (mine): ~19 (2 models, 2 migrations, emails/sponsorship/bursary/payments, the
  sign-invite command, urls, views_admin, settings, 3 test files, tech-debt, CHANGELOG, decisions,
  lessons, this retro).
- Tests: +29 (all green). `apps/scholarship apps/courses` suite green (4093 incl. the concurrent
  agent's additions).
- Deploys: 0 (T1 is backend-only; the single api+web deploy is T2).
