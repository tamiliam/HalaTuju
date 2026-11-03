# Team tables — one person, several hats (roadmap, 2026-11-01)

Status: **APPROVED by the owner 2026-11-01** (design boards TeamAdmins / TeamReviewers / TeamMentors / TeamEmails on the maintenance canvas). Owner's model and rulings 2026-11-01 (decisions.md the same day once approved).

## Why
The owner: *"Mentors are a team member. Reviewer is a team member. Admin is a team member. A person could wear all
three hats, or just one, or two. Once they wear a particular hat, they should sit in that table. And each table has
its own set of permissions."* Today one `PartnerAdmin.role` decides the ONE table a person sits in on Team, and any
extra powers are added as keys on that row (Rohini: role reviewer + `see_all` + `spending`, so she sits only under
Reviewers). Mentors live on a separate page.

## What exists (measured 2026-11-01)
- `apps/courses/staff_permissions.py` (request #39): eight keys — `review`, `see_all`, `qc`, `spending`,
  `payments_prepare`, `payments_check`, `payments_approve`, `manage_team`; `role` is the PRESET LABEL;
  `PartnerAdmin.permissions` NULL = the role's preset; `org_admin` is a fixed LEAD TIER nobody edits.
- Live: ~30 staff; only TWO rows carry custom keys (a reviewer with `see_all`+`spending`; an admin with
  `see_all`+`spending`); one org_admin also mentors (7d).
- ~97 backend `role ==` checks, 67 `has_role(...)` calls, 21 `has_perm(...)`, ~59 web `role ===` checks; the web
  menu (`lib/navigation.ts`) gates most pages by a ROLE LIST (e.g. Payments: super, org_admin, admin, finance), so a
  reviewer holding admin keys cannot open admin pages today.
- Mentors: `scholarship.Mentor` + `PartnerAdmin.mentor` (7a–7d); `mentors_now` is the one predicate.
- A self-QC guard exists (`_require_qc`): nobody QCs a case they reviewed.

## Owner rulings (2026-11-01)
1. Three tables on Team — **Admins, Reviewers, Mentors** — then **Emails** (three sections: Admin, Reviewer, Mentor)
   and **Terms** (three sections, "Soon"). A person sits in every table whose hat they wear.
2. Each table has its OWN permissions and shows only those. Admin keys: `see_all`, `spending`, `payments_prepare`,
   `payments_check`, `payments_approve`. Reviewer keys: `review`, `qc`. Mentor: the 7c desk.
3. **Add Admin / Add Reviewer / Add Mentor** buttons (top right of each table) add an EXISTING team member only;
   new people are invited on Invitations.
4. **No "View-only admin" and no separate "Finance" label**: one **Admin**; what they see and do is their
   permissions. A new admin starts at the absolute minimum (today's view-only = `see_all`). Direction: in future
   the org admin's lead-only powers become admin permissions, so admins can carry most of the org admin's work.
5. **The org admin may also join Reviewers** (be assigned cases). Only requirement: they cannot QC the students
   they reviewed (the existing self-QC guard, applied to them too).
6. Mentors move under Team (same table width); the Mentors page goes (redirect); the "Invite a mentor" button goes;
   clicking a mentor opens a **mentor detail** page (their work and performance).
7. Invitations order: **Admin, Reviewer, Mentor, Source, Sponsor**.
8. "Finance" and "QC" stop being labels: a finance person is an Admin with `payments_approve`; a QC person is a
   Reviewer with `qc` (owner approved with the design).
9. Admin emails (about six, today hard-coded — payment countersign / finance check / run, org requests, profile
   complete, contact form): **listed** in the Admin section now; editable later.

## Rules the build must hold (doors)
- A person is in ≥ 1 table. Removing their LAST table is refused ("revoke instead").
- Remove from Reviewers is refused while they hold open assigned cases (reassign first) — the existing
  `staff_lifecycle.open_cases` door.
- Remove from Mentors = 7d Stop mentoring (assignments end, login untouched).
- Adding a table never touches the sign-in, never emails, and is org-fenced (super / org_admin; `manage_team`).
- A pure invited mentor added to Admins or Reviewers becomes a staff member (7d's link rules) — tested.
- Finance-only people become "Admin with payments_approve"; the payment chain's rules (maker ≠ checker ≠
  approver) are unchanged and re-tested.
- The org admin's lead tier stays fixed; joining Reviewers adds `review` alongside it; self-QC holds.
- Every page / action that today checks ONE role checks the person's TABLES (and keys) instead — the menu, the
  backend `has_role`, the landing page, and the Guide chapter shown.

## Sprints (each: design approved first; Opus builder, lead verifies; adversarial review; en/ms/ta; owner "yes" before push)

**T1 — Hats plumbing, no visible change except Rohini** (high; ~35 files; migration only if a stored field is needed)
- **Status: LIVE 2026-11-03 (main 83cddf96; api-01239-5jr, web-01067-6fr).** Owner ruling option B: a key seat opens the organisation READ pages
  only; the landing stays on the first hat. `apps/courses/staff_tables.py`; decisions.md 2026-11-03; no migration.
- One predicate per table: `in_admins(a)`, `in_reviewers(a)`, `in_mentors(a)` (= `mentors_now`), derived from keys +
  lead tier + mentor link (prefer DERIVED over a new column; the 0123 / no-backfill lesson).
- `has_role` and the web menu's role lists accept a person's tables; the payment chain, assignment, QC, Spending
  read keys (most already do since #39).
- Golden test: every live preset still opens exactly the pages it opens today; Rohini additionally reaches the admin
  pages her keys allow. Accept: no other person's access changes (diff of a page×person matrix before/after).

**T2 — The Team page: Admins · Reviewers · Mentors, Add / Remove** (medium-high; ~35 files)
- **Status: BUILT, NOT LIVE (2026-11-03, branch maint-s7).** Lead rulings Q1-Q4 (decisions.md "Team tables T2"): Add
  writes keys only; Remove moves the role only where a label would keep someone seated (leaving Reviewers -> Admin,
  keeping the admin pages); the org admin joins Reviewers by a stored `['review']` (self or super only); "Remove"
  leaving only Mentors refused until T3. The Mentors TAB links to today's page (T3 moves the table). TD-471 open.
- Tabs in the new order; each table lists its members with only its own permission chips and editor.
- Add Admin / Add Reviewer / Add Mentor (a Sheet listing existing members not in that table); Remove from table
  (with the doors above). "View-only admin" and "Finance" labels retired from Team and Invitations (an invite as
  Admin starts at the minimum; payment keys are ticked after).
- Invitations order: Admin, Reviewer, Mentor, Source, Sponsor.
- Org admin may join Reviewers; self-QC test for them.

**T3 — Mentors under Team, mentor detail** (medium; ~25 files)
- Team → Mentors tab (same width table, Add Mentor = 7d add; Stop / Mentor again); the old Mentors page redirects;
  "Invite a mentor" removed.
- Mentor detail page: profile summary, current and past scholars, meetings logged (count, last, gap between
  meetings), concerns raised / handled, mentoring since — staff only, org-fenced.

**T4 — Emails and Terms in three sections** (low-medium; ~15 files)
- Emails: Admin (the admin emails listed, read-only, with when each is sent), Reviewer (today's editable five),
  Mentor (the editable invitation + "no other email"). Terms: three "Soon" sections.

Order: T1 → T2 → T3 → T4 (T3 and T4 could swap). Then back to Student maintenance Sprint 8 (Announcements).

## Later (not in this plan)
- Moving the org admin's lead-only powers (configuration, gifts, contracts, sponsors, assigning cases, billing,
  requests, …) into admin permission keys — the owner's stated direction. Owner, 2026-11-01: *"Future admins may
  have permission to view Team tables, Requests, Invitations, Billing & Usage, etc."* So T1's per-table
  predicates and the page gates must be written so a NEW admin key (e.g. `team_view`, `requests`, `invitations`,
  `billing`) can open a page without another rewrite: every page gate reads keys/tables, never a role list.
- Making the admin emails editable.
