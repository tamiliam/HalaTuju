# Retrospective — Requests list R1: tabs, filter, search, pager and Previous / Next (2026-11-03)

Plan of record `docs/plans/2026-11-03-requests-list-r1-roadmap.md`; design of record the "Requests list" artifact
(https://claude.ai/artifact/KaYimA2jWrJdfpLEaCKYBF); owner approved the design and option A on 2026-11-03. Platform
work, not billed. LIVE 2026-11-03: api `8e69ecdd` (build 1114af85, `halatuju-api-01242-ntg`), then web `2da37ff4`
(build a972cc1e, `halatuju-web-01070-c44`; the same build carried Team tables T3's web, agreed with that session).
No migration.

## What Was Built
- **A paged, light list on the server** (`AdminOrgRequestListView.get`): the shared pagination envelope, 25 a page,
  plus `summary` (four tab counts of the WHOLE fenced list) and `ids` (the page in order). Filters `?group`, `?kind`
  (effective kind), `?q` (title or `#id`), `?org` (crumb, inside the fence). Unknown group / kind is a 400. A row is
  `{id, title, kind, status, submitted_by_name, created_at, tags}` (+ `organisation_name`, `filed_kind` for the
  owner) — no thread, attachments or analyses, so no Supabase URL is signed per row.
- **One Needs-action rule** (`apps/scholarship/org_requests_queue.py`, `needs_action_q`) shared by the nav badge and
  the Needs-action tab; the tabs partition the list; row tags are served per role.
- **The web list** (`components/admin/RequestsList.tsx`): counted `PanelTabs`, kind filter, debounced search,
  "Showing a–b of N", the shared `Pagination`, URL state, latest-reply-wins tickets. Lands on Needs action.
- **Detail Previous / Next** (`lib/listNav.ts` + `components/admin/RequestListNav.tsx`): "‹ Back to <tab>",
  "‹ Previous · n of m · Next ›", ← / → with the usual exclusions. TD-477 for the Applications cockpit.
- **Fixed by replacement:** the status dropdown, which had never filtered anything.

## What Went Well
- **Reading the code before planning found the dead filter.** The plan's "what exists" table, read rather than
  inherited, noticed that the web sent `?status=` and the server never read it — so the sprint replaced a broken
  control instead of re-skinning it, and the new filters refuse an unknown value instead of silently showing all.
- **One rule, called twice.** Moving the Needs-action predicate into one `Q` let the badge and the tab share it; a
  test asserts the count endpoint equals the tab for both roles, and the existing TD-201 / TD-205 count tests passed
  unchanged across the move.
- **The list got cheaper, not just tidier:** query budgets fell (super 6 → 5, super narrowed 7 → 6) and per-row
  Supabase signing disappeared.
- **Release order held:** api first (old web reads `group=all` by default), then web.

## What Went Wrong
- **The builder's report said all green; the lead's full run was not.** *Symptom:* one subtest of
  `test_document_snapshot.py::TheSnapshotChangesNoResponseByte::test_tagged_and_untagged_income_documents` failed in
  the lead's full `-n auto` run; it passed on two re-runs (serial and `-n 4`). *Cause:* a flake unrelated to R1 — and
  the builder's "green" was a run that did not hit it, which is what a flake does. *System change:* TD-478 raised
  with the subtest's coordinates and a capture plan; the lead's own full run of the gate's command line remains the
  gate (lessons: "the existing tests pass is a full-suite claim").
- **A subset run made a completeness guard look red.** *Symptom:* `test_org_fence::TestFenceCoverageCompleteness::
  test_no_stale_classifications` failed in a subset run (AdminSystemHealthView "stale"); green in the full run.
  *Cause:* the completeness check reasons over every view the whole suite collects; a subset collects fewer, so
  "stale" was an artefact of the selection. *System change:* lesson added — a completeness guard's verdict counts only
  from a full run.
- **TD number collision at rebase.** *Symptom:* Team tables T2 took TD-475 while R1 was building; R1's entry was
  renumbered TD-477 at rebase. *Cause:* two sessions pick "next free" from their own checkouts. *System change:* none
  new — the existing practice (re-grep the register after every rebase, before the close commit) caught it; this
  close re-grepped before raising TD-478 / TD-479.
- **T3's web build failed on an unrelated jest test.** *Symptom:* build c013be40 failed
  `src/app/scholarship/apply/page.gift.test.tsx` under load; the next build passed. *Cause:* the
  test asserted before the profile prefill landed (the M4 lesson's pattern). *System change:* fixed on main by
  `159e824f` (the test now waits for the prefill); TD-479 recorded and closed for the trail.
- **Stitch timed out.** *Symptom:* the design could not be produced in Stitch. *Cause:* Stitch generation time-outs
  (a known pattern). *System change:* the design was approved as a Design artifact instead — the visual-approval
  step was kept, only the tool changed.

## Design Decisions
See decisions.md 2026-11-03 "Requests list R1". In short: the tabs partition the list (owner option A); one
Needs-action predicate for badge and tab; Previous / Next walks the current page only, via `lib/listNav.ts`, with
the Applications cockpit adopting it after Mobile M6b (TD-477); tab counts are of the whole fenced list, never the
kind / search filter; the server default stays `group=all` so an old caller reads what it always did.

## Close Review (step 4b — diff `8e69ecdd` + `2da37ff4`)
Reviewed by reading the diff (server queue / serializers / views; web list, nav hook and component). No correctness
bug found; no product code changed at close. Findings, each answered:
1. **The org badge's window moved from a literal `('done', 'declined')` to `TERMINAL_STATUSES`.** Checked: the tuple
   is `('done', 'declined')` — identical. Accepted, no change.
2. **`~needs_action_q(...)` over nullable columns could drop rows from both In progress and Needs action** (SQL
   three-valued NOT). Checked: Django adds `IS NOT NULL` guards when negating a lookup on a nullable column, and the
   partition test pins every fixture row to exactly one working tab. Accepted.
3. **Previous / Next stops at the page edge, and the record is a snapshot** — a request that changes tab while open
   still walks in its old list. By design (D7); cross-page is a follow-up (TD-477). Accepted.
4. **`RequestListNav` keeps the pressed step in a module-level variable** (to survive the remount a new request's
   page may cause). Harmless: one detail page at a time, cleared on first use. Accepted.
5. **A page past the end is a 404 from the paginator;** the web steps back to page 1 once before concluding the
   feature is dark. Correct, and tested on both sides. Accepted.

**Bite-checks (close):** two faults injected, restored from the original bytes and verified by digest: (a)
`tab_counts` In progress counted without excluding Needs action → `TestTheTabsPartitionTheList` must go red; (b) the
org badge counting quotes only → `TestTheBadgeAndTheTabAgree` must go red. Both BIT: (a) 2 failed / 6 passed,
(b) 1 failed / 1 passed; each needle matched exactly once; both files restored and digest-verified;
`test_requests_list.py` clean afterwards (26 passed, 10 subtests).

## Numbers
- api: 12,015 passed / 3 skipped / 0 failed (`python -m pytest -q -n auto -p no:cacheprovider`, the gate's command
  line, on the rebased tree); `check` clean; `makemigrations --check` no changes.
- web: `npm run gates` green — jest 6,238 tests / 402 suites; bundle-budget ok, median 143.88 kB (1.1–1.3 kB under 145).
- mobile-check (step 1b): NOT measured at close. Run from the R1 worktree (node_modules is a junction to the main
  checkout), `next dev` served pages that never hydrated: every cell timed out on "wait for <html lang>" (21 of 21
  before the run was stopped), public pages R1 never touched included — an environment fault, not a page result.
  `/admin/requests` has no sandbox surface in `targets.ts` either, so it would not have been measured; the only
  layout change is `PanelTabs` gaining `flex-wrap`. Ledger not regenerated. To do from the main checkout.
- Query budget: Requests list 5 / 5 (org_admin), 5 / 5 (super, was 6), 6 / 6 (super narrowed, was 7).
- Deploys: api 1, web 1 (the web one shared with Team tables T3).
- Debt: TD-477 raised (Applications adopts the hook); TD-478 raised at close (an unrelated flake, open); TD-479 raised and closed (fixed by `159e824f`).
