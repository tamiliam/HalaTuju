/**
 * Where an admin lands after login, and whether a reviewer must be held on their profile page
 * until onboarding is complete. Pure (node-testable); the single source both the login/callback
 * redirects and the admin-layout guard read, so the "first login → profile, until fields filled"
 * rule can't drift between them.
 *
 * `reviewer_profile_complete` comes from GET /api/v1/admin/role/ (backend
 * `reviewer_onboarding.reviewer_profile_complete`). It is `true` for every non-reviewer, so only a
 * reviewer is ever gated. We check `=== false` (not falsy) so an OLD payload that omits the field
 * never traps anyone.
 */
export interface AdminRoleLike {
  role?: string
  reviewer_profile_complete?: boolean
}

/** The post-login destination for an authenticated admin. */
export function adminLanding(role: AdminRoleLike): string {
  if (role.role === 'reviewer' && role.reviewer_profile_complete === false) return '/admin/profile'
  if (role.role === 'reviewer' || role.role === 'viewer') return '/admin/scholarship'
  return '/admin'
}

/** True when a reviewer with an incomplete profile is on a page other than the profile page (and
 *  not the login/auth pages) — i.e. the layout should bounce them back to /admin/profile. */
export function mustCompleteProfile(
  role: AdminRoleLike | null | undefined,
  pathname: string,
): boolean {
  if (!role || role.role !== 'reviewer' || role.reviewer_profile_complete !== false) return false
  if (pathname === '/admin/profile') return false
  if (pathname === '/admin/login' || pathname.startsWith('/admin/auth/')) return false
  if (pathname === '/admin/set-password') return false  // must be able to set their password first
  return true
}
