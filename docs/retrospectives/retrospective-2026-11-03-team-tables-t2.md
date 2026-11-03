# Retrospective — Team tables T2 (the Team page) — 2026-11-03

Live 2026-11-03: main 54f997a8; api-01241-9hv, web-01069-4vh (the first web build, 83881ff1, failed on a flaky
test; see below). No migration, no Scheduler job.

## What shipped
- Team: Admins and Reviewers tables (a person sits in every table whose hat they wear), Add Admin / Add Reviewer
  (existing members only), Remove from a table with its doors (last table, Mentors-only left, open cases, the lead).
- "View-only admin", "Finance" and "QC" retired as labels; an invited Admin starts at `see_all`; change role
  refuses a switch INTO finance / qc and keeps keys on a switch out. Invitations order Admin, Reviewer, Mentor,
  Source, Sponsor. The org admin may join Reviewers (self or super only; self-QC holds).
- `apps/scholarship/staff_tables_admin.py`; rulings Q1–Q4 in decisions.md.

## What went well
- The builder asked four precise questions before writing code; each answer fitted one message.
- The adversarial review found no hole and three real improvements (change role bypass, "keeps" wording that hid a
  gain, `may_act` under the lock), all fixed before the push.

## What to improve
- A flaky test (`SourceInvite.test.tsx`: Cancel clicked while still disabled from Resend) failed the deploy build
  and cost the second deploy. The lead's own full jest run had shown "1 failed" and a rerun passed; a jest failure
  that a rerun clears is still a finding — name the test and fix it before the push.
- TD numbers collided with a parallel session (Mobile took 471/472 the same day). Re-check the highest TD number
  after every rebase; T2's became TD-475 / TD-476.

## Owner direction recorded
"Any team member can move between roles, and they'd have the powers given them in permissions — no fixed role."
Added as T5 (every power from permissions) on the roadmap.

## Next
T3 — Mentors under Team, mentor detail page (design approved: TeamMentors board).
