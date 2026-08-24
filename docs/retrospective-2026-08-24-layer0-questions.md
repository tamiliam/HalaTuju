# Retrospective — Layer 0 Sprint 4: the catalogue governs the questions (2026-08-24)

## What shipped

A programme can now switch application QUESTIONS on or off, the way Sprint 3 did for
documents. One journey for every tenant, different contents. **No migration**; worktree
`.worktrees/layer0-sprint4`, branch `feat/layer0-sprint4-questions`.

- **Backend** — `application_completeness` asks `requirements.resolve(app, 'question')`
  which parts may gate: the four story fields each on their own row, `funding`, `address`.
  Only `'required'` gates; `'optional'`/`'off'` make the part vacuously true. `consent` and
  `family_roster` are CORE (the owner's 2026-07-28 policy floor) — the resolver floors them
  at required, and the completeness literals stay with comments saying why.
- **Payload** — `requirements` now carries `questions` beside `documents`
  (`{'required': [...], 'optional': [...]}`, sorted). The Sprint 3b test that pinned the
  block at documents-only was edited deliberately — that was its stated purpose.
- **Frontend** — `questionRequirement()` / `asksForQuestion()` / `visibleNextSteps()` in
  `lib/scholarship.ts`, mirrors of the document helpers, missing-block degrades to
  `'optional'`. The wizard draws a question only if asked, marks `*` only if required,
  collapses Card B when all four narrative questions are off, and drops the Funding step
  entirely when `funding` is off — all COMPUTED from the payload at render.
  `NEXT_STEP_ORDER` itself is untouched (a stored step list is Layer 2 in disguise).
  The review page hides unasked questions and the funding card the same way.
- **Sandbox** — the lean-programme fixture now differs on questions too (two narrative
  questions off, funding off), so a designer can see the collapse case.
- **Sponsor profile audit (acceptance item)** — no change needed: a blank answer already
  renders the `not provided` sentinel and the prompt already instructs "say nothing about
  it". Pinned by a new builder test so a rewording can't quietly break what is now a normal
  state (blank-by-configuration) rather than an edge case.

## Verification

- pytest: full scholarship + courses + reports suite green, existing tests UNMODIFIED except
  the one deliberate payload-pin edit. New: 7 gate tests (`test_layer0_questions.py`),
  4 payload tests, 1 prompt test.
- **Both bite-checks done, committed first**: disabling the empty-catalogue guard in
  `requirements.resolve` failed 3 tests; replacing the resolved set with `{}` in
  `application_completeness` failed 3 tests. The guards are load-bearing, provably.
- jest 1470 (+5) · `tsc` (only the documented pre-existing test-file errors) ·
  `next lint` 0 errors · i18n 4534×3 (no new keys — every label already existed) ·
  `next build` exit 0 · `makemigrations --check` clean.
- Production shape: 0 programme overrides exist, so the deploy is a byte-level no-op for
  BrightPath — every application resolves to the seeded defaults, which reproduce the old
  literals by construction.

## Deviations from the roadmap, stated plainly

1. **The roadmap's file list was wrong about WHERE the questions live.** It named
   `apply/page.tsx` and `buildApplicationPayload`; scoping showed all governed questions are
   on the Step-4 wizard (`ScholarshipNextSteps.tsx`). The apply page needed no change.
2. **`anything_else` and `justification` are in the catalogue but not yet governed.**
   `anything_else` renders on the PRE-application apply form, which has no application
   payload to read requirements from; `justification` renders nowhere (legacy). Both are
   optional and never gate, so an off row changes nothing today. Governing the apply form
   needs a public per-programme requirements surface — deferred deliberately, recorded in
   the roadmap, to be picked up when Sprint 5 makes overrides real.

## Lessons

1. **A roadmap's file table is a hypothesis, not a scope.** Written four weeks before the
   sprint, it predated 3b's own discovery that the JSX governs what students see. Re-derive
   the render sites at sprint start (the catalogue-vs-JSX diff found them in minutes);
   don't code to the table.
2. **When a part of a completeness rollup becomes conditional, its VACUOUS value must be
   True, and the neighbour tests are what prove you didn't over-loosen.** Every "switched
   off stops gating" test here pairs with "its still-on neighbour still gates" — two off and
   everything off are indistinguishable to a test that only checks the two.
3. **A prompt-level guarantee is worth pinning the moment configuration makes its input
   state routine.** "Blank means say nothing" had never needed a test while blank meant a
   student skipped an optional box; now blank can mean "never asked", so the sentinel and
   the instruction each got an assertion.
