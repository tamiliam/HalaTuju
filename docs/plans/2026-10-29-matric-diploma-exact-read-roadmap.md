# Matriculation + polytechnic Diploma results read "Exact" — roadmap (2026-10-29)

**Status:** APPROVED by the owner 2026-10-29 (option 1: polytechnic Diplomas only). Trigger: BrightPath
request #49, triaged a BUG by the owner; we absorb the charge. Planned ~30 h. Template:
`docs/plans/2026-10-27-stpm-exact-read-roadmap.md` (same shape, same ground rules).

## Why
- `higher_results.extract` reads Matriculation and Diploma results by AI only (`capture='ai'`).
- They have no genuineness check: the reviewer always sees `higher_results_not_checked`.
- `results_kind.detect` misses transcripts whose title names no kind ("ACADEMIC TRANSCRIPT"). Request #49 was
  a Matriculation transcript like this. Live 2026-10-29: of 12 non-STPM `higher_results` docs, 3 have a blank
  `results_kind` (one polytechnic transcript whose Gemini read says diploma, one STPM certificate, one Exact
  STPM read).

## Live shape (2026-10-29, current docs only)
- `higher_results`: stpm 40 (31 Exact), matric 5, diploma 4, blank 3. Matric and diploma: 0 Exact.
- Local corpus `eval/fixtures/results_split/` (gitignored, PII): matric 3, diploma 5, asasi 1.
- The corpus is small (STPM had 39). The readers key on a SET of anchors and fall back to AI when unsure.

## Ground rules (from the STPM roadmap)
- Opus builder to a written brief; the lead verifies the diff and re-runs every gate.
- Adversarial review before every push (recognition and verdicts move).
- Bump `MODEL_VERSION` on any recognition change; `VERDICT_ENGINE_VERSION` when a band can move.
- `vision.py` and `_run_field_extraction_impl` are at their size ceilings: new readers live in new files;
  vision.py takes at most a one-line call.
- No re-extraction from a local checkout. Live re-reads only, with the job flags (TD-407).
- No PII in tests: synthetic twins only.
- Coordinate pushes with the other sessions.

## Sprints

### M1 — Corpus + OCR capture + kind gaps · low · ~4 h · paid: Vision OCR, a few cents
- Add the live matric/diploma docs to the local corpus; `capture_ocr` caches for all of them.
- `labels.json`: expected kind, name, CGPA, institution, subject–grade rows.
- `results_kind`: recognise a Matriculation transcript by its fixed markers (college name pattern
  "KOLEJ MATRIKULASI" / "MATRICULATION COLLEGE", KPM Bahagian Matrikulasi wording) and a polytechnic
  transcript by "POLITEKNIK" / JPPKK wording, so a title of "ACADEMIC TRANSCRIPT" alone no longer blanks.
  Backfill the blank `results_kind` rows (read-time classification, no re-extraction).
- **Done when:** every corpus doc has an `.ocr.txt` and a label; the #49 shape detects as matric.

### M2 — `matric_parse.py`: deterministic Matriculation reader · medium · ~8 h
- Text-first, like `stpm_parse`: name, NRIC, matric number, college, semester rows, subject–grade rows
  (A … F with A-, B+ …), PNGK/CGPA, co-curriculum.
- Unsure → nothing, falls back to Gemini. Never a wrong Exact.
- Wired into `higher_results.extract`; a hit stores `capture='deterministic'`. `PARSER_VERSION`.
- **Done when:** the matric corpus reads Exact with correct name/CGPA/grades; 0 wrong values; gates green.

### M3 — `poly_diploma_parse.py`: deterministic polytechnic Diploma reader · medium · ~8 h
- Same shape for the shared polytechnic transcript layout (provisional and final transcripts).
- Non-polytechnic diplomas (UiTM, private colleges) are NOT read here: they stay AI.
- **Done when:** the polytechnic corpus reads Exact; other diplomas still AI; 0 wrong values.

### M4 — Genuineness for Matriculation + polytechnic Diploma · medium · ~7 h
- Signature sets per family (issuer wording, crest, fixed footers), like `genuineness/stpm_doc.py`.
- Replace `higher_results_not_checked` for those two families only; others keep it.
- Bump `MODEL_VERSION` and `VERDICT_ENGINE_VERSION`.
- **Done when:** the owner has seen the before/after list of affected applications (ids only) before release.

### M5 — Live re-read + close · low · ~3 h · paid: Gemini fallback on misses only
- Targeted live `reextract_documents` for matric/diploma `higher_results` with the job flags.
- CHANGELOG, decisions, retrospective; completion report on #49 with TOTAL spent vs TOTAL planned.

**Total: 5 sprints, ~30 h.**

## Out of scope
- Asasi (1 corpus example) and non-polytechnic Diplomas: later, when examples exist.
