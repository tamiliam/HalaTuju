# Document-recognition eval harness

The "golden master" for the **Vision → matcher → verdict** pipeline — the document
equivalent of the SPM/STPM eligibility golden master. Instead of uploading a document and
eyeballing whether the system read it right, distinguished a wrong document, and reached the
right verdict, you capture that judgement **once** and re-check the whole pipeline in seconds.

It drives the SAME `resolution.doc_match_verdict` the cockpit shows — it does not re-detect anything.

## The two layers (why it's cheap)
- **Layer A — the Gemini read** (costs money, wobbles run-to-run). Run only with `--rerun-vision`;
  the result is cached per document in `snapshots/`.
- **Layer B — the matchers + verdict** (deterministic, free). The everyday scorecard replays
  Layer B against the cached snapshot, so it's instant, free, and identical every time.

## Files
| Path | Committed? | Contents |
|------|-----------|----------|
| `labels.json` | **Yes** (PII-free) | Expected outcome per document — assertions only |
| `fixtures/`   | No (gitignored) | The real document files (PII) |
| `snapshots/`  | No (gitignored) | Cached Gemini reads per document (PII) |
| `context.json`| No (gitignored) | Per-document profile context the doc is checked against (PII) |

## Adding a document (the one-time labelling pass)
1. Drop the file into `fixtures/`, named so the stem is your key, e.g. `fixtures/ic_clean.jpg`.
2. Add a `labels.json` → `docs` entry keyed by that stem (copy the shapes from `_example`):
   ```json
   "ic_clean": { "doc_type": "ic", "expect_verdict": "ok", "note": "clean IC matching the profile" }
   ```
   `expect_verdict` is what `doc_match_verdict` should return: `ok` · `mismatch` · `unreadable` · `pending`.
3. Add a `context.json` entry (gitignored) with the profile the doc is checked against:
   ```json
   "ic_clean": { "profile_name": "…", "profile_nric": "…", "income_route": "str", "income_earner": "father" }
   ```
   Only include the fields that matter for that document's checks.

## Running it
Requires a migrated local DB (`python manage.py migrate` once) — the harness builds
throwaway rows to run the checks against (then rolls them back). `GEMINI_API_KEY` in your
local `.env` is needed only for `--rerun-vision`.
```bash
cd halatuju_api
python manage.py eval_doc_recognition --rerun-vision   # once per doc: capture the Gemini read (costs $)
python manage.py eval_doc_recognition                  # the free, repeatable scorecard
python manage.py eval_doc_recognition --json           # machine-readable
```
Typical output: `9/10 correct · 1 regression: water_bill_other_name expected 'ok', got 'mismatch'`.

## The results_split corpus (STPM exact-read, S1)
`fixtures/results_split/<folder>/` holds results documents sorted by the owner and split by page:
`stpm_cert`, `stpm_slip` (the STPM corpus) and the controls `spm_cert`, `spm_slip`, `fake`,
`matric`, `diploma`, `asasi`, `muet`, `spvm`, `other`. File stems are the keys.

`capture_ocr.py` reads each document the way production feeds the reader
(`vision.ocr_document_full`): a digital PDF with a usable text layer is read from that layer for
free; anything else goes to Google Vision, one billable call per page. It writes, per key, into
`snapshots/`:

| File | Contents |
|------|----------|
| `<key>.ocr.txt` | Flattened text, all pages in order |
| `<key>.ocr.words.json` | Vision only: `{"pages": [{page, text, words: [{text, cx, cy, h, angle, x0, y0, x1, y1}], error}]}` — production's word shape plus bounds; `pages[0]` is what production OCRs |
| `<key>.ocr.meta.json` | `path` (`text_layer` or `vision`), page count, Vision calls |
| `<key>.expect.json` | Hand-checked expected answer (STPM: layout, year, name, IC, index no., serial, PNGK, subject rows, readable; controls: `{layout, stpm: false}`) |

**All four are real student data (PII) and gitignored** — never copy a value into a tracked file
or a test.

```bash
cd halatuju_api
python apps/scholarship/eval/capture_ocr.py results_split/stpm_cert   # nested path under fixtures/
python apps/scholarship/eval/capture_ocr.py results_slip              # a plain doc_type still works
```
Re-runs skip keys that already have an `.ocr.txt`, and each run prints how many Vision calls it
made. `python apps/scholarship/eval/stpm_parse_check.py` scores the STPM Exact reader
(`stpm_parse`, S2) against these caches — exact / fallback / WRONG per document, every control
must be None — and prints keys and field names only, never a value. `spm_cert_check.py` does the same for the SPM certificate reader (`spm_cert_parse`) against hand-checked `<key>.expect_spm.json` answers (name, IC digits, year, printed count, subjects + grades, read off each page image; gitignored PII). `poly_parse_check.py` (M3) scores the polytechnic Diploma reader the same way. `matric_parse_check.py` (M2) scores the Matriculation Exact reader the same way against `<key>.expect.json`. `results_kind_check.py` (Matric/Diploma M1) prints the kind `results_kind` reads for every cached results page, from the OCR text and from the stored read, against the folder's kind; `--code <halatuju_api>` runs another checkout's module for a before/after. Four of
the eight SPM certificates are pages split out of combined uploads (`__p<n>`); production reads page 1 only,
so the live hit rate on combined uploads is lower than the corpus score. Credentials: `GOOGLE_CLOUD_VISION_API_KEY` from `halatuju_api/.env` or the repo-root `.env`,
else gcloud Application Default Credentials.

## Limits (honest)
- It scores each document **in isolation**. A check that needs a companion document present
  (e.g. a payslip verified against the matching parent IC) sees only the one doc — note such
  cases or extend the fixture builder later.
- Verdicts can legitimately **drift** if the matchers change; that's exactly what a regression
  here is meant to surface.
- Local/dev only — not wired to any endpoint or cron. Nothing is written to the database
  (every fixture is built inside a rolled-back transaction).
