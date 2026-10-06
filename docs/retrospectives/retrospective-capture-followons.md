# Retrospective — Capture-layer follow-ons (Sprint 2)

**Date:** 2026-06-11 · **Branch:** `sprint/capture-followons` · **Migration:** none

The three items deferred from / carried alongside the deterministic-capture sprint, done as one coherent follow-on.

## What Was Built

- **(1) IC leading-name-break fix** (correctness, the carried debt). `vision._extract_name` could reassemble a surname
  spilled onto the NEXT OCR line (trailing marker) but not a given name spilled onto the PREVIOUS line — so app #61's
  father IC ("SARAWANAN"\n"A/L SUPRAMANIAM") captured only "A/L SUPRAMANIAM". New mirror helpers `_LEADING_PARENTAGE`,
  `_preceding_givenname`, `_with_broken_name_parts` prepend the given-name line when the chosen name line STARTS with a
  parentage marker. `_extract_name` is the SHARED extractor for the applicant `ic` AND every `parent_ic`, so one fix
  covers all relationships; both break directions are regression-tested.
- **(2) P6 water-bill parser** (`doc_parse.py`, SOFT signal). The shared regulated Malay labels (`Bil Semasa` → amount,
  `Baki Terdahulu`/`Tunggakan` → arrears, under a `BIL AIR` header). Conservative — None → Gemini for an unrecognised
  layout.
- **(3) Cockpit capture-confidence badge.** "Exact read" (deterministic / label-anchored) vs "AI read" (Gemini) on each
  cockpit Documents-drawer row, from the `vision_fields.capture` tag the Sprint-1 seam already stores. No backend change
  needed — the admin serializer already exposed `vision_fields`.

## What Went Well

- **Real-file validation again caught the thing that matters.** The IC fix was validated by **rendering the two real
  prod IC PDFs (pypdfium2) and Vision-OCR'ing them**, then running the live `_extract_name` on that text — confirming the
  real OCR has the leading-break structure (`SARAWANAN`\n`A/L SUPRAMANIAM`) and that the fix reassembles it. That's
  stronger than the synthetic fixtures alone (which encode my assumption of the structure).
- **The capture-confidence surface was nearly free** — the `capture` tag was designed into the Sprint-1 seam and the
  admin serializer already passed `vision_fields` through, so item (3) was a type field + a badge + i18n.
- **The water parser stayed honest about its narrow coverage** — it deterministically handles the dominant Air Selangor
  PDFs and defers other companies + photos to Gemini, which is correct for a soft signal that should never degrade.

## What Went Wrong

- Nothing of note this sprint — the conservative None→Gemini contract and the per-item real-file validation kept each
  change low-risk; the full scholarship suite stayed green (1063 → 1067) across all three items. (The one judgement call
  worth recording: the water parser's coverage is narrow by design, so it is logged as a soft, Air-Selangor-first
  parser rather than a comprehensive one — silent under-coverage would have been the trap, so the CHANGELOG/retro state
  the limit explicitly.)

## Design Decisions

No new architectural decisions — these are instances of the Sprint-1 capture-layer decision (deterministic-first,
conservative None→Gemini). The IC fix mirrors the existing `_with_trailing_surname` pattern.

## Numbers

- +5 vision pytest (IC leading-break) + 8 doc_parse pytest (water + earlier). Full scholarship suite **1067** +
  courses/reports **1063** = **2130 backend pytest**; web jest ~297; i18n parity **2500×3**; `next build` clean.
- **No migration.** ~6 Vision OCR calls for validation (2 ICs + water samples), well inside the free tier.
