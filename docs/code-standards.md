Moved word for word from halatuju_api/CLAUDE.md on 2026-11-03. CLAUDE.md keeps the short rules; this is the full text.

## Code standards (enforced by tests — since code health H4, 2026-09-19)

These are not advice. Each one is an assertion in the normal test suite, and since H2 both suites
run inside the Cloud Build deploy gate — so **a change that breaks a standard cannot deploy**,
whoever or whatever wrote it. If you are reading this because a build went red, the failure
message itself tells you what to do; this table is the why.

| Standard | Enforced by | Why it exists |
|---|---|---|
| **No new giant file** — a source file may not pass 600 lines; the 36 api / 20 web files already over are listed with their size and may not grow more than 20 lines | `test_code_standards.py` · `codeStandards.test.ts` | `views_admin.py` was 8,547 lines and had been fixed 34 times in 90 days. Nobody holds a file that size in one head, and nobody reviews it properly. (H11 split it: the entry is now `views_admin/__init__.py` at 5,093, and **a split RENAMES a ledger key** — since TD-272 that is a DECLARED move, not a hand edit of the frozen baseline: see **Moving a file that is in a ledger** below before splitting anything else on this list) |
| **No new giant function** — no Python function of 150+ lines outside the ledger of 16; a listed one may not grow more than 10 lines | `test_code_standards.py` | A 300-line function has no seams, so a branch in the middle of it can only be reached by running the whole thing |
| **One rule, one home** — no module-level function name defined in 3+ files of one app, beyond the ten listed | `test_code_standards.py` | `_money` is seven functions with one name. A money-format fix made in one copy is not made in the other six |
| **Tests can fail** — zero `skip` / `skipif` / `xfail` / `unittest.skip`; zero `.skip` / `.todo` / `xit` / `xdescribe`; the four files using a runtime `self.skipTest` are ledgered and may only shrink | both | Both golden masters used to skip themselves on the run straight after a regenerate: the least supervised moment in the process passed green |
| **No blind spots** — `# noqa` and `# type: ignore` counts may not rise; no `@ts-ignore`; the `any` and `@ts-expect-error` counts may not rise | both | Every one is a gate told to look away, and `tsc` is a deploy gate here |
| **Every `eslint-disable` carries a written reason** — ` -- why` on the same line, or a sentence in the comment above; the 37 without one are ledgered and may only shrink, and the total may not rise | `codeStandards.test.ts` | A rule switched off without a reason cannot be told from one switched off by accident, and nobody can ever judge whether it is still needed |
| **No unguarded mirror** — a `src/lib` comment saying a rule is *mirrored* or *kept in sync* must carry `drift-test: <repo-relative path>` naming the test that proves it; the ledger of those without one is **3** (58 at H4, 17 discharged by H9, 38 by H10) and only shrinks. ⛔ The three that remain are `incomeWizard.ts` and they stay **by decision** until TD-262 is settled — the reason is at the top of that file | `codeStandards.test.ts` | The `SOFT_EVIDENCE` denylist rotted because nothing enforced its mirror, and a fact backed only by soft signals leaked to blue. A comment asking two files to stay in step is a request; only a test is a rule. **Serve a rule that VARIES between callers; guard a rule that is a constant** (decisions.md 2026-09-19) — a served constant can only fail at runtime, a drift test fails in the deploy gate. The shared reader is `halatuju-web/src/test/apiSource.ts` |
| **No dead weight** — every package in `dependencies` is imported somewhere | `codeStandards.test.ts` | Downloaded on every build, audited on every scan, and read by the next person as something this app uses |
| **The app boundary** — `courses → scholarship` imports may not rise above 25, and the module-level ones may not rise above 1 | `test_code_standards.py` | Two apps that import each other are one app with a line drawn through it, and the import-time half is what takes the service down at start-up |
| **New tests use the factory** — a test file not already in the ledger of 134 may not call `ScholarshipApplication.objects.create(`; a listed file's count may only fall | `test_code_standards.py` | A hand-built fixture can describe a state the product cannot reach, and then the test passes for ever while testing nothing (BrightPath #24). See **Test fixtures** below |
| **A route may not get heavier** — no route's first-load JS may reach **250 kB** (300 until TD-360, 2026-10-21) unless it is in the `first_load_js` ledger with its own number, no ledgered route may pass that number, and the **median across all routes** may not rise above **180 kB** (256 until TD-300, 229 until TD-360) | `scripts/bundle-budget.js` **in the deploy gate** (+ `codeStandards.test.ts` for the ledger and the wiring) | A visitor downloaded 1.53 MB of message catalogues to read one language, and nothing counted it for a year. See **The two budgets H18 added** below — this one is NOT measured by jest and that matters |
| **Opening one applicant may not cost more queries** — the officer's applicant-detail GET is pinned at **38**, with or without documents, with ZERO slack | `test_query_budgets.py` (the reading) + `test_code_standards.py` (the ratchet) | It was **315** and **385** — an N+1 nobody had counted since June. TD-282 fixed it with the document snapshot (below); the two numbers are now EQUAL because a document costs nothing extra to open. The budget's job now is to notice if that comes undone |
| **The Mobile Standard may not slip** — the global 16 px phone rule for text fields stays in `globals.css` (outside `@layer`) and no field carries an `!important` small size; `hidden` file inputs, hand-rolled `fixed inset-0` overlays, `vh` heights, `min-h-screen` and `title=`-only icon controls are each a floor that only goes down; the root layout keeps `viewportFit: 'cover'` and never blocks zoom; every `page.tsx` is classed Must / Can / Desktop-only in `src/lib/mobileClass.ts` (closed set) | `mobileStandard.test.ts` **in the deploy gate** · `npm run mobile-check` (local, browser: overflow, fields < 16 px, targets < 44 px per page × width × language against `mobile-check/baseline.json`) | Students use HalaTuju on phones; the Tamil home page scrolled sideways and iPhone zoomed on every small field, and nothing measured it. Rules and the why: `docs/mobile-standard.md` |

