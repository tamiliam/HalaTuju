# Retrospective — The Overview's money charts, round two (2026-09-15)

The owner's first live read of the Programme Overview, one hour after it shipped. Four requests
on the money charts; a small sprint because it changes how money is dated on a screen.

## What Was Built

- **A release on or after the 27th is the following month's payment** (`PAYMENT_MONTH_CUTOFF_DAY`).
  Only the released-vs-spent chart uses it; the money strip and the Payments footer read the
  release date as-is, and a test pins that they still agree.
- **Months named from the locale** ("Jul", "Ogos", "ஜூலை"), on the money and awards charts. The
  numeric month label and its test were deleted.
- **Three figures instead of the month table** — payments, spending, balance — the last month's
  running figures straight off the server.
- **"Purchases" → "transactions"** on the chart, in the payload and in the manual.
- **Y-axis and month ticks on the weekly lines; one whole-period figure beneath each** instead of
  every week's value (`per_student_overall`, same denominator as the weeks).

## What Went Well

- **The payload change was one function and one rename**, because the series builders were
  already pure and separately tested. Five backend tests, four bites, all caught.
- **The chart primitive earned its keep on day one**: `ticks`, `yAxis` and a `left` margin went
  into `Charts.tsx` once and both line charts and both bar charts got them.
- **Merge first, then gate** — the lesson from the morning, applied: `main` had moved (the
  Usage & Billing fixes) and merged clean before a single test ran.

## What Went Wrong

1. **The first build compared June's spending with money released for July.**
   - *What happened:* the chart's June bar showed RM1,800 released and RM0 spent; July showed
     RM12,800 against RM2,561. The owner read it at once as "payments go out early".
   - *Root cause:* I dated a release by its calendar date, which is correct for a ledger and wrong
     for a like-with-like comparison. Nobody had said the runs go out early, and I did not ask
     what the dates meant before charting them.
   - *System change:* the cutoff rule, stated in words under the chart and in the manual, and a
     test that the strip/footer are untouched by it. Lesson recorded: before comparing two dated
     series, ask what the date on each one MEANS.

2. **I listed every week's figure under a weekly chart.**
   - *What happened:* eleven weekly values in three lines of small text; the owner asked me to
     imagine it at fifty weeks.
   - *Root cause:* the rule "every chart prints its figures" was applied to the COLUMNS rather
     than to the figures a person would quote.
   - *System change:* decision amended — the figure beneath a chart is the quotable one; for a
     weekly line that is the whole-period average. Month ticks make the axis readable at any
     length, capped at twelve.

3. **A bite-check script died decoding jest's output on Windows.**
   - *What happened:* `subprocess.run(text=True)` read jest's coloured output as cp1252 and raised
     mid-loop; the `finally` restored the file, but the script's own cleanup did not run.
   - *Root cause:* Python's default console encoding on Windows is not UTF-8.
   - *System change:* every subprocess call in a bite script passes `encoding='utf-8',
     errors='replace'`. Minor; noted here, not a lesson.

## Design Decisions

Recorded in `docs/decisions.md` (2026-09-15): the 27th cutoff, and the whole-period figure
beneath a weekly chart.

## Numbers

- 17 files; no migration; locale keys under `admin.programmeOverview` 86 → 96 per language.
- Gates and deploy: see the CHANGELOG entry and the `Next Sprint` block in `halatuju_api/CLAUDE.md`.
- Bite-checks: 8 injected (4 backend, 4 web), 8 caught.
- No time estimate was given, so there is no planned-versus-actual figure.
