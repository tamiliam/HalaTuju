# Retrospective — the AI-outage sprint: our outage is never the student's unreadable document (2026-10-24)

Commit `9d3ff53a` (pushed to main 2026-10-25, build SUCCESS, revision `halatuju-api-01135-djr`). Built in
the worktree `ai-outage` from base `2c7f0466`, then three adversarial review rounds before the push.
CHANGELOG: "fix: an AI outage is not the student's unreadable document (the Gemini 402 incident)".
Decisions: `docs/decisions.md` 2026-10-24. Register: TD-391 and TD-392 closed; TD-390, TD-393 to TD-399
raised.

## The incident

| When (UTC) | What |
|---|---|
| 2026-10-23 ~10:00 | The Gemini API key's prepaid credit runs out. Every Gemini call answers `402 RESOURCE_EXHAUSTED` ("Your prepayment credits are depleted"). |
| 2026-10-23 12:22 | First document read fails. Every read after it fails the same way, for about 20 hours. |
| 2026-10-23 → 24 | Each failed read is stored `student_verdict='unreadable'` with the error `All AI models failed: 404 … models/gemini-2.0-flash is not found` — the LAST model in the cascade, a retired one. Students are told to re-take good photos; the consent gate blocks them (`offer_letter_unreadable`, `results_slip_unreadable`, `income_document_unreadable`). No alert fires. |
| 2026-10-24 | Found when student #251 telephoned. The live key turns out to sit in a GCP project outside the owner's billing view (…0lsU). |
| 2026-10-24 | The lead swaps `GEMINI_API_KEY` on `halatuju-api` AND the `release-decisions` job to the HalaTuju-project key (…YYr8). Google had moved Gemini API billing to PREPAY; the owner bought MYR 50 of credit. |
| 2026-10-24 | 16 outage documents re-read through the `release-decisions` job: 15 read `ok`; 1 is a genuine `name_mismatch` (#304 — the OCR read Q for O). |
| 2026-10-25 | This sprint ships (`9d3ff53a`); Cloud Scheduler `halatuju-read-outage-start` created (hourly at :05 MYT), a manual run answers 200. |

## What Was Built

- **One classifier, one choke point.** `apps/scholarship/read_errors.py` answers "ours or the document's":
  `is_ai_service_error` (the cascade-failed prefix, no key, no SDK, `rate_limited`, a supporting document's
  `OCR service failed: …`), `is_ocr_service_error` (the IC gate's TD-080 decode-vs-service split, moved here),
  `model_rejected_document` (a 400/413 whose message names the FILE and nothing of ours), `read_deferred` /
  `deferred_by_us`. At `vision._run_field_extraction_impl` our failure is stored `review_manually` +
  `service_error: True` — the existing "AI skipped" state — never `unreadable`. The clobber guard now also
  refuses to let our outage overwrite a real verdict.
- **A deferred read asks the student for nothing.** No `offer_unreadable`, no `birth_cert_unreadable` /
  `guardianship_letter_unreadable` (TD-391), an STR reads `unknown` (bands Unsure, like a badly-read one, with
  an unticketed line), no consent blocker, no re-upload coaching (the bank statement included — TD-392b), no
  attempt stamp, no circuit-breaker, and Check 2 HOLDS its requests (`check2_deferred.py`) — neither raised nor
  resolved on an unscanned document. `VERDICT_ENGINE_VERSION` 2026-10-24.1.
- **Self-heal.** `services/read_retry.py`, called by the hourly `reprocess-ic-vision` sweep: re-reads live
  service-error documents (the incident's own `unreadable` rows included) through the cockpit's Re-run core;
  skipped while Gemini reads are down, one paid probe then stop, 72 hours per document, open cases only,
  never over a real read, `rate_limited` ones under the upload path's own hourly cap.
- **Alert.** `services/outage.py`: the outage check covers Gemini reads and every document's Vision OCR (a
  clean PDF is no proof Vision is up), one email per service, carrying the stored error. `alert_vision_outage
  --hourly` is a stateless start-edge mode (2 h window, ≥2 failures from ≥2 applications, compared with the run
  65 minutes back); cron door `read-outage-start`. The daily job is unchanged.
- **Honest errors.** `gemini.cascade_failure` names every model's own error (≤600 chars);
  `gemini-2.0-flash` (retired) is gone from every cascade and the AI registry; the cascade goes on past an
  empty answer; a document is blamed only when every model refused its content or none parsed an answer.
  `generate_stpm_headlines` runs 2.5-flash with a thinking budget of 0.

## What Went Well

- **The fix reused the state the product already had.** `review_manually` was the "AI skipped → not
  extracted" verdict every reader (pathway, academic, resolution, help, the web checklist) already treated as
  pending. Choosing it instead of a new state meant most readers were right on day one; the review rounds found
  the ones that were not.
- **Every fix was bitten.** Each fix across the build and three review rounds was reverted by
  a fault-injection script (original bytes restored and digest-checked in a `finally`) and its own test went
  red. Four silent bites were found that way and each one's test was rewritten until it spoke (the
  circuit-breaker fixture was too kind; the HTTP-400 rule was never reached because the fixtures carried a
  status; the "no text read" exclusion was only checked beside real outage rows; one injection broke the
  module's syntax and was redone).
- **Baselines measured, not inherited.** The first baseline ran while files were being edited, so it was
  re-measured on a clean worktree of the base commit; the two agreed.

## What Went Wrong

1. **No alert covered Gemini.** The outage ran ~20 hours and was found by a student's phone call.
   *Root cause:* the only outage check (`detect_vision_outage`) was written for Google Vision OCR of the IC and
   was never widened when Gemini became the reader of every other document; "the AI is down" had
   no reader. *System change:* the check now covers Gemini reads and every document's OCR, and an hourly
   start-edge job mails the hour an outage begins (`read-outage-start`), not only the next 02:00.
2. **The stored error showed only the last cascade model.** Every failed read said "gemini-2.0-flash is not
   found", hiding the 402 that was the cause. *Root cause:* the cascade kept `last_error` and the bottom model
   had been retired, so the one message that survived was the least informative one. *System change:*
   `cascade_failure` records every model's own error; retired models are removed from every cascade the day
   they retire; lesson recorded ("the last error in a fallback chain hides the cause").
3. **The live key sat in a project outside the owner's billing view.** The credit ran out with nobody able to
   see the balance. *Root cause:* the key was created in another GCP project, and nothing tied the key in use to
   the project whose billing the owner watches. *System change:* the key was replaced with the HalaTuju-project
   key on both the service and the `release-decisions` job (whose env does not follow the service); CLAUDE.md's
   environment table now says the key must belong to the HalaTuju project and that prepaid credit running out is
   an outage.
4. **Our outage was stored as the student's fault.** Families were told their good photos were unreadable
   and the consent gate blocked them. *Root cause:* `_run_field_extraction_impl` turned ANY extraction error
   into `unreadable`, and `document_unreadable_blockers`' docstring claimed outages surfaced as "pending" — a
   claim no test pinned. *System change:* one classifier and one choke point, regression tests through every
   door that writes the verdict (upload, cockpit Re-run, bulk re-extract, the sweep) and every reader that could
   turn it back into a student ask (the verdict's tickets, Check 2, the STR ladder, help copy, the
   circuit-breaker); a test for each that a genuine `no text` is still `unreadable`.
5. **The first build missed the verdict-side readers.** Round 1 fixed the consent gate but the verdict still
   raised "send a clearer copy" requests after submission, a deferred upload counted as a failed attempt, and a
   deferred STR closed its own request. *Root cause:* the brief's list of readers was taken as complete; the
   ticket path (`resolution.STUDENT_DOC_REQUEST_CODES`) reads the verdict, not the stored read. *System change:*
   the review rounds' rule, now in this retro's design notes: for a new state, grep every reader of the OLD
   value's consequences (ticket codes, coach codes, attempt stamps), not only of the field.
6. **Round 2 over-blamed the document.** Every 400 was classed as the file's fault — a revoked key answers
   `400 INVALID_ARGUMENT … API key not valid`, which would have repeated the incident. *Root cause:* the status
   code was treated as sufficient; a wrong "theirs" costs a student, a wrong "ours" costs only a retry, and the
   rule did not reflect that asymmetry. *System change:* a 400 is the document's only when its message names
   the content and nothing of ours, on every model; any unrecognised 400 is ours.

## Review (sprint-close step 4b)

No `/code-review` run, by the coordinator's instruction: the sprint already had three independent adversarial
review rounds, each answered in full in the same worktree —
- **Round 1 (11 findings):** verdict tickets on a deferred read; attempt stamp + breaker; STR closing its own
  request; unparseable answers as outages; the sweep paying for OCR while Gemini was down; soft-document
  coverage and staged copies; hourly alert noise + jitter; a run-count cap; closed cases; the clobber guard;
  thinking tokens on 2.5-flash. All fixed except staged re-uploads (TD-393, needs the promote chain extracted).
- **Round 2 (7):** Check-2 bill / academic / letter re-asks; the STR band; the cascade stopping at the first
  empty answer; 400 classification; an officer reason line (TD-396, needs i18n); supporting-document OCR in the
  alert; pre-fix Vision rows (TD-395, with the query).
- **Round 3 (3):** over-broad 400 rule (blocker); a clean PDF masking a Vision outage; a deferred read
  RESOLVING an open Check-2 request (the round-2 readers were reverted; the sync holds instead, at zero
  extra queries on both budgeted paths).
Every fix bitten (above); every finding fixed or raised as a TD.

## Design Decisions

See `docs/decisions.md` 2026-10-24: the deferred read is `review_manually` (no new state); the
ours-versus-the-document rule; TD-394's owner ruling; the OpenAI fallback's sequencing.

## Numbers

- API (`python -m pytest -q -n auto -p no:cacheprovider`): **8,605 → 8,659 passed / 3 skipped**
  (3,958 → 4,010 subtests). `test_ai_outage.py`: 54 tests.
- Web (`npm run gates`): **4,412 jest / 274 suites**, typecheck, lint and i18n green (no web change).
- No migration. `VERDICT_ENGINE_VERSION` 2026-10-24.1.
- Register: 130 open (TD-390, TD-393 to TD-399 open; TD-391, TD-392 closed).
- Recovery: 16 outage documents re-read — 15 `ok`, 1 genuine `name_mismatch` (#304).