**Post-freeze query budgets — `_admitted` (TD-286, 2026-10-04).** A query budget set after H18 is a
dated record in the `_admitted` array of `halatuju_api/code-standards.json` — `{on, by, why, ledger,
key, value}`, `ledger` = `query_budgets` only — and its `value` IS the live budget
`test_query_budgets.py` reads (that file holds no numbers). ADD a record for a new reading; LOWER a
value when the tightness test says so; NEVER raise one (`code_health.py`'s `std` reading compares
the array with the last close and FAILs a rise). Never put a new budget in the frozen `baseline`.

**The debt register is not the api gate's (TD-256, 2026-10-04).** The api trigger ignores `docs/**`,
so `test_technical_debt_register.py` does not run on a docs edit. `code_health.py`, run at every
close, performs the same duplicate-id check and FAILs on a new collision; the declared collisions
are the `<!-- td-known-collisions: … -->` comment in the register.

**The two budget files.** `halatuju_api/code-standards.json` and `halatuju-web/code-standards.json`.
Each sits inside its own service folder, so it is inside the path filter of the Cloud Build trigger
that runs the tests reading it. Each holds a frozen `baseline` (every number and every ledger as H4
found them) and a live `budget` (starts identical, only ever tightens). Open either file; the
`_how_this_works` note at the top says the same thing in five sentences.

**The ratchet, in three sentences.** A test asserts `actual <= budget`, so the code may not get
worse. It asserts `budget <= baseline` and that no ledger has gained a member, so a limit can never
be raised back to where H4 found it and an exemption list can only shrink. And it asserts
`budget <= actual + slack`, so when you improve something the build goes red until you lower the
budget to match — that is the ratchet catching up with you, not a complaint. (The `baseline` block
is pinned by a SHA-256 held in the test file, so rewriting history takes a second deliberate edit
that a reviewer sees.)

### The two budgets H18 added (2026-09-20) — and HOW TO RUN EACH LOCALLY

Both are ordinary ratchets: a frozen `baseline`, a live `budget` that only tightens, and a failure
message that tells you which number to lower. What is different is **where each one is measured**,
and that is the part to read before trusting either.

**1. First-load JS per route — `halatuju-web/`, and jest does NOT measure it.**

