'use client'

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import {
  getSponsorPool,
  getSponsorWallet,
  getSponsorImpact,
  getSponsorActivity,
  getSponsorCommunity,
  getSponsorStatement,
  getSponsorGraduationMessages,
  getSponsorReferrals,
  type SponsorPoolCard,
  type SponsorWallet,
  type SponsorImpact,
  type SponsorActivityEvent,
  type SponsorCommunity,
  type SponsorStatement,
  type GraduationRelayMessage,
  type SponsorReferral,
} from '@/lib/api'

interface SponsorPortalValue {
  ready: boolean                       // the availability probe (pool fetch) has settled
  poolUnavailable: boolean             // SPONSOR_POOL_ENABLED off → the dark "coming soon" state
  pool: SponsorPoolCard[] | null
  wallet: SponsorWallet | null
  impact: SponsorImpact | null         // R2: My Giving dashboard aggregate
  activity: SponsorActivityEvent[]     // R3: recent activity feed
  community: SponsorCommunity | null   // R3: community strip counts
  statement: SponsorStatement | null   // R4: giving statement (two ledgers)
  gradMessages: GraduationRelayMessage[]
  referrals: SponsorReferral[]
  refreshReferrals: () => Promise<void>
}

const SponsorPortalContext = createContext<SponsorPortalValue | null>(null)

/**
 * Fetches the approved sponsor's portal data ONCE (pool, wallet, grad messages, referrals)
 * and shares it across the My Giving / Students / Account tabs, so switching tabs doesn't refetch.
 * The pool fetch doubles as the availability probe: a 404 (flag off) → `poolUnavailable`.
 */
export function SponsorPortalProvider({ children }: { children: ReactNode }) {
  const { token } = useSponsorAuth()
  const [ready, setReady] = useState(false)
  const [poolUnavailable, setPoolUnavailable] = useState(false)
  const [pool, setPool] = useState<SponsorPoolCard[] | null>(null)
  const [wallet, setWallet] = useState<SponsorWallet | null>(null)
  const [impact, setImpact] = useState<SponsorImpact | null>(null)
  const [activity, setActivity] = useState<SponsorActivityEvent[]>([])
  const [community, setCommunity] = useState<SponsorCommunity | null>(null)
  const [statement, setStatement] = useState<SponsorStatement | null>(null)
  const [gradMessages, setGradMessages] = useState<GraduationRelayMessage[]>([])
  const [referrals, setReferrals] = useState<SponsorReferral[]>([])

  const refreshReferrals = useCallback(async () => {
    if (!token) return
    try {
      const r = await getSponsorReferrals({ token })
      setReferrals(r.referrals)
    } catch {
      /* leave the current list on failure */
    }
  }, [token])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    getSponsorPool({ token })
      .then((d) => { if (!cancelled) setPool(d.students) })
      .catch(() => { if (!cancelled) setPoolUnavailable(true) })
      .finally(() => { if (!cancelled) setReady(true) })
    getSponsorWallet({ token })
      .then((w) => { if (!cancelled) setWallet(w) })
      .catch(() => { /* 404s while the flag is off — leave null */ })
    getSponsorImpact({ token })
      .then((i) => { if (!cancelled) setImpact(i) })
      .catch(() => { /* leave null */ })
    getSponsorActivity({ token })
      .then((r) => { if (!cancelled) setActivity(r.events) })
      .catch(() => { /* leave empty */ })
    getSponsorCommunity({ token })
      .then((c) => { if (!cancelled) setCommunity(c) })
      .catch(() => { /* leave null */ })
    getSponsorStatement({ token })
      .then((s) => { if (!cancelled) setStatement(s) })
      .catch(() => { /* leave null */ })
    getSponsorGraduationMessages({ token })
      .then((r) => { if (!cancelled) setGradMessages(r.messages) })
      .catch(() => { /* leave empty */ })
    getSponsorReferrals({ token })
      .then((r) => { if (!cancelled) setReferrals(r.referrals) })
      .catch(() => { /* leave empty */ })
    return () => { cancelled = true }
  }, [token])

  return (
    <SponsorPortalContext.Provider
      value={{ ready, poolUnavailable, pool, wallet, impact, activity, community, statement, gradMessages, referrals, refreshReferrals }}
    >
      {children}
    </SponsorPortalContext.Provider>
  )
}

export function useSponsorPortal() {
  const ctx = useContext(SponsorPortalContext)
  if (!ctx) throw new Error('useSponsorPortal must be used within SponsorPortalProvider')
  return ctx
}
