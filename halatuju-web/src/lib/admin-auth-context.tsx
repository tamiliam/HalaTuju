'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from 'react'
import { getAdminSession, getAdminSupabase } from '@/lib/admin-supabase'
import type { Session } from '@supabase/supabase-js'

interface AdminRole {
  is_admin: boolean
  is_super_admin: boolean
  role?: 'super' | 'admin' | 'org_admin' | 'partner' | 'reviewer' | 'qc' | 'finance' | 'source_partner'
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
}

interface AdminAuthContextValue {
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
}

// Exported for the sandbox harness ONLY (src/sandbox), which supplies a canned admin session to
// render admin pages without Supabase. App code must go through `AdminAuthProvider`.
export const AdminAuthContext = createContext<AdminAuthContextValue | null>(null)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [role, setRole] = useState<AdminRole | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [photoUrl, setPhotoUrl] = useState<string | null>(null)
  const photoFor = useRef<number | null>(null)

  // The header photo: ONE `admin/me/` read per signed-in person per session (the provider lives in
  // the admin layout, so client navigation does not repeat it). A failure leaves the initials.
  const adminId = role?.is_admin ? role.admin_id ?? null : null
  const accessToken = session?.access_token ?? null
  // Review fix L6: signed out → no photo; a DIFFERENT person signed in → the last person's photo is
  // dropped at once, and a late answer for somebody who is no longer signed in is ignored.
  useEffect(() => {
    if (adminId == null) { photoFor.current = null; setPhotoUrl(null); return }
    if (!accessToken || photoFor.current === adminId) return
    photoFor.current = adminId
    setPhotoUrl(null)
    const asked = adminId
    fetch(`${API_BASE}/api/v1/admin/me/`, { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((res) => (res.ok ? res.json() : null))
      .then((me) => { if (photoFor.current === asked) setPhotoUrl(me?.photo_url ?? null) })
      .catch(() => {})
  }, [adminId, accessToken])

  const checkRole = useCallback(async (token: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/role/`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      })
      if (res.ok) {
        const data = await res.json()
        if (data.is_admin) {
          setRole(data)
          return true
        }
      }
    } catch {
      // Role check failed
    }
    setRole(null)
    return false
  }, [])

  const refreshRole = useCallback(async () => {
    if (session?.access_token) {
      await checkRole(session.access_token)
    }
  }, [session, checkRole])

  useEffect(() => {
    getAdminSession()
      .then(async ({ session }) => {
        setSession(session ?? null)
        if (session?.access_token) {
          await checkRole(session.access_token)
        }
        setIsLoading(false)
      })
      .catch(() => setIsLoading(false))

    const {
      data: { subscription },
    } = getAdminSupabase().auth.onAuthStateChange(async (event, session) => {
      setSession(session)
      if (session?.access_token) {
        await checkRole(session.access_token)
      } else {
        setRole(null)
      }
    })
    return () => subscription.unsubscribe()
  }, [checkRole])

  const value: AdminAuthContextValue = {
    session,
    token: session?.access_token ?? null,
    isLoading,
    isAdminAuthenticated: !!session && !!role?.is_admin,
    role,
    refreshRole,
    photoUrl,
    setPhotoUrl,
  }

  return (
    <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
  )
}

export function useAdminAuth() {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) throw new Error('useAdminAuth must be used within AdminAuthProvider')
  return ctx
}
