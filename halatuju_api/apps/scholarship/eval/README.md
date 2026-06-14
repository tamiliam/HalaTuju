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

## Limits (honest)
- It scores each document **in isolation**. A check that needs a companion document present
  (e.g. a payslip verified against the matching parent IC) sees only the one doc — note such
  cases or extend the fixture builder later.
- Verdicts can legitimately **drift** if the matchers change; that's exactly what a regression
  here is meant to surface.
- Local/dev only — not wired to any endpoint or cron. Nothing is written to the database
  (every fixture is built inside a rolled-back transaction).
