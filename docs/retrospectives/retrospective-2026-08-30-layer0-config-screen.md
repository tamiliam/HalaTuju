# Retrospective — Layer 0 Sprint 5: "What we ask for" (2026-08-30)

Branch `feat/layer0-sprint5-screen` (worktree `.worktrees/layer0-sprint5`). No migration.
**Layer 0 is complete:** the catalogue (S2), documents (S3), questions (S4), the submit-time
snapshot and the Check-2 pass (the two 3a deferrals), and now the screen an organisation touches.

## What Was Built

- **The endpoint.** `AdminProgrammeConfigurationView` — one org-fenced GET/PUT over the catalogue
  seam. Reads the whole catalogue with the programme's state per row plus a real count of
  applicants in flight. Writes are all-or-nothing, core rows are floored (`400 core_item`), a
  foreign programme is `404`, every changed row is audited. The live rule it writes through is the
  same one `resolve()` reads (`requirements.programme_states`, extracted this sprint), so the
  screen cannot drift from what the student form enforces.
- **The screen.** `/admin/programme`, built to the Stitch design of record with the three stated
  corrections (no mock shell, no orange nav, "Always required" muted to grey sentence case, a
  neutral footer). Documents and questions as rows in one list; three-state segmented control;
  locked rows visible with their reason; the income row heavier; the amber warning above the
  controls naming the counted number; Save as a computed diff with every outcome on screen.
- **The harness.** Two sandbox surfaces (full and lean programme) through a `WithAdminAuth`
  wrapper, reviewed in the browser before the docs were written.

## What Went Well

- **The seam paid for itself.** The endpoint is ~120 lines because Sprints 2–4 put the rule in one
  place. Extracting `programme_states` was a five-line move, and the "switched-off question
  ungates a NEW application" test passes through the real completeness gate with no mocking.
- **The rendered test found a real bug before the browser did** (below). A jsdom test of the real
  page, not the pure helpers, is what caught it.
- **Bite-checks on both halves.** Backend: core refusal + org filter disabled → 9 tests fail.
  Frontend: the Save-diff and outcome tests fail if the diff or the outcome lines are removed.
- **Zero deploys spent on UI.** The design was approved a month ago; the build matched it on the
  first browser look.

## What Went Wrong

1. **The page re-read the server over an unsaved draft.**
   *What:* three rendered tests failed — the role gate test saw 100 fetches, and two save tests
   found the draft reset.
   *Why:* `load` was a `useCallback` that depended on `t` (the translator) because it translated
   the load-error text. The test's `useT` mock returns a fresh `t` each render, so the effect
   re-fired every render, and each fetch's `setConfig` wiped the draft. Production `useT` may or
   may not be stable — the page was one hook change away from the same bug live.
   *Fix:* the loader depends on the token and the gate only; the error is stored as a flag and
   translated at render. **System change:** added to `docs/lessons.md` — a data loader never
   depends on a translator/formatter handle; translate at render.

2. **The worktree had no `node_modules`, and the gates silently ran the wrong thing.**
   *What:* `npx jest` began installing jest 30 from the network and then failed on `ts-jest`;
   `npx tsc` printed "this is not the tsc you are looking for".
   *Why:* a fresh worktree does not share the main checkout's install, and `npx` falls through to a
   network fetch instead of failing.
   *Fix:* a directory junction to the main checkout's `node_modules` (not committed; gitignored).
   **System change:** noted in `parallel-work-isolation.md`'s spirit — the sprint-start checklist
   for a web worktree should link or install `node_modules` before any gate is trusted.

3. **`tsc --noEmit` reports 24 errors on main.** Not from this sprint (all in older test files:
   iteration targets and loose casts), identical count on main and on the branch. The "tsc gate"
   is therefore not actually gating; `next build` (which type-checks app code, not tests) is.
   Logged as tech debt rather than fixed here — it is a separate cleanup.

## Design Decisions

- **The catalogue is not a fence** — the page's `mayView` only avoids rendering a page that would
  403; the endpoint is the authority. Cross-org stays 404.
- **Core rows show all three states with two disabled**, rather than hiding the control. The lock
  is legible and read from `is_core`, never a constant (the IC-padlock lesson).
- **Save outcome is a closed union** (`idle | saved | core | error`) with a line for each; adding
  a value without a line is the #20 bug returning.
- **No confirmation dialog.** The warning names the number above the controls (owner decision 4).
- **The nav placeholder became the page.** `programmeOverview` had no page behind it; admin and qc
  lose an empty slot rather than gaining a page they cannot use.

## Numbers

- Backend: 5666 → **5677** pytest (+11). Web: 1474 → **1482** jest (+8: 7 page, 1 sandbox fixture
  coverage). `next build` clean; `next lint` 0 errors; i18n parity 4581 keys per locale.
- Files: backend 4 (view, urls, requirements, fence test) + 1 test file; web 13.
- Deploys: 0 so far (the merge to main deploys api + web together).
