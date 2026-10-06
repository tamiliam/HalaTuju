# Retrospective — Check-2 gaps found in #117, 2026-07-14

A live review of applicant #117 (KIRIIYARASAN) surfaced four defects, three systemic. Built as an
isolated worktree/branch (`feat/check2-117-gaps`) in parallel with the status-vocabulary stream.
Plan: `docs/plans/2026-07-14-check2-117-gaps.md`. No migration.

## What Was Built

1. **Water bill reads the address, else bails to Gemini** — kills the #36/#66 infinite re-ask loop.
2. **Offer pathway made real** — break the `offer_letter_auto` circularity in `_declared_pathway`;
   stop `_canonical_preu_institution` laundering the student's school; add the **stream/track** as a
   third comparison dimension (`offer_pathway_match`); harden `_parse_stpm` for #117's glued OCR.
3. **The pensioner** — `BENEFIT_OCC` + a `pension_amount_unknown` ask-first clarify + a
   `*_pension_proof_missing` statement request on a "yes", reusing the `salary_slip` slot. 27 i18n
   leaves (en/ms/ta × 3 codes × [title, desc, verdict item]).
4. **Roster under-count margin** 2 → 1.
- A **CLARIFY registry guardrail** (`set(CLARIFY_SPECS) == set(_CLARIFY_ORDER)`); the sibling/guardian
  EPF side-finding.

## What Went Well

- **The plan de-risked the delicate parts up front.** It named the `_CLARIFY_ORDER` silent trap, the
  `offer_letter_auto` circularity, and the "ask-first then proof" ordering before any code — so the
  build was mostly mechanical, and the guardrail was written the same sprint it became load-bearing.
- **Every fix is conservative by construction.** The water parser bails to Gemini rather than emit a
  blank; the circularity break can only reveal clashes, never create them; the pension proof is raised
  only on an explicit "yes"; the stream clash fires only when both sides read a stream. Nothing here
  can retroactively harm a live case, which is why it can deploy as one unit.
- **Reused the #126 shape wholesale.** The pension chain is a near-mechanical mirror of the
  informal-payslip chain (classify at resolve time, store on the item, read a stored value in the gap
  engine), so it inherited that pattern's correctness and its negation-first protection.

## What Went Wrong

1. **Fix 1's address heuristic could not be calibrated locally** (symptom: the `eval/` OCR corpus was
   absent from the worktree).
   **Root cause:** the corpus is gitignored PII (real bills), fetched only on the remote station via
   `eval/capture_ocr.py` against live Storage — it is deliberately not in the repo.
   **What saved it:** the *structural* fix (return `None` → Gemini when the address can't be read) is
   correct **independent of how good the regex is** — worst case every Air Selangor bill routes to
   Gemini, which already reads them, strictly better than the old infinite loop. So the fix ships
   safely uncalibrated; the regex tuning + the live Re-run of the 6 bills are flagged as an explicit
   post-deploy step, not a blocker. Lesson captured.

2. **The stream comparison had a false-match trap** (`SAINS` and `sains_sosial` share the `sains`
   substring, so the generic token-overlap clash detector would read them as a *match*).
   **Root cause:** token-overlap is the wrong tool for a hierarchical code space where one value's
   name is a prefix of another's.
   **Prevention:** both sides are canonicalised through `parse_stpm_stream` to *distinct codes* before
   comparing for equality, and the clash is counted only when both read a stream. A regression test
   asserts `parse_stpm_stream('SAINS') != parse_stpm_stream('SAINS SOSIAL')`. Lesson captured.

## Design Decisions

Logged to `docs/decisions.md`:
- Break the offer-vs-declaration circularity in the *reader* (`_declared_pathway` ignores an
  `offer_letter_auto` pick), not by un-stamping autofill.
- The pension is **ask-and-evidence, not re-band** (owner) — get the statement on file first; feeding
  it into the per-capita figure is a separate, clean follow-up.
- Compare the stream via **canonical codes**, clashing only when both sides read one.

## Numbers

- **Scholarship pytest:** 2408 → **2427** (+19 across the fixes).
- **jest:** the two i18n suites (`actionCentre`, `admin-scholarship-i18n`) — 46 green.
- **Golden masters:** SPM 5319 / STPM 2026 intact (no eligibility-engine change).
- **Migration:** none. **i18n:** +6 keys × 3 locales, parity verified identical.

## Post-deploy follow-ups (LIVE service only — never local; `halatuju_never_reextract_locally`)
- Calibrate `_water_address` on the 6 real Air Selangor bills (30/36/66/80/82/95) via
  `eval/capture_ocr.py`, then cockpit **Re-run** those bills — #36's open request auto-resolves.
- Re-run #117's offer (stream clash → `pathway_confirm`) and STR; surface #33/#99's clash to officers.
- Sync one Completed-stage app with a retired parent → confirm the pension clarify raises and demands
  no document until the student answers "yes".
