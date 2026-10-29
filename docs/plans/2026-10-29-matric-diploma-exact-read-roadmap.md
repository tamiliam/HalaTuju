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
- **BUILT 2026-10-29** (branch `m1-matric-diploma-kinds`, not pushed). Notes:
  - Corpus now 9 Matriculation + 8 Diploma + 1 Asasi pages, every one with `.ocr.txt` and a
    `<key>.expect.json` label (gitignored; the committed `labels.json` is the PII-free verdict
    harness and has no results entries). Labels are seeded from the stored read and OCR-checked;
    `unverified` lists 4 fields to hand-check before M2 scores against them.
  - **Polytechnic is rarer than planned:** of the 4 LIVE diplomas, all are UiTM; the one live
    polytechnic transcript is the blank-kind row (#317). Corpus polytechnic: 4 (one a portal
    screenshot that prints no "POLITEKNIK"). M3 has 3 printed transcripts to build on.
  - The OCR-text detector already read every corpus Matriculation page right; the gap was the
    stored-read path (`detect_from_fields`: no institution, no subject) — the path #49 took.
  - Ruling and backfill: `docs/decisions.md` 2026-10-29. Production step for the lead:
    `python manage.py backfill_higher_results_kind` (report), then `--apply`.

### M2 — `matric_parse.py`: deterministic Matriculation reader · medium · ~8 h
- Text-first, like `stpm_parse`: name, NRIC, matric number, college, semester rows, subject–grade rows
  (A … F with A-, B+ …), PNGK/CGPA, co-curriculum.
- Unsure → nothing, falls back to Gemini. Never a wrong Exact.
- Wired into `higher_results.extract`; a hit stores `capture='deterministic'`. `PARSER_VERSION`.
- **Owner facts (2026-10-29):** Matriculation runs 1 year (2 semesters) or 2 years (4 semesters).
  The reader takes the FINAL CGPA — the last cumulative figure, after the last semester — never a
  semester GPA and never the first CGPA it meets. A transcript may span pages, and the final CGPA
  may be on the LAST page; production OCRs only page 1 of a scanned PDF (a text-layer PDF is read
  whole). So M2 first checks how many pages the higher-results read sees and plans for reading all
  pages — mind the `vision.py` size ceiling (new code in a new file; vision.py takes one call).
  Corpus (M1): all 9 Matriculation pages are one page with the final CGPA on page 1 — the
  multi-page case is not yet in the corpus, so M2 needs a synthetic twin for it.
- **Done when:** the matric corpus reads Exact with correct name/CGPA/grades; 0 wrong values; gates green.
- **BUILT 2026-10-29** (branch `m2-matric-parse`, not pushed). Notes:
  - Corpus (`eval/matric_parse_check.py`, production's input): 3 Exact, 6 to Gemini, 0 wrong; 0 of
    168 controls accepted. Of the 6 transcripts, 3 read Exact; the 3 fallbacks are a skewed scan
    (grades sit between rows), a cropped photo with a misprinted point, and a scan with debris in a
    row. The other 3 pages are semester RESULT SLIPS, which never read Exact (one semester cannot
    prove a cumulative CGPA).
  - Every hit is proven by arithmetic: each semester's PNGS and the final PNGK recomputed from the
    core courses' credits × points. A 4-semester transcript needs its own note naming the counted
    semesters ("Semester III dan IV").
  - **Pages (read from the code):** a text-layer PDF is read whole (`pdf_pages.pdf_text_layer`, all
    pages); a SCANNED PDF is rasterised page 1 only (`pdf_first_page_png`) for BOTH Vision and the
    Gemini fallback. The reader therefore refuses a page that stops before the last semester or the
    final PNGK. Reading every page is PROPOSED, not built (`docs/decisions.md` 2026-10-29 M2).
  - Review fixes (parser 1.1.0): only the core courses are returned (English and minor courses are
    proven by no sum); each semester's fixed shape. Co-curriculum is therefore NOT in the Exact read.
    No real multi-page text-layer transcript is in the corpus; a page 2 that repeats the header
    falls back (two NAMA rows).
  - Labels hand-checked against the page images: two names, one transcript's rows and CGPA rebuilt,
    one transcript's average-grade box dropped from its rows.

### M3 — `poly_diploma_parse.py`: deterministic polytechnic Diploma reader · medium · ~8 h
- Same shape for the shared polytechnic transcript layout (provisional and final transcripts).
- Non-polytechnic diplomas (UiTM, private colleges) are NOT read here: they stay AI.
- **Owner facts (2026-10-29):** a polytechnic Diploma runs 2.5 years (5 semesters) or 3 years (6
  semesters). Same rules as M2: the FINAL CGPA (the last cumulative figure, polytechnic label HPNM or
  CGPA, after the last semester), never a semester GPA (GPA / PNG) nor the first CGPA met; the
  transcript may span pages with the final CGPA on the last; production OCRs only page 1 of a scan,
  so plan for all pages (vision.py ceiling). Corpus (M1): all 4 polytechnic pages are one page with
  the cumulative label on page 1; the only multi-page diploma (UiTM, 2 pages, scanned) carries its
  last cumulative figure on page 2 — exactly the case production's page-1 read misses.
- **Done when:** the polytechnic corpus reads Exact; other diplomas still AI; 0 wrong values.
- **BUILT 2026-10-29** (branch `m3-poly-parse`, not pushed). Notes:
  - The corpus holds ONE polytechnic academic transcript (3926, a digital PDF); the other three
    polytechnic documents are two semester RESULT SLIPS (3390, 3397: "Keputusan Penilaian Akhir
    Semester", HPNM a running figure at 51 / 95 and 68 / 95 credits) and one student-portal screen
    (1311). So the reader is built for the transcript's TEXT LAYER only; a scan is never read Exact.
  - Corpus (`eval/poly_parse_check.py`): 1 Exact (3926), 7 to Gemini (the 2 slips, the portal, the 4
    UiTM), 0 wrong; 0 of 169 controls accepted (Matriculation, STPM, SPM, the slip corpus …).
  - Every graded row is proven: each semester's credits equal its box's Credit Earned, its GPA and the
    running CGPA recomputed; the boxes (out of step with their semesters in the two-column text layer)
    are paired by their own running Total Credits. 0-credit rows (PISPA 3, 4) are left out.
  - Its label was WRONG on one grade (Gemini-seeded; the semester GPA proves the printed grade): the
    LIVE stored Gemini read of 3926 carries the same misread (checked) — M5's re-read fixes it.

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
