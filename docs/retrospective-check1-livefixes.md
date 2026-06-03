# Retrospective — Check-1 live-review fixes (2026-06-03)

Two fixes that came out of a live review of real applicant documents, closing the
Check-1 "good feedback on every document" arc for the Academic and Pathway facts.
Both shipped to prod (no migration in either).

## What Was Built

### (A) Academic OCR grade-transposition + ±-uncertain (`4391f54`, `ef92309`/`b370503`)
- Results-slip extraction now reads the **image** (Gemini multimodal via
  `vision._call_gemini_json(image=)`) instead of flat OCR text, fixing the A↔A+
  row scramble where adjacent science rows had their grades swapped.
- The slip's Malay **band** phrase is captured per subject (`{subject, grade, band}`)
  and cross-checked against the letter; a would-be mismatch whose letter and band
  **disagree** degrades to `uncertain` ("Please check", amber) — never a confident
  wrong mismatch.
- Follow-up: a mismatch whose grades share the same **base letter** (`_base_letter`
  strips ±) — an A+ vs A read, the OCR blind spot — also degrades to `uncertain`.
  A real different-base difference (A vs C) still flags a confident mismatch.

### (B) Pathway — confirm only on a real offer-vs-declared clash (`6a54699`)
- Replaced the always-ask `pathway_confirm` (which nagged every valid offer, even
  ones that matched) with a **lenient offer-vs-declared matcher**
  (`pathway_engine.offer_pathway_match` / `_distinctive_tokens` / `_declared_pathway`).
  It strips generic institution/qualification words and flags a mismatch **only when
  the distinctive place/field tokens are disjoint** — tolerant of naming quirks
  (KM Melaka ≈ Kolej Matrikulasi Melaka), red only when totally off (SMK Mentakab ≠
  Temerloh; Asasi Pintar ≠ Pertanian; Dip Horticulture ≠ Electricity @ UPM).
- `_verdict_pathway`: offer agrees / nothing to clash with → **verified** (the offer
  settles the pathway, no redundant nag); genuine clash → the reframed
  `pathway_confirm` query ("Is this where you're going?"); confirmed → verified.
- Layered, never a block: Check 1 marks the checklist rows red + an "Earlier you'd
  chosen…" note + a **soft Cikgu Gopal nudge** (`offer_pathway_mismatch` — reassures,
  never tells them to re-upload/edit); Check 2 (submit) is the confirm backstop that
  realigns the record and catches a sui-generis offer.

## What Went Well
- **Reusing the multimodal seam.** The image read was a one-argument extension of an
  existing `_call_gemini_json(image=)` path, not a new engine — kept the test surface
  (mock the seam) unchanged and added zero billable CI calls.
- **Layered honesty over bluffing.** Both fixes follow the same principle: when the
  signal can't be trusted (a ± OCR read, an offer that differs from the declaration),
  the system says "check this" / "confirm this" softly rather than asserting a student
  is wrong. No confident-but-wrong feedback survived.
- **The verdict recomputes at read time**, so the ±-uncertain rule applied to
  already-stored extractions with no re-run.

## What Went Wrong
1. **The first image-read prompt instruction emptied the results table.**
   - *Symptom:* a "drop band words from subject names" prompt hint caused one slip to
     extract an empty results array.
   - *Root cause:* prompt-engineering a post-processing concern the deterministic
     `_split_band` already handled — the model over-applied the instruction.
   - *Fix/lesson:* prefer deterministic post-processing over prompt instructions for
     anything a pure function can do; reverted the hint. (Already in `docs/lessons.md`
     scope — reaffirmed.)
2. **OCR can't guarantee the '+'.** Even the image read consistently dropped the '+' /
   'Ter-' on one watermarked Fizik row (letter AND band both read as A), so the band
   cross-check couldn't catch it.
   - *Root cause:* a watermark over the grade cell; no second independent signal.
   - *Fix:* the ±-base-letter rule — never bluff on an A+/A difference; the officer
     verifies by eye. Accepts the OCR ceiling rather than pretending past it.
3. **Wrong assumption about catalogue coverage (pathway).** I initially assumed the
   apply-form filter lacked pre-U institutions and designed around the gap.
   - *Symptom:* over-scoped the "editable chosen study" surface.
   - *Root cause:* didn't verify the catalogue before designing; the user corrected
     that the filter HAS all programmes/institutions, only naming quirks differ.
   - *Fix:* the matcher is lenient by design (red only when totally off), and the
     editable self-edit was deferred to Phase 2 — the system-driven Check-2
     reconciliation handles every case without the unbuilt picker.

## Design Decisions
- See `docs/decisions.md`: "Academic ±-grade difference degrades to uncertain" and
  "Pathway confirm only on a real offer-vs-declared clash (lenient matcher;
  editable self-edit deferred)".

## Numbers
- 574 scholarship pytest · 231 jest · `next build` clean · i18n parity 1848 (en/ms/ta).
- No migration in either fix. 4 deploys across the arc (3 academic-OCR convergence
  passes forced by real-document feedback + 1 pathway).

## Caveat carried forward
- A declared institution stored as a pure **abbreviation** (e.g. "UTeM") vs the
  offer's full name with no shared place token could false-flag a clash. Low risk —
  the catalogue stores full names, and a false clash is only a soft nudge + a confirm
  question (never a block); the student's Yes realigns. Tighten with an abbreviation
  map if real-use shows friction.
