# Retrospective — Layer-1 doc-eval batch: generic UA offer family + IC-anchored identity + BC/EPF live (2026-06-20)

Branch: `feature/doc-eval-harness` (owner-gated, NOT merged to `main`). This batch closes items
1, 2 and 4 of the Layer-1 plan (item 3 = STR signatures is still open).

## What Was Built

1. **Generic `ua_offer` signature family for the 20 fixed public universities** (commits `2c98eb0`,
   `d45b813`). Replaced six per-institution offer-letter families with one `ua_offer` family keyed off
   `_UA_NAMES` (the 20 UA names mirrored from `halatuju-web/src/data/publicUniversities.ts` ==
   courses `UNIV-001..020`). Identity-anchor gate: a recognised UA name floors at `suspect` and can
   reach `genuine` with the full offer structure; an unrecognised issuer defers to holistic
   `doc_genuineness` (so private/IPTS letters aren't force-scored). Validated zero misclassifications
   on the corpus AND 10 held-out production docs.

2. **OCR-tolerant, IC-anchored offer-letter identity** (commit `29f5d63`). The offer-letter NRIC is
   read by image-Gemini, which non-deterministically drops/garbles a digit (`0806201578` vs
   `080620101578`). `pathway_engine._ic_status` now treats a bounded edit-distance (≤2 on the digit
   string, via `_nric_close`) as a `match`; only a gross difference is a real `mismatch`. Identity is
   anchored on the IC + profile NRIC (read reliably by OCR); the offer NRIC is soft corroboration and
   the name is the robust offer-side check. +2 tests.

3. **BC + EPF genuineness wired live + EPF income reverse-engineered** (TD-122/TD-123, commit
   `494adc9`). Birth-certificate and EPF genuineness now come from the probabilistic SIGNATURE scorer
   on the live path (text-only), not the holistic Gemini call. EPF extraction gained
   `employer_number` + `employer_contribution_total` + `employee_contribution_total` (dropped the
   averaged field); income now reverse-engineers salary as
   `max(Σ employer/(n·0.13), Σ employee/(n·0.11))` with a legacy `÷0.24` fallback, and treats
   `No. Majikan == 000000000` as unemployed. BC extraction dropped `bc_number`.

4. **TD-133 follow-through** (commit `974fa5f`). Dropped `results_slip` from `_GENUINENESS_DOCS` —
   the signature scorer's branch wins first in the upload path, so the holistic membership was dead
   code and a renumber magnet on every `main` merge.

## What Went Well
- **Held-out validation paid off.** Running Issue-1 + Issue-2 against 10 unseen production docs (not
  in the calibration corpus) caught the #36 false-mismatch that the corpus never surfaced — exactly
  the kind of generalisation gap a local-only pass hides.
- **The generic family shrank the surface without losing recall.** Folding 6 families into 1 removed
  per-institution drift risk; the corpus + held-out runs confirmed no regression.
- **Re-merging `main` frequently** (the other agent is very active) kept conflicts small and the TD
  churn finally ended by resolving TD-133 outright rather than renumbering it again.

## What Went Wrong
1. **A false wrong-person flag (#36) shipped into the held-out run before it was caught.**
   *Symptom:* held-out eval flagged THAVASRI's offer NRIC as DIFFERS though the IC matched.
   *Root cause:* identity equality was an exact string compare on an image-Gemini-read NRIC, which is
   non-deterministic OCR — a single dropped digit read as a different person. The design assumed the
   offer NRIC was as reliable as the OCR'd IC; it isn't.
   *System change:* identity is now anchored on the reliably-OCR'd IC with a bounded-edit-distance
   tolerance on the soft offer NRIC, plus a regression test (close → match, gross → mismatch). Lesson
   logged below.
2. **Recurring TD-number collisions cost real time across merges.**
   *Symptom:* my `_GENUINENESS_DOCS` tidy was renumbered TD-120→124→127→130→132→133 as `main` reused
   each number.
   *Root cause:* two agents minting TD numbers against the same register on divergent branches — a
   sequential ID allocated on a long-lived branch always collides.
   *System change:* resolved the item outright (TD-133 → RESOLVED) to stop the churn; the durable fix
   is to allocate TD numbers only at merge-to-main time, not on the feature branch — captured as a
   lesson.

## Design Decisions
See `docs/decisions.md`: "Generic `ua_offer` family + identity-anchor gate", "Offer-letter identity
anchored on the IC (offer NRIC is soft)", "EPF salary reverse-engineered from contributions".

## Numbers
- 4 substantive commits on `feature/doc-eval-harness`; 0 unpushed, 0 behind `origin/main` (30 ahead,
  deliberately gated).
- Offer-letter genuineness: 0 misclassifications on the local corpus + 10 held-out production docs.
- Tests: see CHANGELOG `[Unreleased]` (+2 NRIC, +EPF salary cases, +API surface assertions).
- Items 1, 2, 4 of the Layer-1 plan closed; item 3 (STR signatures) remains open.

## Still Open / Next
- **Item 3 — STR signatures** (3 forms: MOF approval letter, Semakan Status, Dashboard; tail = SARA /
  SALINAN). OCR cached for 28 STR docs; awaiting the owner's steer on signature lists.
- Deferred Layer-2 cross-doc matching (poly/PISMP pathway+programme via `courses.pismp_taxonomy`).
- **Merge-to-main is owner-gated** — do not push to `main` until approved (push = deploy).
