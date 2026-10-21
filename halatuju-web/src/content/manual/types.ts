// Role-aware admin manual — shared types.
//
// One module per chapter under src/content/manual/, each exporting a typed ManualChapter.
// English content now; the module shape is deliberately per-file so a future `ms`/`ta`
// sibling per chapter is trivial (per-locale resolution with EN fallback). Do NOT
// machine-translate Tamil — the owner is the Tamil authority (the pages are EN-only today).
//
// Every capability statement in a chapter MUST trace to docs/scholarship/role-matrix.md
// (the authority) and the live UI — no invented behaviour. When a role power changes, its
// chapter + FAQ update in the same change (the currency rule now covers all chapters).
import type { ReactNode } from 'react'
import type { StaffPermission } from '@/lib/staffPermissions'

/** The concrete staff roles a chapter can be scoped to. `super` sees everything. */
export type ManualRole = 'reviewer' | 'qc' | 'org_admin' | 'admin' | 'finance' | 'super'

/** FAQ audiences (also the role-chapter audiences). `everyone` = shown to all roles. */
export type Audience = 'everyone' | 'reviewer' | 'qc' | 'org_admin' | 'admin' | 'finance'

export interface ManualSection {
  /** Stable, unique anchor for deep links, e.g. `org-admin-assigning`
   *  (→ /admin/guide#org-admin-assigning). Never rename casually — emails/queries link here. */
  anchor: string
  title: string
  body: ReactNode
  /** Optional screenshot; new chapters ship a placeholder until the owner capture pass. */
  img?: string
  alt?: string
  /** A tall (portrait) screenshot floats right + wraps so it doesn't dominate. */
  float?: boolean
  /** Render the QC two-person-control ("no conflict") banner above this section. */
  noConflictBanner?: boolean
  /** The staff permission this section documents (request #39 Sprint 4). A team member whose
   *  organisation GAVE them that permission sees this section even though the chapter is another
   *  role's (`visibleChapters`). ⚠ Tag only with a key no OTHER role's preset holds, or that preset
   *  would grow a chapter it never had — `manual.test.ts` asks every preset. */
  perm?: StaffPermission
}

export interface ManualChapter {
  /** Unique slug; also the chapter's URL hash (/admin/guide#<slug>). */
  slug: string
  title: string
  /** Sidebar grouping. */
  group: 'basics' | 'role' | 'help'
  /** For a role chapter: which role it documents (drives visibility + the role badge). */
  role?: ManualRole
  /** One-line sidebar/breadcrumb subtitle. */
  blurb?: string
  sections: ManualSection[]
}