```
cd halatuju-web && npm run bundle-budget        # builds, then checks. One command.
```

The number exists in exactly one place: the route table `next build` prints. jest has no build
output; `code_health.py` does not build either. So the reader is `halatuju-web/scripts/bundle-budget.js`
and it runs **inside the Cloud Build deploy gate** (`halatuju-web/cloudbuild.yaml`, the `test` step,
after `npm run gates`), which is the only place a build already happens. A regression therefore
turns the gate red before the image is pushed.

- It refuses three things: a route at or above the **250 kB ceiling** (300 until TD-360,
  2026-10-21) that is not in the ledger; a ledgered route past its own number; the **median** above
  180 kB (TD-300 took it from 256 to 229, TD-360 to 180).
- **Every run prints a TIGHTNESS NOTE** (TD-300): how far the median sits under its budget, how
  many routes are within 1 kB of it, and how many routes may each cross the budget before the
  median does. **Watch that last count** — at 0 the next byte on a median route turns the gate red
  for a reason unrelated to the change that added it (that was TD-300).
- **A dev-box run is STRICTER than the gate** (Consolidation Review 2026-10-06): it FAILS when any
  budgeted route, or the median, has less than `NEAR_LINE_KB` (0.25 kB) of room under its line,
  because the gate's build reads ~0.06 kB heavier and the next non-admin en.json string moves every
  route. The gate runs `npm run bundle-budget -- --gate` and only prints that finding. Take weight
  off; never raise a line, and never pass `--gate` locally. The margin is a ratchet (0.15 → 0.25 on
  2026-10-21, closing TD-344).
- ⛔ **No value import from `@supabase/supabase-js` in `src/`** — the three clients are AUTH-ONLY
  (`src/lib/supabaseAuthClient.ts`); one `createClient` puts 29 kB back on 73 routes.
  `import type` is fine. Enforced by `src/lib/__tests__/supabaseAuthClient.test.ts`.
- ⚠ **Next's printed first-load for an app route counts the PAGE entry only** — a chunk only a
  LAYOUT loads is downloaded on first paint and is not in the number (`/login` prints 87.6 kB; the
  browser fetches ~231). Moving weight from a page into a layout "passes" without making anything
  lighter. TD-304.
