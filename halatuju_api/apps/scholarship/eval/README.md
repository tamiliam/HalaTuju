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
must be None — and prints keys and field names only, never a value. `spm_cert_check.py` does the same for the SPM certificate reader (`spm_cert_parse`) against hand-checked `<key>.expect_spm.json` answers (name, IC digits, year, printed count, subjects + grades, read off each page image; gitignored PII). `matric_poly_genuineness_check.py` (M4) prints the Matriculation / polytechnic genuineness of every cached page. `poly_parse_check.py` (M3) scores the polytechnic Diploma reader the same way. `matric_parse_check.py` (M2) scores the Matriculation Exact reader the same way against `<key>.expect.json`. `results_kind_check.py` (Matric/Diploma M1) prints the kind `results_kind` reads for every cached results page, from the OCR text and from the stored read, against the folder's kind; `--code <halatuju_api>` runs another checkout's module for a before/after. Four of
the eight SPM certificates are pages split out of combined uploads (`__p<n>`); production reads page 1 only,
so the live hit rate on combined uploads is lower than the corpus score. Credentials: `GOOGLE_CLOUD_VISION_API_KEY` from `halatuju_api/.env` or the repo-root `.env`,
else gcloud Application Default Credentials.

## Offer letters — exact read (offer exact-read S1, 2026-11-01)
Roadmap: `docs/plans/2026-11-01-offer-letter-exact-read-roadmap.md`. The corpus is
`fixtures/offer_letters_2026-11-01/` (gitignored PII): `fixtures/offer_letter/<key>.<ext>`,
`snapshots/<key>.json` (the stored production read), `programme_by_key.csv`, `context.json`,
`applicants.json`, `_manifest.csv`. The old `fixtures/offer_letter/` (~95 letters) is what "seen
before" means (matched by doc id `__d<id>`).

**The correct answer** — `snapshots/<key>.offer_expect.json` beside the snapshot (gitignored PII).
Every key present; a field the letter does not print is JSON `null`, explicitly:

| Key | What to write |
|-----|---------------|
| `candidate_name`, `candidate_nric` | as printed |
| `institution_as_printed` | the college / campus / school line, exactly as printed |
| `institution_campus` | the campus a person would pick from that line (may be `null`; not scored — kept for the campus matcher, TD-451/452) |
| `programme` | the programme / course title, as printed. **PISMP: the degree title** ("IJAZAH SARJANA MUDA PERGURUAN"), the same as any other university course (owner, 2026-11-01) — the Bidang goes in `specialisation` |
| `stream` | STPM "Bidang" / matriculation "Jurusan" (`null` for other families) |
| `specialisation` | PISMP "Bidang Pengkhususan" (`null` for other families) |
| `intake` | the session / intake **as printed, with its label** ("SESI 1-2026/2027", "SESI AKADEMIK 2026/2027", "INTAKE AUGUST 2025", "AMBILAN 2026" — owner, 2026-11-01). The scorer drops the label when it compares, so label or no label scores the same; S1 answers written before the ruling without the label were left as they are, and every new answer keeps it |
| `reporting_date` | the report / registration date (a range: its first day) |
| `offer_date` | the issue date (not the print date) |
| `issuer` | the body that issued the letter |
| `duration`, `fees` | as printed — written, never scored (decision D3) |
| `is_offer_letter` | `yes` · `conditional` · `portal_page` · `not_offer` · `unsure` |
| `pages` | int, pages in the file |
| `unsure_fields` | list of the field names above you are not sure of |
| `labeller_note` | short, or `null` — no personal data beyond the fields |
| `family` (optional) | `stpm` · `matriculation` · `polytechnic` · `pismp` · `uitm` · `other_university` · `tvet` · `other`; absent/`null` = derived from the stored read |

**The scorer** `offer_read_check.py` compares a read (default the stored `vision_fields.fields`;
`--read file:<suffix>` reads `snapshots/<key><suffix>`, for S3's fresh reads) with the answer, per
core field — name, nric, institution, programme (STPM/matric: the stream; every other family,
PISMP included: the programme), intake, reporting_date — as **exact / blank_correct /
missing / wrong / extra**; offer_date, issuer and specialisation (vs the read's
`bidang_pengkhususan`) are scored but not core — specialisation only on letters whose answer has
one, and its `right` % is over those (the `of` column). A letter is **fully
exact** when every core field is exact or blank_correct. Tidying only — case, spacing,
punctuation, accents, NRIC digits, dates to `D Mon YYYY` (Malay/English months, numeric dates),
an intake label (and a "Tahun" before a 4-digit year) dropped, one trailing bracketed acronym on
the institution dropped ("… (UniSZA)" = "…"; a bracket mid-line stays) — and **no fuzzy matching**: one letter different is `wrong`. Reports the
totals, per field, and by family, input kind (pdf / photo), capture, programme, split and answer
kind, the letters not fully exact (keys + field names), and — whatever the split, with or without
answers — the **known-format-AI count**: STPM / matriculation / polytechnic letters whose stored
read is the AI reader's, by family, input kind and programme (likely cheap S5 wins). Prints keys,
field names and counts only, never a value; sorted, identical on re-run; `--json` for the same
counts as JSON. Exit 1 when an answer file is malformed (listed as `FORMAT <key> <field>`).

**The held-out split** `offer_split.json` (committed — keys, seed and rule only) is made by
`offer_split.py`: ~90 letters drawn with a fixed seed from the letters **not** in the old corpus
**whose stored read is the AI reader's** (`capture='ai'` — the fixed-format reader's locks are
covered by the stpm/matric/poly parse checks and are not hand-labelled in S1), stratified by
family + programme. Every other key is dev. `--check` re-derives it and exits 1 on a difference.

