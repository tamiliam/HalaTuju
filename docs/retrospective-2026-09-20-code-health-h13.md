# Retrospective — Code health H13: two barrels, 231 importers, not one of them edited

**Date:** 2026-09-20 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H13 of H19
**Built by:** an Opus 5 agent to the same brief and the same hard rules as H9–H12. The lead reads
the report, pushes and watches the deploy.
**Outcome: `admin-api.ts` (4,118 lines) is 241 lines of re-export; `api.ts` (2,488) is 132. The
bodies are 42 modules, none over 450. No behaviour changed — every moved line is byte-identical to
the line it came from, proved mechanically — and NOT ONE of the 231 importing files was touched.**
**Every gate is green: tsc 0 · lint 0 errors · `next build` exit 0 · jest 2,913 / 159 suites ·
code_health 0 FAIL, `std` ok, `big` 24 → 22, `hot#1` 107.1 → 95.6.**
**Not one route's First Load JS grew; 53 of 72 shrank.**

## What Was Built

- **`src/lib/api/` — 14 modules, 2,604 lines** (avg 186, max 417), behind a 132-line barrel.

  | module | lines | module | lines |
  |---|---|---|---|
  | `documents` | 417 | `award` | 134 |
  | `sponsor` | 372 | `calculations` | 111 |
  | `stpm` | 262 | `bank` | 99 |
  | `application` | 257 | `interview` | 87 |
  | `courses` | 243 | `inProgramme` | 84 |
  | `profile` | 217 | `resolution` | 79 |
  | `guidance` | 187 | `client` | 55 |

- **`src/lib/admin-api/` — 28 modules, 4,385 lines** (avg 157, max 443), behind a 241-line barrel.

  | module | lines | module | lines | module | lines |
  |---|---|---|---|---|---|
  | `applications` | 443 | `contracts` | 151 | `decisions` | 92 |
  | `requests` | 315 | `partners` | 136 | `theme` | 91 |
  | `programmes` | 273 | `reviewers` | 135 | `sources` | 90 |
  | `overview` | 222 | `orgConfig` | 129 | `invitations` | 72 |
  | `billing` | 221 | `lifecycle` | 125 | `resolution` | 66 |
  | `invoices` | 215 | `interviews` | 111 | `courseData` | 48 |
  | `sponsors` | 194 | `documents` | 111 | | |
  | `verdict` | 187 | `spending` | 103 | | |
  | `payments` | 176 | `client` | 97 | | |
  | `admins` | 172 | `profiles` | 95 | | |
  | `sponsorTerms` | 159 | | | | |
  | `emails` | 156 | | | | |

- **Both barrels kept their own paths**, so `@/lib/api` and `@/lib/admin-api` resolve exactly as
  before and **no ledger key was renamed** — H11's trap avoided by construction, not by luck.

- **The two oversize ledger entries were REMOVED** from `budget` in
  `halatuju-web/code-standards.json`. At 241 and 132 lines both barrels are under the 600-line
  standard, so the ratchet asks for the lines to GO rather than fall. `baseline` untouched,
  `BASELINE_SHA256` unmoved.

- **Three drift tests followed the code** (`webMirrorDrift` ×4 reads, `financeAllowlistDrift` ×1,
  `officerGateDrift` ×1) and each was bite-checked at its NEW path. No guard was deleted or
  weakened.

- **One pre-existing break repaired** (see What Went Wrong 1) and **three findings raised, none
  fixed**: TD-269, TD-270, TD-271.

## What Went Well

- **The barrel is the whole trick, and it held.** 231 files import these two modules — 122 by
  `@/lib/admin-api`, 85 by `@/lib/api`, 24 by a relative path — and **thirty-three test files
  `jest.mock()` one of them by automock**, which is the case the roadmap flagged as the risk. Not
  one of the 231 changed. The diff is six modified files and two new folders, and `git status` is
  the proof: no page, no component, no hook, no test file appears in it.
- **The pilot the roadmap demanded paid for itself in ten minutes.** Before cutting anything, one
  module (`api/client.ts`) was extracted by hand and the suite run. It answered the two questions
  that would have been expensive to discover late: does `src/lib/api.ts` still win over
  `src/lib/api/` in module resolution (yes — LOAD_AS_FILE precedes LOAD_AS_DIRECTORY in both
  webpack and jest), and does jest's automock see through a re-export barrel (yes). Everything
  after that was mechanical.
