# Retrospective — a rating of the AI decided a student's case (BrightPath #20)

**Date:** 2026-08-24 · **Lane:** sprint · **Migration:** none · **Files:** 9 + one backfill command
**Request:** BrightPath #20, submitted by Suresh Thirugnanam 2026-08-20, analysis 41 → comment 65.

---

## What was reported, and what was actually wrong

The request was titled *"Kaneswaran's Reviewer report error"*. The next day the reporter withdrew
that himself — *"on further review and chat with Kaneswaran… so no problem with the report !!"* —
and described something else in the same comment: an income check reading FAIL against a blue tag
on a family that holds an STR, and no way to override it as he had done before.

Three separate readings of the situation were all correct, which is why it took a database to
unpick:

- **The AI was right.** Income read `review` (blue), not fail. The STR shows *Lulus* and its
  recipient matches the father's MyKad exactly, but the documents on file do not establish that it
  is still being paid this cycle. Blue is the colour for *true as far as we can see, not proven*.
- **The reviewer was right.** He had established currency by his own enquiry and recommended. He
  also marked income **Fail** — which is a rating of OUR AI, and a fair one: our payslip reader had
  misread the father's IC by two digits.
- **The owner was right** to say the ratings should have no bearing on the outcome.

Nobody made a mistake. The student lost fourteen days anyway.

## The two defects

**1. The AI scorecard was wired into the Submit button.** `isClearAccept` returned false if any of
academic/pathway/income was rated Fail, so the case saved the verdict and then did not submit — and
the block that reports what happened had no branch for it, so the screen said nothing. The reviewer
had no way to know his case had not left his desk.

**2. A blank household tag is a slot of its own, and it is always empty.** The same payslip was
uploaded twice, fifty seconds apart. The tagged copy was correctly judged and replaced. The
untagged copy found an empty blank slot, promoted itself into it, and stayed live beside the good
copy. Because the tag guard derives the member from the NAME read off the document, the documents
it could not tag were exactly the unreadable ones — the sentinel systematically preserved the worst
evidence.

## What shipped

- `isClearAccept` no longer **takes** the officer verdict. Not documented as forbidden — removed
  from the signature, so the old behaviour is unexpressible.
- `verdictSaveOutcome`, a closed union of four names, one line on screen for each. The cure for a
  silent branch is a total function, not one more `else`.
- The upload tag guard gains a last-resort branch: unreadable and untagged, on a route with one
  declared earner, files to that earner via `implied_single_member` — the same helper the readers
  already used, extracted from `_proof_member` so the two cannot drift.
- `backfill_untagged_income_docs` for the 5 documents already in that state (app 73 × 1,
  app 88 × 4). Report-only by default.

## What went well

- **Querying production rather than reasoning from the screen** settled every disputed fact: that
  the AI said `review` and not `fail`, that only one application was frozen, that the payslip IC
  differed from the MyKad by two digits, and that the freeze had bitten exactly once.
- **The sweep before the fix.** Checking all 87 decided applications turned "this is probably
  widespread" into "this is one case, and no accepted case has ever carried a Fail mark" — which
  changed the priority and the message to the customer.
- **Mutation-checking every regression test.** Three assertions were confirmed to fail with their
  fix deleted.

## What went badly

- **I told the owner the STR objection was "gone"** on the strength of a screenshot and a stale
  `ai_verdict_snapshot`. He corrected me: the STR shows approved but was never shown to be current,
  so blue was accurate. I had read a frozen 10-August snapshot as live state.
- **I diagnosed a self-contradiction that did not exist.** Reading income=Fail beside overall=Accept
  as incoherent, I nearly advised the reviewer to change an honest rating. The owner corrected the
  model: the four facts grade the AI. That correction is what turned a copy fix into a design fix.
- **The first regression test was vacuous and passed with the fix deleted.** Pre-consent, the
  STR-route force-tag already stamps every income doc, so the test measured the force-tag. The real
  case was post-consent. Thirty seconds of mutation testing was the difference between a guard and
  a decoration.

## Follow-ups

- The payslip OCR misreads `751206-08-5941` as `751206-06-5041`. Observed, not fixed — an accuracy
  problem, not a logic one, and out of this sprint's scope.
- The ms/ta strings for the two new messages are my drafts and want a native read.
- `next build` passes; nothing is deployed yet.
