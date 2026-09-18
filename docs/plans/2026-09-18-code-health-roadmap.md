# Code health — the sprint roadmap

**Written 2026-09-18** via `Settings/_workflows/implementation-planning.md`. **Revised the same
day on two owner rulings (below). Awaiting the owner's word to start H1.**

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

## The development freeze

**In force from 2026-09-18 — the ruling is the owner's own words — until the owner lifts it.** It is posted at the top of `halatuju_api/CLAUDE.md` "Next Sprint", where every agent reads first.

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

**Two ways out, both the owner's call:**
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

**Nineteen sprints in six phases, about 118 hours, run back to back.** The division is driven by four facts, all
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
| Front-end rules mirrored with no drift guard | ~32 | **0** | H9, H10 |
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

### H3 — The guards the splits will lean on ✅ BUILT 2026-09-18
*Retro: `docs/retrospective-2026-09-18-code-health-h3.md`. TD-219, TD-240, TD-250 closed; the fence is package-aware for H11. Raised **TD-257** (22 endpoints no test drives — a Phase-2 backfill, after the H5 factory) and **TD-258** (HIGH: the sponsor fund view is outside the fence and a mock donation endpoint is live — reported, not patched; the owner's call).*
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

### H4 — The standards become tests, inside the gate
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

### H5 — A backend test factory that builds states the product can reach
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

### H6 — A render harness for the cockpit, and the stopgap guards retired
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

### H7 — Money and text helpers ⚠ touches money
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

### H8 — The income rule gets one served answer (TD-235) ⚠ touches eligibility
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

### H9 — De-mirror the front end, wave 1: the decision gates
- **Goal:** the rules that decide what an officer may do stop living in two languages.
- **Scope:** the template exists — `documentLimits.ts` and `interviewSlots.ts` are headed
  *"⚠ THE RULES ARE SERVED, NOT MIRRORED."* Apply it to: `ORG_REJECT_FROM`, the 13 application
  statuses, `OrgRequest` statuses + `TRANSITIONS`, `STR_COACH_STATES`, `PartnerAdmin.ROLE_CHOICES`,
  the assignment `bad_assignee` rule. One small `GET …/meta/` payload, cached, or the value on a
  payload the screen already loads.
  **Every mirror ends the sprint in one of two states: served, or drift-tested** (a test that
  reads the backend source, as `soft-evidence-drift.test.ts` does). None stays a comment.
  Add one reading to `code_health.py`: `mirror` = mirror comments in `src/lib` with no guard.
- **Acceptance:** each converted rule bite-checked from the **backend** side (change the Python,
  the web test or the screen follows); reading: `mirror` roughly halves.
- **Complexity:** medium. **~7h.** Both services deploy.

### H10 — De-mirror, wave 2: the rest
- **Scope:** `family.py` codes and `is_valid_person_name`, `clauseNumbering.ts`,
  `REQUEST_COMPONENT_TREE`, `invitations.status_of`, `reviewer_profile_complete`,
  `partner_comms.KINDS`, contrast + theme token families (already asserted on both sides — confirm
  and mark). Same two end states.
- **Acceptance:** `mirror` = 0.
- **Complexity:** medium. **~6h.** Both services deploy.

---

## Phase 4 — Make the big files small

**The rule for every sprint in this phase: moves only.** No renames, no "while I'm here", no
wording changes. Lesson 173: *"the temptation is to improve the wording in the same move — which
would make the diff unreviewable."* The proof of a move is a full green suite plus a diff that
`git diff -M --stat` reads as renames and re-exports.

**The freeze means one agent in the checkout.** If the owner lifts it at the checkpoint, each
remaining Phase-4 sprint opens with a line in `AGENT-TERRITORY.log` naming the files it holds and
for how long, and lands in **one** day.

### H11 — `views_admin.py` becomes a package, wave 1
- **Scope:** `views_admin/__init__.py` re-exports all 142 names, so `urls.py` is **byte-identical**.
  Move the six domains with their own service module and no shared helper (~3,200 lines):
  requests (831), gift programmes + intake years (866), invoices (455), contracts (421),
  payments (365), sponsor terms (297). `_AdminBase` stays in `views_admin/base.py` — tenancy
  rule 3: org scoping lives in the base gates, and every moved view still inherits it.
- **The four known trip-wires, all found in the survey:**
  1. `logger = logging.getLogger(__name__)` — twelve `assertLogs('apps.scholarship.views_admin')`
     sites break on a new logger name. Every submodule uses the explicit old name.
  2. `test_org_fence.py` opens `views_admin.py` by filename (made package-aware in H3).
  3. Eight private helpers are imported by tests from the package root — re-export them.
  4. 19 `patch('apps.scholarship.views_admin.build_verdict' / '.refine_sponsor_profile')` strings
     point at re-exported imports; they follow the code in wave 2, not here.
- **Acceptance:** `urls.py` unchanged; pytest identical count, green; org fence green **and**
  bite-checked in a moved file; reading: `hot#1` falls by about a third.
- **Complexity:** medium. **~6h.** api deploy.

### H12 — `views_admin` wave 2
- **Scope:** the remaining nineteen domains (applications/verdict/QC, interviews, sponsors,
  sources, reviewers, billing, org configuration, spending, overview…). The 19 patch strings move
  with `build_verdict` and `refine_sponsor_profile`. `interview_agenda_full` has zero callers
  outside one test — confirm dead, delete (the only deletion in the phase).
- **Acceptance:** `__init__.py` holds re-exports only; no file in the package over ~900 lines;
  reading: `hot#1` under 100.
- **Complexity:** medium. **~7h.** api deploy.

### H13 — `admin-api.ts` and `api.ts` become barrels
- **Scope:** `src/lib/http.ts` takes the four private fetch helpers (they are *not* shared today:
  `apiRequest` handles `nric_required` and field errors; `adminFetch` does not — keep both
  behaviours). `src/lib/admin-api/{applications,billing,requests,…}.ts` behind
  `admin-api/index.ts`; same for `api/`. All 133 + 78 importers use the alias
  `'@/lib/admin-api'` with zero deep imports → **no importer changes.** Two domains split across
  non-contiguous spans today (Requests, Payments) come back together for free.
- **⚠ Two gotchas:** `isolatedModules` is on, so types need `export type *` (tsc is the gate, and
  since today it is a real one). And 30 tests `jest.mock('@/lib/admin-api')` — **first task:
  convert one small file and run the full suite** before doing the rest.
- **Acceptance:** zero importer edits; jest, tsc, lint, `next build` green; bundle size not larger.
- **Complexity:** low–medium. **~5h.** web deploy.

### H14 — The cockpit and the documents component, panel by panel
- **Depends on H6** — not negotiable.
- **Scope:** `view.tsx`: about 1,300 of 2,528 JSX lines sit in panels coupled only to `app`, `t`,
  `token` and one to three handlers — documents drawer (304), disbursement ledger (122), org-admin
  reject wizard (98), QC (98), blockers (88), bursary agreement, witness, assign, closure,
  reporting date. They move to `src/components/admin/cockpit/`. **The Decision/Recommendation
  panel (264 lines, ~9 handlers, the tangle) stays put** — untangling it is design, not a move.
  `ScholarshipDocuments.tsx`: the checklist family (616 lines, all `(doc, t) => JSX`, no state)
  and `IncomeWizard` (539) move out.
  `useApiLoad(token, fn)`: ~26 of the 33 `exhaustive-deps` disables are one shape (the omitted dep
  is always `t`). One hook retires them; the four with a written reason stay.
- **Acceptance:** H6's rendered tests green unchanged; `theme.test.ts` path list re-pointed and
  bite-checked; `view.tsx` under ~2,000 lines; `supp` down ~25.
- **Complexity:** medium–high. **~9h.** web deploy.

### H15 — `models.py` and `services.py`
- **Scope:** `models/` package with full re-export — `ScholarshipApplication` is a wide table
  (159 fields, 3 methods), not a fat class, so this is a file move. 310 importers, 3 patch sites,
  and migrations address models by label, not by file. `services.py` splits on its existing
  seams (blockers, assignment, decline, confirmation, consent) behind a re-exporting shim.
- **Acceptance:** `makemigrations --check` clean — **a models move that generates a migration is a
  failed move**; pytest green.
- **Complexity:** low–medium. **~6h.** api deploy.

### H16 — `emails.py`, `income_engine.py`, and the back-edge
- **Scope:** `emails.py`: copy constants (1,005 lines of EN/BM/TA) out to `email_copy/`; senders
  by domain. The safety net is `test_email_branding.py` — a byte-identity golden over every
  `send_*`. ⚠ **Never set `UPDATE_EMAIL_GOLDEN` during this sprint**; it would bless the
  regression. `income_engine.py`: its 21 banner sections become a package; the 43 patch sites sit
  on public functions that move whole. `courses → scholarship`: six of the 25 back-edges are
  plain numeric constants → `scholarship/constants.py`; the single module-level import
  (`courses/views_admin.py:33`) goes lazy.
- **Acceptance:** email golden byte-identical; both golden masters unchanged; `xapp` back-edge
  under 20.
- **Complexity:** medium. **~7h.** api deploy.

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

## Phase 6 — Lock it in, and lift the freeze

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
  - Close out: final reading against the targets table; TD entries for anything missed; retro for
    the whole arc; **lift the freeze** — update `CLAUDE.md` Next Sprint, the MEMORY.md registry,
    Mission Control, and tell BrightPath their queued requests are open again.
- **Acceptance:** a dry run — a throwaway branch that adds a 700-line file, a mirrored rule, a
  hand-built fixture and a query in a loop is refused **four times, by four different tests**,
  without anyone remembering anything.
- **Complexity:** low–medium. **~6h.**

---

## Sequence, and what blocks what

```
Phase 1   H1 -> H2 -> H3 -> H4
Phase 2   H5 -> H6
Phase 3   H7 -> H8 -> H9 -> H10        <-- CHECKPOINT: "stabilised" - the owner may lift the freeze
Phase 4   H11 -> H12 -> H13 -> H14 -> H15 -> H16
Phase 5   H17 -> H18
Phase 6   H19                          <-- "completed" - the freeze lifts
```

- **H1 → H2 → H3 → H4 are strictly first.** Every later sprint is safer once a red suite cannot ship.
- **H6 blocks H14.** H3 blocks H11. H5 should precede H7/H8 (their tests use the factory).
- Phases 3 and 4 do not block each other; Phase 3 goes first because it is the half that prevents bugs.
- **Back to back, by owner ruling.** With the product frozen there is one agent in the checkout,
  which removes Phase 4's biggest risk (a file changing under a move).
- **If the owner lifts the freeze at the checkpoint**, the remaining sprints alternate with product
  work, and a feature sprint that must change a file still on the hotspot list pulls that file's
  Phase-4 sprint forward instead of adding to it.

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

**Still needed:**
1. **The word to start H1.** (The freeze is already in force.)
2. **H2:** agree to switch the two Cloud Build triggers to committed config files — the one change
   here that touches production infrastructure. Needed when H2 starts, not before.
3. **At the checkpoint (after H10):** lift the freeze, or run to the end.