- **Cutting by line range and reading the files back is now the default, and it caught the one
  thing judgement would have missed.** 6,586 lines were cut from the two files' own bytes and every
  module compared, line by line, with `git show HEAD:…`. The checker also reports which original
  lines did NOT move: twenty, and all twenty are the two file docstrings and the import headers —
  exactly the lines a split CANNOT copy, declared in the spec with a reason before the run. "All
  accounted for, and here is each exception" is worth more than forty-two YESes.
- **The bundle acceptance was MEASURED, not argued.** The work was parked (with a byte-level
  backup), the tree returned to HEAD, a baseline `next build` taken, and the work restored. Result:
  **0 of 72 routes grew, 53 shrank, 19 unchanged**; total First Load JS across routes 30,665 kB →
  30,505 kB; the shared chunk identical at 87.1 kB. The mechanism is real and is the split's best
  argument: a page that imports three admin calls used to drag a 4,118-line module into its chunk
  and now drags only the modules those calls live in. `/admin` fell 7 kB, the cockpit 4 kB.
- **Every bite behaved, including the two that tested my own repairs.** Six run: drop a name from
  each barrel (tsc named the exact importers), one character in a moved body (two named tests red,
  ten still green — the moved code is the code that runs), a whitespace-only edit in that same file
  (full suite green: 2,913 / 159), and the two re-pointed drift guards bitten at their new paths.
  All six restores SHA-256 verified.

## What Went Wrong

**1. The web deploy gate had been red for two sprints, and the sprint that broke it could not see
it.**
- *Symptom.* The baseline run — taken before touching anything, precisely to avoid blaming myself
  later — came back **1 suite failed, 158 passed, 2,900 tests**, against a brief that said the
  baseline was 2,913 / 159. `officerGateDrift.test.ts` was dead at import:
  *"drift test: apps/scholarship/views_admin.py is not in halatuju_api."*
- *Why.* H11 turned `views_admin.py` into a package and H12 finished the job. That file is read by
  a **web** drift test, through `src/test/apiSource.ts`, to check the two officer gates against the
  api's own source. H11 and H12 were backend-only sprints: both ran `pytest`, `manage.py check` and
  `makemigrations --check`, all green, and neither ran `jest`, because neither touched a web file.
  **The break was invisible from the side that caused it.** The guard even printed the right
  instruction — *"The rule it guards has MOVED — find its new home and update the path here, never
  delete the assertion"* — to nobody.
- *Repaired here, because the acceptance is "jest green" and it cannot be.* `VIEWS` is now the two
  package modules that hold the classes (`applications.py` → `AdminOrgRejectView`, `verdict.py` →
  `AdminAssignReviewerView`), read and joined; `viewBody` still asserts the class appears exactly
  once across them, so a class that moves again, or gets duplicated, still throws. 13 tests
  restored; 2,900 + 13 = 2,913, the brief's number exactly.
- *System change.* **TD-269.** The repair is one line; the debt is that nothing connects the two
  trees. 31 web test files read source text and several read `halatuju_api/**`, so **any api
  refactor can kill a web guard with every api gate green.** The proposed fix is a cheap api-side
  check that greps the web tree for `readApi('…')` paths and fails if one names a file that no
  longer exists — the same idea as the guard's own message, run on the side that does the moving.

**2. A previous sprint booked work into H13 that H13's own rules forbid, and it was written in a
code comment where no checklist would find it.**
- *Symptom.* `src/components/scholarship/MemberIncomeGroup.tsx:31-38` says the served
  `income_shown` field is declared locally rather than on `ScholarshipApplication` because
  *"`src/lib/api.ts` sits EXACTLY on its oversize ceiling … and is waiting on H13 to become a
  barrel"*, and states plainly: **"H13 folds it into `ScholarshipApplication` when that file is
  split."**
- *Why it was not done.* H13's brief is moves only, with **"no change to any type's shape"** in
  terms. Folding a field onto `ScholarshipApplication` is exactly a change to a type's shape. The
  two instructions are in direct conflict and the brief wins; doing it would also have put a
  behaviour-adjacent edit inside a 6,586-line move diff, which is the thing Phase 4 exists to
  avoid.
