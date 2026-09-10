# Retrospective — the officer screens said "B40" about gifts that are not B40

**Date:** 2026-09-10 · **Branch:** `feat/officer-income-vocabulary` ·
**Worktree:** `.worktrees/income-vocab` · **Deployable:** api + web ·
**Migration:** none · **Env var:** none · **Data step:** none ·
**Plan:** `docs/plans/2026-09-09-officer-income-vocabulary.md` (owner-approved 2026-09-09)

---

## What prompted it

The owner, planning BrightPath **Sabah** (expected live ~2 weeks from 2026-09-09):

> *"each gift would have its own text and preferences. And they need not be B40 focused."*

Their first instruction was to link the officer's income wording **to the gift's name**. That was
wrong, and the correction is the whole point of the sprint: **B40 is Malaysia's national income
band — the bottom 40% — not the name of a gift.** Substituting the name produces *"Income
(BrightPath Sabah)"* and *"over the BrightPath Sabah line"*. The owner accepted the correction the
same day. The defect they were correctly pointing at was real; only the mechanism was wrong.

## The bug the plan did not know it had

The plan said a gift with no income ceiling still reads "Income (B40)". True. Reading
`income_engine.income_headroom` found the worse half:

```python
if pc is None or not size or not pc_ceiling:
    return 'unknown', {'all_known': all_known}
```

`not pc_ceiling` means **the gift applies no income test**. It returns the *same band* as "we could
not read the documents", and that band prints:

> *"Income can't be document-verified (informal / no payslip) — confirm during the interview…"*

On the **Test round** (both ceilings NULL, measured on production 2026-09-09) the payslips may read
perfectly. **The engine collapsed a property of the GIFT into a defect in the EVIDENCE**, and the
screen renders the two identically. An officer reading that line would go looking for a document
problem that does not exist.

So this was never only a label sprint. It was a label sprint **plus one empty state that had been
lying since ceilings became nullable** (Sabah S2a, 2026-09-02).

## What shipped, and why each piece is the shape it is

**Twelve strings × three languages, not eleven.** The owner-approved list had eleven.
`utility_percapita_high` — *"high (M40/T20 consumption pattern)"* — was not on it and carried the
identical fault in the other direction. It is in.

| | Before | After |
|---|---|---|
| the fact tile | `Income (B40)` | `Income` |
| the threshold lines | "the B40 line" | "this gift's income limit" |
| STR | "STR document verified — B40 status confirmed." | "STR document verified — the government's own means test is satisfied." |
| utility, low | "consistent with a B40 household" | "consistent with a low-income household" |
| utility, high | "(M40/T20 consumption pattern)" | "(a higher-income consumption pattern)" |
| household of 1 | "unusual for a B40 student" | "unusual for a student applying for financial assistance" |

**⚠ STR keeps its name.** STR is a real Malaysian government programme, and *"STR document
verified"* is true whatever the gift is called. Only the trailing "— B40 status confirmed" clause
went, and it was replaced rather than deleted: an STR **is** a means test, just the government's,
not this gift's, and an officer needs to know the check has weight.

**⚠ The key names keep their `b40`** — `income_above_b40_line`, `utility_percapita_b40`. They are
internal identifiers no officer reads, and renaming them would churn the engine, the narrative
gloss, three message files and every test for nobody's benefit. **A decision, not an oversight.**

**The empty state is a PREDICATE, not a new band.** `income_engine.income_test_configured()` asks
the cohort directly; `income_headroom`'s return set is untouched. The first draft added an
`'untested'` band, and that was the wrong shape — the band feeds the verdict tiles on both routes,
so widening its return set would have put every caller of a shared function in the scope of a
wording sprint (*"'the existing tests pass' is a FULL-SUITE claim"*, lessons.md 2026-09-04).

**⚠ THE VERDICT BAND DOES NOT MOVE.** Amber before, amber after — a human places income, and
nothing is blocked. A test pins it in both directions. The plan's own rule: *"if a verdict band
moves, something is wrong."*

**Two English surfaces, not one.** `verdict_narrative._CODE_GLOSS` is a second English copy of the
same sentences that grounds the Check-2 case summary. Fixing only `en.json` would have left the
model reasoning about "the B40 line" while the tile beside it said nothing of the kind.
`CASE_SUMMARY_VERSION` bumped to `2026-09-10.1` so cached summaries regenerate — the file's own
comment asks for that.

**The new gloss forbids the wrong inference explicitly:** *"do not reason about a threshold, and do
not treat the absence of one as a pass."* Without that sentence a summariser reads "no income
limit" as "income cleared".

## What went well

- **The i18n guard bit on the first run, and it was right.** `test_verdict_item_i18n` walks the AST
  for `_item('...')` and failed with *"dynamic _item() call sites changed: 3 != 2"*. The first
  version of `_income_open_item` chose its code with a conditional **inside** the call, which hides
  both codes from the check that stops a raw key path rendering in the cockpit. Fixed by writing
  both codes as literals in branches. A guard somebody wrote months ago caught a real regression in
  a sprint that never thought about it.
- **The absence guard walks whole trees.** Every leaf under `verdict.*`, `agenda.*` and `anomaly.*`
  in all three locales, plus a whole-file sweep for the eight retired sentences. Not the twelve
  keys — *"a guard written from the instance you just fixed is scoped to that instance"*
  (2026-09-08), and `utility_percapita_high` is that lesson's receipt.
- **The out-of-scope fence is a test, not an aspiration.** One case asserts the apply page and the
  landing page **still say B40**. Sweeping them in here would change what applicants are told, in a
  sprint with no owner check for it.
- **Both bite-checks bit.**

## What to watch

- **⚠ `profile_engine.py` is the twin that can now go stale.** It carries a second, larger B40
  vocabulary, including `_OFFICER_FACT_LABELS['income'] = 'Household income (B40 need)'` — the
  direct mirror of the tile this sprint renamed to "Income". It was left alone deliberately: every
  edit there needs a `PROMPT_VERSION` bump, which re-dates every existing profile draft on
  production. That is a data and cost consequence, not a wording one. **Logged, not built.**
- **ms and ta are first drafts.** The Malay uses *"had pendapatan pemberian ini"* and the Tamil
  *"இந்தக் கொடையின் வருமான வரம்பு"*, both matching the app's existing words for a gift
  (`pemberian` / `கொடை`). The Tamil was rewritten sentence by sentence rather than by replacing the
  token, because dropping "B40" from *"B40 எல்லைக்குக் கீழே"* leaves the case ending attached to
  nothing.
- **The landing page and the sign-in prompt** carry the same platform-wide B40 copy. Same class,
  other pages, still unlogged as work.
- **The no-income-test line is deliberately NOT an interview talking point.** It is excluded from
  `_NEEDS_INTERVIEW_AMBERS`, with a test. "This gift does not test income" is the opposite of
  something to confirm.

## Owner check before it ships

The plan's own rule: *"BrightPath must read as it does today… even that is worth showing the owner
before it ships."* BrightPath's only visible change should be the "(B40)" label leaving the income
tile. Everything else on a gift with ceilings set reads as it did yesterday.
