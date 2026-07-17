# Retrospective — Offer-extraction root cause + sponsor card data fix (upstream-first) — 2026-07-17

Brief: `docs/plans/2026-07-16-sponsor-card-data-fix-brief.md`. One sprint, one deploy, NO
migration. Owner-diagnosed from app #125's card + cockpit. Fixed UPSTREAM (parser + data) with
the read/write chain as defence-in-depth.

## Phase 1 — root-cause investigation (evidence first)

**#125 vs #102 (control), stored extraction:**

| App | capture | programme (stored) | institution (stored) | reporting_date |
|-----|---------|--------------------|-----------------------|----------------|
| 125 | **deterministic** | `POLITEKNIK SULTAN IDRIS SHAH` ← an institution | `Tarikh dan Masa Daftar: 15 JUN 2026 (8.00 PAGI…)` ← a date | 2026-06-15 ✓ |
| 102 | ai (Gemini) | `DEE - DIPLOMA KEJURUTERAAN ELEKTRIK DAN ELEKTRONIK` ✓ | `POLITEKNIK UNGKU OMAR (POLITEKNIK PREMIER)` ✓ | 2026-06-20 ✓ |

**Which extractor + why:** #125 was read by the **deterministic govt-offer parser**
(`offer_parse.parse_govt_offer` → `_parse_poly`); #102 by Gemini (clean). The poly parser pairs
a **block-grouped** layout (all labels, then all values) via `_info_block_pairs` and zips by
index. #125's JPPKK **Asasi-TVET-at-Politeknik** letter is **interleaved** (label, value, label,
value): the real programme value sat *between* the `Program` and `Institusi` labels, so the zip's
trailing value block held only `[POLITEKNIK SULTAN IDRIS SHAH, "Tarikh dan Masa Daftar…"]` →
institution paired into the programme slot, the date line into the institution slot. A
label-anchoring failure, exactly the house lesson. #125's `reporting_date` was extracted
correctly (past date → no countdown on the card, which is right).

**Note (evidence gap):** the deterministic offer path does **not persist raw OCR** in
`vision_fields` (keys: error/fields/capture/warnings/authenticity/student_verdict — no `text`),
so the exact #125 bytes couldn't be pulled. The Phase-2 fixture faithfully reproduces the stored
mis-slot *signature* (the interleaved layout) rather than the literal bytes.

**Cohort sweep — TWO distinct faults:**

| Signature | Apps | Nature |
|-----------|------|--------|
| **A — corruption** (institution-as-programme / date-as-institution) | **#125 only** | genuine data corruption → parser fix + data repair |
| **B — school leak** (Form-6 SMK name in the institution slot) | ~19 STPM: #10,14,18,22,25,27,55,56,57,59,68,70,83,90,96,98,100,116 (+#43 `pre_u_institution` only) | privacy — the school must never cross to a sponsor; legit officer data otherwise |

Pooled (sponsor-visible) among B: **#10, #18, #25, #83** (awarded/recommended) — these cards
were exposing secondary-school names to sponsors until this deploy. #43's `chosen_programme.institution`
is an IPG (legitimate post-secondary — passes the block); only its `pre_u_institution` is a school.

## Phase 2 — parser fix

`_parse_poly` now handles BOTH layouts: block-grouped (unchanged zip) AND interleaved (per-label
recovery — read the value on/after the `Program` label when the zip leaves it empty, rejecting a
value that is itself a label / institution / date). `_guard_poly_slots` enforces the invariant:
a date/'Tarikh' value is never an institution, an institution-shaped value is never a programme.
`PARSER_VERSION = '1.1.0'` stamped on every result (`_offer_parser_version`) per the
doc-recognition versioning rule. New fixture `POLY_ASASI_INTERLEAVED` (the #125 signature) now
reads cleanly: programme `ASASI TEKNOLOGI KEJURUTERAAN`, institution `POLITEKNIK SULTAN IDRIS SHAH`.

## Phase 3 — upstream data correction

`repair_chosen_programme` re-derives from **stored fields + catalogue only** (NEVER re-OCRs).
#125 had `course_id=FB0500001` → catalogue name **"Asasi Teknologi Kejuruteraan (Asasi TVET)"**;
the institution-shaped `course_name` ("Politeknik Sultan Idris Shah") IS the real institution
(the catalogue lists FB0500001 at 10 polytechnics, so course_id can't disambiguate — the offer
is the only source). Applied via audited MCP (only #125 matched signature A):
- **Before:** course_name = "Politeknik Sultan Idris Shah", institution = "Tarikh dan Masa Daftar…"
- **After:** course_name = "Asasi Teknologi Kejuruteraan (Asasi TVET)", institution = "Politeknik Sultan Idris Shah", reporting_date = 2026-06-15 (unchanged). **Acceptance met.**
- **#102 control: byte-identical before/after** (verified — never written).

## Phase 4 — defence-in-depth

- **4a read-side** (`card_display.resolve_course`/`resolve_institution`): catalogue → sane
  free-text → pre-U label → taxonomy display name; institution catalogue-single → sane free-text →
  pre-U, each behind `looks_like_date`/`looks_like_school`/`looks_like_institution`. **`SCHOOL_BLOCK_RE`**
  (one named constant, docstring cites the allowlist privacy promise) drops SMK/SJK/SMJK/Sekolah
  Menengah/Jenis; Politeknik/Universiti/Kolej Matrikulasi/KTE/IPG pass. This alone fixes all ~19
  school-leak cards + #125's display at read time.
- **4b write-side** (`services.confirm_pathway` + `autofill_pathway_from_offer`):
  `sanitise_offer_slots` cleans the pair before storing; a mis-slotted 'Tarikh' value fills
  `reporting_date` (when null) instead of being written as institution; a warning logs the doc id.
- **4c** `repair_chosen_programme --report/--apply` — corruption-signature rows only; a school in
  the institution slot is **left alone** (legit officer data; read-side blocks it). No re-extraction.
- **4d frontend**: the browse card's `'—'` fallback removed (mirrors the Part-2 email rule).

## Decisions
- **Schools stay in storage, blocked at the sponsor boundary.** A Form-6 school is real officer
  data (cockpit/verification use it); the privacy fix is read-side, not a data wipe. The repair
  command never deletes a school.
- **The deterministic parser recovers or defers, never junk-locks.** When it can't read a coherent
  programme it returns None → Gemini (which handled the clean control), rather than emitting an
  incoherent pair.

## Numbers
- **2692 scholarship pytest** (+18: card_display matrices, school-block privacy both ways,
  sanitise, repair report/apply on the bug shapes, the #125 parser fixture) + **584 jest**
  (+ no-dash); `next build` clean. One deploy (api rebuild — serializer/services/parser changed).
- Prod data op (MCP, audited): #125 chosen_programme repaired; #102 control untouched.

## Carries (owner)
- The ~19 STPM school-leak cards are now blocked read-side; no data change needed. If you ever
  want the officer cockpit to show a cleaner pre-U label instead of the raw school, that's a
  separate cockpit-display choice (out of scope here).
- Optional: run `python manage.py repair_chosen_programme` (report) on the live service
  periodically — it's the backstop for any future corruption the write-guard doesn't catch.
- Positive deterministic reading of more offer layouts remains future parser work (the guard +
  defer + read-side resolution contain the damage today).
