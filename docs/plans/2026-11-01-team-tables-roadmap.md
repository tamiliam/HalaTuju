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
- **Status: LIVE 2026-11-03 (main 54f997a8; api-01241-9hv, web-01069-4vh).** Lead rulings Q1-Q4 (decisions.md "Team tables T2"): Add
  writes keys only; Remove moves the role only where a label would keep someone seated (leaving Reviewers -> Admin,
  opening the admin work pages, said on the confirm); the org admin joins Reviewers by a stored `['review']` (self or super only); "Remove"
  leaving only Mentors refused until T3. The Mentors TAB links to today's page (T3 moves the table). TD-475 open.
- Tabs in the new order; each table lists its members with only its own permission chips and editor.
- Add Admin / Add Reviewer / Add Mentor (a Sheet listing existing members not in that table); Remove from table
  (with the doors above). "View-only admin" and "Finance" labels retired from Team and Invitations (an invite as
  Admin starts at the minimum; payment keys are ticked after).
- Invitations order: Admin, Reviewer, Mentor, Source, Sponsor.
- Org admin may join Reviewers; self-QC test for them.

**T3 — Mentors under Team, mentor detail** (medium; ~25 files)
- **Status: LIVE 2026-11-03 (main 99d8ac1c; api-01243-dzq, web-01070-c44).** decisions.md "Team tables T3". Table + Add / Stop / Deactivate (7d), detail
  page `/admin/organisation/reviewers/mentors/[id]` (`mentor_detail.py`), old page redirects; T2's mentors-only refusal
  lifted for a signed-in staff mentor with no open case (becomes a mentor login). Owner scope addition: the person
  page's Permissions tab has one section per table; the Team tables lost their permission column. No migration.
- Team → Mentors tab (same width table, Add Mentor = 7d add; Stop / Mentor again); the old Mentors page redirects;
  "Invite a mentor" removed.
- Mentor detail page: profile summary, current and past scholars, meetings logged (count, last, gap between
  meetings), concerns raised / handled, mentoring since — staff only, org-fenced.

**T4 — Emails and Terms in three sections** (low-medium; ~15 files)
- **Status: LIVE 2026-11-03 (main 7871bb39; api-01244-2rq, web-01073-jxr).** decisions.md "Team tables T4". Admin list = the backend
  registry `admin_email_catalogue.py` (10 rows read off the senders, lead ruling option B: HalaTuju's own inbox not
  shown), `GET admin/admin-emails/`; Reviewer card moved whole; Mentor = the Invitations card (`only=invite_mentor`).
- Emails: Admin (the admin emails listed, read-only, with when each is sent), Reviewer (today's editable five),
  Mentor (the editable invitation + "no other email"). Terms: three "Soon" sections.

**T5 — Every power from permissions** (added 2026-11-03 on the owner's word: "any team member can move between
roles, and they'd have the powers given them in permissions — there is no fixed role anymore"; design + scope at
sprint start)
- Permission keys for what a role LABEL still decides after T2: the admin work pages (Announcements, Surveys,
  Development, Sources, Mentors read, sponsor terms/emails — `staff_tables.ADMIN_WORK_KEYS`, empty today) and the
  wallet-credit check (TD-475, still the `finance` role). Then `role` is only a display name.
- **T5.0 APPROVED by the owner 2026-11-03 ("approve all")** — decision page
  https://claude.ai/artifact/1HbE54pJTFu4JznDmNTdXf (evidence: the lead's T5 investigation, page × tier inventory,
  13 two-person rules, 20 conflict rules). Owner model: Reviewer sees only assigned students; QC implicitly sees
  ALL students and may decide on any except those they reviewed / interviewed / were assigned (QC self-sufficient,
  no `see_all` dependency); every team member lands on Organisation → Programmes; the org admin can limit any person
  to one or a few gifts (default all); admin pages in groups (Organisation, Programme, Engagement, Money) with
  View / Create-edit / Check / Approve per page as the page needs; the maker never checks or approves; only the org
  admin sets permissions. Rulings on the 8 questions (all as recommended):
  1. Keys per PAGE, shown in groups with a "whole group" switch.
  2. Organisation settings under Organisation; **gift configuration stays under Programme, with each gift** (owner:
     the rules change by gift) — renamed **Programme Settings** and moved last in the Programme group (2026-11-03,
     small change c166736a); Contracts under Programme; the Mentors list inside Team view.
  3. The org admin's lead-only powers (gifts, invitations, sponsor approval, requests, billing, assigning) become
     keys in T5; no preset grants them — only the org admin ticks them.
  4. The org admin may not approve a payment run they created when another eligible approver exists; otherwise the
     fallback stays and is recorded "approved as fallback".
  5. Wallet credits: create / check / approve by keys, maker never approves; `Donation.created_by` added (closes TD-475).
  6. Assigning reviewers is a key (Students: create/edit); never to oneself.
  7. Engagement pages (names every scholar) depend on Students view, like QC did on `see_all`.
  8. A gift-limited person may READ organisation-wide pages (Team, Invitations, Sources) but not change
     organisation-wide items; they create announcements / surveys only for their gifts.
- Live shapes map with NO access lost; only the custom-permission rows are rewritten (data migration with a
  history row each; `resolve()` reads both vocabularies for one release).
- Sprints, each with the owner's "yes": **T5a** catalogue v2 + aliases, no gate converted · **T5b** QC
  self-sufficient + widened self-QC guard (adversarial) · **T5c** pages open by keys, Programmes landing, role display
  only (adversarial) · **T5d** money: credits maker/check/approve, payments fallback rule, data migration
  (adversarial) · **T5g** the Permissions tab UI + Guide/FAQ · **T5e** lead powers to keys (adversarial) · **T5f**
  real gift limits as a fence (M2M; design first + adversarial; last — biggest blast radius; today "Covers" only
  greys the assign picker, the server ignores it).

Order: T1 → T2 → T3 → T4 → T5 (T3 and T4 could swap). The maintenance roadmap is complete.

## Later (not in this plan)
- Moving the org admin's lead-only powers (configuration, gifts, contracts, sponsors, assigning cases, billing,
  requests, …) into admin permission keys — the owner's stated direction. Owner, 2026-11-01: *"Future admins may
  have permission to view Team tables, Requests, Invitations, Billing & Usage, etc."* So T1's per-table
  predicates and the page gates must be written so a NEW admin key (e.g. `team_view`, `requests`, `invitations`,
  `billing`) can open a page without another rewrite: every page gate reads keys/tables, never a role list.
- Making the admin emails editable.
