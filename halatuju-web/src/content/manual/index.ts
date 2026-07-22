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

export type { ManualChapter, ManualSection, ManualRole, Audience } from './types'

/** Ordered — this is the sidebar order (Basics → role chapters → Help). */
export const CHAPTERS: ManualChapter[] = [
  basicsProgramme, basicsFourChecks, basicsStatuses, basicsConfidentiality,
  roleReviewer, roleQc, roleOrgAdmin, roleAdminGeneral, roleFinance,
  helpChapter,
]

/** Normalise an admin-auth role object to a ManualRole. A super (by flag or role) is 'super';
 *  a partner/unknown → undefined (sees Basics + Help + no role chapter). */
export function manualRole(role: { role?: string; is_super_admin?: boolean } | null | undefined): ManualRole | undefined {
  if (!role) return undefined
  if (role.is_super_admin || role.role === 'super') return 'super'
  if (role.role === 'reviewer' || role.role === 'qc' || role.role === 'org_admin'
      || role.role === 'admin' || role.role === 'finance') {
    return role.role
  }
  return undefined   // partner / anything else
}

/** Chapters visible to a role. Basics + Help are always shown; role chapters are shown to
 *  their own role, to org_admin (they manage those people), and to super. */
export function visibleChapters(role: ManualRole | undefined): ManualChapter[] {
  const seesAllRoles = role === 'super' || role === 'org_admin'
  return CHAPTERS.filter((c) => {
    if (c.group !== 'role') return true
    if (seesAllRoles) return true
    return c.role === role
  })
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
): { slug: string; anchor?: string } {
  const visible = visibleChapters(role)
  const clean = (hash || '').replace(/^#/, '')
  if (clean) {
    const byslug = visible.find((c) => c.slug === clean)
    if (byslug) return { slug: byslug.slug }
    const bysection = visible.find((c) => c.sections.some((s) => s.anchor === clean))
    if (bysection) return { slug: bysection.slug, anchor: clean }
  }
  return { slug: defaultChapterSlug(role) }
}
