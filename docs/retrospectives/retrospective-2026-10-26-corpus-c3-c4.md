# Retrospective — Corpus gaps C3 + C4: STPM results scored as STPM; the live re-run (2026-10-26)

C3: `0ae5f431` (built as `fcb3ced1` in the worktree `ai-outage`, rebased onto TD-403) — live as
api-01147-9gw. C4: the lead's live re-run, no code. Roadmap
`docs/plans/2026-10-25-document-corpus-gaps-roadmap.md` (owner decisions A–D); wording from roadmap C0.
Decisions: `docs/decisions.md` 2026-10-26 (owner rulings 1A, 2A). Register: TD-407 raised. With this the
corpus-gaps arc is complete except the data-gated TVET families.

## What Was Built

- **C3 — the STPM family (MODEL_VERSION 1.9.0).** `genuineness/stpm_doc.py`: a slip list and a certificate
  list (16 signatures each) from the fixed wording of ten real STPM documents, registered beside the
  untouched SPM pair (SPM first, so a tie goes to SPM), in the misfile check and in `assess`. The
  semester-result slot scores a document against STPM only when an STPM issuer is on the page; anything
  else there stays unscored. The picture check asks about "SPM or STPM". Owner rulings: 1A the online
  results-checker page is not a result document; 2A a certified photocopy scores like the certificate.
- **C4 — the live re-run (the lead).** 43 documents re-read on the live service: 11 UiTM offers suspect →
  genuine 0.80–0.90 (incl. #251's d3586 at 0.80); IKBN d3465 → not checked 0.40; TVETMARA d3494 stays
  not_offer_letter 0.11 (below the net's band, by design); 17 STPM documents → genuine 0.92–1.00; d3109 →
  suspect 0.36 (was not_results_slip 0.0); the checker page d3303 stays not_certificate 0.09 (1A); the
  certified copy d3233 genuine 1.0 (2A). One document was superseded by a newer upload that has its score.

## What Went Well

- **The real-data diff before the build, again.** C3 was run against every cached SPM document (96) under
  all four QR/crest combinations and the ten STPM texts before it was committed: SPM moved nowhere, the one
  STPM slip in the eval set moved to genuine. The live re-run matched the offline prediction document for
  document.
- **Bite-checks found two silent guards.** Putting STPM first, and dropping the forge-hard disclaimer
  signature, turned nothing red at first; both are now pinned (`test_corpus_gaps_c3.py`).
- **The owner's rulings were taken before the build** (1A, 2A), so the two hard documents (the checker
  page, the certified copy) had an answer the tests could assert.

## What Went Wrong

1. **The first live re-read wiped 16 genuineness scores — and the same had already happened, unnoticed,
   two days earlier.** C4's first run went through the `release-decisions` Cloud Run job. The job carries
   only the core environment, not the `halatuju-api` service's `DOC_GENUINENESS_CHECK_ENABLED` /
   `BILLING_USAGE_ENABLED`. With the genuineness flag off, the read pipeline (`reextract.reextract_document`
   → `vision._run_field_extraction_impl`) rebuilds `vision_fields` and simply does not add `authenticity`,
   so the re-read replaced each stored score with nothing: an unscored document, which reads as "no
   signal" everywhere (Probable at most; an offer's official status `unknown`, so a not-official offer
   would stop blocking and stop asking). The same thing had silently happened to the 16 AI-outage
   documents re-read on 2026-10-24. The job also hit its 10-minute task timeout and retried. The second
   run passed the flags (`--update-env-vars=DOC_GENUINENESS_CHECK_ENABLED=1,BILLING_USAGE_ENABLED=true`,
   `--task-timeout=3600s`) and re-scored 43 of 44 correctly. *Root cause:* two things together — the job
   is not the service (same image, different env), and the write path treats "flag off" as "nothing to
   say", overwriting a stored value with silence; nothing logged it, and no one checked a written row for
   the very field the run existed to set. *System change:* (a) lesson recorded (a job is not the service);
   (b) **TD-407 (Now tier)**: the re-read keeps a stored `authenticity` while the flag is off (never
   overwrite a score with silence), with a log line, and the re-read commands refuse to start without the
   flag; (c) `halatuju_api/CLAUDE.md` "How a change reaches production" item 11: a re-read through a job
   passes the service's read flags and `--task-timeout`, and a sample of written rows is checked for an
   `authenticity` block. The 16 AI-outage documents of 2026-10-24 should be re-read with the flags too (the
   lead's call — paid, live only).
2. **The builder's version pins broke its own earlier tests.** C1 and C2 tests pinned `MODEL_VERSION` to
   '1.8.0' / '1.8.2'; each bump turned them red (one only caught at C3's full gate). *Root cause:* a test
   that means "this shipped at version X" was written as "the version IS X". *System change:* they now
   assert the stamp equals the live `MODEL_VERSION` and the version is at least X; only each sprint's own
   test pins its exact number.
3. **Two EPF documents (d3519, d3543) read not_epf 0.0 on the re-run, with no prior score to compare.**
   Probably the known pattern (26 of 95 EPF uploads are not EPF statements), but unconfirmed — and the
   missing prior score may itself be the 2026-10-24 wipe. *System change:* none yet — noted for the
   reviewer to look at by eye; TD-407's guard stops a future wipe from hiding the comparison.

## Review (sprint-close step 4b)

No `/code-review`, by the coordinator's instruction: C3 was reviewed against the real STPM texts and the
SPM eval set by the lead before the push; C4 was the lead's own operation, with the incident above found
and fixed during it.

## Numbers

- API (`python -m pytest -q -n auto -p no:cacheprovider`): 8,865 → 8,881 passed / 3 skipped in the
  worktree (`test_corpus_gaps_c3.py`: 16); combined on main by the lead after the TD-403 rebase.
- No web change. No migration. MODEL_VERSION 1.8.2 → 1.9.0.
- C4: 44 documents targeted, 43 re-scored, 1 superseded; 16 scores wiped by the first run and restored.
