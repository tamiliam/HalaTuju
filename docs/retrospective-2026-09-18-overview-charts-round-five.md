# Retrospective — The Overview's charts, round five (2026-09-18)

The owner's third live read, an hour after round four. Web only; no backend change.

## What Was Built

- Hover text is the value alone.
- The money chart: no list beneath; bars and balance points answer on hover; a y-axis on the
  bars' scale; the three totals carry swatches and serve as the legend; the note is gone.
- Applications per week and awards per month: y-axis, hover values, nothing beneath; the weekly
  one is labelled in months.

## What Went Well

- **The chart primitive absorbed all of it**: `titles` on a series and on the line, `Figures`
  that renders nothing when empty, one new axis box. The page changed props, not structure.
- Four bites, four caught, in one script; nothing silent.

## What Went Wrong

1. **A rule from three days earlier had to be superseded, not amended.**
   - *What happened:* "every chart renders its figures beneath it" (15 September) was amended on
     the 18th for the weekly lines, and superseded the same day for every chart.
   - *Root cause:* the rule was written for accessibility and quotability before anybody had read
     the page with real data on it. Real data has fifty columns.
   - *System change:* the decision now says what a figure beneath a chart is FOR (the number a
     person quotes), and hover carries the per-column answer. The lesson from round two stands;
     no new lesson.

2. **A test referenced a deleted i18n key and the hygiene guard caught it.**
   - *What happened:* the page test asserted the old note's key was absent — by naming it, which
     the literal-key scan reads as a use.
   - *Root cause:* asserting absence by key name.
   - *System change:* the assertion was dropped; absence of a `note` is proven by the card's
     markup, not by naming a key that no longer exists.

## Numbers

- 7 files; no migration; two locale keys added, one removed.
- Gates and deploy: see the CHANGELOG entry and the `Next Sprint` block in `halatuju_api/CLAUDE.md`.
- Bite-checks: 4 injected, 4 caught.
- No time estimate was given, so there is no planned-versus-actual figure.
