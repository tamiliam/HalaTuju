# Retrospective — 2026-08-18: the exam-type overload, and four BrightPath requests

One day, six shipped changes, and a single root cause running under three of them.

## What Was Built

1. **25 interviews re-credited** to the reviewer who conducted them (`repair_interview_credit`).
   Pre-TD-216 the credit was stamped at draft-row CREATION, so the July triage sweep claimed every
   case it opened. Production pass DONE: 25 re-credited, 4 already correct, verified idempotent.
2. **The analysis command's database path** stopped dropping the engineer's proposed triage.
3. **BrightPath #15 — answering a question works again.** The view passed `index=` after TD-201
   renamed it `comment_id=`; every answer raised `TypeError` *before* the service and 500-ed, for
   every organisation, for eighteen days.
4. **BrightPath #14 — a student is tagged by the results we hold**, not the exam declared.
5. **Three sandbox surfaces** mounting the real apply form, so a closed intake can still be reviewed.
6. **BrightPath #14 states 1 and 4** — the results step names no exam, and `results_exam_type`
   records which results were last COMPLETED.

## What Went Well

- **The doc's own recorded reason beat every theory.** `_slip_ocr_diag: not_spm_exam` on application
  #106's results slip had recorded the contradiction on 28 July and told nobody. Reading it first
  (lessons.md, 2026-07-10) turned a vague "the tag is wrong" into a dated fact in one query.
- **`intake_snapshot` settled the history.** Both affected students submitted as `spm` — dated,
  frozen, on their own rows. The owner's hypothesis (a July code push) could then be tested against
  evidence rather than argued.
- **Blast radius measured before every write.** #14's narrow rule moves 1 live record where the
  wide one moves 3; the `results_exam_type` backfill moves exactly one profile's displayed answer,
  and that profile has no application. Both measured on production before applying.
- **Every new guard was bite-checked** — disabled, watched to fail, restored. Seven separate times.

## What Went Wrong

**1. I asserted a fact about a live student without checking it.**
*Symptom:* I justified #14's narrow rule by treating application #15's 4.0 STPM CGPA as real, and
wrote that reasoning into the docstring, the tests, the CHANGELOG and the commit message. The owner
corrected it: she sat SPM in 2025 and is on a matriculation course.
*Root cause:* the data was in front of me and I read it as a result because the column is named for
one. Nothing on the record distinguishes a result from a number typed into the course guide to
explore, and I did not ask.
*Fix:* the rule is now stated as **absence is conclusive, presence proves nothing**, and that
asymmetry is documented at `_has_stpm_results` where the next reader will meet it. Added to
lessons.md.

**2. I told the owner nothing is snapshotted at submit. It is.**
*Symptom:* I checked `form_data` (empty on all 143 applications), concluded no submit-time snapshot
existed, and said so twice.
*Root cause:* I generalised from one field to a claim about the whole model without grepping for
the others. `intake_snapshot` sits four lines away in the same model and holds exactly what I said
was missing.
*Fix:* lessons.md — an absence claim about a MODEL needs a column-list check, not one field.
(This is the third instance of the "absence is a query" family; the memory note
`feedback_absence_is_a_query` already covers the DB-vs-grep case.)

**3. An analysis I had already POSTED to the customer overstated a defect.**
*Symptom:* #15's analysis says the reply "attaches to the oldest rather than the one you chose".
There is no chooser in the UI, and `_settle_open_questions` closes every preceding question anyway,
so the distinction is unobservable.
*Root cause:* written before reading the settle rule that closely, and posted before the code was
touched.
*Fix:* consolidation-log candidate rule — an analysis that will be posted verbatim states only what
has been read, and separates "I have confirmed" from "I expect".

**4. Two "third caller is tested nowhere" defects in one day, both in the same module.**
*Symptom:* the analysis command's DB path silently dropped the proposed triage; the answer endpoint
500-ed on every call.
*Root cause:* in both, the service had tests and the endpoint had *auth* tests, and the actual call
between them had none. A gap between two well-tested halves is invisible to tests of either half.
*Fix:* logged in `consolidation-log.md` as a candidate guardrail — every view calling a service
function needs one test exercising it end to end with the flag on and the right role, mechanisable
by diffing view call-sites against endpoint-test URLs. **A third instance makes it a sprint.**

## Design Decisions

Logged separately in `docs/decisions.md`: the credit-repair fence (current holder, not divergence);
`held_qualification` relying on absence only; and `results_exam_type` as a second field rather than
a rename of `exam_type`.

## Numbers

- `pytest` **5601** (scholarship + courses + reports) · `jest` **1458** / 96 suites
- `next lint` **0 errors** · i18n **4530 × 3** · `tsc` no new errors
- Migrations: **courses 70/70, scholarship 146/146**, no gaps, reconciled against production
- One additive migration this sprint (`courses/0070`), applied migrate-first with its ledger row
- Production data passes: 25 interview credits re-credited; `results_exam_type` backfill **not run**
