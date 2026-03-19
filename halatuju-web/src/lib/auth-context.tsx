'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import { getSession, getSupabase } from '@/lib/supabase'
import { getProfile } from '@/lib/api'
import type { Session } from '@supabase/supabase-js'
import { KEY_PENDING_AUTH_ACTION, KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS, migrateProfile } from '@/lib/storage'

export type AuthGateReason = 'quiz' | 'save' | 'report' | 'eligible' | 'profile' | 'loadmore' | null

interface AuthGateOptions {
  courseId?: string
}

interface AuthContextValue {
  session: Session | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  authGateReason: AuthGateReason
  authGateCourseId: string | null
  showAuthGate: (reason: NonNullable<AuthGateReason>, options?: AuthGateOptions) => void
  hideAuthGate: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * Restore student data from Supabase into localStorage for a returning user.
 * Only writes keys that are missing locally (avoids overwriting fresh data).
 */
async function restoreProfileToLocalStorage(token: string) {
  try {
    const profile = await getProfile({ token })
    if (!profile.grades || Object.keys(profile.grades).length === 0) return

    // Grades
    if (!localStorage.getItem(KEY_GRADES)) {
      localStorage.setItem(KEY_GRADES, JSON.stringify(profile.grades))
    }

    // Demographics (gender, nationality, colorblind, disability)
    if (!localStorage.getItem(KEY_PROFILE)) {
      const demo: Record<string, unknown> = {}
      if (profile.gender) demo.gender = profile.gender
      if (profile.nationality) demo.nationality = profile.nationality
      if (profile.colorblind != null) demo.colorblind = profile.colorblind
      if (profile.disability != null) demo.disability = profile.disability
      if (Object.keys(demo).length > 0) {
        localStorage.setItem(KEY_PROFILE, JSON.stringify(demo))
      }
    }

    // Quiz signals
    if (!localStorage.getItem(KEY_QUIZ_SIGNALS) && profile.student_signals) {
      localStorage.setItem(KEY_QUIZ_SIGNALS, JSON.stringify(profile.student_signals))
    }
  } catch {
    // Non-critical — user can still use the app without restored data
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [authGateReason, setAuthGateReason] = useState<AuthGateReason>(null)
  const [authGateCourseId, setAuthGateCourseId] = useState<string | null>(null)

  useEffect(() => {
    // Migrate legacy "Ya"/"Tidak" strings to booleans in localStorage
    migrateProfile()

    getSession()
      .then(({ session }) => {
        setSession(session ?? null)
        setIsLoading(false)

        // Restore profile from Supabase if localStorage is empty (e.g. cache cleared)
        if (session?.access_token && !localStorage.getItem(KEY_GRADES)) {
          restoreProfileToLocalStorage(session.access_token)
        }

        // Check for pending auth action (from Google OAuth redirect)
        if (session) {
          const pending = localStorage.getItem(KEY_PENDING_AUTH_ACTION)
          if (pending) {
            try {
              const { reason, courseId } = JSON.parse(pending)
              if (reason) {
                setAuthGateReason(reason)
                if (courseId) setAuthGateCourseId(courseId)
              }
            } catch {
              localStorage.removeItem(KEY_PENDING_AUTH_ACTION)
            }
          }
        }
      })
      .catch(() => setIsLoading(false))

    const {
      data: { subscription },
    } = getSupabase().auth.onAuthStateChange((event, session) => {
      setSession(session)

      // Restore profile from Supabase when a user signs in
      if (event === 'SIGNED_IN' && session?.access_token) {
        restoreProfileToLocalStorage(session.access_token)
      }
    })
    return () => subscription.unsubscribe()
  }, [])

  const showAuthGate = useCallback(
    (reason: NonNullable<AuthGateReason>, options?: AuthGateOptions) => {
      setAuthGateReason(reason)
      setAuthGateCourseId(options?.courseId ?? null)
    },
    []
  )

  const hideAuthGate = useCallback(() => {
    setAuthGateReason(null)
    setAuthGateCourseId(null)
  }, [])

  const value: AuthContextValue = {
    session,
    token: session?.access_token ?? null,
    isLoading,
    isAuthenticated: !!session,
    authGateReason,
    authGateCourseId,
    showAuthGate,
    hideAuthGate,
  }

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
