'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import { getAdminSession, getAdminSupabase } from '@/lib/admin-supabase'
import type { Session } from '@supabase/supabase-js'

interface AdminRole {
  is_admin: boolean
  is_super_admin: boolean
  org_name: string | null
  admin_name: string
}

interface AdminAuthContextValue {
  session: Session | null
  token: string | null
  isLoading: boolean
  isAdminAuthenticated: boolean
  role: AdminRole | null
  refreshRole: () => Promise<void>
}

const AdminAuthContext = createContext<AdminAuthContextValue | null>(null)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [role, setRole] = useState<AdminRole | null>(null)
  const [isLoading, setIsLoading] = useState(true)

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
