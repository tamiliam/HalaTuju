# Retrospective — Student maintenance Sprint 7b: mentoring (2026-11-01)

**Live:** main 7dc9c15d; api-01224-s6w, web-01047-lvq (both builds SUCCESS; health 200; no 5xx or ERROR logs on
the new revision; the new mentoring endpoint answers 401 without a login). Migration scholarship 0196_mentoring
applied by hand first (two tables, RLS on, one service_role policy each, ledger row); the Security Advisor showed
nothing new.

## What shipped
- `MentorAssignment` (one open per scholar, partial unique index) and `MentoringSession` (staff-only notes).
- Staff (super, org_admin, admin; org-fenced) assign / change / end a mentor and log meetings on the scholar
  file's Mentoring tab; reviewers and QC are refused the tab and no longer see mentoring lines in the timeline.
- The student's Mentoring tab on My Bursary: name, area, languages, About, email, phone only when shared,
  meeting dates and mode. No photo, notes or history.
- "You have a mentor" to the student only, switchable and editable on Student communications.
- Scholars list Mentor column + "No mentor" / "Asked for help" filters; Mentors page "Scholars now".
- Mentoring ends on: staff end, change, mentor deactivated or revoked, file closed, award reverted, and when the
  mentor turns out to be the student.

## What went well
- The doors list in the brief (sprint-start 3b) gave the reviewer a map; it found the door NOT on the list.
- Design boards were approved before the build, so no UI rework.

## What went wrong, and the lesson
1. **"Never the student" was checked only at the moment of assigning.** Identity can change after: a mentor
   invited with no UID is linked to the student's own login on a later sign-in, an email is moved, an alias is
   claimed. **Lesson:** an identity rule on a RELATIONSHIP must be re-checked where the identity changes (the
   link, the move) and guarded at read time — not only where the relationship is created.
2. **A new tab was hidden from reviewers, but the activity timeline carried the same names.** **Lesson:** when a
   surface is fenced by role, list every OTHER reader of the same facts (timelines, exports, emails) and fence
   them in the same change.
3. An award reverted to the pool was a fourth way out that nobody listed.

## Numbers
- pytest 11322 passed (baseline 11212); jest 5838 passed (baseline 5816); makemigrations clean; wat_lint 0 fail.
- Bundle: median 147.413 kB (0.6 kB under budget); `/scholarship/application` 0.209 kB under its line
  (TD-433, not touched by 7b).
- 61 files in the two commits.

## Follow-up (same day) — mentors are invited from Invitations, like sources
LIVE main 23ec0494; api-01226-p5d, web-01052-v94; 0197 ledger row by hand, `invite_mentor` seeded. Owner, looking at the Mentors, Sources and Invitations pages side by side: the Mentors page is a
MANAGEMENT page (like People for reviewers), with Mentors · Emails · Terms tabs; inviting lives on Invitations. The
mentor letter became an editable `invite_mentor` template. Its review found a finance read of mentor invitations, a
way to put the temporary password into an email SUBJECT (all invitation kinds, pre-existing — now refused at save and
at send), two disagreeing edit gates, and a Reactivate that still sent an invitation from the management page.
**Lesson:** when the owner compares pages side by side, the pattern of the SIBLING pages is the spec — 7a built the
mentor invite on the Mentors page because the board drew it there, while every sibling (sources, sponsors, staff)
invites from Invitations. Check the sibling surfaces before trusting a single board.

## Sprint 7c (same day) — mentors see their students and log meetings
LIVE main e5bf699c; api-01228-98t, web-01054-7mz; 0198 applied by hand first. Owner rulings: the mentor sees the student's email and phone and the latest result only; a worry
flag reaches staff, who mark it handled. Design approved first (MentorStudents / MentorStudentFile / MentorPhone
boards). The adversarial review found no horizontal access path (the mentor desk is an allowlist over the mentor's
OWN open assignments, fenced to their organisation's live files, never their own application); two small fixes: the
student's CURRENT contact email (the submit-time copy can be stale), and no concern chip on a closed file (it can no
longer be handled). pytest 11417, jest 5934. **Lesson:** a copied field (`notify_email`) is a snapshot — a reader that
needs the live value must read the source, not the copy.

## Sprint 7d (same day) — staff can also be mentors, on the same login
LIVE main fe6f21de; api-01229-4x6, web-01056-pld; courses 0091 applied by hand first. Org admins, admins, reviewers and QC can be added as mentors from the Mentors page (no email);
they keep their role and gain My students and the mentor profile cards (share-phone-with-students OFF for existing
staff). Every staff exit (Stop, revoke, cancel, role change to finance, re-invite) ends mentoring without touching
the login; mentoring counts as recorded work, so a staff mentor who has mentored is revoke-only. The review found a
staff phone shown on staff screens without the team-visibility rule, and a revoke/cancel racing an add (fixed with
row locks and a refusal for login-less or inactive mentors). **Lesson:** when one row gains a second role, every
"is this a pure X?" test in the code is a door — list them (deny-by-default, staff lists, lifecycle) before building.

## Next
Sprint 8 (Announcements) or 7c (mentors see their students and log meetings), on the owner's choice.

## Sprint 8 (2026-11-02) — announcements
LIVE main adfeddc7; api-01232-zdb, web-01059-4vp; scholarship 0199 applied by hand; Cloud Scheduler job
`halatuju-announcement-emails` (hourly, first run 200). Org admins and admins post to all funded scholars or one
programme; one text for all; publish now or later; pin; edit (never re-emails) and withdraw; students read on My
Bursary → News with an unread badge; optional email claimed once per scholar before sending, behind the
`announcement` switch, metered. The owner paused the build mid-way and resumed it; the half-built work survived
untouched in the worktree. Review found no hole (five low notes, recorded in decisions.md). pytest 11499, jest 6012.
**Lesson:** a new cron job is two deploy steps — the code AND the Scheduler job; the health light going red is the
reminder, but name the job in the push plan so it is never left out.

## Sprint 9 (2026-11-02) — surveys
LIVE 2026-11-02 (main ab806a87; api-01236-jkr, web-01062-wx2; 0200 applied by hand first; Scheduler job halatuju-survey-emails hourly, first run OK). Org admins and admins make surveys (six question types, up to 30) for all funded scholars or one
programme; dates give the status; the questions lock at the first answer; scholars answer on My Bursary → Surveys
and can change their answers until it closes; Results with who answered, Not answered + Remind, CSV with formula
cells escaped; the scholar file's Surveys tab. Optional opening email and 3-days-before reminder, claimed once per
scholar per kind, behind the `survey_open` switch, metered. Review found two real holes, fixed before the push with
a test each: a published survey could be emptied and then frozen by one blank answer, and Remind with the switch
off marked everyone "reminded" for ever. pytest 11564, jest 6118, median 145.385 kB (budget 147).
**Lesson:** a new lazy screen that imports the admin auth PROVIDER drags `admin-supabase` into more chunks, and
webpack then regrouped shared chunks onto every student route (+0.9 kB) although no survey code was there. Lazy
screens that only read the session import `useAdminAuth` from the leaf `src/lib/adminAuthCore.ts`.
