# Retrospective — School-leaving certificate genuineness model + keep-better + duplicate collapse (2026-07-15)

Owner-driven, two linked asks off a live cockpit screenshot (app #66, Tharun's cert shown twice):
1. When a fresh school-leaving cert is uploaded, keep the better one and drop the old to Old/Replaced
   "as is done for all other docs".
2. Give the school-leaving cert its own genuineness signatures + variables, validated against the
   accumulated corpus.

## What Was Built

- **`genuineness/school_leaving_doc.py` (`MODEL_VERSION 1.0.0`)** — a deterministic signature scorer.
  School-leaving certs are **school-issued** (no single national issuer like the SPM slip), so the
  design is leaver-anchor-first + structural-labels-grade, the shape of the water-bill model
  (grammar-first), NOT an issuer cascade. Owner-specified signature set: title `SIJIL BERHENTI
  SEKOLAH` + No. Kad Pengenalan · Tarikh Lahir · Tempat Lahir · Tarikh Masuk Sekolah · Kelakuan ·
  Tarikh Berhenti · Sebab Berhenti. Statuses: genuine / suspect / **unrecognised (a free-form
  testimonial → defer, never fake)** / not_school_leaving_cert (MyKad or another known doc in the
  slot). A leaver anchor guarantees the doc is never rejected (mirrors water's "any water signal ⟹
  never rejected"). Registered in `genuineness.assess()`.
- **Extraction variables** trimmed to the owner set: student name · NRIC · school · kelakuan (added
  `nric` + `kelakuan`, dropped `year` + `catatan`) — schema + prompt hint in `vision.py`.
- **Keep-better made real (Task 1).** The scorer feeds `vision_fields.authenticity`, which
  `income_engine._doc_genuine_rank` already reads and `promotion.doc_quality` already ranks — so
  *no new keep-better code was needed*; giving the cert a genuineness score is what turned its
  quality axis from "usable + newest-id" into a real genuine-beats-suspect comparison. Cockpit chip
  surfaces ONLY the wrong-type reject.
- **`_collapse_duplicate_docs` (Task C).** The stage-judge-promote supersede is scoped to a
  `(doc_type, member, request_code)` slot, so the SAME cert requested twice by an officer (app #66:
  officer_1 + officer_9) left two live copies. New helper collapses academic single-per-person docs
  to the single best live copy across request codes, on upload.
- **`--doc-type` filter on `reextract_documents`** — a scoped, cheap re-extraction pass for
  calibration / a single-type rollout.

## What Went Well

- **Investigation before building paid off.** Querying the live corpus first revealed the real state:
  19 certs, field-extraction already working, but NO genuineness check (authenticity null on all) and
  NO stored OCR text. That reframed both tasks correctly (Task 1 wasn't broken — it just had no score
  to compare; Task 2's corpus couldn't be validated offline).
- **The soft design makes mis-scoring harmless.** The only user-visible effect is the red wrong-type
  chip; suspect/unrecognised/genuine all render nothing, and a genuine cert can't be rejected (leaver
  anchor). So the correctness risk was near-zero by construction — the calibration was confirmation,
  not a gate.
- **Calibration was decisive: 20/20 genuine, 0 false rejects.** The owner's revised signature set held
  across the whole corpus with no tuning. Persisting `markers.label_names` per doc gave a precise
  readback (which of the 8 signatures hit on each real cert) without needing the raw OCR text.

## What Went Wrong

- **The re-extraction trigger had no scoped path.** The cron endpoint (`CronRunView`) calls
  `call_command(job)` with no args, so it can't pass `--doc-type`, and it processes 20 mixed-type
  unprocessed docs per run — it would have churned hundreds of unrelated July uploads to reach the 19
  scattered certs. **Root cause:** `CronRunView` is arg-less by design; there's no first-class "run a
  scoped management command on the service" path. **Fix applied this sprint:** added `--doc-type` to
  the command AND ran the pass via an isolated one-off Cloud Run Job on the new image (env cloned from
  the api into a scratch file so secrets never hit the transcript; job + file deleted after). **System
  fix captured as a lesson** so the next scoped re-extraction reuses the pattern instead of
  rediscovering it.

## Design Decisions

- **Leaver-anchor-first, testimonial-defers (not fake).** A school-issued testimonial letter without
  the numbered-form grammar scores `unrecognised` (defer to reviewer), never a reject — a genuine
  leaver's letter must never be falsely rejected. See decisions.md.
- **Per-family scorer file, not an addition to `results_doc.py`.** Matches the recent salary / water /
  electricity convention (own file + own `MODEL_VERSION`).
- **Chip shows only the wrong-type reject.** Mirrors salary/utility — a thin/cropped or testimonial
  read is common for real B40 families, so hiding suspect/unrecognised avoids amber noise.

## Numbers

- +16 tests (`test_school_leaving_signatures.py`); 2519 scholarship pytest; golden masters intact
  (SPM 5319 / STPM 2026); NO migration.
- Calibration corpus: 19 certs (20 rows incl. the app-66 duplicate) → **20/20 genuine, 0 false
  rejects**; leaver anchor 20/20; labels 4–7; title 18/20.
- 1 deploy for the feature (`af6ef919`) + the close deploy (docstring/CLAUDE.md, no behaviour change).