- *System change.* **TD-271**, with the note that **the reason for deferring is now GONE**: the
  ceiling that blocked it does not exist any more, `api/application.ts` is 257 lines, and the fold
  is a handful of lines in one module plus deleting the local interface. It is an H14-sized job or
  a small change. The general lesson is the sharper half: **a task deferred INTO a named sprint
  must be written where that sprint will read it** — the roadmap's H13 section, not a comment in a
  component the sprint never opens. This one was found only because a stale sentence about file
  sizes turned up in a grep for the file being split.

**3. The reference scanner blanked template literals, so six shared names went missing and tsc
found them for me.**
- *Symptom.* The first `admin-api` cut produced 22 `TS2304: Cannot find name 'API_BASE'` and
  `'giftQuery'` across nine modules. Every one of those uses is inside a template literal —
  `` fetch(`${API_BASE}${path}`) ``.
- *Why.* The cutter decides a module's import header by scanning its body for names declared
  elsewhere, and it blanks comments and string literals first so a name mentioned in prose is not
  imported. A template literal was treated as a string. **It is a string with code in it**, and in
  this codebase `${API_BASE}` is how nearly every call reaches the base URL.
- *System change.* The scanner now keeps every `${ … }` (recursively, since they nest) and blanks
  only the literal text around them. Worth writing down because the failure was silent in the
  direction that matters: the scan reported *fewer* dependencies than exist, so the modules looked
  cleaner than they were, and only a compiler said otherwise. **TypeScript has no `symtable`, so
  `tsc` is the oracle — run it after the first cut, before the second.** H12 had the same shape of
  problem and solved it with `symtable`; this is the TypeScript answer to the same question.

**4. A bite-check could not find its own needle — the same CRLF trap as H12, one sprint later.**
- *Symptom.* Bite (f) reported *"needle appears 0 times"* for a two-line string that is plainly in
  the file.
- *Why.* `src/lib/admin-api/payments.ts` is CRLF (correctly — the cutter sniffs the original's
  endings) and the needle was written with `\n`.
- *System change.* The bite harness now normalises the needle AND the replacement to the file's own
  line ending before counting, so the next multi-line bite in this repo cannot fail this way. H12's
  lesson said "a bite that cannot find its own needle is a fact about the tree" — true, and the
  follow-through is to fix the instrument once rather than dodge it each time. **No file's line
  endings changed in this sprint**: all 42 new modules are CRLF, the two barrels stayed CRLF, the
  three edited test files stayed LF, `code-standards.json` stayed CRLF, checked byte by byte.

## Design Decisions

- **The barrels keep their own file paths; the folders sit beside them.** The roadmap suggested
  `admin-api/index.ts`. That would have RENAMED the ledger key `src/lib/admin-api.ts` and walked
  straight back into H11's problem, where a key naming a file that no longer exists makes the
  frozen baseline have to follow. Keeping `admin-api.ts` as the barrel means the key still names a
  real file, the entry is simply removed as under-standard, `BASELINE_SHA256` never moves, and
  `std` reads `ok`. The cost is a `foo.ts` sitting next to a `foo/`, which resolves correctly in
  both webpack and jest and was proved in the pilot before anything else was cut.
- **Two private clients, not one shared `src/lib/http.ts`.** The roadmap proposed moving the four
  fetch helpers into one shared module. They are not one helper: `apiRequest` turns a 403
  `nric_required` into a window event and carries DRF field errors on a 400; `adminFetch` does
  neither, because no admin screen has an NRIC gate. The roadmap said to keep both behaviours —
  and the surest way to keep two behaviours apart is not to file them under one name. Each folder
  has its own `client.ts`, each says in its header that it is not the other and why, and **neither
  is re-exported by its barrel**, because neither was exported before. `@/lib/http` would also have
  been a new public module outside the two folders, which the acceptance forbids.
- **Six private names gained the word `export`, and the barrels do not re-export any of them.**
  `API_BASE`, `ApiOptions`, `adminFetch`, `adminMutate`, `adminBursaryPost`, `giftQuery` (and
  `apiRequest`/`ApiOptions` on the student side) were file-private and are now folder-private. That
  is the one thing a TypeScript split cannot do for free — Python's `views_admin` split needed no
  equivalent — so the cutter records each promotion separately and the verifier reports it as
  "promoted to `export`" rather than counting it as byte-identical. **The app's public surface is
  unchanged:** every name `@/lib/admin-api` exported before, it exports now; nothing more.
