'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import { getSponsorSession, getSponsorSupabase } from '@/lib/sponsor-supabase'
import { getSponsorMe, type SponsorAccount } from '@/lib/api'
import type { Session } from '@supabase/supabase-js'

interface SponsorAuthContextValue {
  session: Session | null
  token: string | null
  isLoading: boolean
  isSignedIn: boolean              // has a real (non-anonymous) sponsor session
  account: SponsorAccount | null   // /sponsor/me result ({registered:false} or the account)
  refreshAccount: () => Promise<void>
}

/**
 * Exported so a HARNESS can supply the value (Mobile M5) — the design sandbox mounts real portal pages
 * against a synthetic sponsor this way, never a real sign-in (the same rule as `SponsorPortalContext`).
 * Product code must keep using `SponsorAuthProvider` + `useSponsorAuth()`; providing this context
 * anywhere outside a harness would be a second, unauthenticated source of the sponsor's identity.
 */
export const SponsorAuthContext = createContext<SponsorAuthContextValue | null>(null)

export function SponsorAuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [account, setAccount] = useState<SponsorAccount | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadAccount = useCallback(async (token: string) => {
    try {
      setAccount(await getSponsorMe({ token }))
    } catch {
      setAccount(null)
    }
  }, [])

  const refreshAccount = useCallback(async () => {
    if (session?.access_token) await loadAccount(session.access_token)
  }, [session, loadAccount])

  useEffect(() => {
    getSponsorSession()
      .then(async ({ session }) => {
        setSession(session ?? null)
        if (session?.access_token && !session.user?.is_anonymous) {
          await loadAccount(session.access_token)
        }
        setIsLoading(false)
      })
      .catch(() => setIsLoading(false))

    const {
      data: { subscription },
    } = getSponsorSupabase().auth.onAuthStateChange(async (_event, session) => {
      setSession(session)
      if (session?.access_token && !session.user?.is_anonymous) {
        await loadAccount(session.access_token)
      } else {
        setAccount(null)
      }
    })
    return () => subscription.unsubscribe()
  }, [loadAccount])

  const value: SponsorAuthContextValue = {
    session,
    token: session?.access_token ?? null,
    isLoading,
    isSignedIn: !!session && !session.user?.is_anonymous,
    account,
    refreshAccount,
  }

  return (
    <SponsorAuthContext.Provider value={value}>{children}</SponsorAuthContext.Provider>
  )
}

export function useSponsorAuth() {
  const ctx = useContext(SponsorAuthContext)
  if (!ctx) throw new Error('useSponsorAuth must be used within SponsorAuthProvider')
  return ctx
}
