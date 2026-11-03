# Requests list R1 — roadmap (2026-11-03)

**Status:** ✅ DONE — LIVE 2026-11-03 (api `8e69ecdd` → `halatuju-api-01242-ntg`; web `2da37ff4` →
`halatuju-web-01070-c44`; no migration). One-sprint plan, kept as the record; retrospective
`docs/retrospectives/retrospective-2026-11-03-requests-list-r1.md`. Follow-up: TD-477 (Applications adopts
`lib/listNav.ts` after Mobile M6b).

**Original status:** PLAN, awaiting the owner's go. The sprint itself was approved by the owner on 2026-11-03 (design of
record: the "Requests list" artifact, https://claude.ai/artifact/KaYimA2jWrJdfpLEaCKYBF). Planned on branch
`requests-list` at `origin/main c78552d9`. Platform work on the admin Requests module, **not billed**.

**Scope line.** The list at `/admin/requests` becomes a paged, server-filtered list with four tabs, a kind filter and
a search box. The detail page `/admin/requests/<id>` gets "Back to <tab>" and Previous / Next. Nothing about a
request's life changes: no transition, no permission, no e-mail, no model, no migration. The submit form and the
rate card on the same page are untouched.

---

## 0. What exists (read 2026-11-03, not inherited)

| Thing | Where | Today |
|---|---|---|
| List endpoint | `AdminOrgRequestListView.get` (`views_admin/requests.py:118-151`) | Unpaged. Serves the FULL detail payload per row (comments, attachments with a signed Supabase URL each, and for a super every analysis), prefetched so it is flat per row (TD-291, budgets 5 / 6 / 7). `?org=` narrows inside the fence (TD-228). **`?status=` is sent by the web and ignored by the server** — the status dropdown has never filtered anything. |
| Count endpoint | `AdminOrgRequestCountView.get` (`requests.py:196-250`) | The nav badge. Super: `submitted` OR (`triaged` + `triaged_kind='feature'` + no live approved analysis) — decisions.md TD-205. org_admin: own org, not terminal, AND (`quoted` OR a comment `awaiting_reply`). |
| Web list | `src/app/admin/requests/page.tsx` (386 lines) | Rate card + submit form + status dropdown + list. Derives the row tags in the browser: "Answer needed" from `requestActionsFor(...).includes('answer')` + `hasUnansweredQuestions(r.comments)`; "Analysed" / "Analysis to approve" from `listAnalysisTag(r.status, r.analyses)`; kind chip from `effectiveKind` / `filedKindDiffers`. |
| Consumers of the list payload | grep `getOrgRequests` | **Only the list page** (plus its two test mocks `page.orgcrumb.test.tsx`, `page.paste.test.tsx`). The badge (`useNavProbes.ts`) uses the count endpoint; the detail page uses `getOrgRequest(id)`. So the heavy fields can leave the list with no other reader affected. |
| Applications prev/next | `admin/scholarship/page.tsx:237-247` writes sessionStorage `halatuju_admin_scholarship_nav` (ids only); `scholarship/[id]/view.tsx:172-183` reads; `view/CockpitHeader.tsx:50-63` draws | Ids of the current page; hides when the id is not in the list; no keyboard, no position, no "back to" label. |

## 1. Scope

1. **Server.** `AdminOrgRequestListView.get` paged with `FlexiblePageNumberPagination` (25, `?page_size` ≤ 100,
   `paginator.envelope(rows, results_key='requests', summary=…)`), serving a LIGHT row; filters `?group`, `?kind`,
   `?q`, `?org`; `summary` counts for the four tabs. The Needs-action rule extracted ONCE and used by both the list
   and the count endpoint. POST (create) unchanged.
2. **Web list.** The list moves out of `page.tsx` into `components/admin/RequestsList.tsx`; `PanelTabs` with counts,
   a Bug reports / Features filter, a debounced server-side search, "Showing a–b of N", the shared `Pagination`;
   tab / kind / q / page kept in the URL.
3. **Detail Prev / Next.** One shared hook (`src/lib/listNav.ts`) + one component (`components/admin/RequestListNav.tsx`)
   on the detail page: "‹ Back to <tab>" and "‹ Previous · 2 of 7 · Next ›", greyed at the ends, ← / → keys.
4. **i18n** en / ms / ta under `admin.requests.*` (Malay and Tamil first drafts, Sol-tagged).
5. **Tests** api + rendered web, query budget falls.

