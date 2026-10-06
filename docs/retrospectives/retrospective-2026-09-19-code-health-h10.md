# Retrospective — Code health H10: fewer than half of the "mirrors" were mirrors

**Date:** 2026-09-19 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H10 of H19
**Built by:** an Opus 5 agent to the same brief and the same hard rules as H9. The lead reads the
report and pushes.
**Outcome: the ledger is empty but for a documented exception. PHASE 3 COMPLETE — the checkpoint
is now the owner's.**
**No production code changed.** Nine test files, one test helper extended, 38 comment blocks edited.

## What Was Built

- **Nine drift tests, 127 cases**, each named by a `drift-test:` marker in the comment it
  discharges. Seven read the backend's own source through H9's `apiSource.ts`; two read another
  **web** file, because a copied rule is a copied rule whichever side of the wire both halves are on.

  | guard | what it holds | why it matters |
  |---|---|---|
  | `familyRosterDrift` | `family.py` profession codes, `NON_EARNING`, `is_valid_person_name` | a code the form offers and Django's `choices` lacks is a roster row dropped on save, silently |
  | `themeContrastDrift` | `TENANT_FAMILIES`, `PLATFORM_SURFACES`, the `PAIRS` table, the WCAG maths | the browser says "this colour is fine" and the server refuses the save |
  | `commsKindsDrift` | both `KIND_CHOICES` tables, three surfaces | a kind nobody names is an email going to real people with no screen to change it |
  | `staffDrift` | `invitations.status_of`, `reviewer_profile_complete` | `no_reply` is not `expired`; a mismatched gate is a reviewer in a redirect loop |
  | `contractTermsDrift` | `clause_numbers`, `normalise_levels`, `quiz_payload_valid`, the quiz wipe | numbers on a document somebody signs |
  | `requestComponentDrift` | `REQUEST_COMPONENT_TREE`, `VALID_COMPONENTS` | `_clean_choice` blanks an unknown value **silently** |
  | `financeAllowlistDrift` | `FundingSummaryRowSerializer` | the only student data a `finance` admin ever sees |
  | `studentScreenDrift` | `POST_SHORTLIST_EDITABLE + _FUNDED_STATES`, the single-instance rule | which application the student's own screen is about |
  | `webMirrorDrift` | four web-to-web pairs | same standard, no backend to read |

- **Sixteen comments reworded** to say what the code actually does (see below).
- **The ledger: `unguarded_mirrors` 41 → 3**, and the three that remain carry their reason in two
  places — the top of `incomeWizard.ts`, where the temptation is, and beside the entries in
  `code-standards.json`.
- **`apiSource.ts` extended**: an `indented` mode for class attributes, and **line-ending
  normalisation** (see What Went Wrong 1).
- **Two findings, reported and not fixed: TD-266 and TD-265.**

## What Went Well

- **Characterising before guarding found two drifts, both invisible.** `FundingSummaryRowSerializer`
  has eleven fields; the interface reading it has ten — `programme` is computed on every row of
  every request and rendered nowhere (TD-265). And `AdminResolutionItem` is missing two `kind`
  values, one `source` value and a whole field, while **one serializer feeds both** copies
  (TD-266). Neither would ever have failed a test or thrown an error. Third sprint running that
  the characterisation step, not the refactor, is where the findings come from.
- **The comment that over-claimed was corrected rather than blessed.** `partnerComms.ts` said it
  mirrored `partner_comms.KINDS`. That table is **fifteen** kinds across **three** screens; the
  file names eleven. The third screen — `InvitationEmailsCard.tsx` — carries no list at all and
  renders whatever the endpoint sends, which is the good pattern this whole arc is moving towards.
  The test now asserts the real invariant (*every stored kind reaches a screen*) and that the four
  invitation kinds stay OFF both hard-coded lists, so nobody "completes" the list and creates the
  maintenance the good pattern avoids.
- **The three income mirrors were left alone, loudly.** Leaving them silently would have been
  indistinguishable from forgetting them. The reason is now written where somebody would reach for
  the guard, and it says what would go wrong: a test written today either fails on a disagreement
  nobody has ruled on, or passes and thereby *blesses* one.
- **36 bites, 36 behaved**, each turning exactly the named suite red and no other — the harness
  now asserts equality with the expected set, not membership, so a bite that reddens a neighbour
  reports as SPREAD rather than passing.

## What Went Wrong

