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
import { restoreProfileToLocalStorage } from '@/lib/profile-restore'
import type { Session } from '@supabase/supabase-js'
import { KEY_PENDING_AUTH_ACTION } from '@/lib/storage'

export type AuthGateReason = 'quiz' | 'save' | 'report' | 'eligible' | 'profile' | 'loadmore' | null

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
          getProfile({ token: session.access_token }).then(profile => {
            setHasIdentity(!!profile.nric)
            if (profile.nric) restoreProfileToLocalStorage(session.access_token!)
          }).catch(() => setHasIdentity(false))
        } else {
          setHasIdentity(false)
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

      // Check identity and restore profile when a non-anonymous user signs in
      if (event === 'SIGNED_IN' && session?.access_token && !session.user?.is_anonymous) {
        getProfile({ token: session.access_token }).then(profile => {
          setHasIdentity(!!profile.nric)
          if (profile.nric) restoreProfileToLocalStorage(session.access_token!)
        }).catch(() => setHasIdentity(false))
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

  const isAnonymous = session?.user?.is_anonymous ?? true

  const value: AuthContextValue = {
    session,
    token: session?.access_token ?? null,
    isLoading,
    isAuthenticated: hasIdentity,
    isAnonymous,
    hasSession: !!session,
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
