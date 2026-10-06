# Retrospective — TD-352, an officer closes a stalled application (2026-10-06)

Sprint, api + web (cockpit and the student's application page). Owner ruling, option A: a stalled
in-process application is released by an OFFICER closing it by hand; no clock. Built by an Opus
builder in the worktree `feat/td352-close-stalled` (cut from `9dd3bef2`, rebased over request #28's
follow-up `21dd9a3b`), three adversarial review rounds, pushed as `48fda4bd` (26 commits). Migration
`scholarship/0168_closure_reason_stalled` — choices-only, no DDL; the production ledger row was
recorded before the push (`django_migrations` id 263).

---

## 1. What Was Built

* **Close from any in-play status** (`apps/scholarship/closure.py`). `CLOSEABLE_FROM` *is*
  `apply_gate.IN_PLAY_STATUSES` (imported; a test asserts the identity). New reason `stalled`.
  Reasons by stage: submitted…recommended → `stalled`, `withdrawn`; awarded/active/maintenance →
  the five post-award reasons plus `stalled`. The row is re-read under a lock; the checks run in a
  fixed order (`not_closeable` → `bad_reason` → `reason_not_allowed` → `forbidden` →
  `decline_pending` → `sponsorship_open`); an `AUDIT application_closed … from=` line records the
  status it left.
* **Who may close.** Before an award: super or org_admin only (the same pair that may org-reject);
  judged on the LOCKED status. The assigned reviewer keeps the funded close as before.
* **One door per job.** The close REFUSES while a HOLDING sponsorship or a released tranche exists
  and never cancels money. An `awarded` case therefore cannot be closed here at all today (TD-366,
  owner decision); the cockpit hides the card at `awarded`.
* **`closed` is a closed case for the review track.** `'closed'` joined `CASE_CLOSED_STATES`
  (api) and `isCaseClosed` (web, drift-tested): a case closed at `interviewing` no longer takes a
  verdict, an award amount or an interview. A funded closed case loses nothing (payments,
  spending, notes, the thank-you relay read neither set).
* **A FUTURE booked interview is voided** with the close (`scheduling.release_for_unassign`, in
  `transaction.on_commit`, re-read before acting); a past one is left alone; proposed times are
  withdrawn; the reminder sweep reads in-play cases only.
* **The student is told.** A pre-award close emails her ("closed by our team" / "closed at your
  request" for `withdrawn`; both say "apply again in a later round"); the application page's 'one'
  state carries `scholarship.application.oneAtATime` under "Programme:". No email from a
  post-award close.
* **Closed-before-funding is not post-award.** `stageStatus` (`lib/closeOffer.ts`) gates
  "recommended by", the Awarded/Active chips and the witness card on `recommended_at` /
  `active_at` when the status is `closed`; the in-programme page and `in_programme.py` accept
  `closed` only with `active_at`; reviewer figures count a closed case as recommended only with the
  stamp.
* **Weight off three routes.** The award/agreement panels and `IncomeRouteSwitch` load on demand on
  `/scholarship/application`; the 2,480-row secondary-school list behind `SchoolSelect` loads on
  first pointer-over/touch/focus. Budgets LOWERED: `/profile` 300 → 271, `/scholarship/apply`
  272 → 244.

## 2. What Went Well

* **The reasons table has one home and the drift test bites.** Injecting `'lapsed'` into
  `PRE_AWARD_REASONS` in `closure.py` turned `closeOfferDrift.test.ts` red (1 failed, 44 passed);
  restored and verified.
* **The builder stopped at the rails it was given.** It raised the same-round question before
  writing the copy, stopped at the apply route rather than touch the form path, and raised the
  `CASE_CLOSED_STATES` gap instead of leaving it to the reviewer.
* **The weight problem became a win.** The apply route had no spare weight; the house pattern
  (/profile's lazy postcode table) applied to the school list took 29 kB off three routes and
  gave `/profile` a year of room.

## 3. What Went Wrong

1. **A status that became reachable from a new stage inherited every reader that assumed the old
   stage.** *Symptom:* review round 1 found four screens and one api figure reading `closed` as
   "QC-accepted / funded" (the "recommended by" line, the Awarded·Active chips, the witness card,
   the in-programme page, reviewer stats), and a never-funded closed student could reach the
   funded page and send a "thank your sponsor" message. *Root cause:* `closed` had only ever been
   written from `active`/`maintenance`, so every reader could treat it as the END of a funded life;
   the sprint widened the writer without walking the readers. The brief said "list every reader
   of CASE_CLOSED_STATES" but not "every reader of the STATUS". *System change:* lessons.md — when a
   status becomes reachable from a new stage, grep every reader of that status literal on both
   sides before the build, and gate on milestone stamps (`recommended_at`, `active_at`) where the
   reader meant a stage, not a status.
2. **A booked interview has no "happened" state, so a past one looked live.** *Symptom:* round 2
   found the close would delete the calendar event and email the reviewer "interview cancelled"
   for an interview held weeks earlier — the headline TD-352 case (closing at `interviewed` /
   `recommended`). *Root cause:* `interview_status='booked'` persists after the interview; the only
   signal is `interview_start > now`, and the unassign path the close reused had never met a past
   booking because unassign is refused from `interviewed` onward. *System change:* the close voids
   only a future booking (tested both ways); lessons.md carries the general form — a reused
   teardown path was written for the states its caller could reach, and a new caller must list
   the states IT can reach.
3. **The api deploy gate refused the push (`9fd4a007`): 1 failed, 8052 passed.** *Symptom:* the
   gate runs `pytest -n auto`; one new test passed a `datetime` as a `subTest` kwarg, and xdist's
   execnet cannot serialise a datetime back to the controller — a `DumpError`, not an assertion.
   Every local run was serial, so it passed four times here. *Root cause:* the local gate and the
   deploy gate were not the same command; `halatuju_api/cloudbuild.yaml` has said `-n auto` since
   H2 and nobody ran it that way locally. *System change:* the api `CLAUDE.md` test command and the
   lead's close checklist now run `python -m pytest -q -n auto -p no:cacheprovider` — the gate's own
   line (it is also faster); lessons.md. The second deploy of this feature is the fix (`subTest`
   names the marker, not its value) plus the close docs — at the two-deploy cap.
4. **The review's fixes read as churn in the health reading.** `fix%` 43 → 45 because three
   review rounds landed as `fix:` commits the same day as the `feat:`. Not a code problem; recorded
   in `docs/code-health.md` and left for the tool proposal already open there (a `review:` prefix
   or the lane's commit-SHA classification would separate review fixes from field fixes).

## 4. Review findings and their answers

Round 1 (12): #1 permission → super/org_admin pre-award; #2 awarded case → honest refusal copy,
card hidden, TD-366; #3 booked interview → voided (future only, after round 2); #4 email copy →
"a later round", TD-364 struck; #5 closed-as-post-award → `stageStatus`; #6 in-programme →
`active_at`; #7 "Closing is final" + confirm; #8 payment runs → TD-367 (pre-existing); #9 pending
decline → `decline_pending`; #10 docs figures; #11 tests; #12 TD-365 already filed. Round 2 (7):
past interview (blocker) → `interview_start > now`; teardown in the transaction → `on_commit`;
stale role check → judged on the locked row; hidden reviewer count → folded into `awaiting_qc`;
reopen edge → noted in TD-363; loading label; copy. Round 3 (2): propose/book on a finished case
→ TD-368 (pre-existing); template parity → test added. Nothing accepted without a fix or a ticket.

## 5. Numbers

* Baselines (measured in the worktree before any change): 7990 pytest / 3 skipped · 4026 jest /
  242 suites.
* Final (rebased tree): **8053 pytest / 3 skipped · 4136 jest / 252 suites** · tsc 0 ·
  bundle ok (application 273.047 of 274; apply 242.6 of 244; profile 269.8 of 271; median 228.023
  of 229).
* 26 commits, 51 files (28 source, the rest tests, messages and docs), +2413 / −249.
* Debt: TD-352 and TD-364 closed; TD-363, TD-365, TD-366 (owner, money), TD-367, TD-368 raised.
