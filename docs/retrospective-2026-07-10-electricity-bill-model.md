# Retrospective — Utility-bill arc: electricity genuineness model + Extraction-v2 (2026-07-10)

**Commits:** `905c9926` (staleness/currency) · `846d7c7d` (catalogue) · `2a62dd16` (genuineness model
+ Extraction-v2) · `cb876ca9` (wrong-type chip). **Migrations:** none. **MODEL_VERSION:** new per-family
`electricity_doc.MODEL_VERSION = 1.0.0` (no cross-family bump). **Tests:** 2277 scholarship + 489 jest.

## What Was Built

A three-part response to a real stuck student (#63 Jayashree) and an owner request to model electricity
bills the way the salary agent modelled payslips.

1. **Staleness/currency fix (905c9926).** The recheck looped a student re-uploading the same ~4-month
   bill: `_bill_needs_upload` re-raised on staleness, and each clean upload resolved-then-re-raised.
   Fix: we still **ask** for a bill within 3 months, but **accept** a dated bill within 6
   (`_UTILITY_ACCEPT_MONTHS`); the officer chip keeps the 3-month line. Currency is anchored on
   `bill_date` (Tarikh Bil — a point-in-time date) when present, else the Tempoh Bil period
   (`_bill_as_of`). #63 self-heals on the next Action-Centre load.
2. **Genuineness signature model (2a62dd16).** `genuineness/electricity_doc.py` (`MODEL_VERSION 1.0.0`),
   mirroring the salary model's shape but using **issuer identity (TNB/SESB/SESCO) + Malay bill-field
   grammar** (electricity has a dominant issuer, unlike salary's thousand payroll formats) → genuine /
   suspect / `not_electricity_bill`. Wired SOFT (no submission gate); cockpit shows the wrong-type
   reject; keep-better ranking picks it up via `_doc_genuine_rank`. Extraction-v2 added `bill_date` /
   `account_no` / `usage_kwh` / `tariff`.
3. **Wrong-type chip (cb876ca9).** The utility branch of `documentFacts` was the ONE doc-type branch
   that never pushed the shared genuineness fact (`gf`), so `not_electricity_bill` computed the red
   "Wrong type" chip but silently dropped it (row rolled up to amber "Check"). Now it pushes `gf` +
   caps the reads, identical to salary/EPF/IC.

## What Went Well

- **Calibrate-on-real-OCR, not domain guessing.** Reusing the salary agent's `eval/` pipeline
  (`fetch_corpus` + `capture_ocr`, read-only, gitignored snapshots) I measured signature hit-rates on
  27 → then 90 real bills before finalising thresholds: NO AKAUN 100%, TNB/ELEKTRIK 92%, Tarikh Bil
  88%. Result: **0 false-rejects** on the genuine corpus, and the reject floor validated on real +
  synthetic wrong-types. The "issuer marker ⟹ never rejected" rule fell straight out of the data
  (every genuine bill had one).
- **Per-family `MODEL_VERSION` (the salary agent's choice) dissolved the collision I'd feared.** Two
  agents adding signature families never fight over one version or one re-run — each family versions +
  re-scores independently. Waiting for the salary model to land first (owner's call) was the right
  sequencing.
- **The live test paid off immediately.** #83 turned out to be a genuine PBA **water bill** in the
  electricity slot — the model caught it, AND it surfaced that her two bills are swapped (a real
  verification finding, not just a model demo).

## What Went Wrong

- **`git add -A` swept another agent's untracked file into my commit (earlier in the arc).** *Symptom:*
  the utility-staleness commit initially included `docs/scholarship/salary-signature-model.md` (the
  salary agent's in-progress spec). *Root cause:* used `-A` in a repo shared with another live agent
  without worktree isolation — the exact hazard the sprint-close workflow warns about. *Fix applied:*
  caught it in the commit warning, `reset --soft`, unstaged the file (preserved untracked), re-committed
  with explicit paths. *Prevention:* for the rest of the arc I staged **explicit paths only**; the
  lesson is logged so it's not re-learned.
- **The first live test showed only an amber "Check", not the red chip I'd promised.** *Symptom:* the
  serializer surfaced `not_electricity_bill` but the cockpit rendered a soft "Check". *Root cause:* the
  utility branch of `documentFacts` never pushed the genuineness `gf` — every other branch did, so no
  test/type ever caught the omission. *Fix:* push `gf` in the utility branch. *Prevention:* lesson
  logged — when a shared per-doc fact (genuineness) exists, audit that EVERY `documentFacts` branch
  emits it, not just the "main" ones.

## Design Decisions

See `docs/decisions.md` (×3): (1) issuer-identity fingerprint for electricity (vs salary's
statutory-grammar) — single dominant issuer; (2) SOFT, no submission gate for bills (utility bills are
soft signals — unlike the salary #47 gate); (3) natural rollout over a forced backfill (fail-open on
unscored bills; owner's call).

## Numbers

- 4 commits, 0 migrations. New: `electricity_doc.py`, `test_electricity_signatures.py`, 4 extraction
  fields, the wrong-type chip, `_UTILITY_ACCEPT_MONTHS`/`_bill_as_of`. 2277 scholarship + 489 jest.
- Corpus (90 live/historical bills): 87 genuine · 1 suspect · 2 not_electricity_bill.
