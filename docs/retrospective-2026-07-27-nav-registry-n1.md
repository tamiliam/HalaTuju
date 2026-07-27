# Retrospective — Nav/IA Sprint N1: one route registry behind the admin menu

**Date:** 2026-07-27 · **Commit:** `20d683b4` (+ `39732b62`, a ported backend test)
**Build:** `39732b6` SUCCESS both services · api `…00886-zgt`, web `…00729-hth`
**Plan:** `docs/plans/2026-07-27-nav-ia-roadmap.md` · **Design of record:**
<https://claude.ai/code/artifact/17d259a8-f15f-4f0a-858e-492f1cb157a6>
**Migration:** none. **Backend change:** none (one test ported).

---

## What Was Built

First of three sprints restructuring the partner console's navigation. The deliverable was
deliberately invisible: **the menu renders exactly as it did, for all seven roles** — what changed is
that it now comes from data instead of a chain of role checks.

- **`halatuju-web/src/lib/navigation.ts`** — every admin route, grouped by the scope it belongs to
  (platform / organisation / programme / utility), each carrying its i18n key, the roles that may see
  it, and how it is gated. Pure, no React, no fetch; node-testable like `adminLanding.ts`.
- **`effectiveRole()` / `canSee()` / `visibleNav()` / `activeItem()` / `canAccess()`** — the shared
  predicate. `effectiveRole` replaced **17** hand-written copies of `is_super_admin ? 'super' : role`
  across the layout, 13 admin pages, `sessionPolicy.ts`, the login page and the OAuth callback.
- **`navigation.test.ts`, 61 tests** — i18n parity for every registry label across en/ms/ta; a
  per-role visibility snapshot; active-route resolution for every href, alias and nested detail page;
  dark-ship probe semantics; and a drift guard that reads the app router off disk.
- **`admin/layout.tsx`** — the seven-branch ternary and the hand-written `isActive` are gone; the bar
  renders from the registry. The sponsor badge no longer re-derives who may see it.
- Four nav group headings in en/ms/ta (ms/ta first drafts).

**Numbers:** jest **863 passed** / 57 suites (+61) · i18n parity **4034 × 3** · backend **4859
passed** · `tsc` clean · 25 files, inside the 40-file cap.

---

## What Went Well

- **The registry paid for itself before it shipped.** Two of the three bugs below were found by
  tests written against it, not by reading code. Encoding "who sees what" as data made the wrong
  answers visible.
- **Deriving role sets from the existing guards, not the plan.** Every `roles:` array was written by
  opening the page and reading its actual `allowed` / `canManage` expression. That is why N1 changed
  no behaviour, and it caught that `sponsors` and `requests` have *no* client guard at all — so the
  registry deliberately added none.
- **The lessons pass was not ceremony.** Four entries in `lessons.md` applied directly and each
  changed the code: every test collection is derived or read off disk rather than hand-copied, the
  dark-ship gate carries no client flag, and the one mirror kept has cross-references in both
  directions plus a snapshot test.
- **Three-agent coordination held.** Two other agents were working the same repo. Both their
  ancestry claims were verified against the real git graph before acting, both were true, and the
  push order was chosen so each build stayed attributable to its own SHA.

---

## What Went Wrong

