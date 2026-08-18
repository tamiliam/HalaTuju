'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import { usePathname } from 'next/navigation'
import { isAnonymousAuthSuppressed } from '@/lib/sessionPolicy'
import { getSession, getSupabase, signInAnonymously } from '@/lib/supabase'
import { getProfile } from '@/lib/api'
import type { StudentProfile } from '@/lib/api'
import type { Session } from '@supabase/supabase-js'
import { KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS, KEY_STPM_GRADES, KEY_STPM_CGPA, KEY_MUET_BAND, KEY_EXAM_TYPE, KEY_RESULTS_EXAM_TYPE, KEY_PENDING_AUTH_ACTION, KEY_ALIRAN, KEY_ELEKTIF } from '@/lib/storage'

export type AuthGateReason = 'quiz' | 'save' | 'report' | 'eligible' | 'profile' | 'loadmore' | 'apply' | null
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
  refreshProfile: () => Promise<void>
  authGateReason: AuthGateReason
  authGateCourseId: string | null
  showAuthGate: (reason: NonNullable<AuthGateReason>, options?: AuthGateOptions) => void
  hideAuthGate: () => void
}

/**
 * Exported for ONE reason: the design sandbox mounts real signed-in screens without an identity.
 *
 * `AuthProvider` mints an anonymous Supabase user on mount, which a sandbox must never do — it
 * would create real auth rows for a design review — so the sandbox supplies this context directly
 * with a synthetic value instead. That is the sandbox's own rule applied rather than dodged: *if a
 * surface cannot be mounted without re-implementing part of it, make it mountable*. The same
 * accommodation `sponsor-portal-context` already makes.
 *
 * ⚠ NOT a second way to be logged in. Nothing in the app may provide this context — `AuthProvider`
 * is the only writer, and `useAuth` is the only reader. Use `useAuth()`.
 */
export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasIdentity, setHasIdentity] = useState(false)
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [authGateReason, setAuthGateReason] = useState<AuthGateReason>(null)
  const [authGateCourseId, setAuthGateCourseId] = useState<string | null>(null)

  const pathname = usePathname()
  // The STUDENT auth stack must not run on the privileged consoles. They have their own
  // isolated clients, and the student client here would otherwise do two harmful things on
  // /admin/auth/callback: its `detectSessionInUrl` (on by default) claims the `?code=` meant
  // for the admin client and fails to exchange it — it holds no matching PKCE verifier, since
  // the verifier is stored per storageKey — which BURNS the single-use code and leaves the
  // admin callback with no session; and it then signs the visitor in ANONYMOUSLY on an admin
  // page. Whichever client initialises first wins, which is why this reproduced on a local
  // origin and not in production: a race, never a guarantee. (TD-182.)
  //
  // Same guard, same reason, as AuthGateModal's (TD-073), and now the same helper — a bare
  // startsWith('/admin') also swallows '/administrivia'. No admin or sponsor surface consumes
  // this context, so the provider simply stays inert there.
  // Also inert on the design sandbox, for a DIFFERENT reason — it is handed to people outside the
  // organisation and must not create real auth rows. See `isAnonymousAuthSuppressed`.
  const isPrivilegedConsole = isAnonymousAuthSuppressed(pathname)

  useEffect(() => {
    if (isPrivilegedConsole) { setIsLoading(false); return }
    getSession()
      .then(async ({ session: existingSession }) => {
        let session = existingSession
        if (!session) {
          // No session — sign in anonymously
          const { data } = await signInAnonymously()
          session = data?.session ?? null
        }
        setSession(session ?? null)

        // Check identity (NRIC) for non-anonymous users
        if (session?.access_token && !session.user?.is_anonymous) {
          try {
            const p = await getProfile({ token: session.access_token })
            setProfile(p)
            setHasIdentity(!!p.nric)
          } catch {
            setProfile(null)
            setHasIdentity(false)
          }
        } else {
          setHasIdentity(false)
        }
        setIsLoading(false)
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
  }, [isPrivilegedConsole])

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

  const refreshProfile = useCallback(async () => {
    const tkn = session?.access_token
    if (!tkn || session?.user?.is_anonymous) return
    try {
      const p = await getProfile({ token: tkn })
      setProfile(p)
      setHasIdentity(!!p.nric)
    } catch {
      // Ignore — profile may not exist yet
    }
  }, [session])

  // Listen for NRIC-required events from API layer
  useEffect(() => {
    const handler = () => showAuthGate('profile')
    window.addEventListener('nric-required', handler)
    return () => window.removeEventListener('nric-required', handler)
  }, [showAuthGate])

  // Resume pending auth action after OAuth redirect (e.g. Google login → callback → dashboard)
  // When status transitions to 'needs-nric' or 'ready', check if an action was pending.
  useEffect(() => {
    if (isLoading) return
    const isAnon = session?.user?.is_anonymous ?? true
    if (isAnon) return // Not yet signed in with a real account

    const pendingStr = localStorage.getItem(KEY_PENDING_AUTH_ACTION)
    if (!pendingStr) return

    try {
      const { reason, courseId } = JSON.parse(pendingStr)
      if (reason) {
        // Restore the auth gate — modal will auto-advance based on status
        showAuthGate(reason, courseId ? { courseId } : undefined)
      }
    } catch { /* malformed — ignore */ }
    // Remove regardless — consumed once
    localStorage.removeItem(KEY_PENDING_AUTH_ACTION)
  }, [isLoading, session, showAuthGate])

  // Cache profile data to localStorage
  useEffect(() => {
    if (!profile) return
    if (profile.grades && Object.keys(profile.grades).length > 0) {
      localStorage.setItem(KEY_GRADES, JSON.stringify(profile.grades))
    }
    // Re-hydrate the stream/aliran + elective selections from the profile so the
    // onboarding grades form can reconstruct which grade keys are stream vs elective
    // after a logout/login. Without this, the form (which keys off these localStorage
    // selections) drops the electives entirely — electives have no default fallback,
    // unlike aliran which falls back to the stream pool.
    if (Array.isArray(profile.stream_subjects) && profile.stream_subjects.length > 0) {
      localStorage.setItem(KEY_ALIRAN, JSON.stringify(profile.stream_subjects))
    }
    if (Array.isArray(profile.elective_subjects) && profile.elective_subjects.length > 0) {
      localStorage.setItem(KEY_ELEKTIF, JSON.stringify(profile.elective_subjects))
    }
    // Merge into the existing cached profile rather than overwriting it, so values
    // set elsewhere (notably the grades step's coqScore) survive a profile refresh.
    let demo: Record<string, unknown> = {}
    try {
      const existing = localStorage.getItem(KEY_PROFILE)
      if (existing) demo = JSON.parse(existing)
    } catch { /* malformed — start fresh */ }
    if (profile.gender) demo.gender = profile.gender
    if (profile.nationality) demo.nationality = profile.nationality
    if (profile.colorblind != null) demo.colorblind = profile.colorblind
    if (profile.disability != null) demo.disability = profile.disability
    // CoQ is persisted on the profile as snake_case `coq_score`, but the app reads
    // camelCase `coqScore` from this cache — map it so the stored co-curricular
    // score round-trips back into the grades/edit form instead of resetting to 0.
    if (profile.coq_score != null) demo.coqScore = profile.coq_score
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
    if (profile.results_exam_type) {
      // Restored for the same reason as its siblings: without it, a browser that has never
      // completed a results form would sync a BLANK over a recorded completion.
      localStorage.setItem(KEY_RESULTS_EXAM_TYPE, profile.results_exam_type)
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
    refreshProfile,
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
