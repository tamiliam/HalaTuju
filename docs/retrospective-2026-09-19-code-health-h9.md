# Retrospective — Code health H9: the decision gates stop living in two languages

**Date:** 2026-09-19 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H9 of H19
**Built by:** an Opus 5 agent to a written brief carrying H8's rule (characterise first; a mirror
is deleted only where the two sides already agree). The lead reads the report and pushes.
**Outcome: the six named rules converted. No production code changed.**
**Freeze status:** in force. Nine of the nineteen sprints.

## What Was Built

- **A shared reader, `halatuju-web/src/test/apiSource.ts`.** Every drift test needs the same three
  lines — find `halatuju_api`, read a `.py`, lift a Python literal out of it. It is deliberately
  **not** a parser: it reads the small stable shapes the rules are actually written in (a tuple of
  string literals, a `CHOICES` list of pairs, a transition table) and **throws** when a name has
  moved. An api refactor turns a web test red instead of quietly making it assert nothing.
- **Six drift tests, 153 assertions**, one per rule family, each named by a `drift-test:` marker
  inside the comment it discharges:

  | guard | what it reads from the api | what it pins |
  |---|---|---|
  | `applicationStatusDrift` | `ScholarshipApplication.STATUS_CHOICES` | the 13 statuses, both directions; every one has a tone; no synthetic status is a DB value |
  | `requestStatusDrift` (115) | `org_requests.TRANSITIONS`, `TERMINAL_STATUSES`, `OPEN_FOR_SHAPING`, `OrgRequest.STATUS_CHOICES` | every status × role × kind × question-state, both ways |
  | `officerGateDrift` | `services.ORG_REJECT_FROM`, `REVIEW_ROLES`, two view bodies | the reject gate (status + role) and the assignment picker vs `bad_assignee` |
  | `strCoachDrift` | `income_engine.STR_COACH_STATES` | all seven rungs of the STR ladder, including the two that must stay QUIET |
  | `adminRoleDrift` | `PartnerAdmin.ROLE_CHOICES` | the seven roles; every stored role reaches ≥1 page |
  | `payoutAccountDrift` | `BankAccountSerializer.validate_account_number` | the five-digit floor, and the disagreement below it |

- **The ledger tightened: `unguarded_mirrors` 58 → 41.** Seventeen entries discharged, `budget`
  only, `baseline` untouched.
- **A `mirror` reading in `code_health.py`** — mirror claims in `src/lib` with no marker, written
  to the same definition as the in-repo standards test. Both read **41** the day it was added.
- **Two findings, reported and not fixed: TD-264 and TD-263.**

## What Went Well

- **The reverse direction is what earned the sprint.** A mirror test usually asks "does the web
  copy the api?". `requestStatusDrift` also asks the opposite — *does every road out of a status
  have a button?* — and it is the direction a mirror can never catch: the api gains a transition
  and the screen that should offer it is never touched. Eight statuses, both roles, and the api
  table is walked, not restated.
- **Characterising first found a money defect nobody was looking for.** The payout-account floor
  was one cheap ledger entry. Putting the same awkward inputs through both sides — H7's rule —
  showed the FLOOR agrees and the word *digit* does not: `³³³³³` is five digits to Python's
  `isdigit()` and none to JavaScript's `\d`, so the api accepts as a payout target what the
  student's own form refuses. TD-264. It was found by writing the test, not by reading the code.
- **The disagreement was pinned with its own reachability proof.** `requote` is offered on a bug
  and the service refuses it (TD-263). Rather than "unreachable, probably", the test asserts the
  chain that makes it so — the only road into `deferred` is `defer`, the only roads into `quoted`
  are feature-only — so the guard goes red at the exact moment somebody adds a second road. A
  finding with an expiry date on it rather than a sentence in a register.
- **17 bites, 17 behaved.** Every guard bitten from BOTH sides (drift the Python → red; drift the
  TypeScript → red), each turning exactly one suite red and no others, plus two no-cry-wolf edits
  that left all six green. Byte backups restored in a `finally` and SHA-256-verified; `git diff
  halatuju_api/` empty afterwards.
- **The sprint declined the thing the roadmap invited.** The plan reserved *serving* for the
  decision gates. All six are module-level constants with no per-request variation; serving one
  needs a new endpoint during a freeze and can only fail at runtime in front of a user, where a
  drift test fails in the deploy gate. Serve a rule that varies; guard a rule that is a constant.

## What Went Wrong

