# Retrospective: the learning loop (LL1, LL2, LL2b, LL3, LL4) - 2026-11-19

Five sprints, built on 18-19 November as one stack of branches (`ll1 -> ll3 -> ll4 -> ll2 -> ll2b`), then brought up to `main`. Saved to `main`; NOT published. Plan: `docs/plans/2026-11-18-learning-loop-roadmap.md`. LL5 (the learning report) is not built.

## What Was Built

- **LL1 - the AI prediction scoreboard.** A new "AI prediction" section on the Organisation Overview and the Programme Overview: how often the AI's green was right, how often it was too careful, by month and by engine version, and how often the QC agreed with the reviewer's decision. Counts always shown with the percent. A reviewer sees only their own assigned applicants.
- **LL2 - one clear question.** The rating box now says "Check the four facts". A reviewer who fails a fact the AI called green taps one reason (five choices). A soft warning appears if a fact failed and the decision is accept. No migration.
- **LL2b - the QC's second look.** On the QC step, a short "Facts in doubt" block. Doing nothing agrees with the reviewer; one tap disagrees. The numbers appear on the AI prediction card as "checked by the QC". No migration.
- **LL3 - the model version guard.** One register of every AI model, one append-only log per model, and tests that fail when a model's files change without a new version.
- **LL4 - what fed each decision.** Each recorded verdict stores a record with no personal data: which documents, which model versions, and one keyed fingerprint of the evidence. One additive migration, `0215_application_verdict_context`. The owner applies it by hand before any publish.

## What Went Well

- The owner approved the words and the pictures before any screen code was written (LL1 picture, LL2 words, LL2b picture). No screen was rebuilt for taste.
- The stack stayed off `main` while it was built, so no other work was disturbed.
- The rebase onto `main` had one conflict only (a test).
- Checking with the OCR-first work found one shared file (`CHANGELOG.md`) and one real link (the version guard). Nothing else collided, and both sides now know the rule: bump the version, never re-seed a digest.
- Each sprint had a fresh reviewer. The sprints that touch the decision flow (LL2, LL2b, LL4) also had an adversarial review on Opus. These reviews found real problems before the push (the stale-tab gap in LL2b, fields missing from the LL4 fingerprint, holes in the LL3 pins).
- A fresh adversarial review of the rebase said "ship with notes". The notes are fixed.

## What Went Wrong

1. **The first end-of-stack gate run failed 2 api tests and 5 web tests.**
   - Why: three pinned guards were not updated in the sprint that changed what they pin: the status-lock call-shape pin, the serializer field-order pins, and the Guide access matrix. Each sprint ran targeted tests only, and those guards live outside the sprint's own test files. No product fault.
   - Proposal for the owner (a workflow change, so it needs the owner's word): a sprint that adds a serializer field, adds a Guide section, or changes a locked view's call shape also runs those three guard files in its targeted set.
2. **Commit trailers were wrong in 15 commits** (a made-up `Migration: none`, a `Phone-check: none needed` line, a missing `Services`). Found only at merge time.
   - Why: trailers were written per commit by hand, and nothing read them until the merge.
   - Proposal for the owner: before asking for a merge, run `release_queue.py queue --live origin/main --main <branch>` on the local branch and aim for `WARNINGS: none`.
3. **Two sessions planned the same migration number (0215).** Found by the release lead's heads-up, not by a tool.
   - Why: a migration number was treated as final when the branch was made, not when it lands.
   - Proposal for the owner: a migration number is final only at the push to `main`, like a TD number. The branch that lands second renumbers.
4. **The lead first told the owner to merge the A5 replay branch, and first reported that it had no owner.** Both were wrong and were corrected the same day (per the lead's notes).
   - Why: the answer came from memory notes, not from the branch's commit history.
   - Proposal for the owner: check `git log` authorship and the other session before stating who owns a branch.
5. **4 of 836 phone-check cells timed out on network-quiet waits** and passed when re-run alone (per the lead's notes). A flaky wait, not a layout fault.
   - Why: the wait for the network to go quiet is slow on a busy machine.
   - No system change proposed yet. If it recurs, a re-run-alone rule for timeouts would be the smallest fix.

## Design Decisions

Recorded in `docs/decisions.md` (2026-11-19 entries):
- The Pass / Fail tap records the student's fact, not a rating of the AI. The reason for failing a green fact is asked separately.
- The second person for LL2b is the QC, inside the existing QC step. Silence means agreement.
- One human feed for "the reader was wrong" (LL2 reasons and LL2b QC answers). The OCR-first work reads it. No second store.
- A model's version is registered with a digest of its source. A digest is never re-seeded without a version bump once the register is on `main`.
- The first batch of old cases for the QC was left out by the owner on 2026-11-19.

## Numbers

- 5 sprints; 47 commits on top of `origin/main` (`0dea7e809`).
- Last full gate run on the stack, before the rebase: api 23,207 passed, 0 failed, 3 skipped; web jest 7,903 passed; i18n 8,399 keys per locale (8,410 after the rebase); phone check 836 cells; first-load bundle median 157.162 kB of the 157.5 kB line.
- The final full run happens after the last rebase. Its numbers go in `CHANGELOG.md`, not here.
- Debt drafted at close: see the lead's TD step (14 new rows, one existing row, TD-243, to update).
