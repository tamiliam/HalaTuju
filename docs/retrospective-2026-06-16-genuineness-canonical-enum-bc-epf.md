# Retrospective — Genuineness canonical enum + BC/EPF signatures (2026-06-16)

Branch `feature/doc-eval-harness`; 7 commits `45d23e0` → `cf1d905` (after merging current `main` in);
NO migration; not deployed. Builds on the earlier same-session close (`4504cb0`, the genuineness
package + slip signatures + academic/name fixes).

## What Was Built
- **Verification architecture spec** (`docs/scholarship/genuineness-verification-architecture.md`) —
  the two-layer model agreed with the owner: **Layer 1** (per-doc genuineness + field extraction)
  **gates Layer 2** (cross-doc relationship + matching, deferred). A Layer-2 check against a doc that
  hasn't cleared Layer 1 is *indeterminate*, never a confident mismatch.
- **Unified canonical genuineness outcome `genuine` / `suspect` / `not_<type>`** across every doc type
  (BE + FE). Signature docs derive it from the bands (≥0.70 genuine · 0.35–0.70 suspect · <0.35
  not_<type>); IC/STR/EPF map their holistic verdict. `bands.canonical_status()` folds every legacy
  stored value, so live data needs no backfill; all consumers (verdict cap incl. the identity-IC cap,
  anomaly flags, serializer) + the FE render one vocabulary. Treatment uniform: genuine → pass;
  suspect/not_<type> → soft cap + officer flag.
- **Birth-certificate signatures** (JPN Sijil Kelahiran) — calibrated on all 28 corpus BCs; same band;
  bilingual variant handled; a typed fake → not_bc, a cropped BC → suspect; zero false positives.
- **EPF signatures** (KWSP Penyata Ahli) — calibrated on all 13; same band; **caught three wrong-type
  mis-slots** (a Borang EC tax form, a KWSP withdrawal form, an STR screenshot = the TD-117 case) as
  `not_epf` — a deterministic wrong-type backstop. The scorer generalised to score any doc_type's
  signature family.
- **Issue-2 extraction contracts finalised** for results_slip, BC, EPF (incl. the EPF
  reverse-engineered salary `max(ΣCarumanMajikan/(n·0.13), ΣCarumanAhli/(n·0.11))` that self-corrects
  across salary tiers, and `No. Majikan == 000000000 ⇒ unemployed`).

Tests: +~12 across the work; full scholarship suite green throughout.

## What Went Well
- The signature method generalised cleanly from slip → BC → EPF with **one shared band**, calibrated
  once and reused unchanged — each new doc was "examine the corpus → list signatures → calibrate".
- The owner's reframes sharpened the design repeatedly: probability-not-yes/no, cropped=suspect (=
  re-upload, same standard as a face-cut IC), the band↔outcome 1:1 mapping, and the EPF `max()`
  tier-self-correction.
- EPF signatures incidentally solved TD-117 (wrong-type EPF) with no bespoke code.

## What Went Wrong
1. **The canonical-enum rename left a flag-gated straggler the test suite stayed green through.** The
   identity fact's IC-genuineness cap still keyed on the old `('low_confidence','not_an_ic')` strings —
   tests passed only because they fed *legacy* input values. A post-change `grep` for the old strings
   caught it before commit. Root cause: behaviour tests don't exercise every branch (esp. flag-gated /
   value-specific ones). Fix: after any value rename, grep the old values across the tree + keep an
   import/contract-surface test. (Same lesson recurred from the package-move close — reinforced.)
2. **Local SQLite was a migration behind after merging `main`, so the eval harness scored 0/335
   ("all errored") and looked broken.** Root cause: the merge pulled new migrations not applied to the
   throwaway-fixture DB. Fix: `manage.py migrate` after a merge before running the harness. Cheap,
   recorded.

## Design Decisions (logged in decisions.md)
Unified canonical outcome enum; signature-probability for standard docs (slip/cert/BC/EPF) vs holistic
for IC; EPF salary reverse-engineered from statutory rates with a `max()` tier-self-correction.

## Numbers
- 7 commits, 0 migrations, 0 deploys. Genuineness signature coverage: slip, cert, BC, EPF (all one band).
- Calibration corpora: 48 slips, 28 BCs, 13 EPFs — zero false positives on full genuine documents.
- Backend suite green (count recorded in memory/CLAUDE.md).

## Carried / NOT done (deferred)
- **Wire BC/EPF (and slip's already-wired) genuineness onto the live verdict via the signature path** —
  only results_slip is live; BC/EPF still run the holistic `doc_genuineness` in production.
- **Issue-2 build pass** — implement the finalised extraction changes (BC drop `bc_number`; EPF split
  employer/employee contribution totals + employer-number + the `max()` salary; drop the combined avg).
- **STR** signatures (the MySTR-screenshot vs MOF-letter split).
- **Layer-2 matching fixes** (parent-IC TD-119 etc.) + the harness genuineness cap (TD-121).
- FE i18n *labels* for the canonical statuses are wired to recognise non-genuine; per-status copy
  (suspect vs not_<type> Gopal messages) is the later help-engine work.
