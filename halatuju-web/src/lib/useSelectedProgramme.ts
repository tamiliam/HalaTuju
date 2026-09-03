'use client'

/**
 * The gift the Programme screen is currently about, as a full record rather than a code.
 *
 * The breadcrumb switcher deals in CODES (that is what `GET admin/scholarship/scopes/` returns and
 * what an endpoint is given), while the intake-year endpoints are addressed by the programme's id.
 * This is the one place that join happens, so the Rules tab and the Intake-year tab cannot end up
 * looking at two different gifts.
 *
 * ⚠ IT NEVER PICKS FOR YOU. With one gift the scope context already resolves to it; with several
 * and no choice made, `programme` is null and `ambiguous` is true, and the caller must ASK rather
 * than default. That is PF-1's rule on a screen: `resolve_open_cohort` raises instead of choosing,
 * because a silent wrong answer about which gift you are editing is worse than a question.
 *
 * ⚠ THE LIST IS THE FENCE'S OWN. `getAdminProgrammes` returns only the caller's organisation's
 * gifts (`_ProgrammeScopedBase`), so a code that resolves to nothing here is a code the caller may
 * not open — and the result is simply "not found", never a widened view.
 */

import { useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useProgrammeScope } from '@/lib/programmeScope'
import { getAdminProgrammes, type AdminProgramme } from '@/lib/admin-api'

export interface SelectedProgramme {
  /** Every gift the caller may open. Empty until loaded, or on a failed fetch. */
  programmes: AdminProgramme[]
  /** The one being looked at, or null when it is not yet known. */
  programme: AdminProgramme | null
  /** True while the list is still being fetched — distinct from "there are none". */
  loading: boolean
  /** True when the caller must choose before anything can be shown. */
  mustChoose: boolean
  /** Choose one; the breadcrumb follows, because both read the same context. */
  select: (code: string) => void
}

export function useSelectedProgramme(): SelectedProgramme {
  const { token } = useAdminAuth()
  const { chosen, select } = useProgrammeScope()
  const [programmes, setProgrammes] = useState<AdminProgramme[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    let live = true
    // ⚠ `try/catch` AROUND THE AWAIT, not `.catch()` on the chain. A `.catch()` only sees a
    // REJECTED promise; it cannot see the call itself throwing, and `await undefined.then` is
    // exactly what a mocked module hands back. A failed list must leave `programmes` empty so the
    // caller shows its own empty state — it must never throw into a tab, from either direction.
    void (async () => {
      try {
        const d = await getAdminProgrammes({ token })
        if (live) setProgrammes(d.programmes)
      } catch {
        /* the caller renders the empty case */
      } finally {
        if (live) setLoading(false)
      }
    })()
    return () => { live = false }
  }, [token])

  // The scope context knows the caller's whole list from the scopes endpoint; this one knows the
  // richer records. When exactly one gift exists, either source resolves it — so fall back to the
  // single record rather than requiring both calls to have landed.
  //
  // ⚠ THE FALLBACK ONLY APPLIES WHEN NOTHING WAS CHOSEN. Same rule, same reason as
  // `programmeScope`: a chosen code we cannot find must resolve to NOTHING, never to whichever
  // gift happens to be the only one — that substitution is what showed the owner a different
  // programme's settings than the one they pressed into (2026-09-03).
  const byCode = programmes.find((p) => p.code === chosen) ?? null
  const programme = chosen
    ? byCode
    : (programmes.length === 1 ? programmes[0] : null)

  return {
    programmes,
    programme,
    loading,
    // `> 0`, not `> 1`: a chosen code we could not find leaves ONE gift unresolved too, and the
    // honest screen there is the same question rather than a blank tab.
    mustChoose: !loading && programme === null && programmes.length > 0,
    select,
  }
}
