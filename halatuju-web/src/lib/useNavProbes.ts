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
export function useNavProbes(token: string | null | undefined): Record<ProbeKey, ProbeState> {
  const [probes, setProbes] = useState<Record<ProbeKey, ProbeState>>(NO_PROBES)

  useEffect(() => {
    if (!token) { setProbes(NO_PROBES); return }
    let live = true
    const set = (key: ProbeKey, state: ProbeState) =>
      setProbes((p) => (live && p[key] !== state ? { ...p, [key]: state } : p))

    getOrgRequestCount({ token })
      .then(() => set('requests', 'live'))
      .catch(() => set('requests', 'dark'))
    getBillingUsage({ token })
      .then(() => set('billing', 'live'))
      .catch(() => set('billing', 'dark'))

    return () => { live = false }
  }, [token])

  return probes
}