```bash
cd halatuju_api
python -I apps/scholarship/eval/offer_read_check.py                   # held-out baseline
python -I apps/scholarship/eval/offer_read_check.py --split dev       # or --split all, --json
python -I apps/scholarship/eval/offer_split.py --check                # the split still reproduces
```
Run from a checkout that holds the corpus, or pass `--eval-dir` (and `--old-dir` for the split).
Committed tests: `tests/test_offer_read_scorer.py` (synthetic twins only).

**The owner's spot-check** (decision D1) — `offer_review_page.py` writes ONE offline page,
`<eval-dir>/review_s1.html`, inside the gitignored corpus folder (it shows real student data:
never publish or commit it; it refuses a tracked folder). It samples the held-out letters whose
answer has `unsure_fields` plus a seeded 20 of the rest (`--random N`), shows each document beside
its answer with Right / Wrong per line — every line starts Right, so the owner changes only the
wrong ones (`--blank` starts with nothing ticked) — keeps progress in the browser (an earlier tick
wins over the default), and "Save my answers"
downloads `offer_review_results.json`. `--apply <that file>` prints counts only (letters checked,
lines wrong per field) and changes no answer file — the lead decides. Tests:
`tests/test_offer_review_page.py` (synthetic twins).

**Free text, today's free readers, and the failure map (S2).** `capture_ocr.py offer_letter
--corpus <eval-dir> --reuse-from snapshots` caches OCR for every letter into the corpus's own
`snapshots/` (gitignored): a digital PDF's text layer (free); else an earlier page-1 Vision capture
from `eval/snapshots/` (meta `earlier_vision`, no second call); else Vision, one call per page.
`--dry-run` first prints the counts and the cost and writes nothing. `offer_replay.py --write` runs
today's deterministic offer reader (`offer_parse.parse_govt_offer`) and the offer genuineness on the
text production would feed them (the text layer, or Vision **page 1**), no paid call, and writes
`<key>.replay.json`: a lock is merged over the stored read as a production re-run does; a fallback
keeps the stored read as a stand-in for the Gemini read it does not make (`capture: ai_stand_in`).
It prints lock / fallback by family and input kind (photo / scanned_pdf / text_pdf), the
known-format-AI letters that lock today and, for the rest, a rule-based reason (no_text /
photo_ocr_noise / layout_variant / other — the rules are in its docstring), genuineness stored vs
today, and the stored Exact reads today's parser would now defer. The scorer reads it with
`--read file:.replay.json`. `offer_failure_map.py --split dev` (or heldout / all, `--read`,
`--keys`, `--json`) prints per core field wrong / missing / extra, by family, pages, input kind,
stored capture, stored reader version and stored genuineness version, and a **ranked list of failure
kinds** (institution = reporting venue, programme keeps a code, intake drops Semester, reporting date
only on page 2+, known format not locked, real offer judged not genuine, …), each tagged against
today's free readers: `old read` (a re-read fixes it), `today too`, or `ai, S3` (still Gemini today —
S3 measures it). Every kind's rule is in its docstring. Counts and keys only, never a value. Tests:
`tests/test_offer_replay.py`, `tests/test_capture_ocr.py` (synthetic twins).

```bash
cd halatuju_api
python -I apps/scholarship/eval/capture_ocr.py offer_letter --corpus apps/scholarship/eval/fixtures/offer_letters_2026-11-01 --reuse-from apps/scholarship/eval/snapshots --dry-run
python -I apps/scholarship/eval/offer_replay.py --write
python -I apps/scholarship/eval/offer_failure_map.py --split dev
python -I apps/scholarship/eval/offer_read_check.py --split dev --read file:.replay.json
```

`fetch_corpus.py` pages every PostgREST read (`limit` + `offset` over a stable `order`, stopping on
an empty page): the server caps a response at 1,000 rows whatever `limit` says, which silently
dropped most profiles before 2026-11-01.

## Limits (honest)
- It scores each document **in isolation**. A check that needs a companion document present
  (e.g. a payslip verified against the matching parent IC) sees only the one doc — note such
  cases or extend the fixture builder later.
- Verdicts can legitimately **drift** if the matchers change; that's exactly what a regression
  here is meant to surface.
- Local/dev only — not wired to any endpoint or cron. Nothing is written to the database
  (every fixture is built inside a rolled-back transaction).
