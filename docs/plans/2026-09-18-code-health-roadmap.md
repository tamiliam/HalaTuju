# Code health — the sprint roadmap

**Written 2026-09-18** via `Settings/_workflows/implementation-planning.md`. **Revised the same
day on two owner rulings (below).**

**Status 2026-09-19: Phases 1–3 shipped (H1–H10). The checkpoint has been DECIDED — the freeze is
LIFTED, with a standing rule. See "The development freeze" and the checkpoint section below.
H11 is next on the code-health track, and it now alternates with product work.**

The owner, 2026-09-18: *"occasionally I find bugs being introduced during our coding, as the code
base becomes more and more complicated. I'd like to audit the health of the codebase as we progress
further."* Then, after the first fix was done on its own: *"I need a full implementation plan,
covering all the sprints, and not like this piecemeal version."*

### Owner rulings, 2026-09-18 (do not re-litigate)

1. **Everything else stops.** *"I want to pause all other developments until this is stabilised or
   completed."* → the sprints run **back to back**, not alternating with product work. The freeze
   is defined in the next section.
2. **It has to stay fixed.** *"Once this is built, future builds would ensure the standards are
   maintained to prevent bugs or inefficiencies creeping in."* → the standards become **tests that
   run in the deploy gate** (H4), efficiency gets **budgets** (H18), and the arc ends by writing
   the standards into the workflows every future sprint follows (H19). A standard that lives only
   in a document is a habit, and this project's own record says habits are what fail.

## The development freeze — ✅ LIFTED 2026-09-19

**The owner lifted it at the "stabilised" checkpoint, taking the third option the roadmap offered.
Product work may resume today.** The ruling, in three parts:

1. **The freeze is over.** Features, pages, models and polish are allowed again. Overview phase 2
   Sprint B comes off the parked list; queued BrightPath builds are open again.
2. **Phases 4–6 (H11–H19) stay on the roadmap** and **alternate** with product work rather than
   running back to back. **H11 is next** on the code-health track.
3. **THE STANDING RULE — a feature sprint does not grow a file that is waiting to be split.** If a
   sprint must touch a file on the hotspot/oversize list, it **first runs that file's Phase-4
   split sprint (moves only)**, and builds the feature on the split file afterwards. It does not
   add lines to the big file and leave the split for later. The lookup table is in
   **"Which Phase-4 sprint owns which file"** below, and `sprint-start.md` should be read against it.

**The ratchet standards stay in force, unchanged.** `code-standards.json` on both sides is still a
one-way ratchet: a budget may be tightened and never loosened, an exemption list may only shrink,
and the ten gate tests keep running on every deploy. Lifting the freeze changed *what may be built*,
not *what the gate allows*.

**Also back in use:** `AGENT-TERRITORY.log`, the moment there is more than one agent in the
checkout — the freeze was what made "one agent, one checkout" safe, and it no longer holds.

### The freeze as it stood, 2026-09-18 to 2026-09-19 (kept for the record)

**It was in force from 2026-09-18 — the ruling was the owner's own words — until the owner lifted it.** It was posted at the top of `halatuju_api/CLAUDE.md` "Next Sprint", where every agent reads first.

| Allowed during the freeze | Not allowed |
|---|---|
| A **production defect with a user on the other side** — hotfix lane, smallest fix, regression test | New features, pages, models, screens |
| **Operations with no code**: payment runs, spending imports, invoices (September bills by 15 Oct), student and sponsor support, data repairs through existing doors | Copy or design polish |
| **BrightPath requests:** triage and analysis continue; a request that is a live defect is fixed; **every other build is scheduled for after the freeze**, and the requester is told so | Building a non-defect request |
| Security fixes | Refactors outside this roadmap |

**What the freeze parks — checked, nothing is half-built:** every feature branch is merged into
`main` (0 commits ahead); Overview phase 2 **Sprint A is live and closed, Sprint B (widget order) has
not started** and waits. TD-253 (findings must be complete) and TD-254 (IC-claim second factor,
HIGH, security) were deferred by the owner earlier the same day. ⚠ **TD-254 is a security item:
the owner may pull it forward at any point and the freeze does not argue.**

**Two ways out were offered, both the owner's call — the first was taken on 2026-09-19:**
- **Stabilised** — the checkpoint after **Phase 3** (H10). By then a red suite cannot ship, the
  standards are enforced in the gate, tests can fail, and every rule has one home: the things that
  *prevent* bugs are done. What remains (Phases 4–5) makes the code easier to work in. The owner
  may lift the freeze here and finish the rest alternating with product work.
- **Completed** — after H19, which lifts the freeze as its last act.

Each sprint's retro states which the project is closer to, with the reading to show it.

**The measurement lives in `docs/code-health.md`** (tool: `Settings/_tools/code_health.py`,
workflow: `Settings/_workflows/code-health-audit.md`). This document is only the decomposition.
Every sprint below ends by taking a reading, so the plan is judged by numbers, not by opinion.

---

## The shape of the work

**In one sentence:** stop bugs reaching production, make tests able to fail, give every rule one
home, and only then cut the giant files into pieces — in that order, because each step makes the
next one safe. Then lock the standards in, so the work never has to be done twice.

**Nineteen sprints in six phases, about 125 hours, run back to back.** The division is driven by four facts, all
measured on 2026-09-18:

1. **Nothing runs the tests before a deploy.** Both Cloud Build triggers are inline configs of
   three steps: `docker build`, `docker push`, `gcloud run services update`. The api image build
   runs `collectstatic`; the web image build runs `next build`. A red suite ships. → Phase 1.
2. **Tests are built by hand, and the biggest screen has no rendered test at all.** 303
   `ScholarshipApplication.objects.create(...)` call sites and no factory — which is how request
   #24's fixture came to describe a state the product cannot produce. `view.tsx` (3,587 lines) is
   covered only by two text-matching guards. **Splitting it first would delete the only evidence
   we have.** → Phase 2 comes before Phase 4.
3. **One rule, several homes — and that is where the fixes keep landing.** ~34 rules in
   `halatuju-web/src/lib` carry a "mirrors the backend" comment; two have a drift test. The income
   rule has four homes (TD-235). `_money` is eight functions with one name. → Phase 3.
4. **The giant files are cleaner inside than they look.** `views_admin.py` (8,547 lines) has
   **zero** helpers shared across its 25 domains, and `urls.py` imports it as one flat list of 142
   names. `admin-api.ts` has **zero** deep imports. So both can become packages that re-export
   the same names, and no importer changes. → Phase 4 is mechanical moves, not redesign.

**Every sprint ships tested, is bite-checked, and ends with a code-health reading.** A sprint that
makes a reading worse than its own start has not finished.

### What "done" looks like for the whole arc

