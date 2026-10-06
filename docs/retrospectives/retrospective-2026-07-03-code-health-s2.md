# Retrospective — Code-health Sprint 2: document-pipeline safety (2026-07-03)

## What Was Built

Sprint 2 of the code-health roadmap (`docs/plans/2026-07-03-code-health-review.md`, findings #5 + #22):

1. **Clobber guards (#5a).** All three vision writers now refuse to overwrite a successful read
   with a failed one: `run_field_extraction_for_document` (keeps stored `fields` when the re-run
   errored), `read_text_document` (keeps stored letter text on an empty read),
   `run_vision_match_for_document` (never downgrades a real verdict to `unreadable` on an outage).
   The guard keys on "this run FAILED + the row already holds a good read of the same immutable
   blob" — a genuinely unreadable first upload still records its honest state, and re-uploads are
   new rows so they're unaffected. Callers see `stale_kept: True`.
2. **Honest batch command (#5b).** `reextract_documents` marks a failed/stale-kept doc `'error'`
   instead of `True`: the pass still advances (no wedge), the failure is visible in the summary,
   and `--retry-errors` re-attempts them. Stale-kept runs are detected by unchanged
   `vision_fields_run_at`/`vision_run_at` stamps.
3. **Street pass-through (#5c).** `reextract.py` now passes `profile.address` like the upload path,
   so a re-run can't flip a house-number+street match to `mismatch` in locality-only mode.
4. **Single Vision read (#22).** `ocr_document_full` does one fetch + at most one
   `document_text_detection` per upload/re-run, and its `{text, words, image}` are reused by the
   name/address match, the positional slip/BC parsers (`_extract_slip_deterministic` gained a
   `words=` param), and the genuineness image consumers. Halves Vision billing on slip/BC uploads
   and removes duplicate blob downloads. Digital PDFs keep the free text-layer path (`words=None`
   → consumers fall back exactly as before).

## What Went Well

- The full scholarship suite (1,997) passed first run after all changes — the seams
  (`_vision_words`, `_fetch_image_bytes`, `ocr=` param) were already test-friendly, so the
  refactor slotted in without disturbing the mocked contracts.
- The clobber guard turned a two-line memory rule ("never re-extract locally") into an invariant.

## What Went Wrong

- **The existing `reextract_documents` tests mocked the per-doc read as a pure no-op, so the new
  staleness detection initially read every mocked success as a failure.** Root cause: the mock
  didn't reproduce the one observable side-effect (timestamp advance) that real runs have, and
  which the command now uses as its success signal. Fix: the tests' mock now stamps
  `vision_fields_run_at` like a real read — and that contract is stated in the test. Lesson-class:
  when a command infers success from a side-effect, its tests' mocks must produce that side-effect.

## Design Decisions

Logged in `docs/decisions.md`:
- Guard keys on run-failure + prior-good-read, NOT on content ("unreadable but parseable last
  time") — content changes on re-parse are legitimate parser improvements.
- Failed batch docs are marked `'error'` (advance-but-retryable) rather than left unmarked
  (would wedge the self-batching pass on one broken doc).
- `ocr_document_full` preserves the digital-PDF free path; `words=None` means "not computed",
  distinct from computed-empty `[]`.

## Numbers

- 3,196 backend tests (1,997 scholarship + 1,199 courses/reports), 0 failures; +11 net new tests
  (9 clobber-guard/single-read + 2 command semantics; 1 command test rewritten).
- No migration. No frontend change. No i18n change.
- Cost impact: −1 Vision call and −1/−2 blob downloads per slip/BC upload; re-runs identical.
