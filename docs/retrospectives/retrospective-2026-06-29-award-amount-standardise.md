# Retrospective — Standardised assistance amount (pathway-fixed, super-overridable)

**Date:** 2026-06-29
**Branch:** `feat/award-amount-standardise`
**Migration:** none (logic + gating + a prod data backfill)

## What Was Built
The assistance amount is no longer a free reviewer choice on the slider. It is now **fixed by
the student's pre-U pathway** and only a **super** admin may adjust it:

- **`award.py`** — the single source of truth: `proposed_award_amount(application)` →
  RM3,000 if `chosen_pathway=='stpm'` (Form 6), else RM2,000 (Matrikulasi / UA Diploma /
  Poly Diploma / Asasi / PISMP / university / blank). `ALLOWED_AMOUNTS` = the 5 slider stops
  (RM1,000–3,000 in RM500 steps) + `is_allowed_amount`.
- **`record-verdict` auto-manages the amount:** on APPROVE it sets the pathway amount (only
  if unset, so a super override survives a re-record); on DECLINE it clears it. Reviewers no
  longer touch the amount at all.
- **`AdminSetAwardAmountView` → SUPER-ONLY** (was reviewer) + validates the value is an
  allowed stop. This is the override path.
- **`proposed_award_amount` exposed** on the admin serializer so the cockpit always shows the
  pathway figure even before persistence.
- **Cockpit slider:** range RM1,000–3,000 step 500 (5 stops); **read-only for reviewers,
  draggable only for super**; always shows the amount (the "not set" / "Drag to set…" states
  removed); approve is no longer gated on manually setting an amount.
- **Prod backfill** (deploy step): re-price the 24 recommended students to the rule
  (RM62,000 → RM54,000).

## What Went Well
- The blast-radius investigation up front paid off: confirmed **one writer** of `award_amount`
  and **zero** downstream snapshots (0 sponsorships / agreements / disbursements), so the
  re-price is safe. `chosen_pathway` turned out to be a clean enum — the rule is a one-liner.
- Putting the rule in the backend (auto-apply on approve) rather than the UI keeps the money
  figure deterministic + auditable and means the FE never has to replicate the STPM logic.

## What Went Wrong
1. **`next build` failed twice with `WorkerError` — but this time it was real resource
   starvation, not the usual transient.** *Symptom:* two consecutive builds died in the
   static-gen worker. *Root cause:* **20 stray `node.exe` processes** had accumulated from
   repeated jest/next runs across the session, starving the 8 GB box. *Fix:* `taskkill //F
   //IM node.exe` then rebuild → clean. *Lesson:* on this machine, when `next build` OOMs
   more than once, kill stray node processes before assuming it's the known one-off transient.

## Design Decisions
- **Backend-authoritative rule, auto-applied on approve** (not a UI-only default) — one source
  of truth; the amount is correct regardless of client.
- **Super-only override, constrained to the 5 slider stops** — reviewers propose the decision
  (the four facts), the amount is policy; a super can still adjust within the sanctioned band.
- **`record-verdict` owns the amount lifecycle** (set on accept / clear on decline) so the UI
  no longer pokes the award endpoint on decline — which also removed a would-be 403 for
  reviewers under the new gating.

## Numbers
- Tests: backend 1686 pytest (+10: `test_award_rule.py` + updated `test_sponsorship`),
  frontend 383 jest. i18n parity 2942×3.
- No migration. Prod backfill: 24 rows (RM62k → RM54k).
- Files touched: ~9.
