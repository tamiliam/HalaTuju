'use client'

import {
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from 'react'
import { getAdminSession, getAdminSupabase } from '@/lib/admin-supabase'
import type { Session } from '@supabase/supabase-js'
import { AdminAuthContext, useAdminAuth, type AdminAuthContextValue, type AdminRole } from '@/lib/adminAuthCore'

// The context and its hook live in the leaf `adminAuthCore` (no Supabase client); re-exported so the
// sandbox harness and every importer are unchanged.
export { AdminAuthContext, useAdminAuth }

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
