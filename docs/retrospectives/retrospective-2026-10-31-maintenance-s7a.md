# Retrospective — Student maintenance Sprint 7a: mentors log in (2026-10-31)

**Live:** main f0bcc0f0; api-01218-7sr, web-01041-xhh (both builds SUCCESS; health 200; no 5xx after the deploy;
`admin/mentors/` answers 401 without a login). Migrations scholarship 0194 and courses 0090 applied by hand first,
with ledger rows; `mentors` has RLS on and one service_role policy; the Security Advisor showed nothing new.

## What shipped
- Role `mentor` on the source-partner pattern: `scholarship.Mentor`, `PartnerAdmin.mentor` with the check
  `partner_admin_mentor_iff_mentor` and the unique index `partner_admin_one_login_per_mentor`, `Invitation.mentor`.
- Deny by default (`mentor_methods`): a mentor reaches only their own account and profile. Swept over every
  admin route; never on a staff list, picker or chain.
- Invite / resend / revoke / deactivate / reactivate (super and org_admin only, org-fenced); staff edit of name
  and email only before the first sign-in.
- The mentor's own profile on the common `/admin/profile` (Mentoring card, reviewer cards without Taking part,
  "Show my phone to my students"); Organisation → Mentors page. en / ms / ta.

## What went well
- The design was aligned with the profile session BEFORE the build, so 7a slotted into its cards and its one
  rules file (`staff_contact.py`) instead of inventing a second profile.
- Migration numbers were claimed by message before use; no collision with four other live sessions.
- The adversarial review earned its cost: two CONFIRMED identity defects that every test had passed.

## What went wrong, and the lesson
1. **An invite could adopt somebody's existing login** (a student's or a sponsor's), and a Google address
   skipped the check entirely. The builder copied the staff invite's "already registered → 201" branch, which is
   right for staff and wrong for a role whose rule is "any existing sign-in is refused". **Lesson:** when a new
   role copies a pattern, list where its rules DIFFER from the pattern's and test each difference — including
   the branch the pattern never takes (here: Google addresses are never provisioned, so "already registered"
   is never seen for them).
2. **"Signed in" was read from one stamp.** `get_admin` links a login by verified email on any request without
   stamping `first_seen_at`, so a linked login still looked "invited" and Resend could reset its password.
   Fixed for mentors (`mentor_invite.has_signed_in`); the same gap on the staff path is **TD-440**.
3. The two review-fix commits did not say "Sprint", so `wat_lint` read them as unlogged small changes; reworded
   before the push. **Lesson:** fix commits inside a sprint name the sprint in the subject.

## Numbers
- pytest 11064 passed, 3 skipped; jest 5598 passed; bundle median 147.122 kB (0.9 kB under budget);
  makemigrations clean; wat_lint 0 fail.
- 64 files in the feature commit, 6 + 4 in the review fixes.

## Next
Sprint 7b — `MentorAssignment` / `MentoringSession`, the Mentoring tab on the scholar file, the student's
Mentoring tab, the "Scholars now" column, the "No mentor" / "Asked for help" filters, and the switchable
"You have a mentor" email.
