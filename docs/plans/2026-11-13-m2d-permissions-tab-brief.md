# Sprint M2d brief: the Permissions tab, by page

Parent brief: `docs/plans/2026-11-11-m2-team-pages-brief.md`. Runs after M2c (branch `m2c`, not yet live) and
before M3. Build in worktree `.worktrees/m2d` (branch `m2d`, cut from `m2c` ed3718330). Rebase on main once M2c is
live. Do not push.

Design of record: the clickable mock-up the owner approved on 2026-11-13 ("I like it. Proceed."), in place of a
Stitch screen (Stitch would not connect): https://claude.ai/artifact/BNKCYaWWnLS5fnEtLPU6KV. Read it with the
Artifact tool's `read` action before building. Its colours and fonts are the mock-up's own; build with the site's
tokens and components. Match its STRUCTURE and WORDING.

## What the owner asked for (2026-11-13, six points)

1. No "Custom" chip. Every admin is set up individually.
2. Remove the subtitle "Starts from the Admin set. Switch on extra permissions when they need them."
3. Pages in sidebar order: Organisation (Overview, Invitations, Team, Sources, Sponsors, Usage & Billing, Requests,
   Organisation Settings), then Programme (Overview, Applications, Scholars, Announcements, Surveys, Development,
   Payments, Spending, Contract Templates, Programme Settings). A page with more than one power gets sub-items
   (Payments: Prepare, Check, Approve). No "View payments".
4. Do not say "Only the organisation admin, for now." Those controls are drawn disabled; they come alive when they
   become assignable (M3).
5. Remove "Comes with a permission above." Each power appears once.
6. Collapsible boxes, to make the tab less intimidating.

## Verified facts (branch m2c ed3718330); re-check each before building on it, stop and report if one is wrong