**Not in R1:** converting Applications to the shared hook (see D8), paging across a page boundary from the detail
page (D7), any change to who sees what.

## 2. Decisions (taken here; one line of reason each)

- **D1 — Groups partition the list; All = the sum.** `action` = the shared Needs-action predicate; `progress` = not
  terminal AND NOT needs-action; `closed` = `done` / `declined`; `all` = everything. Reason: with the brief's literal
  In progress (triaged…deferred) an org_admin's plain `submitted` request sits in **no tab but All** (it is not
  Needs-action for them), and a super's untriaged feature would show in two tabs. A partition means every request
  is in exactly one working tab and the numbers add up, which is what a reader assumes when four pills sit in a row.
  Needs-action ⊆ not-terminal holds for both roles today (super: submitted/triaged; org_admin: excludes terminal),
  and a test pins it.
- **D2 — Tab counts ignore `kind` and `q`; they follow the fence and `?org=`.** decisions.md "A tab's count is of the
  WHOLE list" (S7, 2026-09-11) and the `PanelTabs.count` docblock: a number that moves as you type stops being the
  thing you came to read. `?org=` is not a filter in that sense — it chooses WHICH list (the crumb). The filtered
  total is the "Showing a–b of N" line beside the pager.
- **D3 — The Needs-action rule is ONE function returning a `Q`,** `needs_action_q(is_super)` in a new
  `apps/scholarship/org_requests_queue.py`, written with `Exists(...)` subqueries (no multi-valued annotate, so it can
  sit inside `aggregate(Count('id', filter=…))` and inside `.filter()` without fan-out). `AdminOrgRequestCountView`
  switches to `qs.filter(needs_action_q(...)).count()`. The existing TD-205 / TD-201 count tests are the
  characterisation that must stay green unchanged, plus one new agreement test (count == `summary.action` for
  both roles over a mixed fixture). Not in `org_requests.py`: that file is **845 lines against 825 + 20 = 845, no
  room at all**.
- **D4 — Tags are served, per role, never derived in the browser.** A row carries `tags: [...]` of
  `answer_needed` (org_admin only: a comment `awaiting_reply` AND status in `OPEN_FOR_SHAPING` — the same window as
  the answer box, as today), `analysis_draft` / `analysed` (super only, status `submitted`, live = not superseded;
  approved wins — `listAnalysisTag` today). Computed as `Exists` annotations on the page query, so a row still costs
  nothing. `listAnalysisTag` / `listAnalysisTagKey` then have no caller and are **deleted** with their tests in
  `requestAnalysis.test.ts` (keep the i18n keys — the served tag names them).
- **D5 — Two light row serializers, allowlist + exact-key snapshot each,** in `serializers_org_requests.py` (327
  lines): org row `{id, title, kind (EFFECTIVE, as the org serializer's get_kind), status, submitted_by_name,
  created_at, tags}`; owner row adds `organisation_name` and `filed_kind` (the filed kind, only when triage changed
  it — the "Filed as X" chip; the org row never carries it, owner instruction 2026-10-29). No description, comments,
  attachments, analyses, so **no Supabase signing on the list**.
- **D6 — Filters.** `?kind=bug|feature` on the effective kind (`triaged_kind` if set, else `kind` — `_effective_kind`;
  the builder confirms whether an untriaged `triaged_kind` is `''` or NULL and handles both). `?q=`: title
  `icontains`, OR id equal when `q` is `#N` / `N`. Unknown `group` / `kind` → 400 `bad_filter` (not a silent "all").
  Order `-created_at, -id` (the id breaks ties so paging is stable). The envelope also carries `ids` = the ordered
  ids of the page, which the web hands to Prev / Next.
- **D7 — Prev / Next walk the PAGE you came from,** "i of n" within it, greyed at its ends (the Applications
  behaviour). Crossing to the next page would need a fetch from the detail page; at 25 a page and today's volume
  (~50 requests over all organisations) it is rare. Named as a follow-up, not built.
- **D8 — Build the shared hook now, convert Applications LATER.** Mobile M6b (the cockpit case page, next in the
  other stream) re-lays-out exactly `CockpitHeader.tsx`'s Prev / Next (44 px) and `view.tsx`; converting here would
  collide with it, and `view.tsx` has 2 lines of room (1356 vs 1338 + 20). The hook is storage-injectable and
  unit-tested, so M6b (or a small change after it) swaps Applications onto it by deleting code. Recorded as a TD.
