# Sprint M2c brief: the Members tab and the lifecycle rules

Parent brief: `docs/plans/2026-11-11-m2-team-pages-brief.md`. M2a (4728cc534) and M2b (70a51cdc7) are live.
Owner rulings: R1-R5 in `docs/decisions.md` ("Members tab and the lifecycle rules", 2026-11-12). R6 is M3, not here.
Build on main 70a51cdc7 or later, in worktree `.worktrees/m2c` (branch m2c). Do not push.

## What the owner asked for

1. The Team page's **Staff** tab is called **Members**. Old links (`?tab=staff`) keep working. (R4)
2. The Members list becomes a real table: sortable headers, a search field, pagination, like the other admin
   tables. (R4)
3. A case stops counting as "open" once the student is **awarded**. The reviewer keeps `assigned_to`, so they still
   see their past students. (R5)
4. **Suspend** stays immediate even when the person holds open cases; a lead sees those cases on a card. (R1)
5. **Delete** only from "No group" (today's never-self / never-sole-org-admin / not-manageable rules stay). (R2)
6. **Remove from a group** is allowed while the person is suspended, with the same work checks as for an active
   person. (R3)

## Verified facts (main 70a51cdc7) - re-check each before building on it; stop and report if one is wrong

- Tabs: `app/admin/organisation/team/page.tsx:209-224` (`PanelTabs`); Staff is `{key:'staff', labelKey:
  'admin.staff.tab'}` (:212); `?tab=` read at :104, accepted values :115-116, fallback :117. Label strings
  `admin.staff.tab` at line 9741 of `src/messages/{en,ms,ta}.json`. A nav string `"staff"` near line 3486 - check
  whether it names this tab or something else; rename only if it is this list. `lib/teamPaths.ts:13,62`
  (`teamTabHref('staff')`). Tests: `team/page.test.tsx` :26, :904-909, :936-945, :951-954;
  `components/admin/person/GroupPages.split.test.tsx:164`.
- The Staff list is `components/admin/StaffList.tsx` (220 lines): a `<ul>` of `StaffLine` (:131-189), no sort, search
  or paging. Data: `GET /api/v1/admin/staff/` (`apps/courses/views_staff_list.py:30-48`), every row at once, ordered
  `name, id`; rows built by `apps/scholarship/staff_list.py:81-106` (`list_rows`).
- Table pieces: `components/admin/SortHeader.tsx`, `components/admin/TableFrame.tsx`, `lib/usePagedRows.ts`
  (`usePagedRows`, `useSort`), `lib/tableView.ts` (`PAGINATION_MIN_ROWS`, `DEFAULT_PAGE_SIZE`, comparators),
  `components/Pagination.tsx`. Copy the Team Reviewers table (`team/page.tsx` :160, :188, :358-371, :465;
  `lib/reviewerTable.ts`), including its search/filter. Client-side, as all these tables are.
- Open cases, three copies of one rule: `staff_lifecycle.open_cases` (`apps/scholarship/staff_lifecycle.py:88-96`),
  `staff_tables_admin.open_case_counts` (:419-430), `views_admin/reviewers.py:123-131` (`_open_cases`). All read
  `IN_PLAY_STATUSES` (`services/apply_gate.py:59-62`) OR `decision_reopened_at` not null. Status order:
  `models/applications.py:30-49`; submitted..recommended = submitted, shortlisted, profile_complete, interviewing,
  interviewed, recommended.
- Other `IN_PLAY_STATUSES` users (closure.py, send_interview_reminders, apply gate, tests) are a different meaning
  ("an application still in play") - **do not change `IN_PLAY_STATUSES`**.
- Suspend (`apps/courses/views_staff.py:560-573`) is refused only for `last_org_admin` and `has_scholars`; it is not
  refused for open cases today (the web changes its confirm text, `admin.staff.suspendConfirmOpen`).
- Delete never-rules: `staff_list._never` (`apps/scholarship/staff_list.py:51-61`: self, not_manageable,
  sole_org_admin, has_unfinished_work); `staff_delete_rules.delete_fields` (`apps/courses/staff_delete_rules.py:78-91`).
  `staff_tables.tables(a)` returns `()` for an inactive row; `staff_list._groups` (:36-42) reads groups from an
  `is_active=True` copy. Web: `StaffActions.tsx:84-85`, `StaffList.tsx:39-51,178-181`, `lib/staffRefusals`.
- Remove while suspended is refused today: `staff_tables_admin._refuse_basic` (:168-175) and `_cheap_refusal`
  (:374-376) return `not_active`; `row_fields` (:451-452) builds `remove` only when active.
- Reviewer reads: `views_admin/applications.py:101-102` filters `assigned_to` only, no status; detail fence
  `views_admin/base.py:281,308`. So keeping `assigned_to` after award keeps the reviewer's view.
- The "Overview" cards are the pending cards: API `my_pending.pending_for` (`apps/scholarship/my_pending.py:127-160`,
  absent card = not shown), web `components/admin/PendingCards.tsx` `META`. Query ledger for `my-pending` in
  `code-standards.json` `_admitted`.

## Decisions (architect; do not re-open, flag if one cannot hold)

| # | Decision |
|---|----------|
| C1 | Label only: `admin.staff.tab` becomes en "Members", ms "Ahli", ta "உறுப்பினர்கள்". The tab key stays `staff`; `?tab=members` is ALSO accepted (alias). Links the app writes keep `staff`. Retitle other strings that say "staff" for THIS list (heading, empty state, search placeholder); leave unrelated "staff" wording alone. |
| C2 | One rule for "open case": a new `OPEN_CASE_STATUSES` (the six pre-award statuses) in `staff_lifecycle`, used by all three copies (`open_cases`, `open_case_counts`, `reviewers._open_cases`), keeping the `decision_reopened_at` OR. `reviewers.py` is 599/600 lines - net zero or fewer lines there. Do not change `IN_PLAY_STATUSES`, `assigned_to` writes, or any award path. |
| C3 | Members table: columns from what `StaffLine` shows today (name + email, groups, status, actions); sortable by name, groups, status; search on name and email; `usePagedRows` + `Pagination` with the shared defaults. Must work at phone width (stack or scroll as the Reviewers table does). No new design - it follows the Reviewers table, so no Stitch screen. |
| C4 | R1 card: key `suspended_cases`, count = open cases (C2 rule) whose `assigned_to` is an INACTIVE team row of this organisation; shown only to a viewer who may manage the team (`manage_team` door - the same people who can reassign); links to the Reviewers table filtered to suspended people (or the Members tab with a "Suspended" filter if that is simpler). Add it to `pending_for` ONLY if it stays within the admitted query counts (fold into an existing query or replace one). If it cannot, do NOT raise the ledger: put the same count as a banner on the Members tab instead and say so in the report. |
| C5 | R2: a new never-rule `in_a_group`, checked after `sole_org_admin` and before `has_unfinished_work`, using the groups as `_groups` reads them (active copy), Mentors included. Reason text: "Remove them from every group first." Exception until M3: a group seat the person cannot be removed from by their role (today an `org_admin`'s own seat, refused `not_editable`) does NOT count, so an org admin stays deletable as today; record this in the report. |
| C6 | R3: Remove from Admins / Reviewers / Mentors is allowed for an inactive row. Drop `not_active` from the Remove path only (`_refuse_basic` / `_cheap_refusal` stay as they are for Add and permission edits); `row_fields` builds `remove` for an inactive row. The same work checks apply (open cases, scholars, payment runs). The group membership of an inactive row is read from the active copy, as `_groups` does. |
| C7 | Suspend (R1) stays as it is; only the confirm text may mention the new card. No new refusal. |

## Out of scope

- R6 / M3: explicit org-admin keys, lead keys, the 2 org_admin data rows, D12. M4: money.
- `IN_PLAY_STATUSES`, apply gate, closure, reminders. Archive vs erase (unchanged). No migration, no data step.

## Tests (targeted while building; full suites once at the end)

- C2: a case at each status (and a reopened one) counts open exactly for the six pre-award statuses plus reopened;
  awarded/active/maintenance are not open; all three copies agree (one parametrised test); the reviewer still lists
  an awarded case assigned to them.
- C5: in a group -> refused `in_a_group`; no group -> deletable (other rules unchanged); org admin as C5 says.
- C6: suspended reviewer with no open cases -> Remove works; with open cases -> refused with today's code; Add and
  permission edits still refuse `not_active`.
- C4: the count (active holder excluded, other org excluded, awarded excluded); who sees it; query count unchanged.
- Web: tab label and `?tab=members` alias; `?tab=staff` still opens it; table sort, search, paging; delete reason;
  Remove shown for a suspended person. en/ms/ta keys in step (`npm run i18n`).
- Budgets: never raise a budget or ledger. `views_admin.py` 765/765 untouched; courses->scholarship imports 16/16
  (add none); `reviewers.py` 599/600; file cap 600, function cap 150.
- Gates: API `manage.py check`, `makemigrations --check --dry-run`, full pytest `-n auto` via test_queue once; web
  `npm run gates`, `npm run bundle-budget -- --gate`, `npm run mobile-check` against base. Web node_modules: symlink
  `.worktrees/p1-activity-box/halatuju-web/node_modules` (the main checkout's lacks Playwright); remove the link after.
- Docs: CHANGELOG under Unreleased; decisions.md entry already written (do not edit it; add an "as built" note only
  if a decision changed). New TDs from TD-613.

## Release (architect and owner)

No migration. Owner's yes to push; Requests verifies; owner's phone check: Members tab name and table, Delete
disabled for someone in a group with the new reason, Remove offered for a suspended person, an awarded case no longer
blocking, the card (or banner) with the right count.

## Risks

- Changing "open" loosens the stranding rule and the Remove checks: awarded cases no longer block. Intended (R5).
- A reviewer removed from Reviewers keeps `assigned_to` on awarded cases; their read is by `assigned_to`, so check
  what they can still open once outside Reviewers and report it (no change asked).
- Shared files with other lanes (`messages/*.json`, `team/page.tsx`): rebase on main before the gates.
