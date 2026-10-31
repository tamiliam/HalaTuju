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
import { canAccess, defaultRoute } from '@/lib/navigation'

export interface AdminRoleLike {
  role?: string
  is_super_admin?: boolean
  reviewer_profile_complete?: boolean
  /** #39 S3 review fix 3: the served permissions, so the landing matches the menu. */
  permissions?: readonly string[] | null
}

/**
 * The post-login destination for an authenticated admin.
 *
 * ⚠ IT DELEGATES NOW, AND IT DID NOT BEFORE. `navigation.ts:defaultRoute` has claimed in its
 * docstring since N2 that "adminLanding() delegates here, so the rule has one home" — and it did
 * not: this function held a second, hand-copied implementation of the same three lines. They
 * agreed only because nobody had changed either. Deriving the landing route from the registry
 * (2026-09-08) is precisely the kind of change that would have split them, so the claimed
 * delegation is now the real one. There is one rule and one place it lives.
 */
export function adminLanding(role: AdminRoleLike): string {
  return defaultRoute(role, role.reviewer_profile_complete)
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

/** The roles that sign in but are NOT staff, so every staff page refuses them (deny by default). */
const OUTSIDER_ROLES = ['source_partner', 'mentor'] as const
type OutsiderRole = (typeof OUTSIDER_ROLES)[number]

/**
 * A SOURCE user (review M3, source sign-in 2026-10-30) — or, since student maintenance S7a
 * (2026-10-31), a MENTOR — on a page it may not open: the layout sends it to its landing BEFORE the
 * page mounts. Every staff page would otherwise mount and fire staff fetches the server refuses
 * (deny by default): a typed URL, an old bookmark or a staff link must land somewhere real, not on
 * a page of 403s. The registry answers (`canAccess`): an unregistered route is NOT blocked, the
 * module rule. Only these two roles are held here; a mentor's landing is `/admin/profile`.
 */
export function outsiderMustLeave(role: AdminRoleLike | null | undefined, pathname: string): boolean {
  const r = role?.role
  if (!r || !(OUTSIDER_ROLES as readonly string[]).includes(r)) return false
  return !canAccess(pathname, r as OutsiderRole, role?.permissions)
}
