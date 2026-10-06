# Retrospective — Salary-slip genuineness signature model (2026-07-09)

## What Was Built

The first genuineness model for **salary slips** — the one standard income document that had none
(`authenticity` was null on every `salary_slip` row, because unlike EPF/STR/JANM there is no single
issuer with a fixed letterhead).

- **`genuineness/salary_doc.py`** (`MODEL_VERSION 1.0.0`) — a statutory-payroll-grammar cascade over
  the OCR text → six families: `private` (≥2 of KWSP/SOCSO/EIS/PCB + wage labels) · `govt`
  (PENYATA GAJI e-Penyata title; civil-service pension, no EPF) · `singapore` (CPF/Pte Ltd) · `gig`
  (platform brand) · `informal` (wage labels, no scaffold → suspect, low ceiling) · `not_salary`
  (MyKad-in-slot / no payslip fields → reject). Dispatched from `genuineness.assess('salary_slip')`.
- **Calibrated on 99 live slips** — pulled read-only via `eval/fetch_corpus.py`, OCR'd via
  `eval/capture_ocr.py` (gcloud ADC), scored offline. Result: genuine 65 · suspect 26 · not_salary 8.
- **Wired live** (behind the already-ON `DOC_GENUINENESS_CHECK_ENABLED`): scored at extraction
  (`vision.py`, replacing the narrow `misfiled_as` backstop) → `vision_fields.authenticity`; the
  **#47 gate fix** (`income_engine.usable_salary_slip` used by `member_cluster_complete` +
  `services.income_doc_blockers` — a `not_salary` slip no longer satisfies the income requirement,
  SOFT: becomes a Check-2 re-upload, fail-open on unscored); the officer cockpit chip
  (`serializers.ApplicantDocumentSerializer.get_authenticity` now surfaces salary wrong-type).
- **#47 remediated end-to-end:** scored its MyKad-in-salary-slot (`not_salary`); moved the real
  payslip out of the EPF slot into the salary slot (data op); superseded the MyKad; owner Re-ran →
  now reads **genuine · private · gross RM5,187 · net RM4,463.70 · June 2026**.

Design + calibration captured in `docs/scholarship/salary-signature-model.md`.

(Earlier the same session, a separate small-change: the reviewer-unassign orphan fix — commit
`a93b2e25`, already in CHANGELOG + decisions.md — not part of this sprint.)

## What Went Well

- **Corpus-driven calibration caught a false assumption before shipping** (see below) — the model is
  grounded in real token frequencies, not intuition.
- **Reused the existing eval pipeline** (`fetch_corpus` → `capture_ocr` → offline scoring) — no new
  tooling; the OCR corpus is cached (gitignored) for the next re-calibration.
- **Soft by construction:** the income verdict cap already excludes the salary route
  (`verdict_engine._income_genuineness_docs`) and the anomaly `document_not_genuine` flag doesn't
  cover salary — so storing salary authenticity auto-downgrades nothing. No re-banding, no risk to
  genuine families; it feeds only the officer chip + the submission gate.

## What Went Wrong

1. **Claimed "no FE change needed" — but a serializer allowlist silently stripped salary
   authenticity.** *Symptom:* after wiring the scorer and writing `not_salary` to #47's slip, the
   cockpit still showed it "Verified" (the owner caught it in a screenshot). *Root cause:*
   `ApplicantDocumentSerializer.get_authenticity` carries a hard doc-type allowlist that omitted
   `salary_slip`; I verified the FE render path (`genuinenessFact` handles `not_`) but not the
   serializer that FEEDS it. Wiring a new genuineness-scored doc type touches **three** layers —
   extraction/scorer, the serializer allowlist, and the FE render — and I checked two of three.
   *Fix:* lesson added to `lessons.md`; when adding a genuineness doc type, grep every doc-type
   allowlist (`get_authenticity`, `_GENUINENESS_DOC_LABELS`, `_income_genuineness_docs`) as a checklist.

2. **The first calibration analysis over-counted the govt family via a loose token group.** *Symptom:*
   an ad-hoc analysis reported `GRED` as a 10/10 govt marker; the production scorer built on it found
   only 1–2 govt slips. *Root cause:* the throwaway analysis grouped `GRED` with `NO GAJI`/`KUMPULAN`,
   so the "10/10" hit-rate was the GROUP, not the literal token — `GRED` is actually in 1/99 files.
   *Fix:* before trusting a grouped calibration, confirm candidate tokens against ground-truth
   per-token file counts (`grep -il '<token>'`). The reliable govt marker turned out to be the
   `PENYATA GAJI` title (10/99). Corrected in code + spec before shipping.

## Design Decisions

(Logged in `docs/decisions.md`.) Statutory-grammar cascade over a single-issuer signature list;
informal → `suspect` but NOT surfaced to the cockpit (only `not_salary` shows) to avoid amber noise
on the many genuine B40 informal slips; soft wiring (gate excludes `not_salary`, fail-open; verdict
cap untouched); #47-only existing-data backfill (the other 7 `not_salary` are grandfathered/STR-
optional and 6 are cropped STR slips with false-red risk).

## Numbers

- Corpus: 100 live salary slips fetched, 99 OCR'd (4 HEIC/corrupt), calibrated offline (free — ADC
  Vision, inside the 1000/mo tier).
- 3 commits (`dda67aa6` scorer · `5595dc53` wiring+gate · `b4c4c889` serializer chip) + 2 MCP data
  ops for #47. No migration. FE unchanged (chip infra pre-existed).
- Tests: 16 new salary tests; full suite green (combined count in MEMORY.md / CLAUDE.md).
