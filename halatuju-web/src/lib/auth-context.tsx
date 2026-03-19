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
import type { StudentProfile } from '@/lib/api'
import type { Session } from '@supabase/supabase-js'
import { KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS, KEY_STPM_GRADES, KEY_STPM_CGPA, KEY_MUET_BAND, KEY_EXAM_TYPE } from '@/lib/storage'

export type AuthGateReason = 'quiz' | 'save' | 'report' | 'eligible' | 'profile' | 'loadmore' | null
export type AuthStatus = 'loading' | 'anonymous' | 'needs-nric' | 'ready'

interface AuthGateOptions {
  courseId?: string
}

interface AuthContextValue {
  session: Session | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean  // true = has NRIC, full access
  isAnonymous: boolean      // true = anonymous session
  hasSession: boolean       // true = has any session (including anonymous)
  status: AuthStatus
  profile: StudentProfile | null
  authGateReason: AuthGateReason
  authGateCourseId: string | null
  showAuthGate: (reason: NonNullable<AuthGateReason>, options?: AuthGateOptions) => void
  hideAuthGate: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasIdentity, setHasIdentity] = useState(false)
  const [profile, setProfile] = useState<StudentProfile | null>(null)
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

        // Check identity (NRIC) for non-anonymous users
        if (session?.access_token && !session.user?.is_anonymous) {
          getProfile({ token: session.access_token }).then(p => {
            setProfile(p)
            setHasIdentity(!!p.nric)
          }).catch(() => {
            setProfile(null)
            setHasIdentity(false)
          })
        } else {
          setHasIdentity(false)
        }
      })
      .catch(() => setIsLoading(false))

    const {
      data: { subscription },
    } = getSupabase().auth.onAuthStateChange((event, session) => {
      setSession(session)

      // Check identity and restore profile when a non-anonymous user signs in
      if (event === 'SIGNED_IN' && session?.access_token && !session.user?.is_anonymous) {
        getProfile({ token: session.access_token }).then(p => {
          setProfile(p)
          setHasIdentity(!!p.nric)
        }).catch(() => {
          setProfile(null)
          setHasIdentity(false)
        })
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

  // Listen for NRIC-required events from API layer
  useEffect(() => {
    const handler = () => showAuthGate('profile')
    window.addEventListener('nric-required', handler)
    return () => window.removeEventListener('nric-required', handler)
  }, [showAuthGate])

  // Cache profile data to localStorage
  useEffect(() => {
    if (!profile) return
    if (profile.grades && Object.keys(profile.grades).length > 0) {
      localStorage.setItem(KEY_GRADES, JSON.stringify(profile.grades))
    }
    const demo: Record<string, unknown> = {}
    if (profile.gender) demo.gender = profile.gender
    if (profile.nationality) demo.nationality = profile.nationality
    if (profile.colorblind != null) demo.colorblind = profile.colorblind
    if (profile.disability != null) demo.disability = profile.disability
    if (Object.keys(demo).length > 0) {
      localStorage.setItem(KEY_PROFILE, JSON.stringify(demo))
    }
    if (profile.student_signals) {
      localStorage.setItem(KEY_QUIZ_SIGNALS, JSON.stringify(profile.student_signals))
    }
    // STPM data
    if (profile.stpm_grades && Object.keys(profile.stpm_grades).length > 0) {
      localStorage.setItem(KEY_STPM_GRADES, JSON.stringify(profile.stpm_grades))
    }
    if (profile.stpm_cgpa != null) {
      localStorage.setItem(KEY_STPM_CGPA, String(profile.stpm_cgpa))
    }
    if (profile.muet_band != null) {
      localStorage.setItem(KEY_MUET_BAND, String(profile.muet_band))
    }
    if (profile.exam_type) {
      localStorage.setItem(KEY_EXAM_TYPE, profile.exam_type)
    }
  }, [profile])

  const isAnonymous = session?.user?.is_anonymous ?? true

  const status: AuthStatus = isLoading
    ? 'loading'
    : isAnonymous
      ? 'anonymous'
      : hasIdentity
        ? 'ready'
        : 'needs-nric'

  const value: AuthContextValue = {
    session,
    token: session?.access_token ?? null,
    isLoading,
    isAuthenticated: hasIdentity,
    isAnonymous,
    hasSession: !!session,
    status,
    profile,
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
