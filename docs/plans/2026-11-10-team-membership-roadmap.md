# Team membership: one Staff list, groups only Add / Remove (roadmap, 2026-11-10)

Owner rulings 2026-11-10, given in the lead session. Nothing here is built yet. It starts after S1 is live (the audit
agent holds main until T2+T3+P1 and S1 are both live), and it never touches the G8-frozen files (`scholarship/vision.py`,
`scholarship/views.py`, `lib/officerCockpit.ts`, `admin/scholarship/[id]/view.tsx`).

## Why
Today Revoke and Delete sit on EVERY group table a person is in: a person in Admins and Reviewers has the pair twice.
A mentor-only person has the pair in Mentors, but a staff member who mentors does not. Two people with the same chips
can also hold different powers, because a hidden role label decides the admin work pages (the T1 "option B" ruling,
decisions.md 2026-11-03). And a person who was only ever handed cases (no review done) cannot be deleted, because
`staff_footprint` counts `cases_held_before` as work (TD-484, the QC-separation evidence).

## The model (owner rulings)
| # | Ruling |
|---|---|
| O1 | **Invitations** stays the only place to invite. Pending invitations stay there only; a person reaches the Staff list once they accept. |
| O2 | **Staff list**: a new first tab on Team. One row per accepted team member (staff and mentor-only logins; never a super, source or sponsor), their groups shown as chips. |
| O3 | The Staff list is the ONLY place for **Suspend / Restore** (today's Revoke; kept as a separate, undoable action) and **Delete** (remove from the organisation). |
| O4 | **Admins / Reviewers / Mentors** offer only **Add** (an existing staff member) and **Remove**. No Revoke or Delete on a group table. |
| O5 | **Remove from a group** is refused while they have unfinished work IN THAT GROUP: Reviewers = open cases; Mentors = scholars mentored now; Admins = anything waiting on them (to be listed in M1: e.g. an unfinished payment step, a request awaiting their approval). |
| O6 | **Removing the last group is allowed.** They stay on the Staff list with no group (sign-in kept; they see their Profile only) until someone explicitly deletes them from the Staff list. |
| O7 | **Delete** is refused while they have unfinished work in ANY group. Past work does not block it: with no records they are erased; with records (reviews done, cases once held, mentoring, etc.) they are ARCHIVED: off the Team page, sign-in removed, name kept on the records. Re-inviting the same email restores the same person, so the QC-separation rule keeps its evidence. |
| O8 | **Powers follow groups and chips only.** The admin work pages get their own Admins chip. Joining Admins gives the default admin powers (the admin preset); the organisation admin may change them. Rohini gets the default admin powers. |
| O9 | **Phone numbers never show in the Admins table**; they show on the person's profile page (still subject to "Show my phone to my team"). |
| O10 | **The organisation admin's name opens their person page** from the table, as every other admin's does. |
| O11 | **The person page header drops the email under the name**; the email stays in About. |

### Owner rulings, later on 2026-11-10 (admin permissions)
| # | Ruling |
|---|---|
| O12 | The person page's Permissions tab shows only the section for the table it was opened from: Admin permissions from Admins, Reviewer permissions from Reviewers. Built in M1b. |
| O13 | Admin permissions become COMPREHENSIVE: every admin menu item is a grantable permission, grouped by function (People, Partners, Engagement, Applications & scholars, Money, Settings), so the org admin can delegate to general or specialised admins. This resumes the paused T5 plan (`docs/plans/2026-11-01-team-tables-roadmap.md`, decisions.md 2026-11-03 T5.0), which the 2026-11-05 audit freeze paused but did not drop. New order: M1 → M2 (= T5g-lite: store the v2 keys of `staff_permissions_v2.CATALOGUE_V2` per person and draw the Permissions tab by group; the admin preset carries Partners + Engagement + org reads; replaces the single "admin-work chip"; still covers O8 and Rohini) → M3 (= T5e: the remaining org-admin-only actions become keys) → M4 (= T5d: money). |
| O14 | This lane is EXEMPT from the audit feature freeze. Deploys stay one at a time, each with the owner's yes. |
| O15 | Three powers stay with the org admin only and are never grantable: changing other staff's permissions (team edit / manage_team), paying the platform bill (billing.edit), and approving requests that commit paid hours (requests.approve). Everything else may be delegated. |

## Sprints
1. **Small change (small-change lane):**
   - the InfoTip bubble is drawn above the page (a portal, fixed position), so a table frame (`TableFrame`'s
     `overflow-hidden` / `overflow-x-auto`) can no longer clip it;
   - O9 (`StaffAdmin.tsx` phone lines, Admins table only; the Reviewers table is left as it is unless the owner says);
   - O10 (`reviewers/page.tsx` `personHref`: today it admits `TEAM_ROLES` only);
   - O11 (the person page header).
2. **Sprint M1: Staff list and membership rules** (O1-O7). Web: the Staff tab, the actions moved, the group tables
   reduced to Add / Remove. API: a Staff list endpoint (staff + mentor-only logins, per-row `deletable` / work), the
   per-group unfinished-work rules, last-group removal to a no-group shape, Delete-as-archive with the re-invite
   restoring the same row. Suspend and Delete endpoints already act per person (`revokeAdmin`, staff delete,
   `mentor_invite.delete_mentor`), so no permission changes. Risk to test hardest: the no-group shape (what it may
   open, its landing page) and the archive (every reader of a staff row must skip an archived one).
3. **Sprint M2: the admin-work chip** (O8). A new admin key named in `may_do_admin_work`; the admin preset carries it;
   a production data step gives it to the existing admin-labelled rows AND (owner) Rohini's row; after that the role
   label decides no page. Needs the owner's yes and a phone check before going live.

## Sequencing with the audit agent (its answer, 2026-11-10, via Requests)
- **Order:** S1 → G8 (scholarship web/API splits, A3.1-A3.3) → G9 (API: verdict modules, `courses/views` package,
  engine/ranking/profile splits) → this roadmap (small change → M1 → M2). Rebase onto main after G9 is live and re-run
  the gates before asking the owner.
- **Exception:** if the owner wants the SMALL change sooner, it may go between S1 and G8 (it touches none of the audit
  agent's files). Tell the audit agent first, so it rebases G8. Every push still needs the owner's yes.
- **No direct collision:** G8/G9 do not touch `staff_footprint`, `staff_tables_admin`, `staff_person`,
  `staff_permissions`, `views_admin/staff.py`, `courses/views_staff.py`, `models_staff.py`, `staff_delete_rules.py`,
  `TeamTables`, `StaffAdmin`, `StaffActions`, `person/` components, `admins.ts` or `InfoTip`. G8 only adjusts a mock
  target in `scholarship/tests/test_staff_profile_card.py`.
- **Watch-outs on rebase:**
  1. `apps/courses/views.py` becomes the package `apps/courses/views/` (11 modules, re-exported in `__init__`): put an
     edit in the right module.
  2. `apps/scholarship/views.py` and `apps/scholarship/vision.py` become packages (G8); `views_admin/` is unchanged.
     Patch targets stay valid through the re-exports.
  3. `officerCockpit.ts` and `admin/scholarship/[id]/view.tsx` are split (G8).
  4. TD numbers start at TD-603 (S1 took TD-597/598; G9 holds TD-600-602).
  5. Bookkeeping conflicts are expected in `CHANGELOG.md`, `docs/technical-debt.md`, `.claude/ARCHITECTURE_MAP.md` and
     both `code-standards.json` files. Keep both sides, take the lower budget and the later `last_tightened_on`.
- **G10 (the audit agent's next lane, deploys AFTER this roadmap):** it adds no migration, so courses `0096` is ours
  (M1's archive field in `models_staff.py`). Message Requests before M1 edits `serializers_admin.py` or
  `courses/models.py`. G10's A3.8 leaves `courses/views_staff.py` alone until M1 is live.

## Open for the brief (the architect settles; ask the owner only if a choice changes what someone can do)
- The exact list of "waiting on them" items for Admins (O5).
- The no-group shape: reuse the mentor-login shape (role `mentor`, NULL permissions, no mentor record) or a new state.
- Where an archived person shows (nowhere on Team; their name only on the records).
