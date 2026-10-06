# Retrospective — Document upload: stage → judge → promote-only-if-better (Phases 1–4)

**Date:** 2026-07-09
**Commits:** `34caee74` (P1) · `b8b6f087` (P2) · `8615388a` (P3 offers) · `a3516d04` (P3 slips) · `eaa8b78c` (P4)
**Migrations:** none. **MODEL_VERSION:** untouched (1.5.0).
**Tests:** 2244 scholarship pytest + 487 jest.

## What Was Built

A single owner-designed roadmap that inverts the Check-2 document upload flow from *replace-first* to
*stage → judge → promote-only-if-better*, so a worse or wrong re-upload during the Completed stage can
never bury a good live document.

- **Phase 1 — false-red usability fix (`vision.py`).** The STR recipient is a parent/earner, but
  `doc_student_verdict` name-checked it against student+guardians only, stamping a false
  `name_mismatch`. STR now joins utility bills in skipping that name-check; the real household match
  is `student_str_check`. Restored #126 (Lulus Semakan doc 1932 live → income reads Probable).
- **Phase 2 — the staging framework (`promotion.py` + `views.py`).** A KEY NAMED doc is created
  **staged** (not-live), read, then promoted only if **usable** (`doc_match_verdict` not
  mismatch/unreadable) **and** at least as good as the live doc (`should_promote`). Generalised the
  former STR-only keep-better guard to every key type. BYPASS/reviewer docs (`bank_statement`,
  `income_support_doc`, `other`) accepted as-is. **Circuit-breaker**: after
  `DOC_STAGE_MAX_ATTEMPTS` (=3) not-usable re-uploads, the open request is flagged
  `needs_officer_eye` (`params` JSONField, no migration) — a hold for a human, never auto-resolve.
- **Phase 3 — per-doc quality where it adds real value.** `promotion.doc_quality` gained:
  - **offer_letter** → officialness `(usable, official_rank, reporting_bonus, id)`. Offers are the
    one un-deduped type where two *usable* copies genuinely differ (a genuine official vs a
    conditional/private/pemakluman), so a later non-official upload used to bury a good offer on the
    id tiebreak.
  - **results_slip / semester_result** → field-completeness `(usable, genuine, completeness, id)` —
    a fuller slip beats a thinner but equally usable+genuine one (observe-in-practice).
  - Deliberately **not** salary/epf/bills (re-collapsed by `dedupe_income_proof` after promotion) or
    BC (genuineness already in the proxy).
- **Phase 4 — the circuit-breaker's visible half (FE only).** The student Action Centre shows a calm
  "we're looking into this with our team" state instead of the re-upload loop; the officer cockpit
  shows an orange "Hold — needs a person" chip. `needs_officer_eye` was already on
  `ResolutionItemSerializer.params`, so no backend change.

## What Went Well

- **Investigate-before-build repeatedly narrowed scope.** Both Phase 3 and Phase 4 were re-scoped by
  reading the code first: the dedup safety net made most Phase-3 types redundant (only offers/slips
  had an unguarded axis), and `params` already carried the flag to the frontend so Phase 4 needed no
  backend work. Shipped the value, skipped the filler.
- **Pure `promotion.py` stayed pure** — every quality signal is a doc-local read
  (`offer_official_status`, `read_slip`, `semester_check`, `str_proof_quality`), so the module never
  queries `.documents` and stays out of the static read guard with no superseded-read obligation.
- Zero migrations across all four phases; MODEL_VERSION never touched (all reads of already-computed
  fields), so no re-run / re-band was needed.

## What Went Wrong

- **Nothing broke in production**, but two behaviours ship **verified by tests + code-tracing, not by
  a live event**: the actual promote-on-reupload during the Completed stage (all phases) and the two
  quality axes firing on a real case. *Root cause:* the trigger is a student re-upload we can't
  manufacture on demand from a local checkout (re-extraction must run on the live service, never
  locally). *Prevention:* logged as an explicit observe-in-practice item with a concrete check (see
  Next Sprint) rather than claimed as done — a local-code-vs-prod-DATA verification proves the LOGIC,
  never that the live SERVICE exercised it (the 2026-07-09 stale-build lesson, reapplied).

## Design Decisions

See `docs/decisions.md`: (1) stage→judge→promote inversion over the owner's original purgatory model;
(2) `needs_officer_eye` as a `params` flag, not a new STATUS; (3) per-doc quality only where an
orthogonal, unguarded axis exists (offers, slips), not uniformly.

## Numbers

- 5 commits, 4 phases, 0 migrations. 2244 scholarship pytest (+~20) + 487 jest (+~4).
- New: `promotion.py` (doc_quality + should_promote), `_BYPASS_JUDGE_TYPES`, `DOC_STAGE_MAX_ATTEMPTS`,
  `needs_officer_eye` FE surface, i18n `officerHold.*` + `outstanding.hold`.
