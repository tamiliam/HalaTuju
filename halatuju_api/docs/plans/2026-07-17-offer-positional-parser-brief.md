# Brief — Positional (skew-robust) government-offer parser

**Status:** PROPOSED (not started). Own scoped sprint; NO migration. Owner-gated on a real-OCR
capture batch (see Blocker). Follow-up to the #47 clause-number fix (shipped 2026-07-17).

## Problem

The deterministic government-offer parser (`offer_parse._parse_stpm` / `_parse_matric` /
`_parse_poly`) reads values off the **flattened OCR text** — "the words on the same text-line as
the label." A Form-6 offer is a 2-D numbered-clause form: clause numbers (`2.1`…`2.6`) down the
left margin, labels beside them, values in a third column. When the photographed page is **skewed**
(a few degrees is enough), Google Vision's line-grouping snaps a left-margin clause number onto the
label's line instead of the real value — so `Bidang` (2.1) read `2.4.` and `Pusat Tingkatan Enam`
(2.2) read `2.5.` on app #47. A clean, upright scan (#99, same template) reads correctly with the
same parser. The failure is contingent on OCR reading order, which is a property of the individual
image's geometry, not the template.

The **clause-number guard** shipped 2026-07-17 makes this **correct** (rejects the `N.N.` junk →
defers the offer to Gemini, which reads the raw image and is skew-robust). This brief is the
**positive** fix: let the DETERMINISTIC path succeed on skewed photos too, reclaiming the "Exact"
read (and saving a Gemini call) instead of bailing out.

## Approach — reuse the slip parser's positional pattern

The SPM slip parser already solved this exact transposition class by going positional. Reuse it:

1. **Plumb word boxes into the offer branch** (small; mirror the `birth_certificate` branch,
   `vision.py:1919`). The `offer_letter` branch (`vision.py:1892`) currently passes only `_otext`;
   `pre_words` is already in scope (`:1860`), else `_vision_words(image)`. Each word carries
   `{text, cx, cy, h, angle}`.
2. **New positional reader** `offer_parse.parse_govt_offer_positional(words)` (STPM-first):
   - Group words into visual rows via `academic_engine._group_rows(words)` (reuse — it de-rotates
     by the median word angle when the skew crosses the gate, and geometry-groups otherwise).
   - Find each label row (`Bidang`, `Pusat Tingkatan Enam`, `Tarikh Lapor Diri`) and read the value
     from the tokens **to the RIGHT of the label on the same row band** — never a token from another
     row (that is what killed #47).
   - Handle **multi-line values**: the institution spans the value column across several lines
     (KOLEJ… / JALAN ISTANA / 41000 KLANG / SELANGOR / No. Telefon / E-mel) — read the value column
     down to the next numbered label, take the first line as the institution name.
3. **Keep the text parser + clause-number guard as the fallback** (Matric/Poly stay on the text
   path behind the guard until a positional reader is calibrated for them too).
4. Bump `PARSER_VERSION`; capture badge stays "Exact" on a positional read.

## Nuance — the de-rotation gate

`academic_engine._dominant_angle` gates de-rotation at **±25°** (tuned for phones turned *sideways*,
~90°). A few-degree skew (like #47) is **below** that gate, so rotation correction won't fire — and
does not need to: the win comes from **positional row-grouping** (pairing a label with the word on
its own horizontal band), not rotation. For a more steeply skewed page, tune/lower the gate for
offers. Calibration detail, decided against real OCR.

## Blocker / validation discipline (LOAD-BEARING)

- **Do NOT re-OCR locally** (destroys `vision_fields`; standing rule
  `memory/halatuju_never_reextract_locally.md`).
- The raw word boxes are **not persisted** on the offer path, and OCR heuristics **must be validated
  on real documents, not synthetic fixtures** (S15 lesson). So this needs a **real-OCR capture
  batch** of STPM offers from the LIVE service via `eval/capture_ocr.py`, frozen as fixtures like
  `tests/fixtures/slips/`, before the parser can be trusted. Owner runs the capture on prod.

## Scope / cost

- Effort: MEDIUM — small plumbing + a genuine STPM positional re-write + a real-OCR calibration pass.
- Value: MODERATE — reclaims deterministic "Exact" reads on angled photos (common) + saves a Gemini
  call. An optimisation on an already-correct baseline (the guard). Not urgent.
- Migration: none. FE: none. Genuineness `MODEL_VERSION`: untouched (extraction, not signature).

## Definition of done

STPM offers photographed at a mild skew read `stream`/`institution` correctly on the DETERMINISTIC
path (capture "Exact"), validated against a batch of real captured OCR fixtures; the clause-number
guard still catches anything the positional read can't lock (→ Gemini); `PARSER_VERSION` bumped;
tests on frozen real-OCR fixtures.
