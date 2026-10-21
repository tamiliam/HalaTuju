// Role-aware manual — chapter registry + visibility/resolution helpers (pure, unit-tested).
import type { ManualChapter, ManualRole } from './types'
import { basicsProgramme } from './basics-programme'
import { basicsFourChecks } from './basics-four-checks'
import { basicsStatuses } from './basics-statuses'
import { basicsConfidentiality } from './basics-confidentiality'
import { roleReviewer } from './role-reviewer'
import { roleQc } from './role-qc'
import { roleOrgAdmin } from './role-org-admin'
import { roleAdminGeneral } from './role-admin-general'
import { roleFinance } from './role-finance'
import { helpChapter } from './help'
import { effectiveRole } from '@/lib/navigation'
import { TEAM_ROLES } from '@/lib/staffPermissions'

export type { ManualChapter, ManualSection, ManualRole, Audience } from './types'

/** Ordered — this is the sidebar order (Basics → role chapters → Help). */
export const CHAPTERS: ManualChapter[] = [
  basicsProgramme, basicsFourChecks, basicsStatuses, basicsConfidentiality,
  roleReviewer, roleQc, roleOrgAdmin, roleAdminGeneral, roleFinance,
  helpChapter,
]

/** Normalise an admin-auth role object to a ManualRole. A super (by flag or role) is 'super';
 *  a partner/unknown → undefined (sees Basics + Help + no role chapter).
 *
 *  The super rule is the one `effectiveRole` owns (lib/navigation.ts) — it was written out in
 *  eleven places before N1 and this was the last copy. The REST is deliberately still explicit:
 *  `effectiveRole` falls back to 'reviewer' for an unknown or missing role, which is right for a
 *  menu (show the least) and wrong here (it would hand a partner the reviewer's manual). The
 *  manual's fallback is "no role chapter at all", so the accepted list stays literal. */
export function manualRole(role: { role?: string; is_super_admin?: boolean } | null | undefined): ManualRole | undefined {
  if (!role) return undefined
  if (effectiveRole(role) === 'super') return 'super'
  if (role.role === 'reviewer' || role.role === 'qc' || role.role === 'org_admin'
      || role.role === 'admin' || role.role === 'finance') {
    return role.role
  }
  return undefined   // partner / anything else
}

/** The permissions a TEAM member holds, as `/admin/role/` served them (request #39) — and none for
 *  anybody else: an organisation admin and a super already see every chapter, a partner none. */
export function manualPerms(
  role: { role?: string; is_super_admin?: boolean; permissions?: readonly string[] | null } | null | undefined,
): readonly string[] {
  if (!role || effectiveRole(role) === 'super') return []
  return (TEAM_ROLES as readonly string[]).includes(role.role ?? '') ? (role.permissions ?? []) : []
}

/** Shown under another role's chapter when only the sections for given permissions are open. */
export const GIVEN_BLURB = 'The parts of this role your organisation has given you.'

/** Chapters visible to a role. Basics + Help are always shown; role chapters are shown to
 *  their own role, to org_admin (they manage those people), and to super.
 *
 *  ⚠ #39 Sprint 4: a team member ALSO sees, in another role's chapter, the sections tagged with a
 *  permission they hold (`ManualSection.perm`) — Rohini, a Reviewer given Spending, reads her own
 *  chapter whole and the General admin chapter's Spending section. Nothing else of that chapter. */
export function visibleChapters(role: ManualRole | undefined,
                                permissions: readonly string[] = []): ManualChapter[] {
  const seesAllRoles = role === 'super' || role === 'org_admin'
  const out: ManualChapter[] = []
  for (const c of CHAPTERS) {
    if (c.group !== 'role' || seesAllRoles || c.role === role) { out.push(c); continue }
    const given = c.sections.filter((s) => s.perm && permissions.includes(s.perm))
    if (given.length > 0) out.push({ ...c, blurb: GIVEN_BLURB, sections: given })
  }
  return out
}

/** The chapter a caller lands on: their own role chapter if they have one, else the first
 *  Basics chapter. */
export function defaultChapterSlug(role: ManualRole | undefined): string {
  const own = CHAPTERS.find((c) => c.group === 'role' && c.role === role)
  return own?.slug ?? CHAPTERS[0].slug
}

/** Resolve a URL hash (a chapter slug OR a section anchor) to a VISIBLE chapter + optional
 *  section anchor. A hash pointing at a hidden/absent chapter falls back to the default
 *  chapter with no anchor (never an error). */
export function resolveTarget(
  hash: string | undefined,
  role: ManualRole | undefined,
  permissions: readonly string[] = [],
): { slug: string; anchor?: string } {
  const visible = visibleChapters(role, permissions)
  const clean = (hash || '').replace(/^#/, '')
  if (clean) {
    const byslug = visible.find((c) => c.slug === clean)
    if (byslug) return { slug: byslug.slug }
    const bysection = visible.find((c) => c.sections.some((s) => s.anchor === clean))
    if (bysection) return { slug: bysection.slug, anchor: clean }
  }
  return { slug: defaultChapterSlug(role) }
}