**1. The H9 drift tests were one line ending away from being machine-dependent.**
- *Symptom.* A new guard split a Python function body on `'\n\n'` to find its end. It matched
  nothing: the api sources are CRLF on this Windows checkout. The test failed locally in a way
  that had nothing to do with the rule it guards.
- *Root cause.* `readApi` returned the file's raw bytes. On this machine that is CRLF; **in the
  Cloud Build container it is LF**. A guard written against one and run against the other passes or
  fails by accident of where it ran — and the deploy gate is the place that matters. H9's six
  tests escaped only because none of them happened to match a blank line.
- *System change.* `readApi` now normalises to `\n`, with the reason in its docblock. The general
  rule, and it is the bigger half: **a test that reads another file's text must normalise
  everything that differs between a developer's machine and the builder** — line endings,
  path separators, locale, timezone. H2's lesson ("run the gate where the artefact is built") said
  the same thing about the runtime; this says it about the *inputs*.

**2. Two comment rewords broke a budget and a guard, in opposite directions.**
- *Symptom.* Rewording a comment in `src/lib/api.ts` pushed the file one line past its oversize
  allowance — a file the brief had flagged as having one line of room. Separately, the note added
  to `incomeWizard.ts` explaining why it must NOT carry a drift marker contained the literal marker
  text, which *discharged* the very claim it was explaining.
- *Root cause.* Both are the same mistake: treating a comment as free. A comment occupies budgeted
  lines and is scanned by the guard, so editing one is a code change with two mechanical
  consequences.
- *System change.* Both caught by the standards test before anything else ran, which is the system
  working. Recorded because the reflex — "it is only a comment" — is what a future sprint will
  bring to the 16 rewords this one made. The rule for the next agent: **after editing any comment
  in `src/lib`, run `codeStandards.test.ts` before anything else.**

**3. The word "mirror" is doing four jobs in this codebase, and the guard cannot tell them apart.**
- *Symptom.* 41 flagged blocks; 22 were copied rules. The rest were a retired engine, an external
  data source, a design consistency note, a disclaimer of a mirror, and one comment *quoting* a
  comment deleted long ago.
- *Root cause.* The guard matches a WORD. Its own docblock admits this ("this guard is against
  forgetting, not against a determined evader") and it is the right trade — a guard that matched
  only true mirrors would need to understand the code. But it means roughly 40% of a de-mirror
  sprint is editorial, not engineering, and neither H9's nor H10's estimate said so.
- *System change.* Recorded in the roadmap's H10 section so the number is not carried forward as
  "rules". For the future: **a ledger built by matching a word is a list of things to LOOK at, not
  a list of things to fix**, and a sprint sized from one should say which it is.

## Design Decisions

- **A reword is a legitimate end state, and the bar is "the comment now tells the truth".** Sixteen
  blocks stopped claiming a mirror because there was none. Each says what the code actually does —
  several say plainly why there is nothing to guard (`poolCard.ts`: "one side was deleted; this is
  the survivor"). Removing the word without fixing the sentence would have been ledger gaming; the
  diff is reviewable precisely because each one reads better than before.
- **Two guards read another web file rather than the backend.** The standard is about a rule with
  two homes, not about where the homes are. `MALAYSIAN_STATES` and the onboarding page's own list
  are the same kind of debt as a Python/TypeScript pair.
- **`incomeWizard.ts` × 3 stay on the ledger.** The alternative — a guard that passes on today's
  disagreements — would convert an open question into a recorded fact.

## Numbers

| | Before | After |
|---|---|---|
| pytest `-n auto` | 7,000 / 3 skipped | **7,000 passed · 3 skipped · 0 failed** (no api file edited) |
| jest | 2,768 / 150 suites | **2,895 / 159 suites** |
| `unguarded_mirrors` ledger | 41 | **3** — all `incomeWizard.ts`, by decision |
| `mirror` reading | 41 | **3** (−38) |
| `guard%` | 15 | **19** (+4, inside tolerance; now over its WARN line — see `docs/code-health.md`) |
| Every other code-health reading | | unchanged · `std` ok · **0 FAIL** |
| Bite-checks | | **36 run, 36 behaved** (16 api-side, 18 web-side, 2 no-cry-wolf) |
| Production code changed | | **none** — nine test files, one helper, 38 comment blocks |
| Migration | | none |
| Findings raised | | **TD-266**, **TD-265** |
