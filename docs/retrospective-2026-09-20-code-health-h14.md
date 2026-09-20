# Retrospective — Code health H14: the cockpit, panel by panel, and the one panel that stayed

**Date:** 2026-09-20 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H14 of H19
**Built by:** an Opus 5 agent to the same brief and the same hard rules as H9–H13. The lead reads
the report, pushes and watches the deploy.
**Outcome: `view.tsx` (3,599 lines) is 1,338; `ScholarshipDocuments.tsx` (1,914) is 825. The
moved bodies are seventeen modules, none over 512. No behaviour changed — every moved line was
rebuilt from the pre-cut file's own bytes and compared back against it — and no importing file
was touched except the three TD-271 required.**
**Every gate is green: tsc 0 · lint 0 errors · `next build` exit 0 · jest 2,913 / 159 suites ·
pytest 7,021 / 3 skipped · code_health 0 FAIL, `std` ok, `big` 22 → 21, `hot#1` holds.**
**All 59 of H6's rendered cockpit tests passed unedited, first run.**

## What Was Built

- **`src/app/admin/scholarship/[id]/view/` — 14 modules, 2,359 moved lines** (avg 181, max 346).

  | module | lines | module | lines |
  |---|---|---|---|
  | `DocumentsDrawer` | 346 | `AssignAndWitness` | 175 |
  | `PostAwardPanels` | 317 | `VerificationVerdict` | 173 |
  | `InterviewPanels` | 291 | `GeneratedProfile` | 171 |
  | `ApplicantCards` | 281 | `CockpitHeader` | 155 |
  | `OutstandingPanel` | 252 | `QcPanel` | 139 |
  | `RateAndEstimate` | 220 | `OrgRejectPanel` | 136 |
  | `shared` | 181 | `BlockersPanel` | 122 |

- **`src/components/ScholarshipDocuments/` — 3 modules, 900 moved lines** — `cards` 512,
  `checklists` 492, `checklistsPathway` 150.

- **Both original files kept their own paths**, so `./view`,
  `@/app/admin/scholarship/[id]/view` and `@/components/ScholarshipDocuments` resolve exactly as
  before and **no ledger key was renamed** — H13's rule, applied twice more, deliberately and not
  by luck.

- **The Decision / Recommendation panel did not move** (263 lines, 35 names read out of the
  component, 9 handlers). The roadmap rules it out of scope; the reason is now written above it
  in the file, where the next person to reach for it will read it.

- **Two budget entries ratcheted DOWN** — `view.tsx` 3,587 → 1,338 and
  `ScholarshipDocuments.tsx` 1,914 → 825. `baseline` untouched, `BASELINE_SHA256` unmoved, no
  ledger gained a member.

- **Three drift guards followed the code** (`theme.test.ts` F3 list and F5 block,
  `webMirrorDrift.test.ts`), each bite-checked at its new path. No guard was deleted or weakened,
  and no expected value was edited.

- **TD-271 closed** as the sprint's one declared exception, and **two findings raised, neither
  fixed**: TD-272, TD-273.

## What Went Well

- **H6's rendered tests are the reason this sprint can claim anything at all.** 59 tests across
  six files mount the real cockpit for a role and a stage. They passed **unedited, first run**,
  after 2,359 lines of JSX had been lifted into thirteen components — no import path changed in
  any of them, because the component they mount is still exported from the same file. That is
  the whole argument that the moved code is the code that runs, and bite (c) is its proof by
  contradiction: one character in a MOVED panel turned exactly two NAMED tests red and left 73
  green.
- **A fragment wrapper is what makes a JSX lift a pure move.** Every panel is
  `export function X(props) { return (<> …the exact lines… </>) }`. A fragment renders no DOM
  node, so the parent's `space-y-4` — a direct-child selector — still sees the same children in
  the same order. Nothing in the DOM changed, so nothing in the tests had to.
- **Cutting by line range, and rebuilding the file from its own snapshot, caught what judgement
  would not.** Rather than diffing after the fact, each output file is CONSTRUCTED from the
  pre-cut bytes plus the authored header, and the verifier re-derives all fifteen files and
  compares them to disk byte for byte. It reports what did NOT move too: 108 lines in the cockpit
  and 44 in the documents tab, all of them a `'use client'` directive or an import header, all
  declared in the spec before the run.
