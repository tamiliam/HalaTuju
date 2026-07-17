# Implementation Brief — Offer-Extraction Root Cause + Sponsor Card Data Fix (UPSTREAM-FIRST)

**For:** the implementing agent (Opus 4.8), in `c:\Users\tamil\Python\Production\HalaTuju`
**Shape:** ONE sprint, one deploy, NO migrations. Owner-diagnosed 2026-07-16 from live cards + cockpit; **owner-directed 2026-07-16: the fix is UPSTREAM (extraction + application data), with the downstream display chain as defence-in-depth only** — this follows the standing house principle (fix the SYSTEM first; per-case data correction is the last step).

## Context — where the fault actually lives

The sponsor card for app **#125** shows the institution as its programme title and the "Tarikh dan Masa Daftar…" line as its institution — and the COCKPIT shows the same wrong "Chosen Programme: Politeknik Sultan Idris Shah" **with a verified tick** (the pathway compare matched the wrong values against copies of themselves, since both sides derive from the same extraction). Code trace: `student_offer_check` (`apps/scholarship/pathway_engine.py:314-387`) does no parsing — it reads `doc.vision_fields.fields.programme/.institution` AS STORED BY THE DOCUMENT EXTRACTION, and the confirm path (`services.py:~1088-1096`) copies them into `chosen_programme`. **The mis-slot happened at extraction time** for #125's offer letter (an Asasi Teknologi Kejuruteraan / Asasi TVET offer at Politeknik Sultan Idris Shah); app **#102**'s Diploma offer (Politeknik Ungku Omar) extracted cleanly — the control case. Note: #125's `reporting_date` extracted CORRECTLY (15 Jun 2026; no countdown on its card only because the date is past). Two further downstream defects ride along: the pre-U fallback leaks secondary-school names onto sponsor cards (privacy — against the serializer's own allowlist promise), and empty course+field renders "—" while `pre_u_choice`/`pre_u_track` sit unused.

## Phase 1 — ROOT-CAUSE INVESTIGATION (required first; evidence before code)

1. Pull the stored extraction for #125's offer document vs #102's — `vision_fields` (fields + extractor/version markers + `_ocr_diag`-style diagnostics) and the stored raw OCR text/debug rows. Use the live DB (Supabase MCP) / cockpit; NEVER re-extract locally (standing rule — a local run destroys `vision_fields`).
2. Determine WHICH extractor produced each (deterministic govt-offer parser vs Gemini path — the 2026-07-10 deterministic-doc-reading work stamps markers) and WHY #125 mis-slotted. Expected shape (verify, don't assume): the Asasi/politeknik letter layout puts the institution where the parser expects the programme, and the next captured line ("Tarikh dan Masa Daftar…") lands in the institution slot — a label-anchoring failure (house lesson: anchor every value to ITS label, never positional grabs).
3. **Cohort sweep:** find every application sharing the failure signature — `chosen_programme.course_name` matching a known-institution shape, and/or `chosen_programme.institution` matching date/`Tarikh` patterns — plus dash-title and school-name cards. Output a report table: app id, extractor+version, offer layout family, current vs expected values. This report is a deliverable (goes in the retro) and drives Phase 3.

## Phase 2 — PARSER FIX (the system fix)

Fix the extraction for the identified layout family in the deterministic offer parser (label-anchored capture per the house lesson). Add the REAL #125 raw text (from the stored OCR) as a fixture test alongside the existing offer-parser fixtures; cover the layout family, not just the one letter. **Bump the parser's version marker per the doc-recognition versioning rule** (any change to a doc-recognition model bumps its version so re-runs are traceable). If Phase 1 shows the bad slots came from the Gemini path instead, tighten the extraction prompt/normaliser for the same signature and version-stamp likewise.

## Phase 3 — UPSTREAM DATA CORRECTION (sanctioned path only)

For every app in the Phase-1 report: re-run extraction for the affected offer documents **via the existing live-service re-run machinery only** (cockpit Re-run / `reextract-offers`-style command ON the service) — never locally. Apply the merge-preserve discipline (house lesson: count field coverage before/after; deterministic-wins-merge so a re-run never drops a field the old read had — e.g. `reporting_date`). Then re-run the confirm autofill so `chosen_programme` re-derives, and let the pathway checks re-derive their ticks. **Acceptance for #125: Chosen Programme = "Asasi Teknologi Kejuruteraan" (Asasi TVET) at institution "Politeknik Sultan Idris Shah", on the cockpit AND the sponsor card.** #102 must be byte-identical before/after (control).

## Phase 4 — DOWNSTREAM DEFENCE-IN-DEPTH (secondary to Phases 1-3; still required)

