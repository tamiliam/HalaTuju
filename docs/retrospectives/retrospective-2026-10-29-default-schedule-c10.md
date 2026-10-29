# Retrospective — the no-template payment schedule mirrors contract 10 (2026-10-29)

Commit `e6a03fb3`, no migration. Live: `halatuju-api-01191-f9p`, `halatuju-web-01020-b7q`, both 100%, api
health 200.

## What Was Built

- The owner asked what HalaTuju's default payment schedule is, then pointed at draft contract 10 and asked for
  the default to mirror it "for now".
- `apps/scholarship/default_schedule.py`: eight RM200 rows identical to contract 10, as unsaved
  `PaymentScheduleRow`s, chosen by the same rule a template uses (`contracts.pick_schedule_row`, split out of
  `schedule_row_for`). `payments._schedule_row` never returns `None` now; the `PATHWAY_PAYMENT_START_MONTH`
  fallback is deleted.
- Effect on runs: Poly/University grey `gap_month` in November, STPM in December and June, every pathway
  greys `schedule_complete` after its last paid month. Run-page labels for both reasons (en/ms/ta; they had
  none, because no template had ever been active).
- The seed fixture's poly/university rows gained the November gap; a drift test ties the default to it.

## What Went Well

- **Checking the live data before answering.** The first answer came from the seed file; reading contract 10
  in production showed the real gap (the November skip) AND that no template was active — so the "default"
  was the thing paying every student, and the November run was days away.
- **The adversarial review earned its keep.** It found two test files the fixture fix missed, missing screen
  labels, and the in-flight November draft risk. All answered before the push.
- **A read-only money probe before the push:** all 65 payable students still reach exactly their award under
  the new schedule (none short, none over); no student is a late starter.

## What Went Wrong

- **Two date-dependent test fixtures broke, and I first fixed only one.** Symptom: the full gate failed
  `test_on_hold_review_fixes.py` after I had fixed `test_on_hold_money.py`. Root cause: both copied the same
  "last year's matric cohort is always payable" assumption, true only while the schedule had no end; I fixed
  the failure I saw instead of grepping for the assumption. Fix: the second file now imports the one helper
  (`_paid_cohort_year_and_pathway`); lesson added — when a change removes an "always true" property, grep
  every test that leans on it before running the suite.
- **A November draft run already held the old line-up.** Symptom: 65 items including 14 students the new rule
  skips. Root cause: `create_run` snapshots eligibility, and `complete()` never re-checks it; a rule change
  does not reach a draft. Fix: the owner cancels and re-creates the draft (owner chose this); lesson added —
  a change to who is payable checks for open draft runs before the push.
- **`--new` in `sol_tag` tagged ~1,200 entries**, not just this change's six strings, because other sessions'
  new strings were also untagged. Harmless (a tag is a label), but the tag name over-claims. No system change:
  noted here so the reviewer reading Sol knows.

## Design Decisions

- One row shape and one choosing rule for template and default, so they can only differ in numbers
  (`docs/decisions.md`, 2026-10-29). Not activating contract 10 instead: signing (TD-347) is unfinished.
- Accepted risk (review finding 3): the STPM variant is chosen by `award._stpm_continuing` (the offer letter),
  not by the award amount; a flip of a fresh student to "continuing" would end their schedule after November.
  Nobody is in that state today; the probe pairs award with variant and found them all consistent.

## Numbers

- Before the rebase onto maintenance S4a: api **10,216 pass / 3 skipped** (`pytest -n auto`, 10,213 + the 3
  fixed failures re-run green), web **4,914 jest / 316 suites**, tsc 0, lint 0, i18n parity ok.
- After the rebase: the payment, contract, on-hold and code-standards files (238 pass), `makemigrations
  --check` clean, i18n parity, 2,791 jest in `src/test` + `src/lib/__tests__`; the deploy gate then ran the
  full suites green.
- Bite-check: the poly row reverted to ten straight months turned three tests red (drift, diploma gap, parity).
- Hours: planned ~2, actual ~3 (the review's findings and two full-suite runs of ~18 minutes each).