- **Since TD-304 (2026-10-04) the reader budgets EXACT bytes** — each route's page entry from
  `.next/app-build-manifest.json`, gzipped at level 9 as Next does — after checking every exact
  figure against the printed one (a mismatch FAILS: the manifest is another build's). So the 0.5 kB
  rounding trap is gone, and a "LOWER it to" note names a whole kB at or above the exact figure.
  It also PRINTS a **first-paint JS** line (page + every layout above it) that has NO budget: first
  reading median 257.8 kB, worst 324.6 kB (`/profile`). A budget on it is a new standard — owner's
  call, with TD-286 — so do not add one in passing. ⚠ `--from-log` now needs the SAME build's
  `.next/` beside the log.
- ⚠ **87.2 kB is the FLOOR** under every route (React + the Next runtime + the shared chunk). No
  target below that is reachable by any change — subtract it before setting one.
- ⚠ **What it cannot see:** it does not run in `npm test`; it reads what Next PRINTS (gzipped
  first-paint JS — no CSS, no fonts, no lazily-imported chunks, so moving weight behind an
  `import()` lowers the number without shrinking the app); and it is blind between the floor and
  the ceiling, which is what the median covers. The full list is at the top of the script.
- `codeStandards.test.ts` owns the ledger's arithmetic **and asserts `cloudbuild.yaml` still runs
  the reader.** Do not remove that line from the gate; the numbers become decoration the moment
  you do, silently.

**2. Database queries to open one applicant — `halatuju_api/`.**

```
cd halatuju_api && python -m pytest apps/scholarship/tests/test_query_budgets.py -q
```

Two readings through the REAL endpoint, built with the H5 factory: **38** queries with no
documents and **38** with three named documents. The pair separates a fixed cost from a
per-document one — if the three-document budget fails while the bare one holds, the new work is
inside a per-document N+1 and every real applicant pays for it several times over. Zero slack,
because the reading is deterministic.

⚠ **THE TWO NUMBERS BEING EQUAL IS THE POINT.** They were **315** and **385** when H18 recorded
them on 2026-09-20 — roughly twenty queries for every document a family uploaded, so a case with a
dozen was past six hundred. TD-282 (2026-09-21) removed the slope entirely with the **document
snapshot** described in the next section. If these two ever diverge again, the per-document N+1 is
back.

⚠ Its keys are **route patterns**, not file paths (`api/v1/…/<int:pk>/::GET::<fixture>`), so
`query_budgets` is a full member of `_moved` but not of `PATH_KEYED_LEDGERS` — see the next
section, and the reading test asks the equivalent question ("does this pattern still resolve?")
where Django's resolver exists.


**The document snapshot** (TD-282, `apps/scholarship/document_snapshot.py`) is why opening one
applicant costs 38 queries with or without documents. ⚠ **No write path may open or read one**; it is
opened in ONE place (`AdminApplicationDetailView.get`). Widen it only by the four steps in
`docs/domain-rules.md`, and only with the surface added to the ON==OFF matrix first.

### Moving a file that is in a ledger — HOW TO DECLARE A MOVE (TD-272, 2026-09-20)

Every ledger is keyed on a FILE PATH. **So before you plan a cut, grep both `code-standards.json`
files for the file you are about to split** — the question is not "may this file's key move?" but
"does anything INSIDE this file have a key of its own?" A file's size entry, a long function, a
runtime skip, a hand-built fixture, an `eslint-disable` and a mirror claim are all keyed on the
path, and the last two live *inside* the body you are about to lift.

When the answer is yes, **you do not add the new key and you do not touch the frozen `baseline`.**
You declare the move. Add a record to the `_moved` array at the top of that service's
`code-standards.json`:

```json
{
  "on": "2026-09-20",
  "why": "IncomeWizard left ScholarshipDocuments.tsx for its own module; the two reasonless
          exhaustive-deps disables are inside the moved body, so they travelled with it.",
  "ledger": "eslint_disable_without_reason",
  "from": "src/components/ScholarshipDocuments.tsx::react-hooks/exhaustive-deps::1",
  "to":   "src/components/ScholarshipDocuments/IncomeWizard.tsx::react-hooks/exhaustive-deps::1"
}
```

…then edit `budget` to spell the entry at its new key, exactly as you would have edited it anyway.
One record per key: a body carrying two disables is two records. The tests read the frozen
`baseline` THROUGH `_moved`, so every rule above then applies to the relabelled record, unchanged.

**A move may not buy anything, and the test will say so if you try.** It is refused when the `to`
key is one the ledger already holds (a merge would give the survivor the room of both), when the
`from` key is not in the frozen ledger (there is no recorded debt to relabel — fix the code
instead), when `to` names a file that is not in the tree, when the record is incomplete, or when
`why` is a shrug rather than a sentence. And because a relabel swaps one key for one key, **a
ledger's length and total are the same either side** and the moved entry inherits exactly the room
the old one had — not a line more.

**You do NOT re-pin `BASELINE_SHA256` for a move.** `_moved` is a sibling of `baseline`, never a
part of it, so the frozen record stays byte-for-byte what H4 measured. H11 re-pinned by hand and
said in its own retro that a fifth acceptance of a wrong guard is how a guard stops being read;
this is what replaced that. Rewriting the `baseline` block itself is still refused, exactly as
before.

**Prune the record when the debt is paid.** Once the budget line it follows is gone — the file fell
under 600, the disable gained a reason — the record describes nothing and the test asks you to
delete it. The story of the move lives in the CHANGELOG and in `_history`, not in a live lens over
the frozen record.

⚠ **A guard that READS a moved file by path must follow it in the same change.** `theme.test.ts`
walks a directory and so needs nothing; `incomeEvidenceHomes.test.ts` names a file and had to be
re-pointed when `IncomeWizard` moved. A source-read guard left on the old path goes GREEN while
watching a file the rule has left, which is the most dangerous way for a test to pass. **Run BOTH
suites whatever you touched** — a web guard reads api source and vice versa.

**Never raise a budget.** If you must grow a file that is already on the list, **split it first, in
its own commit, with no behaviour change** — then add your work to the smaller module. If you must
add a rule the front end already knows, serve it rather than mirror it. If a suppression is
genuinely unavoidable, write the reason on the line. No failure message here will ever tell you to
raise a number, because there is no case in which that is the right answer.

**Not yet covered** (later sprints, each with its own test): first-load-JS and database-query
budgets arrive with H18. Style and formatting are deliberately out of scope for ever — a formatter
pass rewrites every file and proves nothing about bugs.

### A TREE-WALKING GUARD NEEDS A FLOOR (TD-276, 2026-09-20)

**If a test walks the tree, it must assert that the walk found something — and how much.** This is
not a style note. This arc met the same failure four times and every time it was SILENT: a guard
walks the tree, finds N things, asserts something about each, and then the code moves and the walk
finds ZERO. Every assertion is now vacuous and the guard goes on passing. It never appears in a
failure list, because **a scan that finds less asserts less**. `officerGateDrift.test.ts` read
`views_admin.py` by path and died at import for two sprints (13 tests); `test_verdict_item_i18n.py`
used `glob` where a package needed `rglob`; `AuditLoggerNameTest` was pinned to one package and its
bite came back GREEN; `test_wallet_credit.py` allowlisted by bare filename.

**A guard that can pass while seeing nothing is not a guard.**

Use the shared helper. `halatuju_api/apps/scholarship/tests/source_walk.py` (api) and
`halatuju-web/src/test/sourceGuard.ts` (web); `src/test/apiSource.ts` is the same idea pointed at
the backend's tree and already carries `readApiTree(dir, minFiles)`.

| You are about to… | Use | It fails with |
|---|---|---|
| read one file by path | `read_source(path, why)` · `readWeb` / `readRepo(rel, why)` | the path, and `why` this guard reads it |
| read an api file from a web test | `readApi('apps/…')` — the repo-relative LITERAL | the path; and the api gate sees it (below) |
| walk a directory | `walk_sources(root, '*.py', floor, why)` · `walkFloor(dir, floor, why, {exts})` | the shortfall, the tree, and `why` |
| count what a scan found | `floor_count(found, floor, what, why)` · `floorCount` | the shortfall and `why` |

Four rules for the number itself:

1. **A floor is a MINIMUM, not an equality.** It is the count the walk found the day it was
   written, rounded down for churn. Adding a legitimate file must leave the guard GREEN — a floor
   that cries wolf teaches the next engineer to edit the number without reading it, and a floor
   nobody believes is worse than none. A guard that genuinely needs a CLOSED set asserts that
   equality itself, beside the reason it is closed.
2. **It names its number AND its reason.** "expected 12, got 0" tells a future engineer nothing.
   `why` is a sentence saying what rule this holds and where to look for the code that moved.
3. **Floor the FILES and the THINGS.** A walk can read every file and still find none of what it
   came for, because the marker it greps was renamed. `test_ai_registry.py` floors both, and they
   fail differently on purpose.
4. **Never lower a floor to make red go away, and never convert one to a skip.** A skipped drift
   test is how the 64-subject drift shipped.

⚠ **Allowlist a PATH, never a NAME (TD-277).** A guard that exempts or selects a file by its bare
name (`path.name == 'funding.py'`, `basename(f) === 'source_walk.py'`) silently widens to every
future file of that name anywhere in the tree. Key it on the path relative to the app or the repo.
Swept 2026-10-04: the last two (`test_verdict_item_i18n.py`, `crossTreePaths.test.ts`) now key on
paths; directory-name skips (`migrations`, `__tests__`) are a convention, not an allowlist.

⚠ **Watch for a corpus fed to `parametrize` or `.each`.** An empty list there generates ZERO tests:
the file collects clean, reports nothing, and is green for ever. `test_slip_fixtures.py` was
exactly this.

⚠ **The two trees watch each other.** `test_web_guards_read_live_paths.py` (api side) extracts
every api path the web tree names and fails if one is gone — so a backend refactor goes red in its
OWN gate instead of killing a web suite that nobody will run for two sprints.
`crossTreePaths.test.ts` does the reverse. Both also carry a MANIFEST of the guard files on the
other side, which is the only thing in either tree that notices a whole test FILE leaving the run.
**When you add a guard that reads across the trees, add it to that manifest the same day.**

### THE RULES THE ARC HARVESTED (code health H19, 2026-09-20)

Nineteen sprints put about 150 entries into `docs/lessons.md`. Most are about one incident. These
nine groups are the shapes that came back three, four and five times, reduced to the rule and its
reason. **`lessons.md` keeps the evidence; this keeps the instruction** — read this, and read the
story only when you want to know why. The two classes that earned a section of their own are above:
**moving a file that is in a ledger**, and **a tree-walking guard needs a floor**.

**1. A guard is only as strong as its cheapest passing state.**
- Before writing a source-level guard, ask what the laziest passing state looks like. If the answer
  is *"the right word appears somewhere in the file"*, the guard is decorative — count occurrences,
  or assert the property. `/TableFrame/.test(src)` was satisfied by an import line.
- **A negative assertion goes GREEN when its subject leaves the file it reads.** `not.toMatch` and
  `assertNotIn` reward the code leaving; a positive assertion at least fails loudly. Pair every
  negative with a positive, or point the guard at a walk with a floor.
- A negative assertion over a whole payload needs a sentinel no timestamp, id or amount can
  contain, and a positive line proving the sentinel is in the data at all.
- Match the instrument to the claim. A source-shape test is right for a STRUCTURAL claim (no bare
  `disabled`, no raw hex, no surface forgotten) and is **not evidence** for anything depending on
  focus, event propagation, keyboard, drag, mount/unmount or async — that class needs a mount. A
  rendered test is in turn only evidence of what jsdom actually implements; where it does not,
  assert the structural pair that decides the real behaviour and say in the test why.

**2. Bite it, or you do not know.**
- A guard, a golden master, a drift test and a budget are all hypotheses until an injected fault
  turns them red. **"It still passes after the move" is not a measurement; "it still fails when it
  should" is.**
- **A silent bite is the finding, not a curiosity to note.** Write the test that should have
  spoken, or delete the line that can never matter — in this sprint.
- A silent bite may mean the FIXTURE is too kind rather than the guard unnecessary. Read the
  function from the top and name the branch your fixture returns on; the missing row is the one
  that reaches your code.
- **Verify the injection LANDED.** A zero-match needle is unproven, not passing, and reads exactly
  like "the code has moved". Prove the needle is unique, and derive the newline from the file's own
  bytes — line endings are per FILE here.
- The fault must leave the file parseable. If every test goes red you broke the module, not the
  behaviour; the signal is *the right tests went red and no others*.
- **Restore by writing the original BYTES back in a `finally`, and verify the restore against the
  ORIGINAL digest** — not against "no exception was raised". A harness that edits one file twice
  backs up the intermediate state. **Never `git checkout --`**: it restores to the last commit, not
  to the state you were in. This arc lost real work to it twice.

**3. A number you did not measure is a number you do not have.**
- **Measure every baseline yourself before touching anything, even when the brief states it.**
  H13's brief said 2,913 jest and the tree stood at 2,900 with a whole suite dead at import for two
  sprints. An inherited number is the one most likely to predate the thing that broke it.
- **Do the arithmetic on any target you are asked to accept, on day one.** H14, H16 and H17 each
  inherited an acceptance from a differently-shaped predecessor, and each found on the last day
  that it had never been reachable. Find the FLOOR first — 87.2 kB sits under every route.
- Say what you ran. "3,584 passed" measured in one directory, quoted as a project total, is a trap
  for whoever reads it next.
- **When a reading's DEFINITION changes, say so at the row and do not compare across it** (`xapp`
  steps 133 → 46 on 2026-09-20 because the definition changed, not the code).

