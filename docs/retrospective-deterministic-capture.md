# Retrospective — Deterministic label-anchored capture layer (Sprint 1: P0–P5 + #55 + UI)

**Date:** 2026-06-11 · **Branch:** `sprint/deterministic-capture` · **Migration:** none

The document-extraction audit found that most "AI-captured" docs are actually fixed-format standardised-issuer
documents. This sprint built a deterministic label-anchored capture layer that runs BEFORE Gemini, with Gemini as the
fallback for the unstandardised tail — turning the highest-volume doc types from AI-read to deterministic-read.

## What Was Built

- **P0 — scaffold** (`apps/scholarship/doc_parse.py`): `parse_by_labels(doc_type, text) -> dict | None` dispatcher +
  label helpers (`find_value`, `has`, `first_nric`, `first_amount`), wired into `run_field_extraction_for_document`
  deterministic-first (None → Gemini), tagging `vision_fields['capture']='deterministic'|'ai'`. Mirrors the existing
  results-slip pattern. Safe no-op until a parser registers.
- **P1 — STR**: all four MySTR surfaces; `source_type` (letter/semakan_status/dashboard/unknown) now DETERMINISTIC →
  retires the SARA→STR AI mis-pass (#63) AND closes the SALINAN-as-proof gap, both via the existing `_str_currency`.
- **P2 — TNB electricity**: `ALAMAT POS`→name+addr, `Caj Semasa`→amount, `Baki Terdahulu`→arrears, `TEMPOH BIL`→period.
- **P3 — KWSP EPF**: name/NRIC/employer/`JUMLAH SIMPANAN`/year/latest `CARUMAN`; mis-slotted Borang EC → None (detected).
- **P4 — JPN birth cert**: child + both parents via the `No. Kad Pengenalan` anchors (the child IC sits under
  `No. Daftar`); mononym-tolerant child; partial/mis-slot → None.
- **P4b — #55**: `father_via_bc` + `father_link` — a mononym student's father link via the BC (BC child=student AND BC
  father=earner IC), wired through `member_relationship_status` + both verdict routes. Closes #55 end-to-end.
- **P5 — offer letter**: GOVERNMENT templates only (JPPKK / Matrikulasi / Form 6 / IPG) — deterministic identity
  (name + 12-digit IC = the gate) + clean programme; universities + varied → None → Gemini.
- **UI**: income-wizard card titles name the earner ("Father's salary slip" / "EPF statement") in both routes.

Every parser is CONSERVATIVE — returns `None` (→ Gemini, unchanged behaviour) unless it clearly recognises the document.

## What Went Well

- **L86 was the spine of the sprint.** Every parser was validated against REAL OCR/text-layer samples (9 STR, 8 TNB,
  7 EPF, 8 BC, real offers), not just synthetic fixtures — and the real data caught bugs synthetic fixtures could not:
  a SALINAN mis-classed as semakan; a stray info-icon `i` read as STR status; the EPF employer grabbing `RINGKASAN` on
  image OCR; the offer IC mashed into the next word (`…2306NO`); a Matrikulasi programme swallowing a mashed single-line
  PDF. Each was fixed, then re-validated.
- **Deterministic capture IMPROVED on Gemini** on several digital PDFs Gemini had left blank (TNB ×2, EPF ×1) — and
  detected mis-slotted uploads (Borang EC in the EPF slot; an IC in the BC slot) for free.
- **The conservative None→Gemini contract** kept the blast radius near-zero: every full scholarship-suite run stayed
  green through 6 phases (1042 → 1059) with no regression, because an unrecognised layout degrades to exactly today's
  behaviour.

## What Went Wrong

- **The offer parser cost the most iteration because IMAGE OCR and MASHED PDFs break naive label-anchoring.** Symptom:
  the JPPKK image grabbed a junk programme from a body sentence; the Matrikulasi PDF returned None (the 12-digit IC was
  mashed into the next word, so `\b\d{12}\b` found no boundary) and, once fixed, the Jurusan value swallowed the whole
  single-line PDF. Root cause: I reused PDF-clean assumptions (label then clean value) on text where pypdf concatenates
  a whole page onto one line and where image OCR reorders label/value pairs. Fixes: digit-boundary IC regex
  (`(?<!\d)(\d{12})(?!\d)`); a `_clean_short` guard that rejects a value that swallowed later labels; require a clean
  programme to emit (messy → defer to Gemini). **System lesson (logged):** a parser validated only on clean digital
  PDFs is not validated — test it against the *mashed* pypdf output and the *image* Vision OCR of the same doc type
  before trusting it, because those are the two shapes production actually sends.

## Design Decisions

See `docs/decisions.md`: "Deterministic label-anchored capture runs BEFORE Gemini" (the seam + conservative contract +
the STR source_type/SARA/SALINAN consequence). The offer parser's government-only scope is an instance of the same
principle (deterministic for standardised issuers; Gemini for the varied tail).

## Numbers

- doc_parse: +36 pytest (13 scaffold + 6 STR + 4 TNB + 4 EPF + 4 BC + 5 offer). income/verdict: +9 (#55).
- Full scholarship suite **1059** + courses/reports **1063** = **2122 backend pytest**; web **297 jest**; i18n parity
  **2496×3** (UI titles); `next build` clean. **No migration** (the `capture` tag lives in the existing `vision_fields`).
- Billable: ~30 Vision OCR calls all-sprint for validation (well inside the free 1000/month tier).

## Post-deploy follow-ups

- The deterministic path applies to NEW uploads + cockpit "Re-run" automatically. A backfill `re-run` of existing
  income docs would populate the `capture` tag + deterministic `source_type` retroactively (outcomes are already correct
  today — the legacy SALINAN reads `unconfirmed` because its status is blank — so this is robustness, not a fix).
- Deferred: **water bill** (per-company, soft signal) — P6, not built this sprint. The officer **capture-confidence
  surface** (show `deterministic|ai` on the cockpit doc row) is a small follow-on.
- Tamil first-draft on the new `salaryTitle`/`epfTitle` keys → fold into the Tamil refine queue.
