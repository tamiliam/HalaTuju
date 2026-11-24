# The replay's human lens: how to run it and how to read it (LL5)

This note is for the release lead and the owner. It explains one part of the replay job's output.
The code lives in `halatuju_api/apps/scholarship/eval/replay/` and in
`halatuju_api/apps/scholarship/coach_grade.py`. The full rules are in `docs/decisions.md` (the LL5
entries of 24 Nov 2026).

## What it is

The replay tool (`python -m replay.parent`) normally compares old engines with new ones.
With the human lens on, it also marks the AI against the answers of human reviewers.
It reads stored, decided cases. It writes nothing to the database. It reports counts only.
It has two parts: the exam lens (a fixed set of cases) and the coach grade (each engine version against the one before it).
The lens is a report. It decides nothing by itself.

## How to run it

The lens is OFF by default. Three flags control it. They come from `parse_args` in `parent.py`.

| Flag | What it does |
|------|--------------|
| `--human-lens` | Turns the lens and the coach grade on. Without it, the output is exactly as before. |
| `--human-lens-exam-folder <folder>` | The folder that holds the exam files. It must be a full (absolute) path. It must not be inside a git repository. `--human-lens` without this flag is an argument error (exit code 2). |
| `--human-lens-freeze` | Allows the lens to write a missing exam file. Off by default. Without it, nothing is ever written to the exam folder. |

These are argument errors (exit code 2). The job stops before any child starts and before any file is
touched:

- `--human-lens` without `--human-lens-exam-folder`;
- the folder flag or the freeze flag without `--human-lens`;
- `--counts-only` together with `--human-lens`. They cannot be used together. Run the counts first
  without the lens, then the lens run on its own;