- **`tsc` as the oracle, and the template-literal fix held.** H13's scanner change (keep every
  `${ … }` body, blank only the literal text around it) went straight into this sprint's
  reference derivation, and **both cuts type-checked on the first run** — 14 modules with ~180
  props and 3 modules of checklists, no `Cannot find name` at all. The scanner also had to learn
  two more things this time: a `.foo` member access is not a reference to a binding called `foo`,
  and neither is a JSX attribute name. Without both, `role` and `params` were "needed" by four
  panels that only ever write `{ role: personLabel }` or read `item.params`.
- **The bundle was measured, not argued.** The work was parked with byte backups (SHA-256
  verified on restore, restore in a `finally`), the old tree rebuilt, and the route tables
  diffed: 87 routes, 86 unchanged, one moved. It found a real +2 kB on the cockpit, which no
  amount of reasoning about fragments would have predicted, and which is small enough to accept
  and large enough to write down.
- **Every bite behaved, including the two that tested my own re-pointing.** Six run: a name
  dropped from each shell (tsc named the exact call site), one character in a moved panel (two
  named tests red, 73 green), TD-271's field removed (tsc red in three named places), the two
  re-pointed drift guards bitten at their NEW paths, and a whitespace-only edit that left the
  whole suite green at 2,913 / 159. All six restores SHA-256 verified.

## What Went Wrong

**1. `big` fell by ONE, and the acceptance asked for two. It could not have fallen by two.**
- *Symptom.* The brief's acceptance reads "`big` falls by two". `ScholarshipDocuments.tsx` left
  the over-1,000 list; `view.tsx` did not, at 1,338.
