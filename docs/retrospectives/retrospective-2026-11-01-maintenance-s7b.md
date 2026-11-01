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

## Next
Sprint 8 (Announcements) or 7c (mentors see their students and log meetings), on the owner's choice.
