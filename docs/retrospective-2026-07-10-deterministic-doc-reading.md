# Retrospective — Deterministic document reading: cert parser + capture labels + govt offer parser (2026-07-10)

## What Was Built

A live-review arc that started from one missing chip and grew into "read the standardised documents
DETERMINISTICALLY (Exact), not by Gemini (AI), wherever their format is fixed."

1. **SPM certificate parser** (`academic_engine.parse_spm_cert` + `ensure_exam_year`). A certificate
   (sijil) flattens in OCR into a SUBJECT block and a separate GRADE block (paired by index) — not
   subject+grade per row — so the slip parser (`parse_spm_slip`) recovered zero rows and bailed to
   Gemini, which dropped the cert's foot-of-page year (`Peperiksaan Tahun YYYY`), silently killing the
   exam-year ("old result") chip. The new parser reads the two blocks positionally, self-identifies
   ('layak dianugerahi'), and runs for ANY student — an STPM student's SPM cert included, independent
   of the profile `exam_type` gate that had skipped the SPM parser entirely. Conservative (None →
   Gemini). Validated on all 7 live certs. Wired cert-first + a year backfill on the Gemini path.

2. **Capture-confidence label overhaul** (officer cockpit). Shortened `Exact read`/`AI read` →
   `Exact`/`AI`; the badge now shows on EVERY read doc — field-extracted docs AND the identity ICs
   (read via the MyKad OCR path). Untagged older docs default by doc type: DETERMINISTIC-FIRST types
   (ic/parent_ic/results_slip/birth_certificate/str/epf) → `Exact`, Gemini-read types → `AI`. Backend
   now stamps the IC's `capture` (`deterministic` Vision OCR vs `ai` Gemini fallback).

3. **Government offer-letter parser** (`offer_parse.parse_govt_offer`). Deterministic STPM /
   Matrikulasi / Polytechnic reads — 71 of 90 live offers, previously all Gemini. A text-based offer
   parser (doc_parse P5) was retired 2026-06-18 for the 2-D layout, but issuer-by-issuer the identity
   (name/NRIC) + pathway/intake sit on same/adjacent lines or in the title, and the info-block fields
   (institution, reporting date) are recoverable per issuer. Self-identifying + conservative
   (None → Gemini unless name+nric+programme+intake read). University + PISMP (new format) stay on
   Gemini. Wired deterministic-first with a **merge over the prior fields** so an Exact read can never
   DROP a field the AI read had (the reporting-date bonus depends on `reporting_date`). Validated on
   the real corpus (30/32 parse, identity ~100%, reporting 28/30); it even fixed NRICs Gemini misread.
   **Backfilled 54 existing govt offers to Exact** via cached OCR + Supabase REST PATCH (free, no
   Gemini, no live re-extract — the parser needs only OCR text, so the corruption hazard doesn't apply).

No migration across the whole arc.

## What Went Well

- **Snapshot-based validation.** The eval pipeline (`fetch_corpus` → `capture_ocr`) stores each doc's
  current Gemini read, so I measured every parser field-by-field against the live reads BEFORE shipping
  — that's how the offer parser was tuned to identity ~100% and the reporting-date regression was caught.
- **The cert parser unblocked the offer parser.** Block-pairing proved the positional idea that the
  retired flattened-text P5 lacked; the offers then fell to a per-issuer text parse.
- **Conservative-by-construction.** Every parser returns None → Gemini on any ambiguity (mononym names,
  count mismatch), so the downside of a bad read is only "falls back to AI", never a wrong value.

## What Went Wrong

1. **I gave TWO wrong root causes for the missing cert chip before the right one.** First "old layout",
   then "the parser under-read the cert table" — but the doc's own `_slip_ocr_diag` said `not_spm_exam`:
   the STPM profile gate had skipped the SPM parser entirely. Root cause: I theorised from the OCR
   layout instead of reading the stored diagnostic first. Fix (lessons.md): when a read "failed", read
   the doc's own recorded reason (`vision_fields` diag / capture / authenticity) BEFORE hypothesising.

2. **The first offer wiring replaced fields wholesale — a latent reporting-date regression.** All 64
   live govt offers carry `reporting_date` (feeds the genuineness bonus); the deterministic parse misses
   it on ~2 layouts, so a wholesale replace would drop the bonus a band. Caught it by querying the field
   coverage before the backfill; fixed with a MERGE. Root cause: designed the switch-off-Gemini before
   checking what the current data would lose. Fix (lessons.md): before a change that OVERWRITES an
   extracted field set, query the current field coverage and merge-preserve.

3. **The capture-label tidy took four web deploys** (shorten → always-show → IC → deterministic-first
   defaults), each driven by the next screenshot, over the 2-deploy guideline. Root cause: I shipped the
   narrow fix each round instead of mapping the whole "every doc labelled by its true read method"
   matrix up front. Fix: when a display-consistency gap surfaces across a type dimension, enumerate the
   full doc-type matrix once and fix it in one pass.

## Design Decisions

(Logged in `docs/decisions.md`.) A separate block-pairing cert parser (not extending the slip parser);
doc-type-aware capture defaults as an FE heuristic for untagged docs (self-corrects on re-run);
government offers parsed by per-issuer TEXT lines (the OCR was parseable — no word boxes needed),
conservative with a merge to preserve prior fields; the existing-offer backfill done locally via cached
OCR + REST PATCH (the govt parse needs only OCR text, so it sidesteps the never-re-extract-locally hazard).

## Numbers

- 8 commits (`636d1d8f` cert · `5bb8d049`/`1a72219a`/`cb222d14`/`18f4512c` capture labels · `150df05c`
  offer parser · `25e5d2b4` merge fix; plus this close). No migration.
- Corpora calibrated (gitignored OCR): 7 certs, 99 results docs, 90 offers.
- 54 govt offers backfilled to Exact (0 failures, reporting_date preserved); 5 defer (mononym).
- Tests: +26 across cert/offer/IC-capture; full suite green (count in MEMORY.md / CLAUDE.md).