These guards ensure no future extraction defect ever reaches a sponsor again — they are the safety net, NOT the fix.

### 4a — read-side derivation (serializers.py; the allowlist stays an allowlist)

- **`get_course` resolution order:** (a) catalogue course name via `chosen_programme['course_id']`; (b) `chosen_programme['course_name']` ONLY if it passes sanity (not equal/near-equal to the resolved institution string; no date/`Tarikh`/time patterns); (c) canonical pre-U label from `pre_u_choice` + `pre_u_track` with proper display names — "STPM · Sains", "Matrikulasi · Perakaunan", "Asasi …" (build the small display map; British-cased; reuse existing track vocabularies — grep for the pre_u_track choices); (d) the field taxonomy display name for `field_of_study`; NEVER `''` when any of these exist.
- **`get_institution` resolution order:** (a) catalogue institution via `course_id`; (b) `chosen_programme['institution']` ONLY if sane (no date/`Tarikh` patterns) AND not school-like; (c) `pre_u_institution` ONLY if not school-like; else `''`.
  **School-block rule (enforces the existing promise):** reject values matching secondary-school patterns — `\bSMK\b`, `\bSJK\b`, `\bSMJK\b`, `Sekolah Menengah`, `Sekolah Jenis` (case-insensitive). Politeknik / Universiti / Kolej Matrikulasi / Kolej Tingkatan Enam / `\bKTE\b` / IPG etc. pass. Put the pattern list in ONE named constant with a docstring citing the allowlist promise; unit-test both directions.
- Keep every derivation inside the serializer's explicit-allowlist style with docstrings updated.

### 4b — write-side guard (services.py offer-confirm path ~:1088-1096)

Before storing: (a) if the parsed `institution` contains a date/`Tarikh` pattern, run it through the existing `pathway_engine.parse_reporting_date` — a parsed date fills `application.reporting_date` (only when currently null) and the junk is NOT stored as institution; (b) if `programme` ≈ `institution` (or matches a known-institution shape while `institution` is junk), store what is trustworthy and leave the rest '' rather than writing garbage. Never let a value the read-side would reject be written. Log a warning naming the doc id when the guard fires (ops visibility, no PII beyond the app id).

### 4c — residual repair command (only for rows Phase 3 cannot re-run)

Phase 3's live re-run is the primary correction path. `repair_chosen_programme` with `--report` (default) and `--apply` exists ONLY for rows the re-run cannot fix (e.g. the offer document is gone or unreadable):
- **Report:** every application whose `chosen_programme` values fail the Fix-1 sanity/school rules, or whose card would title-dash — with current values, the proposed repaired values (derived from the offer's already-stored extraction fields / the Fix-1 chain), and `reporting_date` fills. NO writes.
- **Apply:** performs exactly the reported repairs. NEVER re-runs Vision/Gemini extraction (standing rule: local re-extraction destroys `vision_fields`; this command only re-reads stored fields). Owner runs report → reviews → apply, via the internal cron/management path on the live service.
- Register it in `CronRunView.JOBS` only if the existing convention requires; otherwise document the run command in the retro.

### 4d — frontend no-dash rule

The pool card and detail must NEVER render a `'—'` placeholder: a missing course line falls back per Fix 1 server-side; if `institution` is empty the line shows state only; empty state shows nothing. Mirror of the Part-2 email rule. Jest cases for each omission.

## Tests & verification

- Anonymity suite: extend with the school-block cases (an SMK in `pre_u_institution` never reaches the card) — this is now a PRIVACY test, mark it as such.
- Unit tests: full derivation matrices for course/institution (catalogue, sane free-text, junk free-text, pre-U label, taxonomy fallback); write-guard cases (Tarikh string → reporting_date filled, junk not stored); repair command report/apply on fixtures reproducing the three live bugs.
- Full pytest + jest + `next build`; after push verify build by SHORT_SHA (`gcloud builds list --project gen-lang-client-0871147736 --account tamiliam@gmail.com`).
- Live smoke: the three owner-reported cards (title = real programme or pre-U label; no SMK anywhere; no dashes; countdown appears once repair fills `reporting_date`) — run the repair report, owner approves, apply, re-check the cards.

## Out of scope

Offer-parser (vision/doc_parse) accuracy improvements (the guard + repair contain the damage; parser work is its own future fix); My Students page; email Part-2 content (already specified in the pool brief).

## Sizing & risks

~10–14 files. Risks: (1) over-aggressive school-block hiding a legitimate institution — the pattern list is conservative + unit-tested both ways, and the audit report surfaces every blocked value for owner review; (2) repair touching the wrong rows — report-first, owner-gated apply; (3) breaking pool tests that pinned old fallbacks — update deliberately, never weaken the anonymity suite.
