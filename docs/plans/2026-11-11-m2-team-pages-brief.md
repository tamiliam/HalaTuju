# Sprint M2 brief: Team moves to /team, one page per group (M2a), then admin permissions by key (M2b)

Architect brief, 2026-11-11. Roadmap: `docs/plans/2026-11-10-team-membership-roadmap.md` (items 3 and 4).
Owner rulings: decisions.md "2026-11-11 — Team URLs move to /team; each group has its own person page" (U1–U5)
and the roadmap's O8, O12, O13, O15. M2 ships as TWO pushes: **M2a** (web only: addresses, redirects, per-group
pages) and **M2b** (permissions: per-person v2 keys, Permissions by group, the admin preset, the data step).
This brief specifies M2a in full; M2b's section is an outline that is finished after its research pass.

Order with the audit lane (Requests, 2026-11-11): G14 is pushed first, then M2a → M2b → M3 → M4, one deploy at a
time, each with the owner's direct yes. G14 touches no file M2a touches except `messages/{en,ms,ta}.json` and
`mobile-check/pages.pw.ts` — rebase onto G14 before the push and resolve those by hand.

## Owner-settled decisions (do not re-open)

| # | Ruling |
|---|---|
| U1 | Team lives at `/admin/organisation/team`. Person pages: `/admin/organisation/team/admins/<id>`, `/team/reviewers/<id>`, `/team/mentors/<id>`. Every old address gets a PERMANENT redirect that keeps the query string (`?tab=`, `?table=`). |
| U2 | One page per GROUP. A person in two groups (Rohini: Admins and Reviewers) has two pages. Admin page = header, About, admin permissions — admin work only. Reviewer page = header with figures, Covers, Pause new cases; Outcomes (and Reopens); About; reviewer permissions. Mentor page = header with mentor figures and gifts; their scholars; About. |
| U3 | About shows on every group page. |
| U4 | The header chips link to the person's OTHER group pages (the chip of the page you are on is not a link). |
| U5 | Someone in no group appears only on the Staff tab: no person page, no link from Staff. |
| O12 | A Permissions section shows only the table the page belongs to (already built in M1b via `table`). |
| — | These SUPERSEDE T3's single `TeamPersonPage` (its M6 ruling: "the parts each table brings appear for whoever sits in it"). |

## Verified facts (2026-11-11, main 87445f7e1)

- Routes today: `src/app/admin/organisation/reviewers/page.tsx` (Team, 473 lines, tabs Staff/Admins/Reviewers/Mentors),
  `reviewers/[id]/page.tsx`, `reviewers/admins/[id]/page.tsx` (reads `?table=`), `reviewers/mentors/[id]/page.tsx`.
  Each person route lazy-loads `components/admin/person/TeamPersonPage` as chunk `'ad'`.
- `TeamPersonPage.tsx` (131) + `useTeamPerson.ts` reads the entry route's detail, then the other details the `person`
  block's `tables` name. Ids: the admin and reviewer routes take the `PartnerAdmin` id (`person.admin_id`); the mentor
  route takes the MENTOR record id (`person.mentor_id`). `person.tables` lists the groups; `person.mentor_only` marks a
  pure mentor.
- `PersonHeader.tsx` (124) draws the chips (`TableChips`), status, joined / last seen, Covers (reviewer gifts), mentor
  gifts, the action row (Pause, Remove from Mentors), reviewer figures and mentor figures. `PersonProfile.tsx` (88)
  draws About (fields gated by `profile_full`), reviewer Outcomes / Reopens and the mentor's scholars (`mentorWork`).
  `ReviewerParts.tsx`, `MentorOnlyPermissions.tsx` hold the rest.
- In-app links to move (grep `organisation/reviewers`): `lib/navigation.ts:140` (Team row href; `id` stays
  `'reviewers'` — it is a snapshot key), `reviewers/page.tsx:91,138,307,387`, `components/admin/StaffList.tsx:55-56`
  (`pageOf`), `components/mentors/MentorsAdmin.tsx:103` (`mentorHref`), `app/admin/organisation/staff/page.tsx:276`,
  `app/admin/organisation/mentors/page.tsx:20` (client redirect to `?tab=mentors`), `lib/pageWidth.ts:45,89`,
  `lib/mobileClass.ts:191-196`, `lib/reviewerDetail.ts:2` (comment), `sandbox/consoleM8Surfaces.tsx:33-34,396,406`,
  plus the tests and the "before" fixtures under `src/lib/__tests__/fixtures/` (`t5cDoorsMenusBefore.json`,
  `teamTablesAccess*Before.json`). The API has NO link to these paths (grep of `halatuju_api/` is empty);
  `halatuju_api/apps/scholarship/tests/test_team_tables_matrix.py` names the path only in a test.
