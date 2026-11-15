# RUN STATE - student help fixes (lead session "Help me")

Not the root RUN_STATE.md (that one belongs to the HalaTuju release-lead session).

## Grant (owner, 2026-11-15)
"Build continuously, and do not wait for me, until all the work is completed. Come to me only when there
are clear forks or potential deviation from accepted plan. You may want to show me the designs once ready
for my approval, and the drawing images, I want to see as well."

Scope: roadmap docs/plans/2026-11-15-student-help-fixes-roadmap.md, sprints H1-H9. Ends when H9 is merged
(or at the owner's word).

## Rules for this run
- Build on side branches, never on main. H1, H2, H3: own branch each (help-h1, help-h2, help-h3), rebased
  onto main and merged ALONE after the freeze (18 Nov). H4-H9: one branch `student-help`, cut at H4 start,
  rebased onto main every working day, one full review + final rebase, then ff into main.
- Worktrees OUTSIDE the workspace folder: C:/Users/tamil/wt/<branch> (VS Code rg pile-ups).
- ONE builder at a time from this session (project max 2; the release-lead session uses the other).
- Every sprint: fresh reviewer on the real diff; H1-H3 (+ H9 doc recognition) also an Opus adversarial review.
- Owner STOPS (send, keep working on other sprints meanwhile):
  - phone check (<=10 lines) before H1, H2, H3 go live;
  - Stitch designs for H5-H8 (one round) and the 8 sample drawings, before UI code that shows them;
  - paid Gemini re-runs (H1: 4 docs; H2: blocked offer letters; H3 dry run is free) - owner's word;
  - publishing: grouped, via the release-lead session, owner's direct yes;
  - any stop in Settings/_workflows/credit-discipline.md "STOP and ask the owner when".
- Coordinate MODEL_VERSION with the release lead: Gemini Option A bumps it (lands 17 Nov earliest); rebase
  after it and bump on top.

## Cursor
| Sprint | Branch | State | Notes |
|---|---|---|---|
| H1 #552 stamp | help-h1 | REVIEW PASS (Opus, 15 Nov); branch pushed; waits rebase + 18 Nov merge | 6874cdb16; suite 22372 pass; MODEL_VERSION 1.28.0. Follow-up before merge (after H2 builder): scope "stamp outside approver section" line so informal payslips (no approver section) keep a shop chop |
| H2 confirmation letters | help-h2 | IN PROGRESS (Opus builder, 15 Nov) | worktree C:/Users/tamil/wt/help-h2; also uses 1.28.0, fix at rebase |
| H3 start-year rule + recent letter | help-h3 | queued | Opus; land before 10 Dec |
| H4 split + stage lock | student-help | queued | Sonnet |
| H5 redesign | student-help | queued | Stitch round (H5-H8) needs owner approval |
| H6 replace | student-help | queued | Sonnet |
| H7 I don't have this | student-help | queued | Sonnet |
| H8 samples | student-help | queued | drawings need owner approval |
| H9 coach + sample check | student-help | queued | Opus review |

## Waiting on the owner
- Design approval (sent 15 Nov): Action Centre, "I don't have this", load error, sample viewer, 8 sample
  drawings. Only the load-error screen came from Stitch (node 1d8a45619f4748d69691cdcdbecc5f4b); the other
  three are hand-built HTML mock-ups (Stitch timed out). Files: session scratchpad designs/. Open questions:
  hand-built OK as approval? keep "We never take your progress backwards." line? "What we check" lists OK?
  Blocks H5-H8 UI code only.
- H1 phone check + paid Re-run of the 4 #552-pattern docs plus 1 known-bad form (sent 15 Nov). Re-run only
  after H1 is live.

## Open risks
- MODEL_VERSION conflict with Gemini Option A (H1, H2, H9).
