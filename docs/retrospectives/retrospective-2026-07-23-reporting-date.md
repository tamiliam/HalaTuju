# Retrospective — the reporting date becomes a first-class fact — 2026-07-23

Triggered by one observation from the owner: *"Look at #123. The recommended amount is wrong."*

## What Was Built

- **`services.sync_reporting_date_from_offer()`** — one owner for the offer→column copy, called
  before the pathway guards instead of after them.
- **`pathway_engine.course_start_year()` / `started_before_cohort()`** — the continuing-student
  signal, reading the offer's INTAKE YEAR first, then the stored date. Shared by both consumers.
- **QC stop** — `reporting_date_required`, absolute, no override.
- **Reporting-date box** (`AdminReportingDateView`) above Recommendation, in the reviewer's window
  only, plus the surface now reading the stored value rather than the document string.
- +17 backend tests, +5 jest. No migration. 4280 pytest / 648 jest.

## What Went Wrong

**A fact that three rules depended on had no owner.** The copy from the offer letter sat at the
bottom of `autofill_pathway_from_offer`, below four `return False` guards about the PATHWAY. A
letter whose programme disagreed with the declaration — exactly the case that raises the "please
confirm" query — abandoned the function and took the date with it. **45% of applications needing a
pathway confirm had a NULL date, against 3.8% of the rest.** Consequences: #120 and #123 were
committed RM3,000 instead of RM1,000, and #123 was never asked for his semester result.

*Root cause:* the date was a passenger in a function whose real job was settling the pathway, so it
inherited every one of that function's exits. *Fix:* its own function, called from the same
triggers, above the guards. → lessons.md.

**The same rule existed twice.** `award._stpm_continuing` and `income_engine.semester_result_gap`
each hand-rolled "started before the cohort year" against the same unreliable field, so both were
wrong for the same students and a fix to one would have left the other. Now one shared predicate.

**The field was not the question.** What sizes the bursary is the course-START year, and a Form 6
letter routinely carries an intake RANGE (`6 / 2025 – 12 / 2026`) with no reporting date at all —
so reading `reporting_date` alone could never have worked for that document family.

**This exact bug had been found before.** A test named
`test_autofill_persists_date_even_when_pathway_locked` already existed: the identical failure was
diagnosed, fixed and pinned for the LOCK guard, and nobody checked the four guards above it. The
strongest evidence that the shape — not the instance — was the problem.

## What Went Well

- **Two of my own proposals were killed by evidence, both before they shipped.** Parsing the
  student's free-text answer into the field (the obvious reuse of the Vircle-ID pattern) would have
  been wrong for half the live parseable answers — #123 replied with the date he collected a
  confirmation letter. And the three provenance columns I built were removed: the owner called them
  over-engineering, and checking showed the cockpit already derives typed-vs-documented from
  document corroboration, so the schema would have duplicated a free signal.
- **Every new test was verified to fail against the pre-fix code**, including the misread-answer
  case.
- **Predicted the fixture breakage before running it.** Adding the QC stop broke 17 tests whose
  fixtures pre-dated the new contract — the lesson about gates on shared endpoints held exactly.
- **Corrected two of my own analysis errors mid-flight**: a scope query that joined #107's two live
  offer letters without ordering and mis-classified him, and a claimed "fourth untraced write path"
  that did not exist.

## Numbers

- **4280 pytest** (+17) + **648 jest** (+5). No migration.
- Data: #120 and #123 corrected to RM1,000 (neither had a sponsorship or a completed payment);
  12 reporting dates backfilled — 7 NULLs filled and 5 stale values corrected against the latest
  letter. **No amount changed** as a result: only a rejected applicant reads as continuing.
- **▶ CARRY:** ms/ta first-drafts for `reportingDateEntry.*`; #107's superseded duplicate offer
  letter still needs archiving (owner: separate exercise).
