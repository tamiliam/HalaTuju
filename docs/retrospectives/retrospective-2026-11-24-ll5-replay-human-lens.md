# Retrospective: LL5, the replay human lens and the coach grade - 2026-11-24

One sprint, built on branch `ll5` (25 commits on top of `origin/main` `f0631426a`). Built and reviewed; NOT landed. The release lead lands it in its own slot. It changes no live output. Plan: `docs/plans/2026-11-18-learning-loop-roadmap.md` (section LL5, and the block "What changed while building (24 Nov 2026)"). How to read the report: `docs/replay-human-lens.md`.

## What Was Built

- **Phase A - the coach grade.** A new file, `apps/scholarship/coach_grade.py`. The score is points over 2 x the facts marked, with a noise margin. Guards on coverage and on a "generous but wrong" coach. The minimum is 40 facts.
- **Phase B - the replay learns to compare with people.** The replay recomputes fingerprints with a one-way derived key, never `SECRET_KEY`. The human lens scores each version against human answers: exam 1 is frozen at 50 decided cases; old cases form a separate, weaker exam; an extra score line leaves out interview Fails.
- **Phase C - the wiring.** Three flags on `python -m replay.parent`: `--human-lens`, `--human-lens-exam-folder`, `--human-lens-freeze`. Two allow-listed result files (`human_lens.json`, `coach_grade.json`). The report block, the exit codes, and the owner documents.

## What Went Well

- With the lens off, the output is byte-identical to before. A reviewer proved it against the parent commit.
- Every result file passes an allow-list on both the child side and the parent side. No case id and no free text can leave.
- Phase C passed three review rounds with no blocker.
- One full back-end gate on the rebased head: 25,198 passed, 3 skipped, 0 failed, 54,622 subtests, 19 min 55 s.
- No real data was read, no paid call was made, and no agent ran a secret command.

## What Went Wrong

1. **The coach grade (phase A2) failed three review rounds and went to the owner.**
   - Root cause: the review briefs counted crafted hostile Python objects as blockers.
   - Preventive change: every review brief now states the bar. A blocker is a wrong result for realistic input (database rows, real datetimes, files on disk, real command lines). Crafted objects are notes.
2. **A builder brief said a wrong-shaped key "does not start the job".** The code truth is `ImproperlyConfigured`, exit 3, with the lens on or off. It stops every replay run.
   - Root cause: the lead wrote a behaviour claim from memory, without a cite.
   - Preventive change: a brief states code behaviour only with a file:line cite, or tells the builder to verify it first.
3. **The "ready to land" message was wrong about three files.** It said `ai_score.py`, `verdict_context.py` and `eval/replay/settings.py` were not touched. The branch changes all three (earlier phases). The release lead had already advised the owner on a slot and had to withdraw it.
   - Root cause: the lead wrote the hand-over from its notes on the last phase, not from the branch diff.
   - Preventive change: build the hand-over message from `git diff --name-only origin/main..HEAD`. Every changed non-test file outside the feature folder gets one line: who calls it live, and is the live output the same.
4. **Phase C was planned as three parts and took eight** (C1, C1b, C1c, C2a, C2b, C2c, C2d, C3), plus a fix round and a wording touch-up.
   - Root cause: the plan sized the wiring by flags, not by the number of result paths and exit codes.
   - Preventive change: size a wiring phase by counting its exit-code table rows and result files first.
5. **Build agents were pushed to the background on long test commands and lost their result.**
   - Root cause: the default command timeout.
   - Preventive change: every brief says to set the Bash timeout to 600000 ms on test commands, and to start no background runs.
6. **The rebase stopped at commit 1 of 25 on `CHANGELOG.md`.** Both sides add at the top of Unreleased.
   - Resolved once by hand and reused for the other 24 commits. The result was proved equal by numstat.
   - No change proposed.

## Design Decisions

Recorded in `docs/decisions.md` (the LL5 entries). Not repeated here.

## Numbers

- 25 commits on `ll5`; 32 files changed against `origin/main` (5 docs, 14 source, 13 tests); 9,006 insertions, 31 deletions (before this close commit).
- 3 review rounds on phase C (4 readers); all passed with notes.
- Back-end gate: `pytest -q -n auto` in `halatuju_api` (WSL, Python 3.11): 25,198 passed, 3 skipped, 0 failed, 54,622 subtests, 19 min 55 s.
- Jest not run: the branch changes no web file.

## Open Items

- Three owner decisions: which answer is the truth when the QC overturned a Fail; where the exam file lives; who makes the derived key (no helper is built).
- Known limits are written in `docs/replay-human-lens.md`.
- The roadmap section for LL5 is NOT pruned yet, because the owner decisions are open.
- The `docs/code-health.md` and `docs/consolidation-log.md` entries are left to the release lead at landing, because the shas change at the rebase.
