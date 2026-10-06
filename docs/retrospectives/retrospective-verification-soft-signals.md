# Retrospective — Utility holder/address + payslip-vs-EPF verification signals (#8–#9)

**Shipped:** 2026-06-12 · branch `feature/verify-signals` → `main` · **no migration** · backend soft-signals (never gate).

## Objective
Two verification gaps from the owner's live review. The common thread: the engine **already computed** the underlying
facts but only *displayed* them passively — the work is to **escalate** them into actual flags/queries.

## #8 — utility-bill holder + address → a query
`income_engine.utility_check` already returned `name_note='unrelated'` (holder matches neither the student nor any uploaded
parent IC) and `vision_address_match` (match/partial/**mismatch**). New thin helpers expose those as queries:
- `utility_holder_unknown(application)` → the stranger's name (first offending bill) or None.
- `utility_address_mismatch(application)` → True only on a **hard** `mismatch` (a missing-postcode / shortened-street
  `partial` read deliberately stays silent — exactly the "minor differences shouldn't fire" the owner asked for).

Surfaced **two ways** (owner's call — "build both"):
1. **Officer pre-interview flag** — `anomaly_engine` gains `_detect_utility_holder_unknown` + `_detect_utility_address_mismatch`
   (registered in `_DETECTORS`), rendered on the cockpit "Pre-interview flags" card. **Active now.**
2. **Student Check-2 clarify query** — folded into `check2_queries.sync_check2_queries` (same reconcile loop as the
   completeness gaps: created when present, auto-resolved when the bill is fixed) + added to `actionCentre.KNOWN_CODES`.
   **Dark** behind `CHECK2_STUDENT_QUERIES_ENABLED` (OFF): the flag gates student *visibility* + the email at the call
   sites (`views.py`, `services.py`), so these inherit the exact darkness of the existing clarify codes.

## #9 — payslip vs EPF divergence
`income_engine.slip_epf_divergence(application, member)` cross-checks, for a member with **both** a salary slip and an
EPF, the payslip gross against the EPF-implied salary (`monthly_contribution / 0.24`). Flags `payslip_epf_divergence`
(officer pre-interview flag) **only** when the ratio falls outside a generous **0.6–1.67** band (reciprocal bounds →
symmetric; >~1.67× apart). The band is wide on purpose: overtime, commission, and late employer payments routinely move
the two figures apart, so this is a "verify the regular income at interview" nudge, never a gate.

## Decisions
- **DRY the detection.** Both the officer flag and the dark student query call the *same* `income_engine` helpers, so the
  two surfaces can never drift.
- **Multi-earner edge:** the detectors return the first offending bill/member (one anomaly per detector, matching the
  engine's contract). Acceptable — clusters almost always share one holder; noted, not solved.
- **No new query mechanism.** #8(2) reuses the existing Check-2 ResolutionItem plumbing rather than inventing a parallel
  channel; utility codes sit *last* in `_CLARIFY_ORDER` (a completeness gap matters more to a fundable profile).

## Gates
1104 scholarship pytest (**+23** new: 6 income-helper, 7 anomaly, 4 check2, 6 divergence) · actionCentre jest 23 ·
`next build` clean · i18n parity **2512×3** (anomaly fact/question ×3, Check-2 query title/desc ×2, admin summary ×2).

## Lessons / carried notes
- **Real-file context drove the design** (the owner's myTNB screenshot showed both bills in `ATHILATHMY A/P MUNUSAMY`'s
  name) — the system was already detecting it; the fix was escalation, not new OCR.
- **Tamil first-draft** on the 14 new strings — refine queue.
- When `CHECK2_STUDENT_QUERIES_ENABLED` is eventually flipped on, the utility student queries activate automatically
  (no further code) — verify their copy reads well at that point.
