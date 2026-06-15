# Retrospective — Reviewer access fix (2026-06-16)

A short follow-up close for the two reviewer-onboarding faults reported the day after the
reviewer-invite + profile-redesign rounds went live. Commit `4a74b9b`.

## What Was Built
- **Invite link → `/admin/login`.** `AdminInviteView` now sets `redirect_to: {FRONTEND_URL}/admin/login`
  on the Supabase invite POST, so the magic link opens the partner sign-in page instead of the public homepage.
- **Role-aware post-login landing.** Both entry points — `admin/login/page.tsx` and `admin/auth/callback/page.tsx`
  — branch on `role.role` from `/api/v1/admin/role/`: `reviewer`/`viewer` go to `/admin/scholarship`
  (B40 Applications), org `admin`/`super` keep `/admin` (the partner dashboard).

## What Went Well
- Both faults were single-cause and fixed in one 3-file commit, no migration.
- The Supabase Redirect-URL allow-list already had the `halatuju.xyz/**` wildcard, so the invite fix
  needed no dashboard change — confirmed against the live config (screenshot) before assuming.
- Verified post-deploy against the running services (web `/admin/login` 200, api 200, flags intact)
  rather than trusting the deploy log.

## What Went Wrong
1. **Reviewers hit a dead-end on first login ("not a partner organisation admin").**
   - *Symptom:* a freshly-invited reviewer signed in and landed on the partner-org dashboard, which 403s for them.
   - *Root cause:* `/admin` was treated as the universal post-login home, but it is specifically the
     partner-org dashboard (`getPartnerDashboard`). The reviewer/viewer roles — added later for B40 — belong to
     no partner org, so the "default landing" assumption was never re-checked when those roles were introduced.
   - *System change:* landing is now derived from the role, not hardcoded. Lesson recorded so future role
     additions check every place that assumes "admin == partner-org admin".
2. **Invite link silently dropped users on the homepage.**
   - *Symptom:* the invite email's button opened `/`, leaving the invitee with no obvious next step.
   - *Root cause:* `redirect_to` was never passed to the Supabase invite call, so it fell back to the Site URL.
   - *System change:* the invite POST sets `redirect_to` explicitly; verified the Redirect-URL allow-list covers it.

## Design Decisions
- Route by role on the **client** (the two existing auth entry points) rather than adding a server redirect —
  the role is already fetched there for the `is_admin` gate, so it is one extra branch with no new round-trip.

## Numbers
- 3 files (2 web pages + `views_admin.py`), no migration.
- Backend suite unchanged and green (no backend logic changed beyond one invite kwarg).
