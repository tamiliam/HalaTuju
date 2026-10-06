# Consolidated retrospective — the STR-proof stream (June–July 2026)

**Written at the 2026-07-23 Consolidation Review** (promotion of the four 2026-07-01 small-change
entries flagged in `docs/consolidation-log.md`). This ties together work that shipped across
sprints AND the small-change lane so the arc is readable in one place. Detail lives in
`docs/scholarship/str-proof-spec.md` (the spec is authoritative) and the CHANGELOG entries cited.

## The arc

1. **Principle (owner-settled):** a genuine *Lulus* STR takes precedence route-agnostically;
   matching must exhaust ALL parents/guardians (name OR NRIC) before declaring a breach; salary
   is the fallback only when no member matches. (Memory: `feedback_str_precedence`.)
2. **Sprint 1 — model rework, MODEL_VERSION 1.1 → 1.2:** route fall-through fixed; the spec
   (`str-proof-spec.md`) written as the single source of truth. (CHANGELOG ~:3463.)
3. **Sprint 2 — salary spillover** (spec §6/§7): income evidence flowing between routes.
   (CHANGELOG ~:3450.)
4. **Refinement, MODEL_VERSION → 1.2.1 (small lane, 2026-07-01):** means-test payment guard +
   band matrix + date-only "Current" chip; over-B40 revised to red. (CHANGELOG ~:3406.)
5. **Officer copy pass (small lane, 2026-07-01 ×3):** prescriptive Check-2 verdict copy (lean,
   action-first, "Unsure" = asked-the-student); STR Status (Lulus) chip with the finding leading;
   the raw-ICU rendering bug replaced with flat per-status keys. Gopal/help_engine deliberately
   untouched (stays tolerant).
6. **Sprint 4 — Check-2 case summary (LLM), still DARK** behind `VERDICT_CASE_SUMMARY_ENABLED`;
   its own retro follows once the owner live-validates the voice and flips the flag.

## What the cluster teaches

- **The lane leaked scope:** items 4–5 rode the small lane but changed a verification model
  (MODEL_VERSION bump) and money-adjacent verdicts — by the lane's own boundary ("anything
  touching money/consent = sprint") at least the 1.2.1 refinement deserved sprint ceremony.
  It got the tests but not the reflection; this retro is the repayment.
- **Copy is part of the model.** Three of the six steps were wording. Officer-facing verdict
  language carries the model's meaning; treating copy fixes as afterthoughts is how drift
  happens between what the engine decides and what the officer reads.
- **The spec-first pattern held.** Every change amended `str-proof-spec.md` before code —
  the same change-the-matrix-first discipline the role work uses. Keep it.

## Status

Shipped and live through MODEL_VERSION 1.2.1; cohort-wide effects verified in the original
change records. Open: Sprint 4 dark-flag validation (owner), then its retro.