- **D9 — Default tab: Needs action** — the reason anybody opens the page; the badge that brought them there counts
  exactly that tab. If it is empty the tab says 0 and the reader picks another; we do not auto-switch (a landing tab
  that moves is the "count that changes under you" problem again).
- **D10 — URL state.** `?tab=&kind=&q=&page=` via `useSearchParams` + `router.replace` (precedent:
  `admin/sponsors/page.tsx`); defaults are left out of the URL. The sessionStorage record written for Prev / Next
  carries the list's own URL, so "Back to <tab>" returns to the same tab, filter, search and page.
- **D11 — Keys.** ← / → move only when focus is not in input / textarea / select / contenteditable, no modifier is
  held, the event is not already `defaultPrevented`, and no dialog is open (`[role="dialog"]` — the detail page's
  confirm Sheets). Same "typing" test as `AppShell`'s ⌘K handler, plus `SELECT`.
- **D12 — The status dropdown goes.** CHANGELOG: "the status filter never filtered (the server ignored `?status=`);
  fixed by replacement with tabs". `admin.requests.list.filterAll` is reused as the All tab label.

**Owner questions:** none blocking. One to confirm at plan approval: **D1** (tabs partition, so In progress also
holds untriaged requests that are not waiting on anyone) — it differs from the literal brief.

## 3. Files

Ledger room = (budget + 20) − now, from `halatuju-web/code-standards.json` / `halatuju_api/code-standards.json`
`budget.oversize_files`. "—" = not ledgered (a non-ledgered file may not pass 600).

| File | Lines now | Ledger | Change |
|---|---|---|---|
| `halatuju_api/apps/scholarship/views_admin/requests.py` | 504 | — (≤600) | list GET paged + filters + summary; count GET calls the shared predicate (net ≈ +25) |
| `halatuju_api/apps/scholarship/org_requests_queue.py` | NEW | — | `needs_action_q`, `group_q`, `kind_q`, `search_q`, `summary`, `annotate_tags` (≈120) |
| `halatuju_api/apps/scholarship/serializers_org_requests.py` | 327 | — | two light row serializers (≈ +45) |
| `halatuju_api/apps/scholarship/org_requests.py` | 845 | 825 → **room 0** | NOT touched (reason for the new module) |
| `halatuju_api/halatuju/pagination.py` | 44 | — | unchanged (used as is) |
| `halatuju_api/apps/scholarship/tests/test_org_fence.py` | 1022 | tests not ledgered | add `org_requests_queue.py` to `SCANNED` on the day it is written |
| `halatuju_api/apps/scholarship/tests/test_query_budgets.py` | 842 | — | fixture assertions follow the light row (no comments/attachments; tags present); budgets LOWERED as the tightness test asks |
| `halatuju_api/code-standards.json` | — | `_admitted` | requests list values LOWERED (never raised) |
| `halatuju_api/apps/scholarship/tests/test_requests_list.py` | NEW | — | envelope, groups, kind, q, org fence + `?org=` widening, roles, partition, predicate == count |
| `halatuju_api/apps/scholarship/tests/test_td228_requests_org_crumb.py` | 65 | — | read `requests` from the envelope if it reads payload shape |
| `halatuju-web/src/app/admin/requests/page.tsx` | 386 | — | list leaves for `RequestsList`; form + rate card stay; its `exhaustive-deps` disable leaves with the old `load` |
| `halatuju-web/src/components/admin/RequestsList.tsx` | NEW | — | tabs, kind filter, search, rows, pager, URL state, ticket ref (≈220) |
| `halatuju-web/src/app/admin/requests/[id]/page.tsx` | 642 | 624 → **room 2** | the back link line becomes `<RequestListNav id={id} />` (+1 import): net ≤ +1 |
| `halatuju-web/src/components/admin/RequestListNav.tsx` | NEW | — | back-to-tab, Prev / Next, position, keys |
| `halatuju-web/src/lib/listNav.ts` | NEW | — | storage-injectable read / write of `{ids, backHref, labelKey}` per list key |
| `halatuju-web/src/lib/admin-api/requests.ts` | 354 | — | `getOrgRequests` typed to the envelope + new filters; `OrgRequestListRow` type |
| `halatuju-web/src/lib/requestStatus.ts` | 376 | — | delete `listAnalysisTag` / `listAnalysisTagKey` (no caller) |
| `halatuju-web/src/lib/__tests__/requestAnalysis.test.ts` | — | — | drop the deleted helpers' cases |
| `halatuju-web/src/lib/__tests__/requestStatus.test.ts` | — | — | "no local status map" guard also reads `RequestsList.tsx` and `RequestListNav.tsx` |
| `halatuju-web/code-standards.json` | — | `eslint_disable_without_reason` | REMOVE `src/app/admin/requests/page.tsx::react-hooks/exhaustive-deps::1` (the tightness test will ask) |
| `halatuju-web/src/messages/{en,ms,ta}.json` | 9370 each | — | ≈14 new `admin.requests.list.*` / `admin.requests.nav.*` keys |
| `halatuju-web/src/components/admin/RequestsList.test.tsx` | NEW | — | rendered: tabs, counts, kind, search debounce, pager, URL, stale reply |
| `halatuju-web/src/components/admin/RequestListNav.test.tsx` | NEW | — | rendered: prev/next, ends greyed, ← / → incl. typing / dialog / modifier refusals |
| `halatuju-web/src/lib/__tests__/listNav.test.ts` | NEW | — | round-trip with a Map-backed fake; SSR-safe |
| `halatuju-web/src/app/admin/requests/page.orgcrumb.test.tsx` / `page.paste.test.tsx` | 57 / 149 | — | mocks return the envelope |
| `docs/CHANGELOG.md`, `docs/decisions.md`, `docs/technical-debt.md`, `halatuju_api/CLAUDE.md` | — | — | sprint entry; D1–D3; TD for Applications onto `listNav` + cross-page Prev/Next; Next Sprint |