| Reading | 2026-09-18 | Target | Moved by |
|---|---|---|---|
| Tests run before deploy | no | **yes, both services** | H2 |
| `fix%` (fixes ÷ fixes+features, 90 days) | 41 | **under 30**, read 90 days after H17 | all |
| `hot#1` (fixes × KLOC of the worst file) | 290 | **under 100** | H11, H12 |
| `big` (files over 1,000 lines) | 25 | **12 or fewer** | H11–H16 |
| `dup` (one function name, 3+ homes in an app) | 10 | **0 true duplicates** (renames count) | H7 |
| Front-end rules mirrored with no drift guard | **58** *(measured at H4; the survey's ~32 missed file-header docblocks)* | **0** | H9, H10 |
| `unused` npm packages | 4 | **0** | H1 |
| `tsc` | 0 *(was 24; done 2026-09-18)* | **stays 0** | ratchet |
| `guard%` (web tests that read source text) | 17 | **12 or under** | H6 |
| Rendered tests that mount the cockpit | 0 | **1 harness, 6+ tests** | H6 |
| Standards enforced by a test in the deploy gate | 0 | **all of H4's list** | H4, H19 |
| Database queries to open one applicant (officer view) | unmeasured | **measured, budgeted, cannot grow** | H18 |
| First-load JS per route | unbudgeted | **budgeted, cannot grow** | H17, H18 |

`long` (16 long functions) and `xapp` get no target: they fall as a side-effect or not at all, and
chasing them is how a health arc turns into a rewrite.

---

## Phase 1 — Gates: a broken build cannot ship

### H1 — One-word gates and reproducible installs ✅ SHIPPED 2026-09-18
*Retro: `docs/retrospective-2026-09-18-code-health-h1.md`. `unused` 4→0, `skip` 2→0. One deviation: `openpyxl` joined `requirements-dev.txt` (test-only by design). `pytest -n auto` runs in 2 min 59 s — H2's budget figure.*
- **Goal:** anyone (or any agent, or Cloud Build) runs every check with one command, and two builds
  of the same commit install the same code.
- **Scope:**
  - `halatuju-web/package.json`: add `test`, `typecheck` (`tsc --noEmit --incremental false`),
    `i18n`, and `gates` (all four in order). Remove `next-intl`, `react-hook-form`,
    `tailwind-merge`, `@supabase/ssr` — nothing imports them.
  - `halatuju_api/requirements-dev.txt` (new): `pytest`, `pytest-django`, `pytest-xdist`. Today
    **a fresh clone cannot run the suite** — pytest is in no requirements file.
  - `halatuju_api/requirements.lock` (new): exact pins. ⚠ **Freeze what production runs today**
    (`pip freeze` inside the serving image), never "latest" — pinning must change nothing.
    `requirements.txt` keeps its ranges as the intent; the Dockerfile installs the lock.
  - `halatuju_api/.dockerignore` (new): `apps/*/tests/`, `apps/scholarship/eval/`, `docs/`. The api
    image is single-stage `COPY . .`, so ~15 MB of tests ship in production today. ⚠ The triggers
    run `docker build`, so **`.dockerignore` is the file that counts, not `.gcloudignore`.**
  - `pytest.ini`: `--strict-markers`. The STPM golden master's `if GOLDEN_BASELINE is None: skip`
    branch is dead code — delete it. The email golden's regenerate mode ends in `pytest.skip`
    (green); make it end in a loud non-green message so a regeneration can never pass as a run.
  - `halatuju_api/CLAUDE.md` gate list → the one-word commands.
- **Acceptance:** `npm run gates` green; fresh venv + `pip install -r requirements.lock -r
  requirements-dev.txt` + `pytest` green; api image smaller and `manage.py check` passes inside it;
  reading: `unused` 0, `skip` 0.
- **Complexity:** low–medium. **~5h.** Deploys both services (no behaviour change).

### H2 — Tests run before every deploy ✅ SHIPPED 2026-09-18
*Retro: `docs/retrospective-2026-09-18-code-health-h2.md`. Both triggers read committed files; 6,714 pytest + 2,354 jest ran before the first gated deploys. Measured: api 8 min 18 s, web 11 min 44 s, ~1,850 of 2,500 free minutes a month. Raised TD-255 (Node 18) and TD-256.*
- **Goal:** a red suite fails the build, and the deploy steps never run.
- **Scope:**
  - Commit `halatuju_api/cloudbuild.yaml` and `halatuju-web/cloudbuild.yaml` that reproduce the
    live inline steps **exactly** (including the `release-decisions` job image sync on the api
    side) and put a test step first. api: `manage.py check`, `makemigrations --check`,
    `pytest -n auto` on SQLite (the suite already needs no external database). web:
    `npm run gates` with `--maxWorkers=1` (default Cloud Build workers are small).
  - Switch each trigger from inline config to its file. Commit the `includedFiles` /
    `ignoredFiles` as a comment block — today they exist only in the console
    (api: `halatuju_api/**` minus `docs/**`, `halatuju_api/CLAUDE.md`; web: `halatuju-web/**`
    minus `docs/**`).
  - An escape hatch, because a flaky test must never block a hotfix: substitution
    `_SKIP_TESTS=1` on a manual run, which prints a loud line to the build log.
- **⚠ Budget — measured, not guessed.** The last 30 days: **181 builds, 1,016 build-minutes**
  (web 101 × 6.9 min, api 80 × 3.9 min). The free tier is 2,500 minutes a month. pytest takes
  ~5 min on the dev box; **first task is a spike that times it on Cloud Build.** If the projection
  passes ~2,000 minutes, fall back to running the api tests only when `apps/**/*.py` changed.
- **Owner-gated:** the trigger switch is a change to production infrastructure. Rollback = point
  the trigger back at its inline config (kept as a YAML export in the sprint's retro).
- **Acceptance:** a deliberately failing test on a throwaway branch trigger fails the build before
  `docker build`; a normal push deploys as before; build-minutes projection written down.
- **Complexity:** medium. **~6h.**

### H3 — The guards the splits will lean on ✅ SHIPPED 2026-09-18
*Retro: `docs/retrospective-2026-09-18-code-health-h3.md`. TD-219, TD-240, TD-250 closed; the fence is package-aware for H11. Raised **TD-257** (22 endpoints no test drives — a Phase-2 backfill, after the H5 factory) and **TD-258** (HIGH: the sponsor fund view is outside the fence and a mock donation endpoint is live — reported, not patched — then **fixed the same day on the owner's word** and shipped with H3).*
- **Goal:** close three holes in the mechanical guards *before* code starts moving between files.
- **Scope:**
  - **TD-219 (high):** nothing tests the seam between a view and the service it calls — two
    defects in one day, one of them 500-ing for 18 days. A guard that diffs view call-sites
    against the URLs the endpoint tests hit, in the shape of `test_org_fence.py`.
  - **TD-240:** the org-fence guard has never scanned `views_sponsor.py`.
  - **TD-250:** the route-drift test reads only the top level of `src/app/admin/`.
  - Teach `test_org_fence.py` to scan a **package** (`views_admin/*.py`), not just a filename — H11
    breaks it otherwise, and a fence guard that cannot see the queries is the worst kind of green.
- **Acceptance:** each guard bite-checked (remove a fence pragma / an endpoint test / a nested
  route → red). TD-219, TD-240, TD-250 carry their markers.
- **Complexity:** medium. **~6h.** api deploy only if a real gap is found; else tests only.

### H4 — The standards become tests, inside the gate ✅ SHIPPED 2026-09-19 — **PHASE 1 COMPLETE**
*Retro: `docs/retrospective-2026-09-19-code-health-h4.md`. 70 tests, two budget files (one per service, inside its trigger's path filter), a ratchet that needs no git, and a `std` reading in `code_health.py` that holds the one loophole git is needed for. Deviation from the text below: TWO files, not one, so an edit to a budget always triggers the build that checks it.*
- **Goal:** the owner's second ruling, made mechanical. After this sprint a change that breaks a
  standard **cannot deploy**, whoever or whatever wrote it. Built early, on purpose: the rest of
  this arc is then held to the same standards it is installing.
- **How:** one committed budget file, `code-standards.json`, and two test files that read it —
  `halatuju_api/apps/scholarship/tests/test_code_standards.py` and
  `halatuju-web/src/lib/__tests__/codeStandards.test.ts`. They run in the normal suites, so from
  H2 onward they run before every deploy. **The budget is a RATCHET: a number in it may only go
  down.** A test asserts the file itself never loosens against `main`.
- **The standards (each one maps to a way bugs have got in here):**

  | Standard | Rule the test enforces |
  |---|---|
  | No new giant file | A **new** source file may not pass 600 lines. A file already over is listed with its size and **may not grow**; when a split shrinks it, the entry is lowered or removed |
  | No new giant function | No new Python function of 150+ lines; the 16 known ones are listed and may not grow |
  | One rule, one home | No function name defined in 3+ files of one app, beyond the listed exceptions (which H7 empties) |
  | No unguarded mirror | A `src/lib` comment saying *mirrors / keep in sync* must name the drift test that guards it, or the test fails (H9–H10 empty the list) |
  | No blind spots | No `@ts-ignore`; no `any`; every `eslint-disable` carries a written reason; the count may not rise |
  | Tests can fail | Zero skipped / xfail / todo tests |
  | No dead weight | Every npm dependency is imported somewhere |
  | The app boundary | `courses → scholarship` imports may not rise, and may not be module-level |
  | New tests use the factory | From H5: a **new** test file may not hand-build a `ScholarshipApplication` |

- **Kept out on purpose:** style and formatting. A formatter pass rewrites every file and proves
  nothing about bugs.
- **`code_health.py` stays what it is** — the trend and the conversation. The tests are the
  enforcement. One measures, the other refuses; neither does both.
- **Acceptance:** every standard bite-checked **both ways** — a breach goes red, and a legitimate
  change stays green (a guard that cries wolf gets deleted within a month, and one did today).
  The ratchet test refuses a loosened budget.
- **Complexity:** medium. **~8h.** No behaviour change; both suites grow.

---

## Phase 2 — Tests that can fail

### H5 — A backend test factory that builds states the product can reach ✅ SHIPPED 2026-09-19
*Retro: `docs/retrospective-2026-09-19-code-health-h5.md`. 20 files converted, 121 hand-built applications gone, suite 174 s → 123 s, every stage verified against the real code path, and a new gate standard (ledger 154 files → 134, shrink-only). Found one more impossible fixture — the #24 class. The stage list below was the lead's guess; the built one is in `CLAUDE.md` → Test fixtures.*
- **Goal:** tests stop hand-building applications, so a fixture cannot describe an impossible case.
- **Scope:** `apps/scholarship/tests/factories.py`: `make_admin(role)`, `make_cohort()`,
  `make_student()`, `auth_token(uid)` (duplicated per file today), and
  **`make_application(stage=…, outcome=…)`** which walks a record to a named stage the way the
  product does — `stage='awaiting_qc', outcome='decline'` yields `status='interviewed'` with
  **no** `verified_at`, because that is what the decline road leaves. One table of stages, each
  asserted against the real service calls so the factory itself cannot drift.
  Convert the **20 most-fixed test files** (from the hotspot list). The other ~200 move when next
  touched — a rule added to `small-change-lane.md`, not a big-bang rewrite.
- **Acceptance:** factory stage table has its own tests; 20 files converted with identical
  assertions; pytest count unchanged or higher; a bite-check proves a converted test still fails
  when its code is disabled.
- **Complexity:** medium. **~7h.** No deploy (tests only; H1's `.dockerignore` keeps them out).

### H6 — A render harness for the cockpit, and the stopgap guards retired ✅ SHIPPED 2026-09-19 — **PHASE 2 COMPLETE**
*Retro: `docs/retrospective-2026-09-19-code-health-h6.md`. 59 rendered cockpit tests, 16 bite-checks none silent, `guard%` 18 → 10, i18n guard 11 → 35 namespaces, suite 42 s → 21 s. **H14 is unblocked.** Raised **TD-259** (raw i18n keys on the IC-claim screen — to be fixed WITH TD-254, the owner's call).*
- **Goal:** the 3,587-line reviewer screen is mounted by a real test before anybody moves it.
- **Scope:**
  - `src/test/adminApplicationDetail.ts`: a typed `AdminApplicationDetail` fixture builder (the
    "deferred fixture work" `approveLockoutGuard.test.ts` names as its reason to exist).
  - `view.test.tsx` (jsdom, React Testing Library): mounts `view.tsx` and asserts at least — the
    Recommend lock when stuck, the decline banner and Save label (request #24), the closed-case
    cards, the QC panel per role, the org-admin reject wizard, the reporting-date box.
  - Convert the four stopgap source guards to rendered tests: `approveLockoutGuard`,
    `docFileLayout`, the per-surface half of `screenshotInput`, `ActionCentre.vircle`.
  - Collapse the ten near-identical `messages/__tests__/*-i18n.test.ts` into **one** suite driven
    by a namespace list — and extend it to all 35 namespaces (11 are covered today).
  - **Kept on purpose:** brand, sandbox-safety, IC-padlock, ICU, navigation disk-walk,
    soft-evidence drift. They are text by nature. `pageWidth` and most of `theme` are convention
    checks that belong in ESLint — noted, not done here.
- **Acceptance:** the harness mounts with zero console errors; each converted guard bite-checked
  both ways (the old text guard was decorative once and cried wolf once — today); reading:
  `guard%` ≤ 12.
- **Complexity:** medium–high. **~9h.** No deploy.

---

## Phase 3 — One rule, one home

### H7 — Money and text helpers ⚠ touches money ✅ SHIPPED 2026-09-19
*Retro: `docs/retrospective-2026-09-19-code-health-h7.md`. No behaviour change, proven by 417 characterisation assertions written first. `dup` 10 → 4 (the four are declared exceptions). `money.py`, `text.py`, `gemini.py`. Raised **TD-261**: five defects in money helpers, pinned, not fixed — the owner's call.*
- **Goal:** no two functions share a name and differ in behaviour.
- **What the survey found — this is not the merge it looked like:** `_money` is **eight functions
  doing three jobs** (extract a figure from OCR text; parse to `Decimal`; format for display). No
  two are byte-identical. `_norm` ×4 are four different contracts (case, digits, accents) — merging
  them would silently change name-matching in an eligibility path.
- **Scope:**
  - **Characterisation tests first:** pin all eight `_money`, four `_norm`, three `_digits`
    behaviours exactly as they are today, including `None` and the error code each raises.
  - `apps/scholarship/money.py`: `parse_money(value, *, allow_zero, exc, code)` and
    `format_money(value, *, blank_for_null)`. Every caller keeps its **current** behaviour through
    the parameters. `doc_parse._money` → `_first_rm_figure` (a rename; it shares only the name).
  - `_norm` ×4: **renamed to say what each does; not merged.** `_digits` ×3: merged to the
    defensive (`str()`-coercing) version.
  - `_gemini_generate` ×3: one shared core; each module keeps a three-line wrapper of the same
    name, so every existing `patch(...)` and the metering seam (tenancy rule 6) stay where they are.
  - **Left alone, on purpose:** `render` / `banned_phrases` / `unknown_placeholders` are one engine
    with two thin adapters — already correctly factored. ⚠ One asymmetry to investigate, not
    assume: `partner_comms.render` defaults every structural token to empty;
    `sponsor_comms.render` does not. Possible latent `{token}` leak in a sponsor email.
- **Acceptance:** characterisation tests green before and after, unchanged; email golden
  byte-identical; reading: `dup` has no true duplicates.
- **Complexity:** medium. **~7h.** api deploy.

### H8 — The income rule gets one served answer (TD-235) ⚠ touches eligibility — ⛔ PHASE A DELIVERED 2026-09-19, PHASE B STOPPED AT ITS GATE
*Retro: `docs/retrospective-2026-09-19-code-health-h8.md`. The rule has **eleven** homes, not four, and they disagree in sixteen places today (**TD-262**). No production code changed. **The goal as written below is NOT achievable:** "the frozen gate reads the single answer" would un-submit real students — the frozen arm is more permissive on purpose and may only ever widen. What remains is owner-ruled and ordered in TD-262: (1) student screens tell the truth, (2) officer screens follow the gate's rule — needs a production count first, (3) one served answer plus a NAMED frozen arm, then the web reads it, (4) a ruling on whose STR may open the gate. **H9–H10 inherit the rule: characterise first; a mirror is deleted only where the two sides already agree.***
- **Goal:** "is this household's income evidenced?" is answered in one place and *served*.
- **Scope:** `income_engine.any_member_income_evidenced` becomes the single answer; the frozen
  gate, the cockpit display and the de-dup sweep read it. `src/lib/incomeWizard.ts` — a declared
  "pure mirror of the backend income requirement engine" — reads the served requirement list.
  Follow lesson 290: *"the best fix for a keep-in-sync pair is to DELETE one side."*
- **Backward repair (small-change-lane rule):** state how many stored applications change verdict
  under the single answer **before** shipping. Expected zero; measured, not assumed.
- **Acceptance:** one home, proven by a guard that fails if a second one appears; SPM 5319 and
  STPM 2026 golden masters unchanged; stored-row count reported.
- **Complexity:** medium–high. **~9h.** Both services deploy.

### H9 — De-mirror the front end, wave 1: the decision gates ✅ SHIPPED 2026-09-19
*Retro: `docs/retrospective-2026-09-19-code-health-h9.md`. **No production code changed.** All six
named rules characterised side by side first and converted: six drift tests, 153 assertions, 17
bites (both directions + two no-cry-wolf), every one behaved. Ledger `unguarded_mirrors` **58 → 41**.
Reading `mirror` added to `code_health.py`, agreeing exactly with the in-repo ledger (41). Raised
**TD-264** (money path: the api and the web disagree on what a digit is, on the payout account) and
**TD-263** (low: `requote` offered on a bug). **Nothing was served** — see the decision below.*

- **Goal:** the rules that decide what an officer may do stop living in two languages.
- **What shipped, against the named scope:** `ORG_REJECT_FROM` ✓, the 13 application statuses ✓,
  `OrgRequest` statuses + `TRANSITIONS` ✓, `STR_COACH_STATES` ✓, `PartnerAdmin.ROLE_CHOICES` ✓, the
  assignment `bad_assignee` rule ✓ — plus the payout-account floor, taken because it is a money gate
  in the same shape. Each guarded by a test that reads the backend's **own source**, in both
  directions, plus a shared reader (`halatuju-web/src/test/apiSource.ts`).
- **⚠ THE DECISION: DRIFT-TESTED, NOT SERVED — and this is the right answer for these six.** The
  roadmap reserved *serving* for the decision gates. Every one of them turned out to be a Python
  module-level CONSTANT with no per-org, per-request variation. Serving such a value needs a new
  endpoint (org-fence + endpoint-exercise ledgers, a deploy of both services, during a freeze) and
  buys nothing: a served value can only fail at RUNTIME, in front of a user, whereas a drift test
  fails in the deploy gate before the change ships. Serve a rule that VARIES; guard a rule that is
  a constant. `documentLimits.ts` / `interviewSlots.ts` remain the template for the first kind.
- **⚠ THE SIZE LESSON, for H10 to plan against.** "Six rules" and "29 ledger entries" are different
  units. The ledger counts comment BLOCKS; the six named rules were **17** of them. This is H4's
  count error in a new place — a number carried into a plan without re-deriving it from what it
  counts.

### H10 — De-mirror, wave 2: the rest ✅ SHIPPED 2026-09-19 — **PHASE 3 COMPLETE**
*Retro: `docs/retrospective-2026-09-19-code-health-h10.md`. **No production code changed.** All 41
remaining ledger entries resolved: 22 gained a drift test, 16 were comments that did not describe a
copied rule and were reworded to say what the code actually does, and **3 stay on the ledger by
decision** (the income rule — see below). Reading `mirror` **41 → 3**. Nine drift tests, 36 bites,
36 behaved. Raised **TD-266** (the admin/student `ResolutionItem` pair has drifted; one serializer
feeds both) and **TD-265** (a finance column nothing renders).*

- **What the 41 turned out to be**, and this is the finding worth carrying forward: **fewer than
  half were mirrors.** 22 were genuine copied rules. 16 were comments using the word *mirror* for
  something else entirely — a retired engine, an external data source, a design consistency note,
  a disclaimer ("this mirrors only what the SCREEN decides"), and one that QUOTED a comment
  deleted years earlier. Those were reworded to describe the code honestly, which is not ledger
  gaming: each one now says what it is, and several say plainly why there is nothing to guard.
- **⛔ THE THREE THAT REMAIN ARE A DECISION, NOT A BACKLOG.** `incomeWizard.ts` × 3 are the income
  rule. TD-262 pins **eleven** homes of it disagreeing in sixteen places, several awaiting an owner
  ruling on eligibility. A drift test written today would either fail on a disagreement nobody has
  ruled on, or pass and thereby BLESS one. The reason is written at the top of `incomeWizard.ts`
  and in `code-standards.json` beside the entries. **They leave the ledger when TD-262 is settled,
  and whoever settles it writes the guard as part of that work.**
- **Acceptance:** met — `mirror` = 3, each remainder a named exception with its reason recorded in
  two places. Every converted rule bite-checked from both sides.
- **Complexity:** medium. **~8h.** Web only; no api file was edited.

---

## ✅ CHECKPOINT — "stabilised" (after H10). **DECIDED 2026-09-19: LIFT, with a standing rule.**

*Written 2026-09-19, at the end of Phase 3. Plain language, because this is the page the owner
read to make one decision.*

> **THE DECISION — 2026-09-19.** The owner chose to **lift the freeze now**, taking the third
> option set out under "The honest trade" below.
>
> - **Product work resumes today.** Overview phase 2 Sprint B is unparked; queued BrightPath
>   builds are open again.
> - **H11–H19 stay on the roadmap and alternate with product work.** H11 is next on the
>   code-health track.
> - **The standing rule:** a feature sprint that must touch a file on the hotspot/oversize list
>   **runs that file's Phase-4 split sprint first — moves only — instead of growing the file.**
>   Which sprint owns which file is in the table under Phase 4.
> - **The ratchet standards in the gate are unchanged.** A budget still only goes down.

*Everything below this line is the briefing the decision was made on, kept as written.*

### What was promised at this point

> *"By then a red suite cannot ship, the standards are enforced in the gate, tests can fail, and
> every rule has one home: the things that **prevent** bugs are done."*

All four are true. Taken one at a time:

**1. A red suite cannot ship.** Before H2, the two Cloud Build triggers deployed whatever was
pushed; no test ran between a commit and production. Now both run a committed `cloudbuild.yaml`
that executes the full suite first, and a failing test stops the deploy. That is the single
biggest change in the arc, and it is the one that makes everything after it safe.

**2. The standards are enforced in the gate.** Ten rules — no giant new file, no giant new
function, one rule one home, no skipped tests, no new blind spots, every suppression carries a
reason, no unguarded mirror, no dead dependency, the app boundary, new tests use the factory — are
now *tests*, inside that gate. They are ratchets: a limit can be tightened and never loosened, and
an exemption list can only shrink. Nobody has to remember them.

**3. Tests can fail.** Both golden masters used to skip themselves on the run straight after a
regenerate — the least supervised moment in the process passed green. That is gone. So is the
hand-built fixture problem: `factories.py` builds only states the product can actually reach, and
the cockpit — 3,600 lines, the most consequential screen we have — went from **no rendered test at
all** to 59 of them.

**4. Every rule has one home.** `_money` was eight functions with one name; it is now one module
with named wrappers. 55 of the 58 front-end rules that were copied from the backend now have a
test that reads the backend's own source and fails if either side moves.

### The readings, then and now

| Reading | 2026-09-18 | now | |
|---|---|---|---|
| Tests run before deploy | no | **yes, both services** | done |
| Front-end rules mirrored with no guard | 58 | **3** | done bar the income rule |
| `dup` — one function name, 3+ homes | 10 | **4** (all declared exceptions) | done |
| `unused` npm packages | 4 | **0** | done |
| `tsc` errors | 24 | **0** | done |
| Skipped tests | 2 | **0** | done |
| Rendered tests that mount the cockpit | 0 | **59** | done |
| Standards enforced in the gate | 0 | **10** | done |
| pytest / jest | 6,714 / 2,354 | **7,000 / 2,895** | +931 |
| `big` — files over 1,000 lines | 25 | **25** | Phase 4 |
| `hot#1` — the worst file's bug score | 290 | **274** | Phase 4 |
| `fix%` — fixes ÷ all commits, 90 days | 41 | **42** | lags; re-read after Phase 4 |
| First-load JS / query budgets | none | **none** | Phase 5 |

**Findings the arc produced along the way, none of them created by it:** TD-258 (a sponsor view
outside the org fence and a mock donation endpoint live in production — *fixed the same day*),
TD-259, TD-261 (five defects in money code — *fixed*), TD-262 (the income rule has eleven homes
and they disagree in sixteen places — **HIGH, eligibility, awaiting the owner**), TD-263, TD-264
(a payout account the api accepts and no bank could pay — **money path, awaiting the owner**),
TD-265, TD-266. Two of these are on the owner's desk and neither depends on the freeze.

### What H11–H19 would buy, in plain terms

- **Phase 4 (H11–H16) — make the big files small.** `views_admin.py` is 8,556 lines and was fixed
  34 times in 90 days; `admin-api.ts` is 4,118. Nobody holds a file that size in one head, so
  nobody reviews one properly, and that is where the next bug will be. This phase is *moves only* —
  no renames, no rewording — and it is what the `hot#1` and `big` numbers above are waiting for.
  **The benefit is speed and safety of every future change**, not a fix to anything broken today.
- **Phase 5 (H17–H18) — what the visitor downloads, and what each page costs.** One locale per
  visitor instead of three, then first-load-JS and database-query budgets that cannot grow. **The
  benefit is a faster site for students on a phone**, and a limit that stops it slowly getting
  worse again.
- **Phase 6 (H19) — lock it in.** The standards become part of how every sprint is run, and the
  freeze lifts as its last act.

### The honest trade

**Lifting the freeze now** means product work resumes and Phases 4–6 alternate with it. Everything
that *prevents* bugs is already in place, so the risk of resuming is much lower than it was on
2026-09-18. The cost is that the big files stay big, and each feature sprint that touches one
either grows it (the ratchet allows 20 lines) or pulls its Phase-4 sprint forward.

**Running on** means roughly six more sprints before product work resumes. The gain is a codebase
where the next feature is cheaper to build and safer to review, and a measurable one — `hot#1`
under 100, `big` at 12 or fewer.

**There is a third option the roadmap already allows:** lift the freeze, and make the rule that any
feature sprint touching a file on the hotspot list pulls that file's Phase-4 sprint forward instead
of adding to it. That trades a slower first few feature sprints for no pause at all.

**Not a factor either way:** TD-262 and TD-264 both need an owner ruling and neither is blocked by
the freeze. They can be answered today, whichever way this goes.
*(TD-264 was answered on 2026-09-19 — the api was narrowed to ASCII digits, and it is resolved.
TD-262's F2 + W1 is still open.)*

---

## Phase 4 — Make the big files small

**The rule for every sprint in this phase: moves only.** No renames, no "while I'm here", no
wording changes. Lesson 173: *"the temptation is to improve the wording in the same move — which
would make the diff unreviewable."* The proof of a move is a full green suite plus a diff that
`git diff -M --stat` reads as renames and re-exports.

**The freeze meant one agent in the checkout. It was lifted on 2026-09-19**, so each remaining
Phase-4 sprint now opens with a line in `AGENT-TERRITORY.log` naming the files it holds and for
how long, and lands in **one** day.

### Which Phase-4 sprint owns which file

**Read this at sprint start.** The standing rule of 2026-09-19: if the sprint you are about to
start must change a file in this table, **run its sprint first (moves only), then build on the
split file.** Do not add lines to the big file and leave the split for later. Sizes are the
2026-09-19 reading; the live list is `big` in `docs/code-health.md`.

| File | Lines | Split sprint |
|---|---|---|
| ~~`halatuju_api/apps/scholarship/views_admin/__init__.py`~~ | ~~8,556~~ ~~5,093~~ **154** | ~~H11~~ ~~H12~~ ✅ **DONE 2026-09-20.** The package is thirty modules, none over 600, and the root left the `big` list. Nothing here is waiting on a split any more |
| ~~`halatuju_api/apps/scholarship/models.py`~~ | ~~4,756~~ **81** | ~~H15~~ ✅ **DONE 2026-09-20.** A re-export shell; 15 modules in `models/`, the largest `applications.py` at 899 (one class of 847 lines — see the retro). `makemigrations --check` clean. The file has LEFT `big` |
| ~~`halatuju_api/apps/scholarship/emails.py`~~ | ~~4,242~~ **134** | ~~H16~~ ✅ **DONE 2026-09-20.** A re-export shell; 21 modules in `emails/`, largest `interview_mail.py` at 464, none over 600. The email golden master is BYTE-UNCHANGED. The file has LEFT `big` |
| ~~`halatuju-web/src/lib/admin-api.ts`~~ | ~~4,118~~ **241** | ~~H13~~ ✅ **DONE 2026-09-20.** A barrel; 28 modules in `src/lib/admin-api/`, none over 450. Nothing here is waiting on a split any more |
| ~~`halatuju-web/src/app/admin/scholarship/[id]/view.tsx`~~ | ~~3,599~~ **1,338** | ~~H14~~ ✅ **DONE 2026-09-20.** Thirteen panels + the shared furniture are 14 modules in `[id]/view/`, none over 350. ⚠ It is STILL over 1,000 and always will be until the Decision panel is untangled — that is design work, not a move |
| ~~`halatuju_api/apps/scholarship/income_engine.py`~~ | ~~3,201~~ **132** | ~~H16~~ ✅ **DONE 2026-09-20.** A re-export shell; 19 modules in `income_engine/`, largest `identity_checks.py` at 377. ⛔ ELIGIBILITY: no verdict moved, no `VERDICT_ENGINE_VERSION` bump. `incomeWizard.ts`, its deliberate mirror, was NOT touched. The file has LEFT `big` |
| ~~`halatuju_api/apps/scholarship/services.py`~~ | ~~2,946~~ **109** | ~~H15~~ ✅ **DONE 2026-09-20.** A re-export shell; 18 modules in `services/`, none over 430. ⛔ `application_completeness` is in `completeness.py`, moved byte-identically and NOT touched. The file has LEFT `big` |
| ~~`halatuju-web/src/lib/api.ts`~~ | ~~2,488~~ **132** | ~~H13~~ ✅ **DONE 2026-09-20.** A barrel; 14 modules in `src/lib/api/`, none over 420. ⚠ Its size ceiling was the stated reason `income_shown` is declared locally — TD-271 |
| ~~`halatuju-web/src/components/ScholarshipDocuments.tsx`~~ | ~~1,957~~ **286** | ~~H14~~ ✅ **DONE 2026-09-20.** The checklists + card furniture are 3 modules in `ScholarshipDocuments/`; **`IncomeWizard` followed them on 2026-09-20 once TD-272 was fixed** (565 lines, its two disable entries relabelled by a declared move). The file has LEFT `oversize_files` |
| `halatuju_api/apps/scholarship/vision.py` | 2,321 | **none — deliberately out of scope** (140 patch sites). Growing it is allowed; it is not waiting on a split |

**Everything else over 1,000 lines has no Phase-4 sprint** — `views.py` (2,421), `courses/views.py`
(2,309), `officerCockpit.ts` (1,632), `courses/models.py`, `stpm_quiz_data.py`, `profile/page.tsx`,
`scholarship.ts`, `courses/views_admin.py`, `serializers_admin.py`, `serializers.py`,
`verdict_engine.py`, `contracts.py`, `apply/page.tsx`, `org_requests.py`, `profile_engine.py`.
The standing rule does not apply to them; **the ratchet in `code-standards.json` still does**, so a
sprint that would push one past its budget splits it in its own commit first.

### H11 — `views_admin.py` becomes a package, wave 1 ✅ SHIPPED 2026-09-20

**What moved.** `views_admin.py` (8,556) is the package `views_admin/` (root 5,093 + ten modules,
3,532 lines, average 370, none over 500). `urls.py` byte-identical; all 142 names re-exported.

| module | lines | what |
|---|---|---|
| `base.py` | 332 | `_AdminBase`, `_MONTH_RE`, `_org_or_none` |
| `payments.py` | 377 | payment runs |
| `invoices.py` | 466 | tenant invoices, receipts, build hours |
| `contracts.py` | 436 | contract templates |
| `requests.py` | 480 | a request and its conversation |
| `requests_delivery.py` | 391 | analysis, quote, schedule, attachments |
| `sponsor_terms.py` | 300 | sponsor terms authoring |
| `gifts.py` | 315 | gift + intake-year readers and row builders |
| `gift_programmes.py` | 315 | the Programme endpoints |
| `intake_years.py` | 287 | the ScholarshipCohort endpoints |

**Three things the plan got wrong, and they are the reason H12's estimate moves:**

1. **The 600-line standard decides how many modules there are, not the domain.** H4's ledger is
   frozen and may not gain a member, so any new file over 600 lines is simply refused by the gate
   with nowhere to record it. `requests` (833) and the gift domain (868) therefore had to land as
   two and three modules. ⚠ **H12's old acceptance line — "no file in the package over ~900
   lines" — was never reachable. It is 600, and it always was.**
2. **A ledger-key RENAME is the one case where the frozen baseline has to follow.** A key naming
   a file that no longer exists describes nothing: `test_a_listed_file_that_shrank…` demands the
   line be removed and `test_no_unlisted_source_file…` then refuses the package root with no line
   left to lower. The key was renamed in BOTH blocks and `BASELINE_SHA256` re-pinned, with the
   reason in the JSON's `_history`. **`Settings/_tools/code_health.py` reads that as a new
   exemption and FAILs `std`. It will do so on H12, H13, H15 and H16 too** — see the fix proposed
   under `## Reviews` in `docs/code-health.md`. Four acceptances in a row for a guard that is
   wrong every time is how a guard stops being read.
3. **Trip-wire 1 did not exist.** Switching a submodule to `logging.getLogger(__name__)` turned
   NONE of the twelve `assertLogs` sites red — `assertLogs` on a parent records what propagates up
   from its children, and every one of those tests then matches on the message. The explicit logger
   name is still right (the Cloud Logging scrape metric counts by logger name), but nothing was
   enforcing it. H11 added the guard that does.

**Held:** pytest 7,019 → **7,021** (the +2 is the new logger guard and its floor; every
pre-existing test is unchanged and green) · `manage.py check` 0 · `makemigrations --check` clean ·
`xapp` 133 → 133 · `big` 25 → 25 · every other reading delta 0.
**`hot#1` 273.8 → 107.1**, but read `docs/code-health.md` before quoting it: the tool counts fixes
by path and does not follow a rename, so the split reads as a hotspot vanishing rather than
shrinking. **Retro:** `docs/retrospective-2026-09-20-code-health-h11.md`.

### H12 — `views_admin` wave 2 ✅ SHIPPED 2026-09-20

**What moved.** `views_admin/__init__.py` (5,093) is **154 lines of re-export and no code**. The
nineteen domains moved out as twenty modules, 4,914 lines, average 246, none over 600. The package
is thirty modules plus the root. `urls.py` byte-identical; all twenty moved bodies byte-identical
to the lines they came from, proved by reading them back off disk against `git show HEAD:…`.

| module | lines | module | lines |
|---|---|---|---|
| `reviewers` | 475 | `overview` | 187 |
| `verdict` | 468 | `credits` | 174 |
| `applications` | 467 | `profiles` | 173 |
| `sponsors` | 429 | `sponsorships` | 168 |
| `billing` | 346 | `graduation` | 141 |
| `org_config` | 341 | `resolution` | 113 |
| `lifecycle` | 326 | `interview_slots` | 98 |
| `org_emails` | 301 | `theme` | 267 |
| `interviews` | 246 | `spending` | 210 |
| `sources` | 203 | `invitations` | 195 |

**Three things this sprint corrects for whoever reads it next:**

1. ⛔ **`interview_agenda_full` IS NOT DEAD AND WAS NOT DELETED.** This roadmap, the H12 brief and
   `halatuju_api/CLAUDE.md` all said it had "zero callers outside one test". It is served on every
   admin cockpit load: `serializers_admin.py:756` imports it lazily for the `interview_agenda`
   field (listed at `:542`), typed at `admin-api.ts:1066`, rendered at `view.tsx:1052`. The claim
   came from a symbol search, which answers "who IMPORTS this" — a different question from "who
   CALLS this" in a codebase that uses lazy imports deliberately. **The phase's one permitted
   deletion was not spent, and does not transfer.**
2. **The patch strings were 23, not 19** — 11 `build_verdict` + 9 `refine_sponsor_profile` (6 of
   them `.profiles`, 3 `.verdict`; the two call sites are in different modules, so each site had
   to be read) + 2 `timezone.localtime` → `.billing` + 1 `send_request_info_email` →
   `.resolution`. Plus one reflection target (`vars(views_admin)` → `vars(views_admin.billing)`,
   a function rebuilt from a code constant needs the globals it was compiled against) and one
   docstring. Found by grepping the whole tree for `views_admin.` followed by a dependency name.
3. **A pure split raises `xapp` and there is no honest way round it.** 133 → 135: two module-level
   `apps.courses` imports served four call sites, and the four call sites landed in four modules.
   H11's rule was applied and removed nothing (every other cross-app import in the package already
   sits inside its own function). ACCEPTED with the arithmetic; **TD-268** proposes the metric
   count `(app → app, name)` edges instead. ⚠ **H15 and H16 should expect the same and say what
   their rise is made of, not engineer it away.**

**Held:** pytest **7,021 / 3 skipped** (identical — no test added or removed) · `manage.py check`
0 · `makemigrations --check` clean · `urls.py` byte-identical · code_health **0 FAIL**, `std` ok,
**`big` 25 → 24**, `hot#1` unchanged. Five bite-checks, all five behaved.
**Retro:** `docs/retrospective-2026-09-20-code-health-h12.md`. **Cost: ~6h** against the ~9h
estimate — the ledger was an ordinary tightening this time (no baseline re-pin), and a `symtable`
pass rather than an AST name walk got every import header right first time.

### H13 — `admin-api.ts` and `api.ts` become barrels ✅ SHIPPED 2026-09-20

**What moved.** `admin-api.ts` (4,118) is **241 lines of re-export and no code**; `api.ts` (2,488)
is **132**. The bodies are 42 modules — 28 in `src/lib/admin-api/` (4,385 lines, avg 157, max 443)
and 14 in `src/lib/api/` (2,604 lines, avg 186, max 417) — all under the 600-line standard. Every
moved line is byte-identical to the line it came from, proved by reading each module back off disk
against `git show HEAD:…`; the twenty lines that did NOT move (two file docstrings, two import
headers) were declared in the cut spec in advance, with the reason.

| admin-api | lines | | lines | api | lines |
|---|---|---|---|---|---|
| `applications` | 443 | `partners` | 136 | `documents` | 417 |
| `requests` | 315 | `reviewers` | 135 | `sponsor` | 372 |
| `programmes` | 273 | `orgConfig` | 129 | `stpm` | 262 |
| `overview` | 222 | `lifecycle` | 125 | `application` | 257 |
| `billing` | 221 | `interviews` | 111 | `courses` | 243 |
| `invoices` | 215 | `documents` | 111 | `profile` | 217 |
| `sponsors` | 194 | `spending` | 103 | `guidance` | 187 |
| `verdict` | 187 | `client` | 97 | `award` | 134 |
| `payments` | 176 | `profiles` | 95 | `calculations` | 111 |
| `admins` | 172 | `decisions` | 92 | `bank` | 99 |
| `sponsorTerms` | 159 | `theme` | 91 | `interview` | 87 |
| `emails` | 156 | `sources` | 90 | `inProgramme` | 84 |
| `contracts` | 151 | `invitations` | 72 | `resolution` | 79 |
| | | `resolution` 66 · `courseData` 48 | | `client` | 55 |

**Zero importer edits, which was the whole acceptance.** 231 files import these two modules — 122
by `@/lib/admin-api`, 85 by `@/lib/api`, 24 by a relative path, and 33 of them `jest.mock()` a
barrel by automock. **Not one changed**, and there are no deep imports into the new folders from
outside them. The diff is six modified files (two barrels, three drift tests, the standards file)
plus two new folders.

**Four things this sprint corrects or adds for whoever reads it next:**

1. ⛔ **THE WEB SUITE HAD BEEN RED SINCE H11 AND NOBODY COULD SEE IT.** The real baseline was
   **2,900 tests / 158 suites**, not the 2,913 / 159 on record: `officerGateDrift.test.ts` reads
   `views_admin.py` by path and H11/H12 turned that file into a package, so it died at import,
   taking 13 tests with it — including the guard on the irreversible org-admin reject gate. Both
   sprints were backend-only, ran pytest and passed. **Repaired here** (the path follows the code
   to `views_admin/applications.py` + `verdict.py`), and the systemic half is **TD-269**: 31 of 159
   web test files read source text and several read `halatuju_api/**`, so **any api refactor can
   kill a web guard with every api gate green.** ⚠ **H15 and H16 both move files that web drift
   tests read by path — `services.py` is read by `officerGateDrift` itself. Do TD-269 before H15,
   or H15 repeats H11 exactly.**
2. **Keep the barrel at the ORIGINAL file's path and the ledger-key problem simply does not
   arise.** The plan said `admin-api/index.ts`; that would have renamed the key
   `src/lib/admin-api.ts` and walked back into H11's frozen-baseline trap. `admin-api.ts` stayed
   `admin-api.ts` and the bodies went beside it, so `std` read **ok**, the two entries were merely
   REMOVED as under-standard, and `BASELINE_SHA256` never moved. `foo.ts` next to `foo/` resolves
   to the file in both webpack and jest — proved with a one-module pilot before anything was cut.
3. **`src/lib/http.ts` was NOT created, deliberately.** The plan proposed one shared home for the
   four fetch helpers while also saying the two behaviours must stay apart (`apiRequest` raises
   `nric-required` and carries DRF field errors; `adminFetch` does neither). The surest way to keep
   two behaviours apart is not to file them under one name, so each folder has its own
   `client.ts`, each says in its header that it is not the other, and **neither is re-exported by
   its barrel** — the eight promoted names are folder-private, and the app's public surface is
   exactly the set of names it was before.
4. **The bundle acceptance was measured against a rebuild of the old tree, not argued.** **0 of 72
   routes grew; 53 shrank, 19 unchanged**; total First Load JS across routes 30,665 → 30,505 kB,
   shared chunk identical at 87.1 kB. A page that imports three admin calls used to drag a
   4,118-line module into its chunk and now drags only the modules those calls live in.

**Held:** jest **2,913 passed / 159 suites** (2,900/158 as found — see 1) · tsc 0 · lint 0 errors ·
i18n ok · `npx next build` exit 0 · `manage.py check` 0 · `makemigrations --check` clean (no api
file touched, so no pytest) · code_health **0 FAIL**, `std` ok, **`big` 24 → 22**, **`hot#1` 107.1
`admin-api.ts` → 95.6 `income_engine.py`**, `xapp`/`supp`/`skip`/`guard%` all unchanged. Six
bite-checks, all six behaved. **Findings raised: TD-269, TD-270, TD-271.**
⚠ Read the `hot#1` caveat in the retro before quoting it: the fix COUNT is unchanged at 26; only
KLOC moved (4.118 → 0.241). The 4,000 lines did not get safer today, they moved to 28 files with no
fix history yet.
**Retro:** `docs/retrospective-2026-09-20-code-health-h13.md`. **Cost: ~6h** against the ~6h
estimate.

### H14 — The cockpit and the documents component, panel by panel ✅ SHIPPED 2026-09-20

**What moved.** `view.tsx` (3,599) is **1,338 lines**: the cockpit's state, its thirty handlers,
the derived readings, the layout, and the Decision panel. Thirteen panels plus the shared
furniture moved to `src/app/admin/scholarship/[id]/view/` — 14 modules, 2,359 moved lines,
average 181, **none over 350**. `ScholarshipDocuments.tsx` (1,914) is **825 lines**; the
checklists and the card furniture moved to `src/components/ScholarshipDocuments/` — 3 modules,
900 moved lines, none over 512. Every moved line was rebuilt from the pre-cut file's own bytes
and compared back against it; the lines that did NOT move were declared in advance (108 in the
cockpit, 44 in the documents tab — each file's `'use client'` and its import header, the one part
of a split that must be re-derived per module).

| cockpit module | lines | | lines | documents module | lines |
|---|---|---|---|---|---|
| `DocumentsDrawer` | 346 | `AssignAndWitness` | 175 | `cards` | 512 |
| `PostAwardPanels` | 317 | `VerificationVerdict` | 173 | `checklists` | 492 |
| `InterviewPanels` | 291 | `GeneratedProfile` | 171 | `checklistsPathway` | 150 |
| `ApplicantCards` | 281 | `CockpitHeader` | 155 | | |
| `OutstandingPanel` | 252 | `QcPanel` | 139 | | |
| `RateAndEstimate` | 220 | `OrgRejectPanel` | 136 | | |
| `shared` | 181 | `BlockersPanel` | 122 | | |

**Five things this sprint corrects or adds for whoever reads it next:**

1. ⛔ **`big` FELL BY ONE, NOT TWO, AND IT COULD NOT HAVE FALLEN BY TWO.** The brief's acceptance
   assumed `view.tsx` could become a thin shell the way H13's barrels did. It cannot, and the
   arithmetic is fixed, not a matter of effort: what must STAY in that file is 784 lines of state
   and handlers, 137 of derived readings, the 263-line Decision panel the roadmap rules out of
   scope, ~75 of imports and ~150 of panel call sites — about 1,300 whatever else moves. Moving
   the component body to `view/CockpitView.tsx` and leaving a shell does not help either: a new
   file over 600 lines is refused by the in-repo standard with no ledger line to record it (H11's
   note 1). **`view.tsx` goes under 1,000 only when the Decision panel is untangled, which is
   design work.** 3,599 → 1,338 is what a moves-only sprint can do here.
2. **`IncomeWizard` DID NOT MOVE, AND THE STANDARD REFUSED IT — TD-272.** Its two reasonless
   `exhaustive-deps` disables are recorded in `code-standards.json` under
   `src/components/ScholarshipDocuments.tsx`. Move the wizard and they sit at a path the frozen
   ledger has no line for: unlisted → FAIL, add the line → "a ledger has gained a member" → FAIL,
   re-pin the baseline → `std: FAIL` from the external tool. H11's ledger-key trap in a SECOND
   ledger, and the one H13's keep-the-path trick cannot dodge, because the exemption is inside
   the moved body. ⚠ **H15 and H16: grep the ledger for the file you are about to split, before
   planning the cut.**
3. **A fragment wrapper is what makes a JSX lift a pure move.** Every panel is
   `export function X(props) { return (<> …the exact lines… </>) }`. A fragment renders no DOM
   node, so `space-y-4`'s direct-child selector still sees the same children in the same order —
   which is why all 59 of H6's rendered tests passed with no edit at all, first run.
4. **The two re-pointed guards read a WALK, not a list.** `theme.test.ts`'s F5 block and
   `webMirrorDrift.test.ts`'s Assignment-card pair now read `view.tsx` plus every file in
   `view/`. Two of `webMirrorDrift`'s assertions are `not.toMatch` — had the path stayed on one
   file they would have gone GREEN because the code had moved elsewhere, which is the most
   dangerous way for a guard to pass. Each has a floor (`>= 15 files`, `>= 14 modules`) folded
   into an existing test, so the count of tests is unchanged and the guard cannot silently narrow
   back.
5. **The bundle was MEASURED, and one route grew.** Against a rebuild of the parked old tree: 87
   routes, 86 unchanged, **the cockpit 32.8 → 34.8 kB** (First Load JS 513 → 515), shared chunk
   identical at 87.1 kB. The +2 kB is the mechanical cost of turning inline JSX into thirteen
   components with ~180 explicit props. Say it rather than round it away — H13's split shrank 53
   routes, this one grows one, and both are what the change actually does.

**Held:** jest **2,913 / 159 suites** (the measured baseline, unchanged — it matched this section
this time) · tsc 0 · lint 0 errors · i18n ok · `npx next build` exit 0 · `manage.py check` 0 ·
`makemigrations --check` clean · pytest **7,021 / 3 skipped** (run anyway, though no api file was
touched) · code_health **0 FAIL**, `std` ok, **`big` 22 → 21**, `hot#1` holds at
`income_engine.py` 95.6, `xapp`/`supp`/`skip`/`guard%` unchanged. Six bite-checks, all six
behaved. **TD-271 CLOSED** (the sprint's one declared exception). **Findings raised: TD-272,
TD-273.**
⚠ **`supp` did NOT fall by ~25.** The `useApiLoad` hook that would have retired ~26
`exhaustive-deps` disables was cut from this sprint's brief: a new shared hook is a design
change, not a move, and Phase 4 is moves only. It is still worth doing, though it no longer
unblocks anything: TD-272's fix (2026-09-20) let `IncomeWizard` move with its two disables intact.
**Retro:** `docs/retrospective-2026-09-20-code-health-h14.md`. **Cost: ~7h** against the ~8h
estimate.

### H15 — `models.py` and `services.py` ✅ SHIPPED 2026-09-20

**What moved.** `models.py` (4,756) is **81 lines of re-export and no code**; `services.py` (2,946)
is **109**. The bodies are 33 modules — 15 in `models/` (4,715 moved lines, largest 899) and 18 in
`services/` (2,890 moved lines, largest 430). Every moved line is byte-identical to the line it came
from, asserted by the cut itself; the 97 lines that did NOT move (two headers, five deliberate
re-export lines, 56 blank separators) were declared in advance, and a second assertion proved every
declared line was blank or header, so no section banner could be lost in a gap.

| models | lines | | lines | services | lines | | lines |
|---|---|---|---|---|---|---|---|
| `applications` | 899 | `documents` | 248 | `blockers` | 430 | `querying` | 124 |
| `billing` | 547 | `interviews` | 205 | `offer_sync` | 386 | `queries_sla` | 88 |
| `comms_templates` | 413 | `invoices` | 153 | `assignment` | 332 | `details` | 78 |
| `funding` | 388 | `spending` | 152 | `decline` | 301 | `reminders` | 73 |
| `tenant_requests` | 382 | `sponsors` | 133 | `intake` | 266 | `consent_blockers` | 71 |
| `programmes` | 363 | `content` | 118 | `confirmation` | 240 | `errors` | 61 |
| `agreements` | 329 | | | `completeness` | 185 | `ready_profiles` | 60 |
| `review` | 294 | | | `query_emails` | 147 | `constants` | 18 |
| `items` | 257 | | | `profile_sync` | 139 | | |
| | | | | `consent` | 134 | | |

**Five things this sprint corrects or adds for whoever reads it next:**

1. ⛔ **PYTHON CANNOT USE H13's KEEP-THE-PATH TRICK, so both ledger keys HAD to move.** `foo.ts`
   beside `foo/` resolves to the file in webpack and jest, which is how H13 dodged the ledger-key
   problem entirely. In Python a package **shadows** a module of the same name in the same
   directory, so `models.py` cannot sit beside `models/`. H16 gets no choice either. This is what
   `_moved` is for, and **its first real use went exactly as TD-272 designed**: two records, the
   frozen `baseline` untouched, `BASELINE_SHA256` NOT re-pinned, `std` **ok**. `services.py` left
   `oversize_files` outright; `models.py`'s entry relabelled onto `models/applications.py` and
   ratcheted 4756 → 899.
2. ⛔ **THREE KINDS OF GUARD READ THESE FILES BY PATH, AND TWO WOULD HAVE FAILED SILENTLY.** The six
   WEB drift tests failed loudly (`readApi` throws — TD-269's repair holding). But
   `test_verdict_item_i18n.py` walked `apps/scholarship/` with **`glob`, not `rglob`**, so it simply
   stopped looking inside both new packages **and went on passing**; and `test_wallet_credit.py`
   allowlisted by **bare file name**, where the obvious fix would have been a real weakening. ⚠
   **H16 must grep for BOTH shapes before cutting**: a path string, and a directory walk that will
   quietly cover less. Raised **TD-276** and **TD-277**.
3. **A patch-target search must cover `patch.object`, not just the dotted string.** Grepping
   `apps.scholarship.services.<name>` found the nine strings that had to follow a dependency into a
   submodule. It did not find `mock.patch.object(services, 'switch_income_route')` — the same H12
   trap in a different shape, caught only by the suite.
4. **Four new module names collided with existing top-level modules** (`money`, `contracts`,
   `org_requests`, `email_templates` all already existed in `apps/scholarship/`). Python does not
   care; the basename-keyed guard in note 2 does, and so would any future one. Renamed to
   `funding`, `agreements`, `tenant_requests`, `comms_templates`. ⚠ **H16 should check `emails.py`
   and `income_engine.py` module names against the app's existing files at cut time** — it is free
   then and expensive later.
5. **The logger bite came back SILENT, in a second package, for H11's exact reason.**
   `AuditLoggerNameTest` was hard-coded to `views_admin`; switching `services/assignment.py` to
   `getLogger(__name__)` turned nothing red, the one `assertLogs('apps.scholarship.services')` site
   included. The guard now takes a LIST of packages with a floor each. ⚠ **H16 adds
   `apps.scholarship.income_engine` to that list if it gives the package a logger.**

**Held:** pytest **7,037 / 3 skipped** (identical; the two generalised logger checks are subtests,
807 → 811) · jest **2,929 / 159 suites** (identical) · `manage.py check` 0 ·
`makemigrations --check --dry-run` **`No changes detected`** · tsc 0 · lint 0 · i18n ok ·
`next build` exit 0 · code_health **0 FAIL**, `std` ok, **`big` 21 → 19**, `hot#1` holds at
`income_engine.py` 95.6, **`xapp` 46 → 46 — it did NOT rise**, because TD-268's edge counting
landed first. Six bite-checks; five behaved, the sixth was silent and its guard was written.
**Findings raised: TD-275, TD-276, TD-277. TD-269 discharged for these two files.**
**Retro:** `docs/retrospective-2026-09-20-code-health-h15.md`. **Cost: ~7h** against the ~8h
estimate.

<details>
<summary>The original H15 plan, as written</summary>

- **Scope:** `models/` package with full re-export — `ScholarshipApplication` is a wide table
  (159 fields, 3 methods), not a fat class, so this is a file move. 310 importers, 3 patch sites,
  and migrations address models by label, not by file. `services.py` splits on its existing
  seams (blockers, assignment, decline, confirmation, consent) behind a re-exporting shim.
- **Acceptance:** `makemigrations --check` clean — **a models move that generates a migration is a
  failed move**; pytest green.
- **Complexity:** low–medium. **~6h → ~8h**, re-estimated on H14's measured cost. The +2h is not
  the move; it is the four checks H11–H14 have each paid for separately and H15 must do up front:
  - ⚠ **DO TD-269 FIRST, OR H15 REPEATS H11 EXACTLY.** `officerGateDrift.test.ts` reads
    `services.py` BY PATH from the web tree. H11 and H12 killed that same test by moving
    `views_admin.py` and neither could see it, because a backend sprint runs pytest and not jest.
    **H15 must run BOTH suites**, whatever it touches, and should grep the web tree for
    `services.py` and `models.py` before cutting anything.
  - ⚠ **Grep `code-standards.json` and the api's own exemption ledgers for both files before
    planning the cut — TD-272.** H14 was refused a scoped move because a suppression inside the
    moved body was recorded under the parent file's path. `models.py` and `services.py` are
    prime candidates for the same trap. ✅ **TD-272 IS FIXED (2026-09-20): the grep still has to
    happen, but the answer is no longer a refusal.** Declare the move in the `_moved` array of
    that service's `code-standards.json` — one record per key, `{on, why, ledger, from, to}` —
    and spell the budget entry at its new key. The frozen `baseline` is NOT edited and
    `BASELINE_SHA256` is NOT re-pinned. `models.py` carries `long_functions` and
    `hand_built_application_fixtures` keys as well as its size entry; every one of them relabels
    the same way. See `## Code standards → Moving a file that is in a ledger` in
    `halatuju_api/CLAUDE.md`.
  - ⚠ **`std` will still FAIL on a move that touches a STRING ledger until TD-274 lands.**
    `code_health.loosened` learnt the rename exception for dict entries on 2026-09-20 but not for
    JSON arrays, so relabelling an `eslint_disable_without_reason` or `unguarded_mirrors` member
    reads as `gained "<new key>"`. That is the tool, not the repo — but say so in the sprint
    report rather than accepting a bare FAIL, and prefer landing TD-274 first (~1h).
  - **Expect `xapp` to rise and say what the rise is made of** — H12's lesson, unchanged, and
    TD-268 is still open.
  - **Take BOTH baselines yourself before touching anything.** H13's brief was wrong by 13
    tests; H14's was right. The ten minutes is the point either way.
- **api deploy.**

</details>

### H16 — `emails.py`, `income_engine.py`, and the back-edge ✅ SHIPPED 2026-09-20

**What moved.** `emails.py` (4,242) is **134 lines of re-export and no code**; `income_engine.py`
(3,188) is **132**. The bodies are 40 modules — 21 in `emails/` (4,228 moved lines, largest 464)
and 19 in `income_engine/` (3,155 moved lines, largest 377). Every moved line is byte-identical to
the line it came from, asserted by the cut itself, and the 47 lines that did NOT move (14 + 33
header lines) were declared in advance and proved to be header or blank. **No importing file
changed.**

| emails | lines | | lines | income_engine | lines | | lines |
|---|---|---|---|---|---|---|---|
| `interview_mail` | 464 | `payment_mail` | 162 | `identity_checks` | 377 | `gaps` | 139 |
| `student_decisions` | 403 | `student_queries` | 143 | `utilities` | 338 | `epf_evidence` | 130 |
| `reviewer_mail` | 366 | `invitation_mail` | 118 | `evidence` | 310 | `doc_checks` | 125 |
| `award_offer` | 334 | `spend_alerts` | 113 | `relationships` | 258 | `pension` | 95 |
| `student_notices` | 326 | `invoice_mail` | 85 | `amounts` | 205 | `bill_followups` | 88 |
| `sponsor_cards` | 313 | `ops_alerts` | 65 | `str_route` | 196 | `buckets` | 69 |
| `signing` | 286 | `shared` | 61 | `freshness` | 188 | `followups` | 63 |
| `vircle_install` | 269 | `referral_mail` | 60 | `advice` | 169 | | |
| `reviewer_interviews` | 228 | `decline_mail` | 48 | `household` | 163 | | |
| `sending` | 217 | | | `occupation` | 148 | | |
| `student_reminders` | 187 | | | `informal` | 146 | | |
| `org_request_mail` | 177 | | | `salary_figures` | 139 | | |

**Six things this sprint corrects or adds for whoever reads it next:**

1. ⛔ **A `__file__`-RELATIVE PATH IS THE SAME HAZARD AS A `__name__` LOGGER, AND ONLY THE GOLDEN
   SAW IT.** `emails.py` built the Vircle installation-guide path from
   `os.path.dirname(os.path.abspath(__file__))`. One level deeper, that answers
   `apps/scholarship/emails/` and the attachment silently vanishes — no exception, no log line, a
   `return None` and an email that goes out without its PDF. Every suite was green; the **email
   golden master** failed, because it pins attachment filenames. This arc had a written rule for
   `__name__`; it did not have one for `__file__`, and the two are the same rule.
   **⚠ Before the next package split, grep the file for `__file__` as well as `__name__`.**
2. **`_moved` WAS NOT NEEDED, AND NOT USING IT IS THE RESULT.** Both `oversize_files` entries left
   the budget outright. H15 needed a relabel because `ScholarshipApplication` is one 847-line
   class no move can divide; neither of these files had an indivisible lump, so both fell under
   600 everywhere. **A sprint that declares a move it did not need has quietly kept an exemption
   alive.** ⚠ The roadmap also said `income_engine.py` "carries `long_functions` entries as well
   as its size entry" — **it did not.** Grep the ledger; do not trust a sprint brief about it.
3. ⚠ **PATCHING A NAME ON A PACKAGE SHELL IS A NO-OP FOR THE CODE INSIDE IT, AND SOMETIMES A SILENT
   ONE.** H12 and H15 both said this about dotted strings; H16 met it at scale — 36 of the 36
   failures after the cut were patch targets, guards, or the ledger, and nothing else. A name in a
   package is looked up three ways (through the package, from a sibling's import header, in its own
   home) and the old single target covered only the first. `tests/package_patch.py` now patches one
   shared mock into all three **and asserts it patched something**, which is the half that stops a
   future move turning a test into a no-op.
4. ⚠ **A CYCLE IS NOT A FAILURE OF THE DOMAIN SPLIT; IT NAMES THE ONE FUNCTION IN THE WRONG PLACE.**
   Two appeared. `_send_plain` sat with the reviewer mail it serves but reads
   `_interview_unsub_headers`, so it went to `sending`. `_name_bucket` / `_nric_bucket` /
   `_combine_relationship` sat with the document checks that use them, but `relationships`,
   `identity_checks` and `str_route` read them too — they became `buckets.py`, which its docstring
   says. Both were found by the generator before a single file was written, not by the suite.
5. **THE FREE-NAME ANALYSIS THAT BIT H15 WAS FIXED AT SOURCE.** H15's one bug was a scope-blind
   pass: a lazy `from django.utils import timezone` inside one function made the name look
   satisfied for another. H16 used `symtable`, which is scope-aware — a lazy import binds LOCALLY
   there, so a sibling's use still reads as a free global. **Zero missing imports; the suite found
   none.** ⚠ The module symbol table ALONE is not enough (a global used only inside a function is
   not `is_referenced()` at module scope); every nested scope has to be walked. The first draft did
   not, and reported three dependencies where there are seventeen.
6. **THE BACK-EDGE TARGET WAS NOT REACHED AND WAS NOT REACHABLE BY A MOVE — see TD-278.** The
   acceptance said "`xapp` back-edge under 20"; it went **31 → 30 edges** (41 → 41 statements).
   Six constants are six distinct names, so they are six edges whichever module holds them, and
   consolidating three source modules into one leaf changes which module is named rather than how
   many names cross. What DID land is real and bankable: the last import-time cross-app import is
   gone (`courses_to_scholarship_module_level_imports` **1 → 0**, ratcheted), and `courses` no
   longer pulls the eighteen-module `services` package, `check2_queries` and `scheduling` across
   the border to read six integers — it reads `apps/scholarship/constants.py`, a leaf that imports
   nothing, so the "it would be circular" comment beside each of those imports is now false by
   construction.

**Held:** pytest **7,043 passed / 3 skipped** (identical; subtests 811 → 813) · jest **2,934 /
160 suites** (identical) · `manage.py check` 0 · `makemigrations --check --dry-run`
**`No changes detected`** · **the email golden master BYTE-UNCHANGED** · tsc 0 · lint 0 · i18n ok
· `next build` exit 0 · code_health **0 FAIL, 6 WARN**, `std` **ok**, **`big` 19 → 17**,
**`hot#1` `income_engine.py` 95.6 → `officerCockpit.ts` 49** (income_engine left the table),
**`xapp` 46 → 45 — it FELL**, `supp` 139, `skip` 0, `dup` 4, `mirror` 3, `guard%` 20.
**Seven bite-checks, all seven behaved** — including the logger bite that was SILENT at H15.
**Findings raised: TD-278, TD-279.**
**Retro:** `docs/retrospective-2026-09-20-code-health-h16.md`. **Cost: ~7h** against the ~7h
estimate.

<details>
<summary>The original H16 plan, as written</summary>

- **Scope:** `emails.py`: copy constants (1,005 lines of EN/BM/TA) out to `email_copy/`; senders
  by domain. The safety net is `test_email_branding.py` — a byte-identity golden over every
  `send_*`. ⚠ **Never set `UPDATE_EMAIL_GOLDEN` during this sprint**; it would bless the
  regression. `income_engine.py`: its 21 banner sections become a package; the 43 patch sites sit
  on public functions that move whole. `courses → scholarship`: six of the 25 back-edges are
  plain numeric constants → `scholarship/constants.py`; the single module-level import
  (`courses/views_admin.py:33`) goes lazy.
- **Acceptance:** email golden byte-identical; both golden masters unchanged; `xapp` back-edge
  under 20.
- **Complexity:** medium. **~7h → ~7h, re-estimated on H15's measured cost (~7h for TWO files of
  7,702 lines).** The cut itself is cheaper than it looks — H15's generator and its checks transfer
  whole — so the estimate holds rather than falls, because the time goes somewhere else. Read H15's
  five notes above first; these are the four things that actually cost it time, and H16 meets all
  of them:
  - ⚠ **Both files become PACKAGES and both ledger keys MUST move.** `foo.py` cannot sit beside
    `foo/` in Python (H15 note 1), so H13's keep-the-path trick is unavailable. Declare each in
    `_moved`; the mechanism is proven now and the frozen baseline is not touched.
    `income_engine.py` carries `long_functions` entries as well as its size entry — **grep both
    `code-standards.json` files for every path before planning the cut**, as H15 did.
  - ⚠ **Grep for TWO guard shapes, not one.** A path string in a test (loud, easy) AND a directory
    walk that will quietly cover less (silent — H15 note 2, TD-276). `grep -rn "glob(" apps/` and
    check every walk that touches `apps/scholarship`. Grep the WEB tree too: **`income_engine.py`
    is read by `incomeEvidenceHomes.test.ts` and the `incomeWizard` mirror claims point at it.**
  - ⚠ **Check new module basenames against `ls apps/scholarship/*.py` at cut time** (H15 note 4).
    `email_copy/` is safe; a `models`-style domain split of `income_engine` could easily collide.
  - ⚠ **Search patch targets in both shapes** — `patch('...emails.<name>')` and
    `patch.object(emails, '<name>')` (H15 note 3).
  - ⛔ **Never set `UPDATE_EMAIL_GOLDEN`.** `test_email_branding.py` is a byte-identity golden over
    every `send_*` and it is the whole safety net for the `emails.py` half.
  - **Expect `xapp` NOT to rise** — TD-268 landed and H15 confirmed it: 46 → 46 across a 33-module
    split. If it does rise, say what the rise is made of rather than engineering it away.
- **api deploy.**

</details>

---

## PHASE 4 CLOSING SUMMARY — 2026-09-20

**Phase 4 is complete.** Six sprints, all on one day, all moves only.

### What the six sprints delivered

| sprint | what it split | before | after |
|---|---|---|---|
| H11 | `views_admin.py` → package, wave 1 | 8,556 | root 5,093 + 10 modules |
| H12 | `views_admin` wave 2 | 5,093 | root **154** + 30 modules total |
| H13 | `admin-api.ts`, `api.ts` → barrels | 4,118 / 2,488 | **241** + 28, **132** + 14 |
| H14 | the cockpit `view.tsx`, `ScholarshipDocuments.tsx` | 3,599 / 1,957 | **1,338** + 13, **286** + 3 |
| H15 | `models.py`, `services.py` → packages | 4,756 / 2,946 | **81** + 15, **109** + 18 |
| H16 | `emails.py`, `income_engine.py` → packages; the back-edge | 4,242 / 3,188 | **134** + 21, **132** + 19 |

**Nine files totalling 35,850 lines became 138 modules and eight shells.** Not one of those lines
was reworded. No migration was created, both golden masters are byte-unchanged, and **no importing
file was changed in any of the six sprints.**

### The readings, before H11 and now

| reading | before H11 | now | note |
|---|---|---|---|
| `big` — files over 1,000 lines | **25** | **17** | the target was 12 or fewer — see below |
| `hot#1` — the worst file's bug score | **273.8** (`views_admin.py`) | **49** (`officerCockpit.ts`) | ⚠ the tool counts fixes by PATH and does not follow a rename, so a split reads as a hotspot vanishing rather than shrinking. The honest claim is that the four worst files by fix-density are no longer single files |
| `xapp` — cross-app edges | **133** statements | **45** edges | ⚠ THE DEFINITION CHANGED at TD-268 (2026-09-20): edges, not statements. Not comparable across that date. H12 → H16 on the new definition: 46 → 45 |
| `courses → scholarship` module-level imports | **1** | **0** | the import-time half of the back-edge is gone |
| `supp` · `skip` · `dup` · `mirror` | 139 · 0 · 4 · 3 | 139 · 0 · 4 · 3 | **unchanged, deliberately** — a moves-only phase must not move these |
| pytest · jest | 7,019 · 2,881 | **7,043** · **2,934** | every pre-existing test unchanged and green; the additions are guards, never a rewrite |

### What is still over 1,000 lines, and why each one is

Seventeen files. **None of them is waiting on a Phase-4 sprint** — the split table is empty.

| file | lines | why it is still big |
|---|---|---|
| `apps/scholarship/views.py` | 2,421 | never had a Phase-4 sprint. A real candidate for a future one; `DocumentListCreateView.post` alone is 312 lines |
| `apps/scholarship/vision.py` | 2,321 | **deliberately out of scope** — 140 patch sites address it by dotted string. Splitting it is a test-suite rewrite, not a move |
| `apps/courses/views.py` | 2,309 | never had a sprint; the courses app was out of Phase 4's scope |
| `src/lib/officerCockpit.ts` | 1,632 | never had a sprint. It is now `hot#1` and is the obvious first file of any Phase 4b |
| `apps/courses/models.py` | 1,375 | a wide table, like `models/applications.py`. A move cannot divide a class |
| `apps/courses/stpm_quiz_data.py` | 1,371 | **data, not code** — a question bank. Splitting it buys nothing |
| `src/app/profile/page.tsx` | 1,371 | a page component; the H14 panel treatment would work, and was not scoped |
| `src/lib/scholarship.ts` | 1,342 | never had a sprint |
| `src/app/admin/scholarship/[id]/view.tsx` | 1,338 | ⚠ H14 took it from 3,599 and **stopped here on purpose**. The rest is the Decision panel, and untangling it is design work, not a move |
| `apps/courses/views_admin.py` | 1,262 | never had a sprint |
| `serializers_admin.py` · `serializers.py` | 1,229 · 1,212 | never had a sprint; both are flat lists of serializer classes, so a split is cheap when someone wants it |
| `verdict_engine.py` | 1,151 | ⛔ **eligibility.** TD-262 is not fully settled; splitting it before the rulings land repeats the mistake H16's brief was written to avoid |
| `contracts.py` | 1,145 | money and consent. Same argument as `verdict_engine.py`, one notch lower |
| `src/app/scholarship/apply/page.tsx` | 1,142 | a page component, as above |
| `org_requests.py` · `profile_engine.py` | 1,061 · 1,023 | just over the line; neither was scoped |

**So `big` finished at 17 against a target of 12 or fewer, and that is an honest miss.** The eight
that left were the eight the phase named. The nine that remain divide into three groups: four
nobody scoped (`views.py` ×2, `officerCockpit.ts`, `scholarship.ts` and the two serializer files),
three that a move cannot help (`vision.py`'s patch sites, `stpm_quiz_data.py`'s data,
`courses/models.py`'s wide table), and two that are **eligibility and money and should not be
touched until their owner rulings land**. Closing the gap is a Phase 4b, and it is a smaller and
more obvious piece of work than Phase 4 was, because the method is now written down and proven six
times.

### What Phase 5 (H17, H18) should expect

- **The method transfers whole and it is cheap now.** H16's generator computes free names with
  `symtable`, asserts byte-identity per line before a file is allowed to exist, proves every
  unmoved line is blank or header, and detects cycles before anything is written. H15 and H16 each
  cost ~7h for two files of 7,000+ lines, and most of that was NOT the cut.
- **⚠ THE COST IS THE GUARDS, NOT THE MOVE.** Every one of the six sprints found at least one
  guard reading a moved file by path, and the arc has met a SILENT one four times. Before cutting
  anything: grep both trees for the path, grep for `glob(`/`rglob(`/directory walks, grep for
  `patch('...')` **and** `patch.object(...)`, and grep the file itself for `__name__` **and**
  `__file__`. That list is the whole of H11–H16's hard-won knowledge and it is ten minutes.
- **Phase 5 is not a moves phase, so the ratchet works differently.** H17 (one locale per visitor)
  and H18 (first-load-JS and query budgets) both CHANGE what runs. Phase 4's proof — green suites
  on identical counts — does not apply; H17 needs a measured before-and-after of the bundle, and
  H18 needs its budgets set from a real reading, not from a hope.
- **Two new budgets will want the `_moved` treatment eventually.** A first-load-JS budget keyed on
  a route path has exactly the problem TD-272 solved for file paths: a renamed route orphans its
  entry. Design it with a declared-move escape from the start rather than after the first rename.
- **⚠ `hot#1` still does not follow a rename (the tool, not the repo).** After six splits the
  hotspot table is much less informative than it looks. Fix it, or stop quoting it, before Phase 5
  sets budgets that lean on it.

---

## Phase 5 — Efficiency: what the visitor downloads, and what each page costs

### H17 — One locale per visitor
- **Goal:** an English reader stops downloading ~1.2 MB of Malay and Tamil.
- **Scope:** `src/lib/i18n.tsx` statically imports all three locale files (1.53 MB) into every
  client bundle. English stays static as the fallback; `ms` and `ta` load on demand. Watch for a
  flash of English on first paint for a returning Tamil reader — settle the stored locale before
  render. The i18n guards read the JSON directly and survive unchanged.
- **Acceptance:** first-load JS for `/` down by roughly three-quarters on the default locale; no
  flash in a recorded Playwright run for each locale.
- **Complexity:** medium. **~5h.** web deploy.

### H18 — Efficiency gets budgets too
- **Goal:** the owner's word was *"bugs **or inefficiencies**"*. Slowness creeps in the same way
  bugs do — one reasonable change at a time, with nothing counting.
- **Scope:**
  - **Query budgets.** `assertNumQueries`-style tests on the five busiest endpoints: officer
    applicant detail, applications list, student application, sponsor pool, Programme Overview.
    ⚠ The June audit found the applicant-detail GET made **20–30 duplicate queries, wrote to the
    database, and ran the verdict engine 2–3 times** — and nothing marks those as closed.
    **Measure first.** If still true, fixing that one endpoint is this sprint's main work.
  - **Bundle budget.** First-load JS per route, read from `next build`, recorded in
    `code-standards.json`, ratcheted. H17 sets the new low; this keeps it.
  - **Build budget.** Build minutes per deploy and api image size, recorded at sprint close.
  - One reading added to `code_health.py`: `queries` for the applicant detail.
- **Acceptance:** each budget bite-checked (add a query in a loop → red; add a heavy import → red).
- **Complexity:** medium–high. **~9h.** api deploy if the N+1 is real.

---

## Phase 6 — Lock it in

*(The freeze was lifted early, at the checkpoint on 2026-09-19, so H19's last act is no longer to
lift it — it is to write the standing rule and the standards into the workflows for good.)*

### H19 — The standards move into how every future sprint is run
- **Goal:** six months from now, an agent that has never seen this document still keeps to it.
- **Scope — each line is a change to a workflow or a project file, not advice:**
  - **`halatuju_api/CLAUDE.md` — a "Code standards" section**, short: the standards, each with the
    test that enforces it and the one-line reason. New rule → one home, served not mirrored. New
    view → a seam test. New test → the factory. A file you must grow past its budget → split it
    first, in its own commit.
  - **`sprint-start.md`** — a health pre-flight: read the hotspot list in `docs/code-health.md`;
    if the sprint touches a file on it, the sprint plan says how that file is left **no worse**.
  - **`sprint-close.md`** — already takes the reading (added 2026-09-18). Add: run the built-in
    `/code-review` on the sprint's diff before the deploy push, findings answered in the retro.
  - **`small-change-lane.md`** — the consolidation review already runs the reading. Add: the third
    consecutive accept of the same WARN becomes a TD entry.
  - **`system-audit.md`** — every fifth sprint, a **read-through** of the top three hotspots by an
    agent, recorded in `docs/code-health.md`. Numbers find growth; only reading finds a wrong idea.
  - **Tighten `code-standards.json` to the arc's targets** — the last turn of the ratchet.
  - **Write the standing rule of 2026-09-19 into `sprint-start.md`** — a sprint that must touch a
    file in the "Which Phase-4 sprint owns which file" table runs that split first. While any row
    of that table is unsplit, the rule is live and belongs in the workflow, not only here.
  - Close out: final reading against the targets table; TD entries for anything missed; retro for
    the whole arc; update `CLAUDE.md` Next Sprint, the MEMORY.md registry and Mission Control.
    *(The freeze itself was lifted at the checkpoint on 2026-09-19, and BrightPath's queued
    requests opened then.)*
- **Acceptance:** a dry run — a throwaway branch that adds a 700-line file, a mirrored rule, a
  hand-built fixture and a query in a loop is refused **four times, by four different tests**,
  without anyone remembering anything.
- **Complexity:** low–medium. **~6h.**

---

## Sequence, and what blocks what

```
Phase 1   H1 -> H2 -> H3 -> H4
Phase 2   H5 -> H6
Phase 3   H7 -> H8 -> H9 -> H10        <-- CHECKPOINT reached 2026-09-19: the owner LIFTED the freeze
Phase 4   H11 -> H12 -> H13 -> H14 -> H15 -> H16   <-- COMPLETE, all six shipped 2026-09-20
Phase 5   H17 -> H18
Phase 6   H19                          <-- "completed"
```

- **H1 → H2 → H3 → H4 are strictly first.** Every later sprint is safer once a red suite cannot ship.
- **H6 blocks H14.** H3 blocks H11. H5 should precede H7/H8 (their tests use the factory).
  H6 paid for itself here: its 59 rendered tests passed unedited through a 2,359-line lift, which
  is the only reason H14 could claim the moved code is the code that runs.
- ~~⚠ **TD-269 should block H15.**~~ ✅ **DISCHARGED for these two files, 2026-09-20.** H15 grepped
  the web tree before planning the cut and found SIX drift tests reading `models.py` /
  `services.py` by path; all six followed the code, three of them onto a package WALK with a floor
  because they assert "exactly one match" and would otherwise have narrowed silently. `readApi`
  throwing on a missing path is what made this loud rather than invisible. ⚠ **The systemic half
  stays open, and H15 widened it: a path string is the EASY shape. The dangerous one is a
  directory walk that quietly covers less — see TD-276, and H15's note 2.**
- ~~⚠ **TD-272 constrains H15 and H16.**~~ ✅ **FIXED 2026-09-20 — it no longer blocks either.** A
  ledger key may now FOLLOW its code, through a declared move in the `_moved` array of
  `code-standards.json`, and a move may only relabel: it buys no extra room, no extra member and
  no re-pin of the frozen baseline. `IncomeWizard` made the move H14 could not, as the acceptance
  test for the change. **Still grep the ledgers for the file BEFORE planning the cut** — the
  question ("does anything INSIDE this file have a key of its own?") is unchanged; only the answer
  is. ⚠ **Its one loose end is TD-274**, in `Settings/_tools`: `std` still reads a relabelled
  STRING-ledger member as a new exemption.
- Phases 3 and 4 do not block each other; Phase 3 goes first because it is the half that prevents bugs.
- **Back to back through H10, by the owner's 2026-09-18 ruling.** With the product frozen there was
  one agent in the checkout, which removed Phase 4's biggest risk (a file changing under a move).
- **From H11 on, alternating with product work** — the owner lifted the freeze at the checkpoint on
  2026-09-19. A feature sprint that must change a file still on the hotspot list **pulls that
  file's Phase-4 sprint forward instead of adding to it**; the lookup table is under Phase 4. More
  than one agent in the checkout means `AGENT-TERRITORY.log` is back in use, and each move lands
  within one day.

## Deliberately NOT in scope

- **Splitting `vision.py`.** 140 patch sites on two network seams. Most expensive move, least
  benefit. Revisit only if it re-enters the top three hotspots after H12.
- **Untangling the Decision/Recommendation panel.** That is a redesign with a Stitch prototype, its
  own roadmap, and the owner's eye — not a health move.
- **Coverage percentages.** A coverage number invites tests written for the number. The bite-check
  habit is the better instrument and is already in use. Reconsider after H6.
- **ruff / mypy / prettier / pre-commit across the repo.** A formatter pass rewrites every file
  the other agent is editing, and mypy on 70k untyped lines is its own arc.
- **GitHub Actions as the gate.** It is only a *check*; the Cloud Build triggers fire on push
  regardless, and this repo pushes straight to `main`. H2 puts the gate where the deploy is.
- **Product fixes found along the way** (TD-164 status mask, TD-218 `exam_type`, the P3 tail from
  the July review, TD-253, TD-254). They keep their own TD entries and their own turn.
- **The four findings the June audit REJECTED by verification** — notably "a circular import
  between the apps": the graph is a clean DAG; 24 of the 25 back-edges are already lazy.

## Risks

| Risk | Guard |
|---|---|
| A "pure move" changes behaviour | Moves only; full suite; email golden; golden masters; rendered cockpit tests exist first (H6) |
| Two agents, one checkout, a file mid-move | Removed by the freeze; if lifted early, `AGENT-TERRITORY.log` and each move lands within one day |
| The test step eats the free build minutes | Spike measures it first (H2); path-filter fallback; `pytest -n auto` |
| A flaky test blocks a hotfix | `_SKIP_TESTS=1`, loud in the log, recorded in the retro |
| Pinning changes what production runs | Lock is a freeze of the **serving** image, not a fresh resolve |
| The arc stalls half-way | Every sprint stands alone and leaves the code better; the Phase 3 checkpoint is a planned place to stop |
| A long freeze frustrates students, sponsors or BrightPath | Defects and operations are never frozen; requesters are told when work resumes; the checkpoint offers an early exit |
| The standards get loosened later, "just this once" | The budget is a ratchet guarded by its own test; loosening it needs a commit that says so, which the owner sees |

## Owner decisions

**Settled 2026-09-18:** cadence — back to back, under a freeze. Standards — enforced in the gate.

**Settled 2026-09-19 — all three now answered:**
1. **The word to start H1** — given; H1–H10 shipped.
2. **H2's committed Cloud Build config** — agreed; both triggers run a committed `cloudbuild.yaml`.
3. **At the checkpoint (after H10): lift the freeze, or run to the end** — **LIFT**, with the
   standing rule that a feature sprint touching a file on the hotspot/oversize list runs that
   file's Phase-4 split sprint first. H11–H19 alternate with product work. The ratchet standards
   are unchanged.

**Still on the owner's desk (none of them blocked by anything):** TD-262 (F2 + W1, the income
rule's fourth way has no upload slot — needs a Stitch prototype), TD-260, TD-255, TD-257, TD-253,
TD-265. TD-264 was ruled on 2026-09-19 and is resolved.
