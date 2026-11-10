'use client'

/**
 * The admin auth CONTEXT and its hook, without the Supabase client (student maintenance S9, 2026-11-02).
 *
 * ⚠ WHY A LEAF: `admin-auth-context.tsx` (the PROVIDER) imports `admin-supabase`, and every lazy admin
 * screen that imported `useAdminAuth` from it carried those modules into its own chunk. With two more such
 * screens (Programme -> Surveys and its Results) webpack pulled the admin and sponsor session modules out
 * into a NEW shared chunk that every student route then loaded (+0.9 kB on /scholarship/application and
 * /scholarship/apply). A screen that only READS the session imports the hook from HERE; the provider, the
 * sandbox harness and every existing importer keep `@/lib/admin-auth-context`, which re-exports both.
 */
import { createContext, useContext } from 'react'
import type { Session } from '@supabase/supabase-js'
import type { ProfileCompletion } from '@/lib/admin-api/profiles'

export interface AdminRole {
  is_admin: boolean
  is_super_admin: boolean
  role?: 'super' | 'admin' | 'org_admin' | 'partner' | 'reviewer' | 'qc' | 'finance' | 'source_partner' | 'mentor'
  admin_id?: number | null
  org_name: string | null
  // The B40 tenant this staff member administers (their access boundary) — NOT the
  // referral org. The Administration panel's org section keys off these.
  owning_org_id?: number | null
  owning_org_name?: string | null
  admin_name: string
  /** False only for a reviewer who hasn't filled their compulsory profile fields yet — the
   *  admin layout then holds them on /admin/profile until it flips true. True for everyone else. */
  reviewer_profile_complete?: boolean
  /** The caller's org-resolved temp-password TTL (Org Config Sprint C). The login gate reads
   *  THIS — never a hard-coded mirror of the platform's 7. */
  temp_password_ttl_days?: number
  /** Request #39: the staff permissions the server RESOLVED for this person (never null when
   *  served), the preset they came from, and whether they were customised. Read with
   *  `staffPermissions.hasPerm`; the server stays the fence. */
  permissions?: string[]
  preset?: string
  custom?: boolean
  /** Source sign-in S1: the referral source a `source_partner` signs in for; null for every
   *  other role (absent on a payload from before S1). */
  source_id?: number | null
  source_name?: string | null
  /** S7d: a STAFF member who also mentors NOW (an active mentor record) — My students joins their
   *  menu and the profile gains the mentoring bits. False / absent for everybody else (a mentor login
   *  reads its `role`). */
  mentoring?: boolean
  /** Team tables T1: the tables the server seats this person at (`staff_tables.tables`, derived, never
   *  stored) — 'admins' / 'reviewers' / 'mentors'. The menu, the page guards (`mayOpen`), the landing
   *  and the Guide read it; absent on a payload from before T1, which then reads exactly as before. */
  tables?: string[]
  /** Team tables T5c P4a: the v2 keys the server's page doors ask (`staff_tables.page_keys`, never null when
   *  served; `[]` for a person with no page). The menu rows and page guards on a server door read it
   *  (`pageDoors.opensDoor`); absent on a payload from before P4a, which then reads its role rules. */
  page_keys?: string[]
}

export interface AdminAuthContextValue {
  session: Session | null
  token: string | null
  isLoading: boolean
  isAdminAuthenticated: boolean
  role: AdminRole | null
  refreshRole: () => Promise<void>
  /** Common profile S2: the signed-in person's photo (a ~1-hour signed URL) for the header, or null.
   *  Read from `admin/me/` ONCE per session — never from `admin/role/`, which signs nothing. */
  photoUrl: string | null
  /** The Profile page sets it after an upload or a removal, so the header follows at once. */
  setPhotoUrl: (url: string | null) => void
  /** Staff nudges (2026-11-08): the person's profile completion (`admin/me/` `completion`, the server's
   *  ONE rule), read in the SAME `admin/me/` call as the photo; null for a super or until it arrives.
   *  The console's profile banner reads it. Optional so a harness may leave it out (no banner). */
  profileCompletion?: ProfileCompletion | null
  /** The Profile page sets it after a save or a photo change, so the banner follows at once. */
  setProfileCompletion?: (c: ProfileCompletion | null) => void
}

// Exported for the sandbox harness ONLY (src/sandbox), which supplies a canned admin session to
// render admin pages without Supabase. App code must go through `AdminAuthProvider`.
export const AdminAuthContext = createContext<AdminAuthContextValue | null>(null)

export function useAdminAuth() {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) throw new Error('useAdminAuth must be used within AdminAuthProvider')
  return ctx
}