**4. When a reading punishes the right behaviour, fix the reading — never the number.**
- `xapp` counted import STATEMENTS, so a faithful split could only inflate it. `guard%` counts
  source-reading tests, which are the cure for unguarded mirrors and not the disease. `hot#1` does
  not follow a rename, so a split reads as a hotspot vanishing rather than shrinking.
- **A number held by hiding the thing it measures is worse than a number that went up honestly.**
  Write the arithmetic out, raise the tool shortcoming as a TD entry, accept the rise in the review.
- A metric's match list is reviewed whenever a sprint invents a new idiom for the thing it counts,
  and a widened definition is dated in the source, so the step reads as the definition catching up.

**5. A standard is the thing that RUNS.**
- A budget needs a READER before it needs a number, and the reader needs a home that already runs.
  **A ledger full of figures nothing reads is worse than an empty column: it reads as enforced.**
- **When a standard is enforced somewhere other than the test suite, a test in the suite asserts
  the wiring.** `codeStandards.test.ts` asserts `cloudbuild.yaml` still runs `npm run
  bundle-budget`; without it, one tidy-up of the gate turns every kilobyte in the ledger into a
  comment, silently.
- Name where it runs and what it cannot see, in the file itself.
- If the number cannot be measured yet, ship the SOURCE rule that causes it and make the measured
  half a named finding with its reader as the first task. H17 refused a number it could not measure
  and that refusal was worth more than the number.

