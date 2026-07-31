'use client'

import { useEffect, useState } from 'react'

import { getOrgRequestCount, getBillingUsage } from '@/lib/admin-api'
import { NO_PROBES, type ProbeKey, type ProbeState } from '@/lib/navigation'

/**
 * Whether each dark-shipped feature is live, inferred from whether its endpoint answers.
 *
 * There is deliberately NO client-side flag. `REQUESTS_ENABLED` and `BILLING_USAGE_ENABLED`
 * are server-side env vars; the API's 404 IS the answer, so nothing has to be kept in step.
 * This reproduces exactly what the Administration hub has done since those features were dark
 * shipped (see the probe comments in admin/administration/page.tsx) — the hook just gives the
 * whole shell one copy of it instead of each surface probing for itself.
 *
 * Any failure, not only a 404, resolves to 'dark'. A probe is a hint about what to show; it
 * must never reveal a feature on a network blip, and it must never block the shell.
 */
export function useNavProbes(token: string | null | undefined): {
  probes: Record<ProbeKey, ProbeState>
  requestsWaiting: number
} {
  const [probes, setProbes] = useState<Record<ProbeKey, ProbeState>>(NO_PROBES)
  const [requestsWaiting, setRequestsWaiting] = useState(0)

  useEffect(() => {
    if (!token) { setProbes(NO_PROBES); setRequestsWaiting(0); return }
    let live = true
    const set = (key: ProbeKey, state: ProbeState) =>
      setProbes((p) => (live && p[key] !== state ? { ...p, [key]: state } : p))

    // TD-205: this call already asked "how many requests are waiting on us?" and threw the
    // NUMBER away, keeping only "did it answer?". So four bug reports (#5–#8) sat on production
    // for two days with the count sitting unread in this promise. The probe still works exactly
    // as before — the count is simply no longer discarded.
    getOrgRequestCount({ token })
      .then((d) => {
        set('requests', 'live')
        if (live) setRequestsWaiting(d.count)
      })
      .catch(() => { set('requests', 'dark'); if (live) setRequestsWaiting(0) })
    getBillingUsage({ token })
      .then(() => set('billing', 'live'))
      .catch(() => set('billing', 'dark'))

    return () => { live = false }
  }, [token])

  return { probes, requestsWaiting }
}