- **`AdminScholarshipDetail` (240 lines) was NOT split further.** Every field on it comes from one
  serializer, and a type whose halves live in two files is a type nobody can read in one sitting.
  It sets `applications.ts` at 443 lines, comfortably the largest module and comfortably under 600.
- **Twenty original lines were deliberately not moved, and they are declared in the spec, not
  discovered afterwards.** They are the two file docstrings (the first line of each is kept
  verbatim at the head of its barrel) and the two `import type` headers. An import header is the
  one part of a split that has to be re-derived per module; pretending otherwise would have meant
  copying `import type { Locale } from './branding'` into a subfolder where that path is wrong.
- **The type-only import cycles in `admin-api/` were NAMED, not engineered away** — see TD-270 and
  H12's `xapp` lesson, which is the same lesson in a different key.

## Numbers

| | Before | After |
|---|---|---|
| `src/lib/admin-api.ts` | 4,118 lines | **241 lines** of re-export, no code |
| `src/lib/api.ts` | 2,488 lines | **132 lines** of re-export, no code |
| `src/lib/admin-api/` | — | **28 modules, 4,385 lines** (avg 157, max 443) |
| `src/lib/api/` | — | **14 modules, 2,604 lines** (avg 186, max 417) |
| Moved bodies vs the original | — | **byte-identical, all 42 modules**; 6,586 lines |
| Original lines NOT moved | — | **20**, all declared: 2 docstrings + 2 import headers |
| Private names promoted to `export` | — | **8**, none re-exported by a barrel |
| Importing files changed | 231 | **0** — 122 `@/lib/admin-api`, 85 `@/lib/api`, 24 relative |
| Deep imports into the new folders | — | **0** from outside them |
| Files in the diff | — | **6 modified + 2 new folders**; no page, component, hook or app test |
| jest | 2,913 / 159 suites *(2,900 / 158 as actually found — see What Went Wrong 1)* | **2,913 passed · 159 suites · 0 failed** |
| tsc / lint / i18n | 0 / 0 errors / ok | **0 · 0 errors (17 pre-existing warnings) · ok** |
| `npx next build` | exit 0 | **exit 0** |
| First Load JS | — | **0 routes up · 53 down · 19 same**; 30,665 → 30,505 kB; shared chunk 87.1 kB both |
| `big` (files over 1,000 lines) | 24 | **22** — both barrels left the list |
| `hot#1` | `admin-api.ts` 107.1 | **`income_engine.py` 95.6** (−11.5) — read the caveat below |
| `std` | ok | **ok** — no key renamed, `baseline` untouched |
| `xapp` / `supp` / `skip` / `guard%` | 46 / 139 / 0 / 19 | **46 / 139 / 0 / 19** — all unchanged |
| code_health | 0 FAIL, 6 WARN | **0 FAIL, 6 WARN** — the same six |
| `manage.py check` / `makemigrations --check` | 0 / clean | **0 issues · no changes detected** |
| Bite-checks | | **6 run, 6 behaved**, all restores SHA-256 verified |
| Behaviour changed | | **none** |
| api code touched | | **none** — no pytest run, and no api file is in the diff |
| Migration | | none |
| Deletions | | **none** |
| Findings raised | | **TD-269 · TD-270 · TD-271** (one pre-existing break repaired) |

**⚠ How to read `hot#1`, and please do read this before quoting it.** The metric is
`fixes × KLOC` in a 90-day window. `admin-api.ts` scored 26 × 4.118 = 107.1. The path SURVIVED the
split (it is the barrel), so its fix history is intact and the **fix count is unchanged at 26** —
what fell is KLOC, from 4.118 to 0.241, which takes the same file to about 6.3 and hands the top
spot to `income_engine.py` at 95.6. Some of that is a genuine improvement, and it is the
improvement the metric is designed to reward: no single file now carries 4,000 lines of
bug-attracting surface. But the 4,000 lines did not become safer today — they moved to 28 files
with **no fix history at all in the window**, and those files will earn their own scores over the
next ninety days. Read −11.5 as "the blast radius per file is smaller", never as "26 bugs were
fixed". This is H11's note 3 in a milder form: there, a rename made a hotspot appear to vanish;
here, a split makes one appear to shrink faster than the code improved.