**1. The plan's scope estimate was wrong by 70%, and only an unfiltered grep caught it.**
*Symptom:* the approved plan said "ten pages re-derive the role"; the real figure was 17 files.
*Root cause:* the exploration that produced the estimate used a truncated search. `lessons.md`
already carries this exact lesson from 2026-07-23 ("never conclude a thing DOESN'T EXIST from a
search you truncated") — it was applied to *verifying* the claim but had not been applied when the
claim was *made*, one phase earlier.
*System change:* the lessons pass now runs **before** the file-count estimate is committed to a
plan, not after. Recorded as a lesson so the next planning phase re-derives counts with `head_limit:
0` rather than trusting a summary.

**2. `/admin` silently swallowed every unrecognised route.**
*Symptom:* `canAccess('/admin/anything-new', 'reviewer')` returned `false` — a refusal for a page
nobody had declared.
*Root cause:* longest-prefix matching is correct for `/admin/payments/7 → payments`, but `/admin` is
a prefix of *every* admin URL, and it is an index page whose siblings are separate routes rather
than its children. I implemented one matching rule where the data needed two.
*System change:* `NavItem.exact` marks index routes, and a test asserts an unknown route resolves to
`undefined` rather than to the dashboard. The general form — "a prefix rule needs an exception for
the root of the namespace" — is now in `lessons.md`.

**3. I deleted a build log before reading it, and had to re-run a nine-minute build.**
*Symptom:* `next build` exited 1; the log had already been removed in the same command.
*Root cause:* the cleanup (`rm -f`) was chained onto the inspection command, so it ran regardless of
outcome — convenience wired ahead of the failure path.
*System change:* never chain the removal of a diagnostic artefact onto the command that produces it;
delete it after the result has been read and acted on. Cheap, but it cost a full rebuild on a box
where builds are already memory-constrained.

**4. Two agents wrote the same test suite in parallel.**
*Symptom:* my uncommitted `test_platform_cost.py` additions (118 lines) duplicated
`test_billing_rates.py`, which another agent had already pushed. Their handoff flagged the overlap
and proposed consolidating "in a tidy-up, not before a deploy".
*Root cause:* no coordination on test-file ownership when two agents work adjacent areas of the same
module; both independently noticed the same untested behaviour.
*System change:* the duplicate was **deleted rather than shipped** — two files asserting one contract
is precisely how a behaviour change updates one and not the other. The single assertion that was
genuinely new (hours fenced to the *month*, not just the organisation) was ported into the surviving
file. Recorded as a lesson: consolidating a duplicate is a *deletion*, which is lower risk than
shipping it, so "tidy up later" is the wrong default.

**5. Toolchain flakiness muddied the verification signal.**
*Symptom:* jest died once with a Windows spawn error (`errno -4094`) and `next build` failed once,
both passing on retry.
*Root cause:* documented memory pressure on the 8 GB dev box after a full test run — already noted in
`halatuju_api/CLAUDE.md`.
*System change:* none needed in code, but the retrospective records it explicitly rather than
reporting a clean run, because "failed once, passed on retry" is indistinguishable from a real
intermittent bug. `tsc --noEmit` is the authoritative type check on this machine and was clean.

---

## Design Decisions

Logged in full in `docs/decisions.md` (2026-07-27):

1. **Scope grouping, with today's bar order preserved by transitional fields.** `NAV_GROUPS` carries
   the target structure; `chrome` / `hubParent` / `LEGACY_BAR_ORDER` reproduce the existing sequence
   so N1 is visually inert. Tracked as **TD-181** so the scaffolding cannot become permanent.
2. **The registry is not the fence, and says so.** Nav visibility is UX; the org fence and endpoint
   role gates are untouched. The module docstring cites the 2026-07-15 surface-partition incident
   ("nav hid it, backend didn't") so the next reader cannot mistake it for access control.
3. **Dark-ship gating reads the API's 404, never a client flag.** `unknown` and `dark` both mean
   not-live, so a dark feature cannot flash in during the round trip.

---

## Numbers

| | Before | After |
|---|---|---|
| jest | 802 / 57 suites | **863** / 57 suites |
| i18n keys × 3 locales | 4030 | **4034** |
| backend pytest | 4848 | **4859** (+11; one test ported, one duplicate suite removed) |
| Copies of the role normalisation | 17 | **1** |
| Admin routes with no menu home | 6 | **0** |
| Admin routes that highlighted nothing | 3 | **0** |
| Files touched | — | 25 (cap 40) |

---

## Carried Forward

- **▶ N2 (next):** the shell — scope sidebar, breadcrumb, ⌘K palette, help + account menus,
  notification bell aggregating counts the console already fetches. No backend, no migration.
  Deletes TD-181.
- **▶ N3:** org/programme switchers (one new org-fenced endpoint, classified in `test_org_fence.py`)
  + the Administration route split.
- **Owner review:** Malay and Tamil nav group headings are first drafts.
- **Resolved during close — a near-miss worth recording.** A concurrent agent's handoff reported
  "3584 passed" at this HEAD, against a recorded baseline of 4809. I drafted this retrospective
  quoting 3584 and only caught it by running the full suite as step 10 of sprint-close mandates:
  the real figure is **4859**, and 3584 was a subset run (`apps/scholarship` alone). Two lessons
  fell out — a quoted test count is not a measured one, and the sprint-close instruction to run the
  full suite across *all* directories exists precisely to catch this. The number was never wrong in
  the repo, only in the draft; it would have been wrong in the record had the step been skipped.
