'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import { getSession, getSupabase, signInAnonymously } from '@/lib/supabase'
import { getProfile } from '@/lib/api'
import type { Session } from '@supabase/supabase-js'
import { KEY_PENDING_AUTH_ACTION, KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS } from '@/lib/storage'

export type AuthGateReason = 'quiz' | 'save' | 'report' | 'eligible' | 'profile' | 'loadmore' | null

interface AuthGateOptions {
  courseId?: string
}

interface AuthContextValue {
  session: Session | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  isAnonymous: boolean  // true if anonymous session
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
/**
 * Restore student data from Supabase into localStorage.
 * Always overwrites — Supabase is the source of truth, localStorage is a cache.
 */
async function restoreProfileToLocalStorage(token: string) {
  try {
    const profile = await getProfile({ token })
    if (!profile.grades || Object.keys(profile.grades).length === 0) return

    // Grades
    localStorage.setItem(KEY_GRADES, JSON.stringify(profile.grades))

    // Demographics (gender, nationality, colorblind, disability)
    const demo: Record<string, unknown> = {}
    if (profile.gender) demo.gender = profile.gender
    if (profile.nationality) demo.nationality = profile.nationality
    if (profile.colorblind != null) demo.colorblind = profile.colorblind
    if (profile.disability != null) demo.disability = profile.disability
    if (Object.keys(demo).length > 0) {
      localStorage.setItem(KEY_PROFILE, JSON.stringify(demo))
    }

    // Quiz signals
    if (profile.student_signals) {
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
    getSession()
      .then(async ({ session: existingSession }) => {
        let session = existingSession
        if (!session) {
          // No session — sign in anonymously
          const { data } = await signInAnonymously()
          session = data?.session ?? null
        }
        setSession(session ?? null)
        setIsLoading(false)

        // Only restore profile for non-anonymous returning users
        if (session?.access_token && !session.user?.is_anonymous) {
          restoreProfileToLocalStorage(session.access_token)
        }

        // Check for pending auth action (from Google OAuth redirect)
        if (session && !session.user?.is_anonymous) {
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

      // Restore profile from Supabase when a non-anonymous user signs in
      if (event === 'SIGNED_IN' && session?.access_token && !session.user?.is_anonymous) {
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

  const isAnonymous = session?.user?.is_anonymous ?? true

  const value: AuthContextValue = {
    session,
    token: session?.access_token ?? null,
    isLoading,
    isAuthenticated: !!session,
    isAnonymous,
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