**6. "Nothing uses this" is a claim about your SEARCH.**
- A symbol search answers *who imports this*. Lazy imports are deliberate here, so that is not *who
  calls this*. **Grep for what the thing PRODUCES** — the served field name, the status value, the
  error code — not only for its own name. `interview_agenda_full` was written into a roadmap, a
  brief and this file as dead, and serves every cockpit load.
- Two greps for a patch target, always: `patch('pkg.name')` **and** `patch.object(pkg, 'name')`. On
  a re-export shell the first SUCCEEDS, rebinds something nothing calls, and the real function runs
  — use `tests/package_patch.py`'s `patch_engine`.
- Never conclude an absence from a truncated search (`| head`), from one field of a model, or from
  the repository at all: authored content — clauses, templates, copy — lives in the database.

**7. Measure before you reach for the obvious fix.**
- **A performance fix is not done until the MEASUREMENT moved.** Take the reading, apply the fix,
  take it again; if the two are equal you have not fixed it, whatever the mechanism suggests. A
  `.filter(...)` on a related manager ignores a prefetch cache, so the reflex fix for the cockpit's
  315 queries is a no-op that passes every test (TD-282).
- Budgeting a bad number is a legitimate outcome: it stops the number growing while the real fix is
  scoped, and it makes the fix visible when it lands, because the tightness rule then fails with
  *"LOWER it to N"*.