- *Why, as arithmetic rather than effort.* What must STAY in `view.tsx` is: 784 lines of state
  and handlers, 137 of derived readings, the **263-line Decision panel the roadmap rules out of
  scope**, about 75 of imports and about 150 of panel call sites. That is ~1,300 whatever else
  moves, and 2,359 lines already did move. The obvious escape — make `view.tsx` a thin shell and
  put the component body in `view/CockpitView.tsx` — is closed from the other end: a NEW file
  over 600 lines is refused by the in-repo standard with no ledger line available to record it
  (H11's note 1). A React component cannot span two files, so there is no third option.
- *What it means.* **`view.tsx` goes under 1,000 when the Decision panel is untangled, and that
  is design work.** The acceptance inherited H13's shape — two barrels, two files leaving the
  list — and a cockpit is not a barrel. Recorded in the roadmap's H14 section as note 1 so the
  next brief does not carry the same assumption forward.
- *Not a failure of the move.* 3,599 → 1,338 beats the roadmap's own acceptance for this sprint
  ("`view.tsx` under ~2,000 lines") by 660 lines.

**2. A frozen exemption ledger keyed on a PATH refused a scoped move, and there was no honest way
round it.**
- *Symptom.* `IncomeWizard` (524 lines) is named in the roadmap's H14 scope. Moved out, the
  suite went red: *"eslint-disable comment(s) with no written reason …
  `src/components/ScholarshipDocuments/IncomeWizard.tsx:130`, `:145`"*.
- *Why.* Those two `react-hooks/exhaustive-deps` disables are recorded in `code-standards.json`
  under the PARENT file's path. At the new path they are unlisted → FAIL. Adding the new path →
  *"a ledger has gained a member"* → FAIL, because `budget` may not hold a key absent from the
  frozen `baseline`. Editing the baseline and re-pinning `BASELINE_SHA256` (H11's documented
  escape) makes `Settings/_tools/code_health.py` report **`std: FAIL — a NEW exemption`**, which
  is the false FAIL H11's lesson 2 asked not to be accepted a fifth time.
- *The choice made.* The wizard stayed. The only remaining route was to write a reason for each
  disable — and a reason for why a dependency array is deliberately incomplete is ANALYSIS, not
  a move; a wrong justification written into the code is worse than the recorded debt. The
  refusal is written at the top of `ScholarshipDocuments.tsx` so the next reader does not
  rediscover it.
- *System change.* **TD-272**, medium, with two candidate fixes for H19 (key the ledger on the
  rule plus the surrounding line, or teach the ratchet a `moved_to` that permits a rename only
  when the count does not rise). ⚠ **This is H11's ledger-key lesson in a SECOND ledger, and it
  is the one H13's keep-the-path trick cannot dodge** — that trick protects a FILE's key; it does
  nothing for an exemption sitting inside a moved body. H15 and H16 must grep the ledgers for the
  file they intend to split BEFORE planning the cut.

**3. Two `not.toMatch` assertions would have gone green for the wrong reason, and only re-pointing
the guard as a WALK stopped it.**
- *Symptom.* `webMirrorDrift.test.ts` asserts the cockpit carries no second
  `status !== 'shortlisted'` test of its own. It reads `view.tsx` by path. The Assignment card —
  the very card the pair is about — moved to `view/AssignAndWitness.tsx`.
- *Why it is worse than an ordinary red.* Two of the three assertions are `not.toMatch`. Had the
  guard been left reading one file, it would have PASSED, for ever, because the code it polices
  is somewhere else. A guard that goes red tells you something; a guard that goes green because
  the subject left the room tells you nothing and looks identical.
- *System change.* Both guards now read `view.tsx` plus a WALK of `view/`, so a panel added or
  split tomorrow is read the day it lands, and each carries a floor (`>= 15 files`, `>= 14
  modules`) **folded into an existing test** rather than added as a new one — so the suite count
  stayed exactly at the 2,913 the baseline measured. `theme.test.ts`'s F3 list gained a walk of
  the documents folder for the same reason: it named one file, and 1,100 converted lines would
  have dropped out of the only guard keeping that student surface out of a light-mode island.

**4. The bite harness crashed twice on its own console output, and the `finally` is why that cost
nothing.**
- *Symptom.* Bite (c) died with `UnicodeDecodeError` reading jest's output on a cp1252 console,
  then with `UnicodeEncodeError` printing jest's `●` bullet.
- *Why it did not matter.* The restore is in a `finally` and the SHA-256 is compared after it:
  both times the file came back byte-identical and the run simply had to be repeated with
  `encoding='utf-8'` and an ASCII-safe print. **An instrument that fails loudly after restoring
  is a working instrument**; the failure mode to fear is one that fails before it.

## Design Decisions

- **The panels went to `[id]/view/`, not `src/components/admin/cockpit/` as the roadmap
  suggested.** The brief's rule — original file keeps its path, bodies go in a folder beside it —
  is what keeps the ledger key naming a real file, and it also keeps a panel one directory away
  from the only screen that draws it. A folder under `app/` with no `page.tsx`, `layout.tsx` or
  `route.ts` creates no route: `next build` lists 87 routes, the same 87, with no
  `/admin/scholarship/[id]/view` among them.
- **`view.tsx` has no default export, and never did.** The brief warned to check that a page
  shell keeps its default export and route semantics. It does not apply here: the ROUTE is
  `[id]/page.tsx` (22 lines, untouched, still the only default export), and `view.tsx` exports
  exactly one name, `AdminScholarshipDetailView`, as it did before — because Next refuses a page
  module that exports anything but its default, which is why F7c split them in the first place.
  Worth recording as a non-finding: the check was right to ask, and the answer is that the file
  in question is not the page.
- **Prop types are DERIVED, never re-declared.** `shared.tsx` exports
  `type T = ReturnType<typeof useT>['t']` and
  `type AdminRole = ReturnType<typeof useAdminAuth>['role']`. The alternative was to export
  `AdminRole` from `admin-auth-context.tsx` — a change to a file outside the sprint's scope — or
  to hand-write `{ role?: string; admin_id?: number | null }`, which is a new type shape that can
  drift from the real one. Reading the type off the hook that produces it costs nothing and
  cannot drift.
- **Every setter is `Dispatch<SetStateAction<T>>`, not `(v: T) => void`.** It is exactly what
  `useState` returns, so passing one through is type-exact, and it accepts both the plain-value
  and the updater-function call styles the moved bodies use. A narrower type would have forced a
  change to a moved line, which is the one thing this sprint may not do.
- **Thirteen panels, not twenty-three.** Several panels are siblings that always appear together
  and share every prop (referees + interview stage; rate + estimate + reporting date; bursary +
  disbursement + closure; org-reject + its record; assign + witness). Grouping them keeps the
  call-site count — and therefore `view.tsx`'s length — down, and every module is still far
  inside the 600-line standard. The largest is 346.
- **State stayed in the cockpit; only JSX moved.** Several panels own state read by nothing else
  (the witness card's five, the disbursement form's three, the closure form's two), and pushing
  them down would have shortened `view.tsx` by about 140 more lines. It would not have reached
  under 1,000 (see What Went Wrong 1), and it would have put a structural change — where state
  lives, when a subtree remounts — inside a diff whose entire claim is that it is a move. Not
  worth a line count it could not buy.

## Numbers

| | Before | After |
|---|---|---|
| `src/app/admin/scholarship/[id]/view.tsx` | 3,599 lines | **1,338 lines** |
| `src/app/admin/scholarship/[id]/view/` | — | **14 modules, 2,359 moved lines** (avg 181, max 346) |
| `src/components/ScholarshipDocuments.tsx` | 1,914 lines | **825 lines** |
| `src/components/ScholarshipDocuments/` | — | **3 modules, 900 moved lines** (max 512) |
| Moved bodies vs the original | — | **byte-identical, all 17 modules**; 3,259 lines |
| Original lines NOT moved | — | **152**, all declared: `'use client'` + the import header of each file |
| Private names promoted to `export` | — | **32**, none re-exported outside its folder |
| Importing files changed | — | **3, all TD-271** — `MemberIncomeGroup.tsx`, `ScholarshipDocuments.tsx`, `ScholarshipDocuments.test.tsx` |
| Files in the diff | — | **8 modified + 2 new folders**; no page, no route file, no api file |
| Deep imports into the new folders from outside | — | **0** |
| H6's rendered cockpit tests | 59 | **59 passed, 0 edited** |
| jest | 2,913 / 159 suites | **2,913 passed · 159 suites · 0 failed** |
| pytest | 7,021 / 3 skipped | **7,021 passed · 3 skipped** (no api file touched; run anyway) |
| tsc / lint / i18n | 0 / 0 errors / ok | **0 · 0 errors (17 pre-existing warnings) · ok** |
| `npx next build` | exit 0 | **exit 0** — 87 routes, the same 87 |
| First Load JS | — | **86 routes unchanged, 1 up**: cockpit 32.8 → 34.8 kB (513 → 515 kB); shared chunk 87.1 kB both |
| `big` (files over 1,000 lines) | 22 | **21** — see What Went Wrong 1 |
| `hot#1` | `income_engine.py` 95.6 | **`income_engine.py` 95.6** — holds |
| `std` | ok | **ok** — no key renamed, `baseline` untouched |
| `xapp` / `supp` / `skip` / `guard%` | 46 / 139 / 0 / 19 | **46 / 139 / 0 / 19** — all unchanged |
| code_health | 0 FAIL, 6 WARN | **0 FAIL, 6 WARN** — the same six |
| `manage.py check` / `makemigrations --check` | 0 / clean | **0 issues · no changes detected** |
| Line endings | CRLF (LF in `webMirrorDrift`) | **unchanged, checked byte by byte on all 25 files** |
| Bite-checks | | **6 run, 6 behaved**, all restores SHA-256 verified |
| Behaviour changed | | **none** |
| Migration | | none |
| Deletions | | `ServesIncomeShown` (TD-271), replaced by the field on `ScholarshipApplication` |
| Findings raised | | **TD-272 · TD-273** (TD-271 closed) |

**⚠ How to read `supp`, and please read it before asking why it did not move.** The roadmap's H14
scope included a `useApiLoad(token, fn)` hook to retire about 26 of the 33 `exhaustive-deps`
disables, and predicted `supp` down ~25. **That half was cut from this sprint's brief**: a new
shared hook is a design change, not a move, and Phase 4 is moves only. `supp` is 139 either side,
correctly. The hook is still worth doing, and TD-272 makes it worth more than it was — one hook
would retire those disables AND unblock `IncomeWizard`'s move, which the frozen ledger currently
refuses.
