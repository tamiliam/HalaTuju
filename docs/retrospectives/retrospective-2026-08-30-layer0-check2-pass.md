# Retrospective — Layer 0: the Check-2 pass (2026-08-30)

## What shipped

The second and last item Sprint 3a deferred. `check2_queries.py` raises the automatic follow-up
asks after Submit (clarify questions and document requests). It now respects what a programme
asks for — **per code**, via `GOVERNED_BY`: each ask names the catalogue item whose absence makes
it meaningless, or `None` where the ask follows a per-student rule the catalogue does not express.
`_gap_sets` filters both sets through it once, so `sync_check2_queries` never raises a governed
ask the programme does not make and auto-resolves an open one through the housekeeping it already
had. It reads through `requirements.asks_for`, so a submitted student's FROZEN copy governs.

Why per code and not the income switch: the file is income-driven but also carries academic and
family follow-ups. A wholesale gate on `income_proof` would have silenced "which school is your
sibling at?" for a programme that merely dropped the means test. No migration; backend only.

## Verification

- +6 tests: defaults unchanged; income asks silenced only by platform deactivation (the item is
  CORE, so an organisation's `off` row is floored — the test documents that); both bills off
  silences the utility asks and one bill back on restores the shared ones; an open ask whose item
  is off auto-resolves; a frozen application ignores a later switch; every code classified.
- Bite-check: filter disabled → 2 tests fail. Committed first.
- Existing Check-2 suite (68 tests) unmodified and green; full backend suite green.

## Lessons

- **When a deferral says "cannot be gated wholesale", the fix is a classification table with an
  explicit exempt value, plus a completeness test.** The same shape as `FENCED_OR_EXEMPT`: the
  value of `None` is that it is a decision someone wrote down, not a code the filter never saw.