- Existing redirect style: a client page with `router.replace` (`admin/organisation/mentors`, `admin/invite`).
  `next.config.js` has `headers()` but no `redirects()`.
- `canAccess` resolves a path by its LONGEST registered prefix, so `/admin/organisation/team/...` belongs to the Team
  row once its `href` is `/admin/organisation/team`.

## M2a — what to build (web only; no API change, no migration)

1. **Move the routes** (git mv, then edit): `organisation/reviewers/` → `organisation/team/`, with
   `team/page.tsx`, `team/admins/[id]`, `team/reviewers/[id]`, `team/mentors/[id]`. The old `reviewers/[id]` (a
   reviewer) becomes `team/reviewers/[id]`. Move the colocated tests with them.
2. **Redirects in `next.config.js`** — `async redirects()` with `permanent: true` (308; Next keeps the query string,
   the browser keeps `#permissions`). Explicit rules, most specific first; NO catch-all `:path*` (it would send
   `/reviewers/7` to `/team/7`):
   - `/admin/organisation/reviewers` → `/admin/organisation/team`
   - `/admin/organisation/reviewers/admins/:id` → `/admin/organisation/team/admins/:id`
   - `/admin/organisation/reviewers/mentors/:id` → `/admin/organisation/team/mentors/:id`
   - `/admin/organisation/reviewers/:id` → `/admin/organisation/team/reviewers/:id`
   - `/admin/organisation/mentors` → `/admin/organisation/team?tab=mentors` (replaces the client redirect page;
     delete that page and update `navigation.ts` `match` to the new path or drop it — the server redirect means the
     old path never renders).
   Add a test that pins these five rules (read `next.config.js` the way `securityHeaders.test.ts` does).
3. **Every in-app link** listed above moves to the new paths. The nav row keeps `id: 'reviewers'`, its roles, keys,
   door and chord; only `href` (and `match`) change. Frozen "before" fixtures: a path in them changes ONLY as a
   mechanical rename, in a commit of its own, saying so.
4. **Split `TeamPersonPage` into three group pages** sharing one shell. Suggested shape (the builder may improve it,
   keeping every file under 600 lines and no route heavier):
   - `person/PersonShell.tsx` — Back link, `PersonHeader`, optional tabs, About.
   - `person/AdminGroupPage.tsx` — reads `getStaffPermissions(id)` only; header without figures, Covers or Pause;
     tabs About | Permissions; Permissions = `PermissionEditor table="admins"` (read-only for a fellow org admin, as
     M1b). Fence as today: super / org_admin only (`admin.person.notAllowed` otherwise).
   - `person/ReviewerGroupPage.tsx` — reads `getReviewerDetail(id)`; header with reviewer figures, Covers, Pause;
     About tab = Outcomes + About + Reopens (today's reviewer layout); Permissions = `PermissionEditor
     table="reviewers"` for a manager, the "not allowed" line otherwise. Fence: `mayOpen(team)`.
   - `person/MentorGroupPage.tsx` — reads `getMentorDetail(id)`; header with mentor figures and gifts, Remove from
     Mentors for a staff mentor as today; About + the scholars (`MentorWork`). A PURE mentor keeps the Permissions tab
     with `MentorOnlyPermissions` (add to a group). A STAFF mentor's mentor page has NO Permissions tab (mentoring is
     not a permission; their admin / reviewer permissions are on those pages). Fence: `mayReadMentors`.
   - Each page reads ONE detail. `useTeamPerson`'s cross-reads go (U2: the other group's parts live on its own page).
     ⚠ About needs `person.profile` and `profile_full`, which every detail's `person` block already carries — check
     the mentor route's `profile_full === false` rule still holds (T3 review fix 1).
   - Each route stays its own lazy chunk (`'ad'`) with one loader line; the Mentors table's chunk is still loaded by
     its literal specifier for the mentor parts (no new chunk).
5. **Chips link (U4).** `TableChips` gains an optional link mode: on a person page each chip other than the current
   group links to that group's page — Admins and Reviewers by `person.admin_id`, Mentors by `person.mentor_id`; a
   chip with no id (a mentor chip without `mentor_id`) or one whose page the VIEWER may not open (admin page:
   super / org_admin; mentor page: `mayReadMentors`; reviewer page: `mayOpen(team)`) stays plain text. The lead
   badge (`lead`) is unchanged. The chip of the current page is plain and carries `aria-current="page"`.
6. **Wrong group.** A group page opened for someone NOT in that group (old links: `admins/<id>?table=reviewers`, a
   reviewer-only person opened at `/team/admins/<id>`) does `router.replace` to the first group page they are in, in
   the order Admins, Reviewers, Mentors, keeping nothing of the query but `#permissions`; in no group → `/team?tab=staff`
   (U5). The decision is a pure function in `lib/` with its own tests.
7. **Staff tab (U5).** `StaffList.pageOf`: no group → no link (already); otherwise the first group page in the order
   Admins, Reviewers, Mentors (a pure mentor → the mentor page by `mentor_id`). The group tables link each row to
   THAT group's page (Admins table → `/team/admins/<id>`, Reviewers → `/team/reviewers/<id>`, Mentors →
   `/team/mentors/<mentor_id>`).
