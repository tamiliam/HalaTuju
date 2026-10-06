# Retrospective — Sponsor spending S2: the reports arrive on their own

**2026-09-10.** Worktree `.worktrees/spending-ingest`, branch `feat/spending-ingest`.
Roadmap `docs/plans/2026-09-10-sponsor-spending-roadmap.md`.
**Backend only. NO MIGRATION. Not merged, not deployed.**

## What was built

`sheets.spending_reports_in` + `read_spending_report`; `spending_import.files_needing_read` /
`drive_sources` / `days_since_last_report` / `should_nudge`; `--drive` and `--no-email` on the
command; `emails.send_spending_alert_email`; cron job `spending-ingest` (daily, `--drive --apply`).
23 new tests, 55 in the file, **6179 in the full suite**.

## What went well

- **The S1 seam paid for itself exactly as designed.** `rows_from_values` takes plain lists, so the
  Drive path handed it Sheets API values and inherited all five drift rules for free. Not one
  parsing rule was written twice.
- **Reading the email before calling it done found nothing wrong — which is the point.** The
  standing lesson is that `_send_html` defaults its sender to the interview alias and the wrong
  call is the shorter one. Following `send_vircle_activation_email`'s plain-`EmailMessage` shape
  avoided it, and rendering one instance proved it rather than assuming it.
- **The owner rejected my first framing of the file-tracking decision, and was right.** I offered
  "re-read everything daily" versus "keep a seen-list" and justified the first with an argument
  about duplicates — which the `txn_id` dedup already handles regardless. Being pushed on it
  produced option C (Drive's `modifiedTime` against our own `imported_at`), which is better than
  both: no waste, no new table, and an edited file is still noticed.
- **The full suite caught a break the targeted suite could not.** See below.

## What went wrong

### 1. Two bite-checks came back silent, and both had a lesson already on file

**Symptom.** Injecting a fault into the quiet-day guard changed no assertion. Injecting one into
the filename guard changed no assertion. Both reported green while genuinely broken.

**Root cause, and it is the same for both: I designed each test against the CODE I had just
written, not against the HARM the guard exists to prevent.**
- The quiet-day tests asserted "no rows stored, no email" on an empty folder — true with or without
  the guard. What the guard actually prevents is a **standing** finding (a funded student with no
  wallet, true every day until fixed) generating an alert **every single day, for ever** — the
  all-clear email the owner explicitly refused, wearing a finding's clothes.
- The filename tests asserted the regex matches the right names. All three stayed green with the
  filter deleted from `spending_reports_in`, because none of them called it.

**Why this stings.** `lessons.md` already carries both: *"when an injected fault produces SILENCE,
ask which test should have failed and write it"* (2026-09-08) and *"a unit test on a helper does not
prove the helper is CALLED"* (2026-07-30). I read that file at sprint-start and let it change the
**production code** (the missing-column refusal is shaped by it) while leaving my **test design**
untouched.

**System change.** A test written for each; both then bit. The general form — design a guard's test
from what the guard prevents, not from what it does — is in `lessons.md`.

### 2. Two bite anchors matched nothing, twice, on a line-ending rule I already knew

**Symptom.** Two of six bites reported `ANCHOR NOT UNIQUE (0)`. Later, patching the door guard, the
same thing: an `assert` on an anchor that could not match.

**Root cause.** `views.py` and `sheets.py` are **CRLF**; the new modules are LF. I typed multi-line
anchors containing `\n` from files I had authored myself. The bite helper reads with `newline=''`
(correct, and written that way *because* of this rule) — so it preserved CRLF faithfully and my
anchor simply was not there.

**What saved it.** The helper refuses to run on a non-unique match and says so. A count of 0 reads
as *"the code has moved"*, which is what a bite probes for — so without that explicit
`ANCHOR NOT UNIQUE` line I would have recorded two unproven bites as findings.

**System change.** Anchors now **derive** the newline from the file
(`nl = '\r\n' if '\r\n' in raw else '\n'`) rather than having one typed into them. In `lessons.md`.

### 3. I changed a shared registry's SHAPE and checked its writer, not its readers

**Symptom.** `test_repair_commands_have_a_door` — two sprints old, in a file I had no reason to open
— died with `TypeError: unhashable type: 'list'` on `set(CronRunView.JOBS.values())`.

**Root cause.** Before adding `(name, [args])` to `JOBS` I checked exactly one thing: how
`CronRunView` **invokes** it. I never asked who else **reads** it. The grep that found the answer
took ten seconds and I ran it only after the failure.

**Fixed properly, not worked around.** The entry is an immutable tuple, and the guard unwraps a pair
through a named `_registered_commands()` helper — because its question is *"is this command
reachable?"*, so a future `repair_*` job registered with flags must not read as stranded.

**System change.** The full suite is what found it, which is the existing rule working. The habit to
add is in `lessons.md`: changing a shared structure's SHAPE puts every reader in scope, and the
grep belongs *before* the change.

## Design decisions

In `docs/decisions.md`: a new file is the trigger rather than the calendar; which files to download
is new-or-changed with no state of our own; the nudge fires on multiples and is derived, never
stored; `CronRunView.JOBS` accepts a `(name, args)` pair; the alert uses a plain `EmailMessage`
with an explicit sender; and the filename pattern is a guard against reading our own output.

## Numbers

| | |
|---|---|
| Files touched | 9 |
| pytest, full `apps/` | **6179 passed** (+23) |
| `makemigrations --check` | clean — **no migration this sprint** |
| Migration ledger vs production | unchanged: scholarship 154/155 (S1's `0155` still unapplied), courses 74/74 |
| Bite-checks | 6 injected, **2 silent on the first pass**, tests written, 6 bit |
| Frontend gates | not run — no web file changed |

## At deploy (owner-gated, NOT done)

1. S1's **`scholarship/0155` MIGRATE-FIRST** — unchanged, still the first step.
2. Set **`VIRCLE_SPENDING_FOLDER`** if the live tree differs from the default (read it from
   `gcloud run services describe`, never from the settings default — every other `VIRCLE_*` folder
   is already overridden there).
3. **⚠ RUN `--drive` WITHOUT `--apply` ONCE AND READ IT.** This is S2's only real proof: the
   service-account key exists nowhere but the live service, so nothing about the Drive hop can be
   verified from a laptop. Expect the eight files listed and the S1 figures re-derived.
4. Only then create the **daily** Cloud Scheduler job hitting `spending-ingest`.
5. **Nothing a student or sponsor sees changes.**
