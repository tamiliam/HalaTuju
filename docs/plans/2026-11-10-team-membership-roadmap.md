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

## Open for the brief (the architect settles; ask the owner only if a choice changes what someone can do)
- The exact list of "waiting on them" items for Admins (O5).
- The no-group shape: reuse the mentor-login shape (role `mentor`, NULL permissions, no mentor record) or a new state.
- Where an archived person shows (nowhere on Team; their name only on the records).
