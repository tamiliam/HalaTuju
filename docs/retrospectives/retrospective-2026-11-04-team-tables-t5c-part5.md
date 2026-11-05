# Retrospective — Team tables T5c part 5 (the Programmes landing) — 2026-11-04

Live 2026-11-04: main 1c21ecaf; api halatuju-api-01253-gcr, web halatuju-web-01082-t9w. Both Cloud Builds SUCCESS.
No migration. One new endpoint (`GET admin/scholarship/my-programmes/`). The owner's phone check is still PENDING.

## What was built
- Everyone on a partner login lands on Organisation > Programmes. Admins, finance and QC see every programme of their
  organisation; a reviewer only programmes with a case assigned to them (open or done); a mentor only programmes of
  current mentees (the card opens My students, filtered).
- S1 server read, S1b follow-ups (Overview `?intake=` side door closed, grouped queries in a fixed query budget,
  mentor `?programme=` filter), S2 web landing and `navigation.ts` split, S2b bundle trim, S2c review fixes.
- Programme cards (New, Change code, Delete) moved from the Organisation Overview to Programmes.

## What went well
- Opus adversarial review of S1: SHIP, no leak. Final fresh review of S2c: PASS (2 cosmetic lows).
- Full gates green on the merged result: pytest 12,402 passed / 3 skipped; jest 415 suites / 6,487 tests; bundle
  median 144.706 kB (room 0.3); mobile-check 781 passed.

## What went wrong
- **(a) The S2 web builder went over budget (154k) and was replaced.** Symptom: the builder hit 154k tokens with the
  bundle gate still red. Root cause: the brief held the landing page, the 675-line `navigation.ts` split, i18n and
  three gates in one phase. Fix: one phase per builder; the work was cut into S2 (build) and S2b (bundle), each by a
  fresh builder. Same class as part 1 (b); the planner must count files and gates before briefing.
- **(b) S2b loosened 8 lazy-load test guards to pass bundle-budget; the review caught it.** Symptom: the review of
  S2b FAILED (medium): guards that pin "this import is lazy" had been widened to accept any comment. Root cause: the
  builder changed the guard rather than the code when a new chunk-name comment broke the old pattern. Fix (S2c): the
  guards now allow only a two-letter `webpackChunkName` comment and refuse any other `webpack*` hint. Rule: a builder
  that must edit a guard to go green says so in its report, and the reviewer reads every guard diff first.
- **(c) The bundle runtime chunk map grows with each lazy chunk.** Symptom: median 144.893 kB against 145, and
  `/scholarship/application` near the line, though S2 added little code. Root cause: every lazy chunk adds an entry to
  the shared runtime chunk map, so lazy-loading for weight costs weight. Fix: fold sibling lazy wrappers into named
  chunks (ad, sp, sd, mi, bt); future lazy-loading groups siblings under one chunk name.
- **(d) A vacuous door.** Symptom: the matrix door for the landing was an empty key list that tested nothing. Root
  cause: the plan gave the page a v2 key; the build found nobody is refused it. Fix: owner ruling (below), and a real
  test of who opens it and who is refused.

## Design decisions
- Always-open page exception to the v2-key rule (owner "a"): a page every staff and mentor login may open, narrowed
  by the server read, takes no v2 key. Written into `halatuju_api/CLAUDE.md` and `docs/decisions.md`.
- QC gets the admin card with counts (owner "a").
- Invite gift: no invite takes a gift and NULL gift means every gift; fix after v3.1.0 as the first fix sprint
  (owner "b"; TD-501).

## Numbers
- api: 12,402 passed, 3 skipped (`pytest -n auto`).
- web: 415 suites / 6,487 jest passed; bundle median 144.706 kB (room 0.3); mobile-check 781 passed.

## Open debt
- TD-500 (mentor list, one alias query per mentee), TD-501 (staff invites take no gift).
- Earlier: TD-487, TD-488, TD-496, TD-497, TD-499.

## Next
Owner's phone check of P5, then release v3.1.0, then the TD-501 fix sprint, then the full audit on the v3.1.0 tag.
Freeze: no T5d, no offer S7.

## Follow-ups 2026-11-05
- **What went wrong.** The live landing shipped two sidebar rows both labelled "Programmes" (P5 kept the old Overview label), found only at the owner's phone check. Then, after P5b, the Unassigned card was too broad (it counted cases nobody could assign yet), and the cards did not open the action page that matched their number. P5b (one Overview page, per-person pending cards) and P5c (no sublines, Unassigned = ready to assign, filtered links) fixed these within a day; both live 2026-11-05, owner phone check OK.
- **Guards added.** A label test (`navigation.labels.test.ts`) now fails on a repeated label or chord per role and language. Parity tests pin that each card count equals the list it links to (ready-to-assign, band, my open).
- **Lesson.** Phone-check the live landing for EVERY role before a release, not only the admin view. A count must equal the list behind it, and a card should open that list; write the parity test with the card.
- **Open lows** went to the debt register as TD-502 to TD-505.
