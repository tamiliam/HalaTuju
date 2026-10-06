# Retrospective — reviewer first-login onboarding gate (2026-07-15)

Branch `feat/reviewer-onboarding` (worktree, off `origin/main`). No migration.

## What Was Built

A newly-invited reviewer used to land on the B40 Applications list with a blank profile. Now they
land on **/admin/profile** and are held there until their compulsory fields are filled.

- **Backend:** `reviewer_onboarding.reviewer_profile_complete(admin)` — reviewer-only (`True` for
  super/qc/viewer/partner/admin), computed from the `ReviewerProfile` row + the PartnerAdmin name.
  Surfaced as `reviewer_profile_complete` on `GET /api/v1/admin/role/` (the one place login,
  callback and the layout guard all already read).
- **Frontend:** pure `adminLanding()` + `mustCompleteProfile()` (`lib/adminLanding.ts`) drive the
  login/callback landing AND a guard in the admin layout; `lib/reviewerProfile.ts` mirrors the
  compulsory-field check for the `*` markers + the live "still needed" banner + the redirect on a
  completing save. Reviewer-only; the profile/set-password/auth/login pages are exempt from the
  guard so it can't loop.
- **Folded-in fix:** the set-password page now renders the account email as an
  `autocomplete="username"` field, fixing the empty "Username" in Chrome's password-manager prompt.

## What Went Well

- **The plan surfaced the one real decision up front.** No completeness concept existed anywhere, so
  "which fields are compulsory" was a genuine owner call — asked and answered before any code, so the
  build was unambiguous.
- **Everything gated on one backend flag.** login, callback and the layout guard all read the same
  `reviewer_profile_complete`, so the "first login → profile, until filled" rule can't drift between
  the three surfaces. The two pure helpers made it node-testable (19 jest).

## What Went Wrong

- **The super-admin misfired on the first backend cut.** `reviewer_profile_complete` gated on
  `admin.role == 'reviewer'`, but a super's `role` COLUMN defaults to `'reviewer'` — so a super with
  no explicit role was (briefly, in the test) treated as an un-onboarded reviewer.
  - *Root cause:* the app has a two-layer role model — the `is_super` bridge overrides the `role`
    column — and the `role` column's default is `'reviewer'`, so reading `.role` alone is wrong for a
    super. The role ENDPOINT already knew this (`'super' if admin.is_super else admin.role`); the new
    gate didn't mirror it.
  - *Fix (this sprint):* the gate checks `is_super` first, matching the endpoint. A regression test
    (`test_super_flag_true`) locks it. *Systemic:* any new code branching on a PartnerAdmin's role
    must honour the `is_super` bridge, never the bare `role` column — captured in lessons.md.

## Design Decisions

See `docs/decisions.md`:
- Reviewer-only gate off a single `reviewer_profile_complete` flag; "at least one spoken language"
  rather than "all three set" (the "None" option is an empty value indistinguishable from unset).

## Numbers

- `pytest` (onboarding + role-endpoint-adjacent suites) **106 passed** (+11 new); jest **19 passed**
  (landing/guard/mirror + i18n parity); `next build` **exit 0**. No migration.
- Files: 2 backend (new module + AdminRoleView) + 1 test; 2 new FE libs + 1 jest; login/callback/
  layout/auth-context/profile/set-password rewired; 3 i18n (`admin.reviewer.onboarding.*`).
