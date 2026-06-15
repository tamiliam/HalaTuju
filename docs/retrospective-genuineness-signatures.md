# Retrospective — Document genuineness signatures + academic slip fixes (2026-06-16)

Branch `feature/doc-eval-harness`; 3 commits `f57f343` → `c788c8e`; NO migration; not deployed.

## What Was Built
- **A `genuineness/` package** — one home for every "is this document genuine?" check:
  `ic.py` (MyKad markers), `supporting_doc.py` (STR/BC/EPF), `results_doc.py` (the new slip/cert
  signature scorer), shared `bands.py`, and an `assess()` entry point. `ic_genuineness` +
  `doc_genuineness` moved out of `vision.py` (re-exported there for back-compat). Behaviour-preserving
  relocation, bracketed by before/after tests.
- **A probabilistic SIGNATURE scorer for SPM slips + certificates** (`results_doc.signature_genuineness`).
  Two per-type signature lists (mostly fixed printed strings → deterministic OCR-text matching, plus two
  visual signatures — QR + Jata Negara crest — from one focused multimodal read). Weighted-fraction
  probability → soft bands (suspect <0.35 · review 0.35–0.70 · genuine ≥0.70), **calibrated on the real
  48-doc corpus** (46 genuine 0.56–0.80, 1 typed fake 0.04; zero misclassifications).
- **Live wiring (results_slip only):** the upload path scores signatures instead of the old holistic
  `doc_genuineness` read; the new `suspect` band rides the same SOFT cap + officer flag. OCR failure → no
  signal. STR/BC/EPF unchanged.
- **Academic fix #1:** an undeclared extra subject on the slip is now a SOFT discrepancy (Gopal's existing
  `/profile` nudge + Academic "review" + Check-2 follow-up), no longer a document mismatch / submission block.
- **Name fix #2:** strip a leaked `NAMA :` field-label from an extracted candidate name before the token-set
  match (fixed a genuine slip falsely flagged name_mismatch).
- **Harness tooling:** `eval/capture_ocr.py` (Cloud Vision OCR via gcloud ADC, cached) + `eval/calibrate_signatures.py`.

Tests: +40 across the work (scorer, import/contract surface, suspect cap/flag, live wiring, visual credit,
academic + name fixes). Full scholarship suite **1287 passed**.

## What Went Well
- The eval harness paid for itself: the hypothesis ("masthead + QR/serial separates genuine from fake") was
  *tested against real data* and the threshold calibrated on the labelled corpus, not guessed.
- The owner's "use probability, not yes/no, and handle a cropped photo" reframing made the design robust:
  a genuinely cropped slip lands in soft "review", not "suspect".
- Before/after characterization tests made the package relocation safe and caught a real bug (below).

## What Went Wrong
1. **I audited 47 documents by eye and wrongly condemned a24 (a genuine cropped slip) as a fake.**
   Root cause: I substituted my own visual judgement for a system — exactly the manual, non-reproducible
   work the harness exists to replace. Fix: built the deterministic signature scorer so the *system* labels;
   a24 now correctly scores 0.56 → "review". Lesson recorded.
2. **The package move left a flag-gated `NameError` the behaviour tests couldn't catch.** `vision.py` still
   referenced `_GENUINENESS_DOCS` (moved out) on a line that only runs when `DOC_GENUINENESS_CHECK_ENABLED`
   is ON — off in tests, so 1267 green hid a prod crash. Root cause: behaviour tests don't exercise
   flag-gated branches. Fix: a straggler `grep` for moved names after the move + an import-surface test that
   pins `vision._GENUINENESS_DOCS` resolves. Lesson recorded.
3. **A naive deterministic QR detector (cv2) failed on 85% of genuine photos.** Root cause: assumed "QR is a
   machine token, so decode it" — but cv2 can't decode a blurry phone-photo QR. Fix: ask a multimodal model
   whether a QR is *present* (robust) rather than decoding it; the cv2 path was abandoned (deps not added to
   requirements). Lesson recorded.

## Design Decisions
Logged in `docs/decisions.md`: probabilistic signatures over a holistic AI read; the `genuineness/` package;
`suspect` rides the same soft cap; undeclared subjects are soft.

## Numbers
- 3 commits, 0 migrations, 0 deploys. ~17 files. Scholarship suite 1287 passed.
- Corpus: 48 results-slip docs (46 genuine, 1 fake, 1 cropped-genuine), 5 of them certificates.
- Signature calibration: genuine 0.56–0.80 vs fake 0.04; bands suspect/review/genuine = 0.35/0.70.