- a folder that is not a full (absolute) path, for example `exams` or `./exams`. The parent uses the
  same rule as the `new` child (Python's `os.path.isabs`). The message does not repeat the folder.
  The child still refuses such a folder too (`folder_not_absolute`), as a second lock.

`--counts-only` without the lens works exactly as before.

A freeze happens only with `--human-lens-freeze`. A normal run never writes an exam file.
An exam file that already exists is never replaced.
If an exam file is lost, a normal run says so (`exam_missing`). It does not make a new one.

With the lens on, only the `new` child gets the fingerprint key (`REPLAY_FINGERPRINT_KEY`).
With the lens off, no child gets it.

The standing rules:

- The first run on live data needs the owner's yes. The first freeze is part of that run.
- The run time is agreed with the release lead.
- Never run it in a release slot (11:00, 16:00 or 21:00 MYT).
- Never run it beside a migration or a deploy (see the hard rule in step 5 of
  `docs/plans/2026-11-13-a5-replay-owner-steps.md`).
- Never run it on an R3 run day.
- The lens must not run on real data until the owner decides where the exam file lives. The two
  options are in the owner-steps doc, in the section "Where the exam file lives in production".

## Where to find the result

The job's output goes to Cloud Logging, under the job.
With `--human-lens` on, the lens block comes after the job's JSON lines.
It starts with this line:

`=== LL5 lens report start ===`

It ends with this line:

`=== LL5 lens report end ===`

Cloud Logging stores each line as its own entry. So find the two marker lines first. Then read every
entry between them, in order.

A block with a start line but no end line is NOT a result. The output may have broken while the block
was printing, and a fatal line could follow half a block. Treat a block with no end line as a failure.

There is no block when the lens is off, after an argument error (exit code 2; `--counts-only` with
`--human-lens` is one), or after a fatal error (exit code 3).

The job's exit codes:

| Exit code | Meaning |
|-----------|---------|
| 0 | The run finished. This does NOT mean pass. Read the block. A refusal also exits 0. For example, a missing or blank fingerprint key gives exam-1 the refusal `key_blank`: exit 0, but the exam did not run. |
| 2 | An argument error. Nothing ran. |
| 3 | A fatal error. There is no block. A fingerprint key that is set but is not 64 hex characters (a newline or a space in it, for example) is one: the job stops at its set-up, before any child starts. |
| 4 | A lens or coach-grade error, or a report that could not be shown. |

## How to read it

The block reads from top to bottom. The parts below are in the order they print.
The words in quotes are the words the block uses.

### 1. The summary line

The first line under the heading "Human lens and coach grade" is the summary.

- "No blocking item." means nothing in the block is marked BLOCKING.
- "BLOCKING: N item(s): ..." counts the blocking items and names each one.
- "Not run: ..." lists what was refused, for example "exam-1 (refused)" or "coach grade (refused)".
- "No grade yet: ..." lists what has no grade yet: "(not frozen yet)", "(too few facts to grade yet)"
  or "coach grade (no pair to grade yet)".

### 2. The human lens

The heading is "Human lens". If the lens failed, there is one line: "lens failed: <code>. BLOCKING."
and nothing else. Otherwise:

- "Engine version": the engine version that the `new` side ran.
- "Cases read": every application the lens read. "Not decided": cases with no decision time.
  "No human verdict": decided cases with no fact marked Pass or Fail.
- "Decided cases whose context record failed (in neither exam)": cases whose stored context record
  holds an error. They are in neither exam.

Then one part for each exam. There are two exams. They are never mixed.

- **exam-1**, "same evidence, checked by fingerprint". The first 50 decided cases with a full stored
  context, by decision time. A keyed fingerprint checks that each case's evidence has not changed.
- **exam-old**, "weaker exam: evidence state unknown". Cases decided before LL4. Their stored context
  is empty, so they have no fingerprint. This exam is weaker, and its label says so.

The exam file holds the plain application ids and one decision time for each id. Nothing else about
a case is stored in it.

Each exam part shows:

- "not run: <code>". Shown only when the exam was refused. The words after "Meaning" say why.
  A refusal is not a pass.
- "Status": "frozen", "not frozen yet: N of 50", or "refused: <code>".
- "Frozen": "yes, at <time>" with "Size" (the number of cases in the exam), "Digest" (the first 12
  characters of the exam file's check sum) and "Key check" (8 characters that show which key the exam
  was frozen under; it is not the key). exam-old shows "Key check: not used for this exam".
  "Frozen: no" means there is no exam file yet.
- "Candidates": how many cases could enter the exam. Shown when the exam file is missing.
- "Cases with another key check": how many cases carry a different key check. Shown with a key
  refusal.
- "Validity": each listed case gets one state in this run. "still valid" (scored), "evidence changed",
  "could not recompute", "missing", "context record changed", "no longer decided" and "decided again"
  are not scored. The counts add up to the size.
- "N of M still valid": how many listed cases are scored in this run.
- "Valid split" (exam-1 only): "matched directly" means today's fingerprint equals the stored one.
  "recovered by twin" means a copy of the case at an in-review status gave the stored fingerprint.
- "Could not recompute, by reason" (exam-1 only): "past the award stage", "twin in a decided group",
  "twin not unique", "recompute error" and "key not current". Each is a case the lens could not check.
  exam-old shows "Valid split and could-not-recompute reasons: not kept for this exam."
- "Fails the QC turned to Pass": on a fact the reviewer failed, a QC second look that disagreed turns
  the Fail into a Pass in this exam. This counts those facts.
- "Score": facts marked, points out of the best possible points, the score as a percent, and facts
  not scored. Under 5 facts it shows "too few facts to grade yet" and no score.
- "Outcomes": how many facts were "right and sure", "right but leaning", "unsure", "wrong but leaning"
  and "wrong and sure".
- "Coverage": facts where the AI did not show Unsure, out of all facts marked.
  "Generous-wrong": facts where the AI showed Certain or Probable but the human failed it.
- "Score without interview Fails": the same score with each Fail whose reason is "interview differs"
  left out. It is an extra line to compare with. The main score still counts those Fails.
- "Fails": the Fails, counted by the AI's band and the reviewer's reason. Interview Fails are counted
  apart, in "Interview Fails by band".
- "Share of "other" among the Fails": how many Fails carry the reason "other". It shows no percent
  when there are too few.
- "Known limits": the limits of this exam's score, for example "a score on N facts" and "drop-outs
  shrink the exam". exam-old also shows its weaker label here.

### 3. The coach grade

The heading is "Coach grade". If it failed, there is one line: "coach grade failed: <code>. BLOCKING."
If it was refused, there is one line: "not run: debug_on". Otherwise:

- "Floors": "a month needs 5 facts for a score; a version needs 40 facts to be graded".
- "Guard level: 1 in 20": a guard breaks only when luck alone would give a change this big less than
  1 time in 20.
- "Score margin: 2 standard errors": the score counts as up or down only when the change is bigger
  than 2 standard errors (the usual size of a chance wobble).
- "Decided records": every decided case the coach grade read. "Versions without marks": versions with
  no marked fact at all.
- "Malformed records": records the coach grade could not read. They are left out and counted, by kind,
  for example "record too short". A kind it does not expect means a bug, not bad data.
- The line about "score without interview Fails": which Fails the extra line leaves out.
- "Monthly score": a table with one row for each engine version and each month (Malaysia time). A row
  with under 5 facts shows "too few facts to grade yet" and no figures. A version that was not
  recorded shows as "unknown: version not recorded" or "unknown: made before versions were recorded".
  Those are never graded.
- "Coach pairs": each version compared with the gradeable version before it, on its own newly decided
  cases. Each pair shows a grade ("pass", "fail" or "no clear change"), the reasons, and how many
  smaller versions lay between the two. Under each pair, "Previous" and "New" show each side's facts,
  score, coverage and generous-wrong.
- "Waiting versions": versions with under 40 facts. They show "too few facts to grade yet".

How a pair is graded, in this order:

1. Guard 1: coverage must not clearly drop.
2. Guard 2: generous-wrong must not clearly rise.
3. A broken guard is a "fail", whatever the score.
4. With no guard broken: score clearly up is "pass"; score clearly down is "fail"; anything else is
   "no clear change".

### 4. Read with care

When at least one of the two results is clean, the block ends with the heading "Read with care" and
three fixed lines. A refusal counts as clean here. When BOTH results failed, these lines do not print.
When the report could not be shown, the block holds only the line "lens report failed. BLOCKING.
There is no result, so this is not a pass.", and these lines do not print either.

The three lines, word for word:

- "The exam lens turns a Fail the QC disagreed with into a Pass. The coach grade keeps the reviewer's
  stored answer. So the two can differ on those facts."
- "A coach grade moves from run to run on small numbers. "No clear change" means the difference is not
  bigger than luck."
- "Counts only: this section holds no case id and no name."

## When a result blocks the next release

**A missing key is a refusal, and a refusal exits 0; read the block, not the exit code.**

These lines carry the word BLOCKING:

- a lens error: "lens failed: <code>. BLOCKING.";
- a coach-grade error: "coach grade failed: <code>. BLOCKING.";
- a report that could not be shown: "lens report failed. BLOCKING.";
- each coach pair graded fail: "<previous> to <new>: fail. BLOCKING." with its reasons.

The first three make the job exit with code 4.

**Exit code 0 does not mean pass.** A coach pair graded fail prints BLOCKING, but the job still exits
with code 0, because a fail is a result, not a job error. So read the block, not only the exit code.

A block with no end marker line is treated as a failure (see "Where to find the result").

These are NOT a pass and NOT a fail. They are no evidence:

- "not run" (a refusal, for example "not run: exam_missing" or "not run: debug_on");
- "too few facts to grade yet";
- "not frozen yet";
- "no clear change".

Who decides: the release lead reports the block to the owner. The owner decides whether the next
release goes ahead. This tool only reports.

## What the numbers cannot tell you

- The facts inside one case are not independent. One case carries about 4 facts from the same student
  and the same reviewer. So "1 in 20" is not the true false-alarm rate. Simulations on made-up cases
  graded an unchanged AI "fail" about 4 to 10 times in 100 with independent facts, and more often when
  a case's facts move together.
- There are three checks (two guards and the score). Nothing adjusts for that. Each one is one more
  chance of a result that is only luck.
- Points are lumpy: mostly +2, with the odd -10. The score test treats them as smooth. This is rough
  at 40 facts.
- At 40 facts a side, a real worsening of generous-wrong from 5% to 15% is missed more often than it
  is caught: about 6 or 7 times in 10.
- A grade can move from one run to the next on small numbers. A waiting version that reaches 40 facts
  joins the chain, and the newest version keeps growing.
- "Can't verify" counts as covered. Only Unsure is uncovered.
- The exam lens turns a Fail that the QC disagreed with into a Pass. The coach grade keeps the
  reviewer's stored answer. So the two can differ on those facts. The owner has not yet ruled which is
  right.
- Cases past the award stage, and cases whose only matching twin is in the decided group, are left
  out of exam-1's score. The block shows the counts by reason, under "Could not recompute, by reason".
- The stage at the decision is not stored. So only a case whose stored fingerprint comes back at an
  in-review status can be recovered by a twin.
- The allow-list checks that each number is a whole number. It cannot check what a number means.
- Each coach-grade version is scored on its own cases. A change in which students applied can look
  like a change in the AI. The frozen exam (the same cases for every version) is the answer to that.
- The exam lens catches only some errors (a bad case row, a value or type error, a file error). If it
  meets an error it does not catch (for example a database error, or a document snapshot left open),
  the whole `new` child stops. Then the coach grade does not run either. Both parts show `no_output`
  and the job exits with code 4.
- Two runs that share one work folder (the default is `/tmp/replay`) can read each other's result
  files. Never run two at once in one folder.

## Safety

- Read-only: one read-only session; no save, no network, no AI call.
- Counts only: no case id, no name and no free-text reason in the block.
- Under Django `DEBUG`, both the exam lens and the coach grade refuse before any query (`debug_on`).
- The fingerprint key is never printed. Only its 8-character key check is shown.
- Both result files (`human_lens.json`, `coach_grade.json`) pass an allow-list in the child before
  they are written, and again in the parent when they are read.