About 27 files. `view.tsx`, `CockpitHeader.tsx` and `admin/scholarship/page.tsx` are **not** touched (D8).
`mobileClass.ts` already classifies both routes (`can`, M7) — no new page.

## 4. Query budget (`test_query_budgets.py:620`)

Today 5 (org_admin) / 6 (super) / 7 (super, `?org=`), flat 2 → 6 rows. Arithmetic for the new shape: auth (2) +
`summary` aggregate (1) + paginator COUNT (1) + page with `Exists` tag annotations and `select_related`
(1) = **5 / 5 / 6** — super and narrowed **fall by 1** (three prefetches go, two counts arrive); **org_admin is
flat at 5**. To make org_admin fall too would need the paginator to reuse the summary count when no `kind`/`q` is
set — a custom paginator for one query; not worth it, said honestly here rather than engineered. The builder
MEASURES before and after (rule 7) and lowers what the tightness test names.

## 5. Estimate

| Part | Hours |
|---|---|
| Server: predicate module, list view, serializers, count switch | 2.5 |
| Server tests + budget + fence scan | 1.5 |
| Web list component, URL state, api client | 2.5 |
| `listNav` + `RequestListNav` + detail page | 1.25 |
| Web rendered tests | 1.5 |
| i18n ×3 + Sol tag | 0.5 |
| Gates (both suites, tsc, lint, i18n, bundle-budget), mobile-check 360/390 × 3 languages, docs | 1.5 |
| **Total** | **11.25** (inside 10–12) |

## 6. Measured baselines (2026-11-03, worktree at `c78552d9`)

- **API, the gate's line** `cd halatuju_api && python -m pytest -q -n auto -p no:cacheprovider`: **11,947 passed, 3 skipped, 0 failed** (5,579 subtests passed; 17 min 04 s; whole api tree).
- **Web jest:** NOT MEASURED — `halatuju-web/node_modules` is absent in this worktree; per the brief no install and no
  junction was made. The lead provides deps and measures `npx jest --maxWorkers=4` before building.
- **`npm run bundle-budget`:** NOT MEASURED, same reason. Note: the median line is now **145 kB** (TD-470,
  2026-11-03), not the 148 the brief carried; new strings are `admin.*` only, which move no budgeted line (TD-360).

## 7. Lessons that apply, and how this sprint avoids each

1. **Org-fence pragma must touch its query; a guard selecting by name is blind beside it** (lessons 2026-09-08,
   2026-09-10). Every `OrgRequest*.objects` in the new module carries `# org-fence:` as the LAST line above it, and
   `org_requests_queue.py` joins `SCANNED` in the same commit.
