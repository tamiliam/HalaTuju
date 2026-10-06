# Retrospective — The Overview's money charts, round four (2026-09-18)

The owner questioned one figure and asked for three small things. Closed as a sprint because
the figure was wrong on a money screen and its definition changed.

## What Was Built

- **Weekly transactions per student = mean of the weekly averages** (was total ÷ today's
  students ÷ weeks; 3.1 → about 5.0 on the live gift).
- **Y-axis with a middle value and gridlines** at the top and middle, on both weekly lines.
- **Hover a point to see the week's value** — a `<title>` on an invisible hit circle.
- **Total spending beneath the category ring** — the money strip's `spent`.

## What Went Well

- **The owner asked "how was it calculated?" and offered both formulas** — the question came
  with its own answer key, and the test now names both and pins the gap.
- **The hover cost nothing.** The 2026-09-15 decision had named this exact trigger; a
  `<title>` needed no state, no library and no `ResizeObserver`.
- Four bites, four caught; merged `main` first.

## What Went Wrong

1. **A whole-period rate was divided by today's headcount.**
   - *What happened:* "Average weekly transactions per student: 3.1" under a line whose points
     average 5.0. The owner saw it at once.
   - *Root cause:* I took the simplest division — total rows over the final student count over
     weeks — without asking whether the count was the same in every week it covered. It was not:
     the programme grew from a dozen wallets to 58, so the early weeks were charged with people
     who had no wallet yet. The figure would have FALLEN as the programme grew.
   - *System change:* mean of the weekly averages, with both denominators in the payload; a
     test that names the wrong formula and its wrong answer; lesson recorded.

2. **Three rounds in, the "no tooltips" trade-off was still in force while the owner wanted one.**
   - *What happened:* the round-two decision listed hover as a revisit trigger; the owner
     tripped it three days later.
   - *Root cause:* none to fix — the clause worked as designed. Noted so the next reader sees
     that a revisit clause firing is the system succeeding, not a reversal.

## Numbers

- 9 files; no migration; one locale key added (`series.spendingTotal`).
- Gates and deploy: see the CHANGELOG entry and the `Next Sprint` block in `halatuju_api/CLAUDE.md`.
- Bite-checks: 4 injected (1 backend, 3 web), 4 caught.
- No time estimate was given, so there is no planned-versus-actual figure.