**8. Characterise before you change, and never edit an expectation.**
- A de-duplication or unification sprint starts with a characterisation table over ALL the copies
  against ONE input list, written against the unchanged tree. Surprises are pinned and reported,
  never folded into the move. H7 found five defects that way; H8 found eleven homes where the
  register said four.
- **A test that starts failing when you convert a fixture is a FINDING, not a fixture to bend
  back.** A test that breaks is a claim about which behaviour was intended: read its purpose before
  touching its assertion, and when you must amend one, write into the test what superseded it.
- **Any sprint on eligibility, money, consent or identity states its STOP condition in the brief
  and names the smaller deliverable that ships if it stops.** H8 stopped, shipped a verified map
  and no production code, and that was the right outcome — the literal goal would have un-submitted
  real students with a green suite.

**9. Prose rots; write it so it cannot.**
- **A docstring describing THE CURRENT SPRINT has a shelf life.** Write status as a dated sequence
  — *"Sprint 2 landed this inert; 3a moved the gates onto it"* — which can never be falsified,
  instead of a present tense that the next sprint silently makes false.
- **Advocacy text expires the day the gap closes**, and the sprint that closes it owns rewriting
  the case that was made for it.
- **A comment asking two files to stay in step is a defect report, not a safeguard.** Extract it,
  serve it, or write the drift test.
- An exemption carries its reason at the SITE somebody would open to remove it, and names the
  condition that releases it. Left silent, a decision is indistinguishable from an oversight and
  the next sweep "finishes the job".
- A promise to a named future sprint belongs in that sprint's ROADMAP section. A code comment is a
  note to whoever next opens that file, which is a different person (TD-271).