2. **Narrowing must be tested from the widening side** (TD-241). Tests: an org_admin passing `?org=<other>` gets
   404 / nothing; a `q` that matches another org's request id returns nothing for an org_admin.
3. **Two affordances, two windows** (TD-201). The tag window (answer box, `OPEN_FOR_SHAPING`) and the Needs-action
   window (not terminal) differ ON PURPOSE: an approved request with a still-open question IS waiting on the
   requester (they can reply by comment, which settles it) but has no answer box. Test the approved+awaiting case
   explicitly: in Needs action, no "Answer needed" tag. Pinned, not "fixed".
4. **Characterise before you change; never edit an expectation** (rule 8). The existing count tests stay as they
   are and must pass after the switch to the shared predicate; the agreement test is added beside them.
5. **Bite it** (rule 2). Bite the predicate agreement test (perturb one branch of `needs_action_q` — both the count
   tests and the agreement test must go red), the partition test, and the keyboard test (remove the typing check).
6. **Rendered tests for interactive behaviour; a late reply resolved inside `act`** (2026-07-30, TD-298). Keys,
   debounce, tab switches and stale replies are mounted tests; the stale-reply test resolves the old promise in
   `act` and is bitten by deleting the ticket check.
7. **A control that disables itself on its own press** (2026-09 lesson on keyboard focus). Pressing Next onto the
   last item greys Next: assert where focus lands (on Previous), not only that navigation happened.
8. **Pagination renders twice** (2026-07-28, 2026-09-08). Use `getAllBy*` / a scoped helper on the pager; give
   Prev / Next `data-` hooks.
9. **Session storage: injectable, SSR-safe, and stale flags** (B40 9b). `listNav` takes a `StorageLike`; the record
   is keyed per list and rewritten on every list load; a detail id not in the record hides the nav (direct link).
10. **Delete replaced code at once.** `listAnalysisTag`, the status dropdown, the client tag derivation and the
    `load` with its eslint-disable all go in this sprint; the ledger entry is removed as asked.
11. **A guard that reads a moved file must follow it** (TD-272). `requestStatus.test.ts`'s "no local status map"
    guard is widened to the new components in the same change; `screenshotInput.test.ts` still points at
    `page.tsx`, where the form stays.
12. **Run BOTH suites whatever you touched; merge main BEFORE the gates** (2026-09-15).
13. **`?format=` and friends are DRF-reserved** (TD-163). `page` / `page_size` are the paginator's own; the new
    names `group`, `kind`, `q`, `org` are not reserved (`search` is avoided on purpose).
14. **Measure before reaching for the obvious fix** (rule 7). The budget is read before and after; the plan's 5/5/6
    is a prediction until the reading says so.

## 8. Decisions that constrain it

- *Pagination is opted in per view* (2026-06-09) — `FlexiblePageNumberPagination` + `envelope`, on this one view.
- *The engineer badge counts untriaged plus awaiting-analysis features, never triaged bugs* (TD-205, 2026-08-01) —
  the super's Needs action is exactly that; a triaged bug sits in In progress.
- *A tab's count is of the WHOLE list* (S7, 2026-09-11) — D2; counts are `undefined` (no pill) while loading.
- *Rules are served, not mirrored* — D4 / D5 (tags, effective kind).
- *Org payload is an allowlist; `triaged_kind` resolved into `kind`, no "filed as" for the org* (2026-10-29) — D5.
- *Org fence*: `_org_scoped` + `_org_narrowing`, cross-org 404, every admin class classified in
  `test_org_fence.py` (no new view class here).

## 9. Release

API BEFORE web: the old web on the new API still works (it reads `requests`; missing `comments` / `analyses` only
hide the tags for a few minutes), the new web on the old API would not (no `summary`, no paging). No migration.
Not money / identity / eligibility, so no adversarial review is required; a `/code-review` of the diff before merge.

## 10. Execution

**One builder** (an Opus subagent, per the build rule), sequential: server first (green api suite + budget), then
web. The two halves share the envelope contract, the files do not overlap with any other live stream except
`requests/[id]/page.tsx` (M7 later) and the cockpit files are deliberately left alone. The lead verifies the diff,
re-runs both gates, runs `mobile-check` and bites the four tests named in lesson 5.
