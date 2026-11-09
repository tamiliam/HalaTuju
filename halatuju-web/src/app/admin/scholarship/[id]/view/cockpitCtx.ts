/**
 * What every cockpit hook is handed (audit A3.3): the case, its id and token, the translator, and
 * the few setters they all write through. One object, so a hook's signature says "the cockpit's
 * common ground" rather than listing eight names.
 */
import type { Dispatch, SetStateAction } from 'react'
import type { AdminScholarshipDetail, AdminSponsorProfile } from '@/lib/admin-api'

export type TFn = (key: string, params?: Record<string, string>) => string

export interface CockpitCtx {
  id: number
  token: string | null | undefined
  t: TFn
  app: AdminScholarshipDetail | null
  setApp: Dispatch<SetStateAction<AdminScholarshipDetail | null>>
  setProfile: (p: AdminSponsorProfile | null) => void
  setBusy: (s: string) => void
  setError: (s: string) => void
  /** Re-read the case from the api (after a write that returns something slimmer). */
  refreshApp: () => Promise<void>
}
