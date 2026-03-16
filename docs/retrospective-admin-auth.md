# Retrospective — Admin Auth Sprint

**Date:** 2026-03-16
**Branch:** feature/admin-auth (merged to main)

## What Was Built

A completely separate admin authentication system, decoupled from student auth at every layer:

- **Backend**: PartnerAdmin model (separate from StudentProfile), PartnerAdminMixin rewrite (UID lookup + email fallback + UID backfill), invite endpoint (Supabase inviteUserByEmail), orgs endpoint, AdminRoleView with admin_name
- **Frontend**: Isolated admin Supabase client (separate localStorage key), AdminAuthProvider + useAdminAuth() hook, admin login page (email/password + Google + forgot password), OAuth callback, invite page (super admin only), admin layout with nav
- **Data model changes**: Added contact_person + phone to PartnerOrganisation, removed admin_org_code from StudentProfile
- **Migrations**: 0036_partneradmin, 0037_remove_admin_org_code_add_org_fields

## What Went Well

- **Clean separation**: Admin and student sessions are completely independent at every layer (different Supabase clients, different localStorage keys, different auth providers, different models). No cross-contamination possible.
- **Subagent-driven development**: 12 tasks executed efficiently across subagents with clear boundaries.
- **Spec compliance review passed on first try**: The implementation matched the design doc without deviations.
- **Code quality review caught a real issue**: Double `get_admin` calls in admin pages — fixed immediately before merge.

## What Went Wrong

- **Migration conflict**: Feature branch created `0035_partneradmin` but main already had `0035_add_angka_giliran`. Root cause: branch diverged before the angka_giliran migration was merged to main. Fix: renumbered to 0036/0037 after merge.
- **This is the THIRD time migration numbering has been an issue in this project.** Pattern: parallel work on feature branches creates same-numbered migrations. The previous instances were partner referral migrations (renumbered from 0031) and another earlier conflict. **Prevention needed**: Always rebase feature branches before creating migrations, or check `max(migration number)` on main before numbering.

## Design Decisions

1. **Separate PartnerAdmin table** (not a role on StudentProfile): Admin identity is fundamentally different from student identity. Different fields (org FK, is_super_admin), different auth flow, different lifecycle. A role flag on StudentProfile would have required every admin to also have a student profile.

2. **Isolated Supabase clients with separate localStorage keys**: Even if the same person is both a student and an admin, they log in separately. This prevents session confusion and makes it impossible for a student session to accidentally grant admin access.

3. **UID lookup + email fallback + UID backfill**: First login uses email to find the PartnerAdmin row (created by invite), then backfills the Supabase UID. Subsequent logins use UID directly. This handles the chicken-and-egg problem where the admin row exists before the user has a Supabase account.

## Numbers

- **Commits**: 12 feature commits + 1 merge
- **Backend tests**: 590 -> 615 (+25, of which 14 are new admin auth tests)
- **Migrations**: 2 new (0036, 0037)
- **Files created**: ~10 (model, views, tests, admin client, auth provider, login page, callback, invite page, admin-api.ts)
- **Files modified**: ~15 (views.py, models.py, urls.py, admin layout, footer, storage keys)
