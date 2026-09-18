# Retrospective — Code health H4: the standards become tests, inside the gate

**Date:** 2026-09-19 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H4 of H19
**Built by:** an Opus 5 agent to a written brief; the lead verified, re-ran both suites, extended
the workspace health tool to close the one loophole the agent named, and closed.
**Freeze status:** in force. **Phase 1 (Gates) is complete** — four of the ten sprints to *stabilised*.
**First sprint run under the owner's standing word** (2026-09-18: *"progress independently and
continuously, and only stop if my decision is needed"*). Nothing in it met a stop condition.

## What Was Built

The owner's second ruling — *"future builds would ensure the standards are maintained"* — made
mechanical. Since H2 both suites run before every deploy, so **a standard written as a test cannot
be broken by a change that ships.**

- **Two budget files, each inside its service folder** (so an edit to a budget triggers the build
  that checks it): `halatuju_api/code-standards.json`, `halatuju-web/code-standards.json`. Each has
  a frozen `baseline` block and a `budget` block that only ever tightens.
- **70 tests** (`test_code_standards.py` 30, 1.2 s · `codeStandards.test.ts` 40, 0.6 s) enforcing:

  | Standard | api | web |
  |---|---|---|
  | No new file over 600 lines; listed ones may not grow past +20 | 36 listed | 20 listed |
  | No new function of 150+ lines | 16 listed | — |
  | One rule, one home (a name in 3+ files of one app) | 10 listed | — |
  | No new blind spots | `# noqa` 80 · `# type: ignore` 15 | `any` 2 · `@ts-ignore` 0 |
  | Every `eslint-disable` carries a written reason; total may not rise | — | 42, of which **37 reasonless** |
  | No unguarded mirror of a backend rule | — | **60 claims, 2 guarded, 58 listed** |
  | Tests can fail (no skip / xfail / todo) | 0 · runtime `skipTest` in 4 named files | 0 |
  | The app boundary: `courses → scholarship` imports | 25, of which 1 module-level | — |
  | No dead weight (every dependency imported) | — | 0 |

- **The ratchet, without git** (the deploy checkout is depth-1): `actual ≤ budget`, `budget ≤
  baseline`, every ledger a subset of its baseline, **tightness** (`budget ≤ actual + slack`, so
  when code improves the test fails until the budget is lowered), and the baseline block pinned by
  a SHA-256 held in the test file.
- **Every failure message says what to do** — split the file first in its own commit, give the
  rule one home, add a reason, lower the budget to N. None suggests raising a budget.
- **`## Code standards` in `CLAUDE.md`** — the table, the two files, the ratchet in three sentences.
- **The loophole the tests cannot close, closed elsewhere.** A number could fall and later rise
  back up to baseline. The lead added a `std` reading to `Settings/_tools/code_health.py`: it
  compares each budget file with the copy at the last recorded run's commit and **FAILs** when a
  limit rose or a ledger gained a member. That tool has git; the deploy build does not.

## What Went Well

- **31 bite-checks, none silent, and eight that prove the guard does not cry wolf** — a
  comment-only edit, +5 lines on a listed file, a new 590-line CRLF file, a "SERVED, NOT MIRRORED"
  comment. A standards test that fires on harmless work is deleted within a month; these will not.
- **The agent measured instead of trusting the brief.** The brief said ~29 reasonless
  `eslint-disable`s and ~34 mirrored rules. Measured: **37** and **60**. The mirror count nearly
  doubles because whole-file docblocks that declare a mirror count too — which is right.
- **It found that its own test file broke the lead's tool.** Writing the skip pattern as one
  string made `code_health.py` report three phantom skipped tests. Fixed in the test, reported
  plainly.

## What Went Wrong

**1. The brief's numbers were wrong twice, and the roadmap's H9–H10 estimate with them.**
- *Symptom.* 60 mirrored rules, not 34; 58 unguarded, not 32.
- *Root cause.* The survey that fed the roadmap counted comments that *said* "mirrors" on a line;
  it missed file-header docblocks. The lead carried the figure into the roadmap's targets table.
- *System change.* The roadmap's target row now reads 58. H9–H10 (de-mirror) are re-estimated in
  the roadmap from two waves of ~17 to two waves of ~29; if they run long that is a stop
  condition under the owner's standing word, and will be raised then, not now.

**2. One standard is stricter than it may want to be.** A *new, reasoned* `eslint-disable` is
refused, because the total may not rise. The lead kept it: 37 reasonless ones exist to retire, so a
justified new one costs retiring an unjustified old one — a fair trade for years. Recorded so the
owner can overrule it.

**3. `guard%` rose 17 → 18.** The web standards test must read source, by nature. Inside tolerance;
accepted, and H6 (which retires four text guards) more than pays it back.

**4. The gate blocked this sprint's own web deploy — a load-dependent flake, not H4's code.**
- *Symptom.* api deployed (6,760 passed in the build). Web: `2 failed, 2394 passed` — both
  rendered tests (`admin/spending/page.test.tsx`, `AppShell.test.tsx`), `Unable to find an element
  with the text…`. `Push` and `Deploy` never ran; production kept the previous web revision.
- *Root cause.* Testing Library's `findBy*`/`waitFor` give up after **one second**. The gate runs
  jest beside `next build` on 2 vCPUs. The same tests passed in the H2, H3 and TD-258 builds and
  failed in this one: a race against machine load, which nobody sees on an 8-core dev box.
- *System change.* `halatuju-web/jest.setup.ts` sets `asyncUtilTimeout` to 10 s and the per-test
  limit to 30 s for the whole suite, wired by `setupFilesAfterEnv`. A timeout is a limit, not a
  delay, so nothing gets slower unless the machine is. `jestSetup.test.ts` fails at once if the
  wiring is ever dropped (bite-checked) — otherwise the flake would return weeks later, in the
  gate, blocking a deploy. This is the risk H2's retro named ("a flaky test then blocks a deploy"),
  arriving on schedule.

## Numbers
## Numbers

| Gate | Before | After |
|---|---|---|
| pytest `-n auto` | 6,730 passed · 3 skipped | **6,760 passed · 3 skipped · 0 failed** |
| jest | 2,356 / 140 suites | **2,396 / 141** |
| tsc · lint · i18n | 0 · 0 errors · ok | unchanged |
| Web standards test under Node 18 (the gate's runtime) | | 40 / 40 |
| Workspace tool tests | 22 | **25** (the `std` reading; a raised budget fails the run) |
| App code changed | | 3 comment lines (`drift-test:` markers) |
