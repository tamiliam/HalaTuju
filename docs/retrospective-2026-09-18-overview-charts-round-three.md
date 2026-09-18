# Retrospective — The Overview's money charts, round three (2026-09-18)

The owner's second live read, three days after round two: three requests on the three small
charts. Small, but it changes what a figure MEANS on a money screen, so it closed as a sprint.

## What Was Built

- A week is filed under the month of its Thursday (`monthOf`), so "Jun" no longer appears over
  data that starts in July.
- The first weekly line is ringgit per transaction (`spent_per_transaction`), titled and axised as
  such; its figure is the whole-period average per transaction with **n: x students** beneath.
- The second line's figure is the average weekly transactions per student
  (`weekly_transactions_per_student`; `weeks` sent alongside).
- The category legend is largest first, *Not categorised* last, and *Not yet sorted* hidden while
  it is zero — never dropped (`orderSlices`).

## What Went Well

- **Every change was one pure function and its test**: `monthOf`, `orderSlices`, `_per`. Five
  bites, five caught; the page tests read the new words through the i18n keys.
- **Merged `main` first.** Three days of other agents' work merged clean before a test ran.

## What Went Wrong

1. **The axis named a month that had no data.**
   - *What happened:* "Jun" under a series whose first row is 3 July.
   - *Root cause:* the weekly bucket is keyed on its Monday and the label was derived from that
     key; the week containing 1 July starts on 29 June. A coarse label was taken from a fine
     bucket without a rule for the boundary.
   - *System change:* ISO's Thursday rule in `monthOf`, with boundary cases pinned (29 Jun → Jul,
     31 Aug → Sep, 28 Dec → Dec). Lesson recorded.

2. **Round two's figures answered a question the owner had not asked.**
   - *What happened:* "average per student, whole period" and "transactions per student, whole
     period" were replaced on sight by per-transaction ringgit and per-week transactions.
   - *Root cause:* I derived the figure from the data that was easiest to divide, not from the
     question an officer asks of the chart. The chart's title said "per student, per week" and
     the figure beneath it was neither.
   - *System change:* the figure beneath a chart is now defined in the decision as "the answer to
     the question the title asks", and both denominators travel in the payload so the next
     reader can check them.

3. **A rule from three days earlier had to be amended, not kept.**
   - *What happened:* "every slice is listed, even at zero" met "REMOVE Not yet sorted".
   - *Root cause:* the rule was right about the harm (silent unfiled money) and wrong about the
     mechanism (a permanent zero row is noise, not a signal).
   - *System change:* hidden at zero, shown with money, with a test for the return. The decision
     entry records the amendment rather than silently overriding the earlier one.

## Numbers

- 12 files; no migration; locale keys unchanged in count (values only).
- Gates and deploy: see the CHANGELOG entry and the `Next Sprint` block in `halatuju_api/CLAUDE.md`.
- Bite-checks: 5 injected (2 backend, 3 web), 5 caught.
- No time estimate was given, so there is no planned-versus-actual figure.