- The card is `halatuju-web/src/components/admin/PermissionEditor.tsx` (355 lines). Today, for somebody in Admins
  it draws "Admin permissions" (`TABLE_KEYS.admins`, :51-53, old keys as `row`, :203-228), then "Pages"
  (`pageGroups`, :265-277: the server's `v2_keys` by group, `pageRow` :241-264, locked with `permV2.reason.*`), then
  "Reviewer permissions" (`review`, `qc`). The same powers appear twice: `see_all` and `students.view`,
  `scholars` and `scholars.view`, `spending` and `spending.*`, the payment keys and `payments.*` / `sponsors.check`.
- `flip` (:135-149) already adds a page's `.view` with its change and drops the page's other keys with its view.
  Quality check brings `see_all` (TD-499), kept.
- "Custom" chip :308-312; subtitle :314-315 (`permEditor.subtitle`); legend strings `permV2.intro`,
  `permV2.reason.{never_grantable,lead_only,alias}` (`messages/en.json` ~8496-8519, and ms/ta).
- The server serves, per page key, `{key, page, level, grantable, reason, held}` (`staff_permissions_admin.v2_editor`,
  `apps/scholarship/staff_permissions_admin.py:125-144`); `reason` is `never_grantable` (billing.edit,
  requests.approve), `lead_only`, `alias` or null (`staff_permissions_v2.refusal_reason`).
- Dry-run consequences: `staff_permissions_admin.consequences` (:197-234), codes at :31-45, worded by
  `admin.permEditor.effect.*`. `staff_permissions_v2.dependency_gaps` (ruling 7: Announcements, Surveys,
  Development, Mentoring need `scholars.view`) is reported nowhere today.
- History: `components/admin/PermissionHistory.tsx` (66 lines), one `<li>` per change listing every key.
- A 44 px segmented control already exists as a pattern: `components/DisplaySegments.tsx` (`role="radiogroup"`,
  `min-h-11`). Switch: `components/Toggle.tsx`. Sidebar order and names: `components/admin/Sidebar.tsx`; page names
  `orgSettings.nav` "Organisation Settings", `billing.title` "Usage & Billing", Programme Settings ~7451.

## Decisions (architect; do not re-open, flag if one cannot hold)

| # | Decision |
|---|----------|
| D1 | Web layout, ONE constant (e.g. `lib/permissionLayout.ts`): two boxes, Organisation and Programme, each a list of page rows in sidebar order, each row naming the key(s) it drives and its control. Engagement and Money pages sit in Programme (Mentoring after Development). A guard test: every key the server serves (`keys` for the Admins table, every `v2_keys` key) appears in the layout exactly once OR is hidden by D3. A key the server adds later still falls to the existing "other" rows. |
| D2 | Controls. **Three-way** "No access / View / View and change" (segmented, 44 px, `radiogroup`) for a page with `.view` and `.edit`: Invitations, Sources, Sponsors, Requests, Announcements, Surveys, Development, Mentoring, Contract Templates. **One switch** for Team (`team.view`), Usage & Billing (`billing.view`), Organisation Settings (`settings.edit`), Programme Settings (`programmes.edit`), Applications (`see_all`), Scholars (`scholars`), Spending (`spending`). **Sub-item switches**: Sponsors > Approve sponsor credits (`sponsors.approve`); Applications > Assign and nudge (`students.edit`), Approve awards (`students.approve`); Scholars > Ask to withdraw an award, Approve award withdrawals (the two `award_withdraw_*` keys); Payments > Prepare / Check / Approve payment runs (`payments_prepare/check/approve`). **No control**: the two Overview rows and the Payments row itself ("Opens with any of the three below."). Verify each Overview sentence against the door code (`staff_tables` doors); if "Opens with any page in this box" is not true, word it truthfully or drop that row and report. |
| D3 | Hidden: a key the server marks `never_grantable` (billing.edit, requests.approve), and every `alias` key (its old key's row stands in for it: `students.view`, `scholars.view`, `spending.*`, `payments.view`, `sponsors.check`). `manage_team` is not on this tab (unchanged). Approve payment runs' description gains "Also checks sponsor credits." (en/ms/ta). |
| D4 | Locked (`lead_only`): drawn disabled with a padlock icon, no reason text. ONE legend line under the intro, "Not assignable yet.", shown only when a locked control is on screen and the card is not `fixed`. In a three-way, only the locked option is disabled (Invitations: "View and change"). A locked control shows `held` (what opens today). `fixed` (an org admin, yourself) keeps today's behaviour: everything disabled, its `permEditor.fixed` line. |
| D5 | Each box is a collapsible section (button with `aria-expanded`, chevron), both open on load, with a live "N of M on" count: M = the box's ENABLED controls (a three-way counts once, on unless "No access"; sub-items count each); N = those on in the working set. |
| D6 | Copy: drop the Custom chip (and `permEditor.custom` if unused) and `permEditor.subtitle`; the new subtitle is "Choose what {name} can see and do. Changes apply when you save." Drop `permV2.intro`, `permV2.reason.*`, the "Pages" heading and the group headings. Keep the title, the "changed" pills, the server's consequence line, Save, Reset (label "Reset to {preset} set"), the footnote, `unlistedHint`. The server's `custom` field stays (Reset's `onPreset` reads it). |
| D7 | The ruling-7 note, SERVED: (a) `v2_editor` also serves `v2_gaps`, the pages short of Scholars for the person as held (`dependency_gaps` over what they hold, read through `ALIASES`); (b) a new consequence code `scholars_needed` whenever the `after` set has a gap. Web: a caution note naming the pages (from the latest answer: the dry run while dirty, `v2_gaps` at rest). Wording per the mock-up: "{pages} show scholars by name. Switch on Scholars as well, or this person will see those pages without the scholars' files." Not a refusal; nothing blocks a save. |
| D8 | Save bar: the consequence line, Save and Reset in a bar that stays in view at the bottom of the card while it scrolls (`position: sticky`, bottom, safe-area aware). If it collides with the admin shell on a phone (mobile-check, or a bottom nav), make it non-sticky and say so in the report. |
| D9 | History: each change row shows a summary line ("{n} switched on", "{n} switched off", or the role reset) with "Show" / "Hide" for the full list when the row names more than 3 keys; 3 or fewer stay listed inline as today. The 0097 rows read "The system update" (`by_migration`, unchanged). |
| D10 | Reviewers section (`review`, `qc`) and the mentor view: same box style, contents unchanged. |

## Out of scope

- Any change to what a key opens, who may grant it, `GRANTABLE_V2`, `refusal_reason`, the stored data. No migration.
- M3 (lead-only keys become assignable, R6, D12) and M4 (money gates).

## Tests (targeted while building; full suites once at the end)

- D1 guard (every served key placed once or hidden). D2/D3: each row drives exactly its keys; choosing View /
  View and change / No access sends the right set (dry run asked); hidden keys never drawn yet still saved as held.
- D4: lead-only locked with padlock, legend shown once, no "for now" text anywhere; fixed card unchanged.
- D5 counts move with clicks; collapse hides rows and keeps state. D7: API tests for `v2_gaps` and
  `scholars_needed` (gap in after only; aliases read); web note from both sources. D9: summary and Show/Hide.
- Update `PermissionEditor.test.tsx`, `PermissionEditorPages.test.tsx`, `PermissionEditorNullRow.test.tsx`,
  `GroupPages.test.tsx` where they pin the old layout; do not weaken an assertion about what is SAVED.
- en/ms/ta in step (`npm run i18n`); Tamil per the style guide. Budgets: never raise one; file cap 600 (split the
  card into a box component if it nears it), function cap 150; the editor stays in its lazy chunk.
- Gates: API `manage.py check`, `makemigrations --check --dry-run`, full pytest `-n auto` via test_queue once; web
  `npm run gates`, `npm run bundle-budget -- --gate`, `npm run mobile-check` against base. Web node_modules: symlink
  `.worktrees/p1-activity-box/halatuju-web/node_modules`; remove the link after.
- Docs: CHANGELOG under Unreleased. New TDs from TD-613 (check the register for the next free number).

## Release (architect and owner)

No migration. Owner's yes to push; Requests verifies; owner's phone check on the live tab: boxes and counts, the
three-way choice, Payments sub-items, padlocks with the one legend line, the Scholars note, the history summary, at
phone width in light and dark.

## Risks

- A layout that misses a key would hide a power: the D1 guard fails the build instead.
- The three-way writes two keys at once; the server's dry run stays the judge (refusals unchanged).
- Shared files with M2c (`messages/*.json`): rebase on main after M2c lands, before the gates.