8. **Back link**: each page returns to its own tab (`/admin/organisation/team?tab=admins|reviewers|mentors`); the
   `?table=` reader goes (the wrong-group rule replaces it).
9. **Copy**: no new strings unless a page needs one; reuse `admin.person.*`. Any new key goes in en, ms AND ta.
10. **Ledgers and registries**: `mobileClass.ts` (new paths, old removed; same classes and surfaces),
    `pageWidth.ts`, `docs/mobile-ledger.md`, `mobile-check/pages.pw.ts` if it names these paths, the sandbox
    surfaces. `t3-mentor-person` and `m8-reviewer-detail` surfaces keep their ids.

### M2a tests (targeted while building; full gates once at the end)
- The redirect rules (5) are pinned; a `/reviewers/7` → `/team/reviewers/7` case and a query-kept case.
- Each group page: draws only its own parts (an Admin+Reviewer person: the admin page has no figures, no Covers, no
  Pause, no Outcomes; the reviewer page has no admin Permissions section), About on all three.
- Chips: links to the other groups only; the current chip plain; a viewer who may not open a group sees that chip
  plain; a mentor chip without `mentor_id` plain.
- Wrong-group replace and no-group → Staff; `StaffList.pageOf` order.
- The old tests of `TeamPersonPage` are moved to the new pages, not deleted: every behaviour they pin (the fence
  messages, `notFound`, `#permissions`, read-only for a fellow org admin, the pure mentor's Permissions, Remove from
  Mentors) is still pinned somewhere.
- Gates: `npm run gates`, `npm run bundle-budget -- --gate` (no route heavier; the renamed routes must keep their
  ledger lines if they have one), `npm run mobile-check` (the 125 public / sandbox cells that fail on base fail here
  too — compare against base, do not "fix" them). API: `test_team_tables_matrix.py` and the full suite once (the
  path string in it moves only if it is asserted).

### M2a risks
- **The catch-all trap** (rule order / `:path*`), pinned by the redirect test.
- **Lost behaviour in the split**: the T3 tests are the inventory; move each assertion.
- **Bundle ratchet on renamed routes**: check `bundle-budget.js` keys routes by path; a rename may need its ledger
  line renamed (a rename is not a raise — say so in the commit).
- **Frozen fixtures**: mechanical path renames only, own commit.
- **Shared files with G14** (`messages/*.json`, `mobile-check/pages.pw.ts`): rebase after G14 lands.

## M2b — outline (finished after its research pass; not built yet)

O8 + O13 (T5g-lite). Store the v2 keys of `staff_permissions_v2.CATALOGUE_V2` per person; the Permissions tab draws
them by group; joining Admins applies the ADMIN PRESET (Partners + Engagement + org reads); the organisation admin may
change them; the O15 three (`manage_team`, `billing.edit`, `requests.approve`) are never grantable. A production data
step (owner's yes) gives the preset to every admin-labelled row and to Rohini's row; after it, `LABEL_GRANTS['admin']`
goes and the role label decides no page. Open questions for the research pass: where the v2 keys are stored
(`PartnerAdmin.permissions` mixed with today's keys, or a new field), how `asked_set` / `clean` / `effective_v2`
change, what reads `admin/me` (G14 changes `lib/admin-auth-context.tsx`: build on its version), and the lock order of
the save. Adversarial review and the owner's phone check before it goes live.
