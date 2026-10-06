# Retrospective — The Overview, round six (2026-09-18)

The owner's fourth live read. Two questions about who is counted, and two things to remove.
Investigated on production before changing anything — the owner asked for that explicitly.

## What Was Built

- **n = students who have spent** (47 on the live gift, not the 58 with a wallet).
- **Weekly rate over the students who spent THAT week**; chart retitled "per active student";
  whole-period figure is the mean of those (about 7.2, up from 5.0).
- **Funnel tiles at zero are not drawn**; the total always is.
- **Intake card removed** end to end: payload, page, types, locales, manual, role matrix.

## What Went Well

- **"Investigate first. Do not change anything yet."** A read-only probe against production
  (creds piped from `gcloud`, nothing written to disk) answered both questions with a week-by-
  week table before any code moved, and the owner ruled on the table.
- **The two denominators the owner could choose between were both on the table, with numbers**
  (6.4 vs 7.2), so the ruling was a choice, not a guess.
- Three bites, three caught; the intake removal touched fourteen files and every guard stayed
  green.

## What Went Wrong

1. **n counted wallets under a chart about spending.**
   - *What happened:* "n: 58 students" beside "average spending per transaction", when 47 had
     spent.
   - *Root cause:* the denominator was inherited from the weekly series' "wallet live that week"
     rule without asking whether a wallet with no rows belongs in a spending report. It does
     not, and TD-245 already said we cannot even tell why such a wallet is empty.
   - *System change:* one rule — a student is on this page only once they have spent — applied
     to n and to the weekly rate; a fixture test plants a wallet with no rows and asserts it is
     counted nowhere. Lesson recorded.

2. **A section kept "because every role shares it" was the least useful one on the page.**
   - *What happened:* the Intake card read "No intake year has been set up" in a card the size
     of the attention list.
   - *Root cause:* the 15 September design argued from symmetry (one section for everyone)
     rather than from what each role would do with it.
   - *System change:* removed; the decision records why the symmetry argument lost.

## Numbers

- 15 files; no migration; the `intake` locale block removed from three locales, four values
  reworded.
- Gates and deploy: see the CHANGELOG entry and the `Next Sprint` block in `halatuju_api/CLAUDE.md`.
- Bite-checks: 3 injected (2 backend, 1 web), 3 caught.
- No time estimate was given, so there is no planned-versus-actual figure.