**1. "Six rules" and "29 ledger entries" were quietly treated as the same unit.**
- *Symptom.* The roadmap's acceptance line said `mirror` should "roughly halve" (58 → ~29) and its
  scope line named six rules. The six rules are **17** ledger entries. Delivering the named scope
  in full lands at 41, not 29, and for a while it looked like the sprint had underdelivered.
- *Root cause.* The re-estimate note divided 58 by two to size two waves, without asking what the
  58 counts. It counts comment BLOCKS in `src/lib`; a "rule" is one constant, which may carry a
  file docblock, an inline note at its definition and a third at its call site. This is H4's
  finding ("a number in a brief is a hypothesis") recurring inside the plan H4's finding rewrote.
- *System change.* H10's section now states its own unit explicitly (41 entries ≈ 15–20 rules) and
  H9's section records the two units side by side, so the next sprint sizes against entries and
  reports against rules. Any acceptance line phrased as a count now names what is counted.

**2. The new guards were invisible to the reading that exists to watch guards.**
- *Symptom.* `code_health.m_guard_share` watches "tests that read source text", because such a test
  asserts a shape rather than a behaviour. Six new source-text tests were added and the reading did
  not move: they delegate the reading to `apiSource.ts`, and the metric matched the literal string
  `readFileSync`.
- *Root cause.* The metric was written from the PROCEDURE (the call it had seen) rather than the
  PROPERTY (a test that reads source). That is lessons.md's *"a guard written from the same reading
  as the change inherits the change's blind spot"* — this time in the tool, not the repo.
- *System change.* `GUARD_SIGNALS` now counts a delegated read too, with the widening dated in the
  source so the step from 11% to 15% reads as a definition catching up and not as a regression.
  The general form: **a metric over "code that does X" is written against the property, and when a
  sprint introduces a new way of doing X the metric is part of that sprint's diff.**

**3. Three comments turned out to describe rules the code does not have.**
- *Symptom.* `requestStatus.ts` said the `answer` window is "submitted/triaged" (it is
  submitted/triaged/quoted/deferred — widening it was a named bug fix for request #3) and that
  `ask` is "the same window as the answer path" (it is strictly narrower, and the module's own
  `canComment` docblock said so nine lines away). `applicationStatus.ts` claimed a mirror of the
  api's status list including its order; only the membership is shared.
- *Root cause.* All three are prose ABOUT a rule sitting next to the rule. Nothing read the prose,
  so it aged while the code moved — the mirror problem one level up.
- *System change.* None beyond the sprint itself: the drift tests now assert the corrected
  statements, so the prose and the rule fail together. Worth noting as the reason a mirror comment
  is not a cheap substitute for a test even when nobody has changed the constant.

## Design Decisions

- **Drift-tested, not served** (above) — recorded in `docs/decisions.md`.
- **The order of the application statuses is the web's own.** Django lists them in the order they
  were added; the web in funnel order, because that is the order the filter dropdown reads. The
  guard asserts MEMBERSHIP both ways and leaves the order alone. Asserting the order would have
  forced a cosmetic reorder of a Django model for a dropdown's benefit.
- **The STR coach set is guarded through `shouldShowCoach`, not by exporting the constant.** The
  set is module-private; reading it the way a student's screen does means the guard survives the
  set being renamed or inlined, and it costs no widening of the module's public surface.
- **`REQUEST_COMPONENT_TREE` was left alone** although its two ledger entries sit in a file this
  sprint edited. It is H10's named scope; taking it here would have made H9's diff harder to read
  for no gain in safety.

## Numbers

| | Before | After |
|---|---|---|
| pytest `-n auto` | 7,000 / 3 skipped | **7,000 passed · 3 skipped · 0 failed** (no api file edited) |
| jest | 2,615 / 144 suites | **2,768 / 150 suites** |
| `unguarded_mirrors` ledger | 58 | **41** |
| `mirror` reading | (did not exist) | **41** — agrees with the ledger exactly |
| `guard%` | 11 | **15** (+4; the definition widened, see What Went Wrong 2) |
| Every other code-health reading | | unchanged · `std` ok · **0 FAIL** |
| Bite-checks | | **17 run, 17 behaved** (8 api-side, 7 web-side, 2 no-cry-wolf) |
| Production code changed | | **none** — six test files, one test helper, seventeen comment blocks |
| Migration | | none |
| Findings raised | | **TD-264** (money path), **TD-263** (low) |
