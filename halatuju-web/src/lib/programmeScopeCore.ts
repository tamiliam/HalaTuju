'use client'

/**
 * The CONTEXT half of `programmeScope` — the types, the context object and the two hooks a page
 * reads — without the provider (2026-09-28).
 *
 * ⚠ WHY IT IS A SEPARATE MODULE, AND IT IS A MEASUREMENT, NOT TIDINESS. The payment-run page began
 * pinning its gift this sprint, and importing the whole `programmeScope` module pulled the
 * PROVIDER into that route's first-load JS: 256.6 kB, printed as 257, took the median route over
 * its 256 kB budget (`scripts/bundle-budget.js`). A detail page needs only the context and the
 * pin hook. Everything here is RE-EXPORTED from `programmeScope`, so every other importer — and
 * every `jest.mock('@/lib/programmeScope')` — is unchanged; the provider imports `Ctx` from here,
 * so there is still exactly ONE context and one holder of the answer. Read `programmeScope.tsx`
 * for what the scope means; this file only holds its shape.
 */
import { createContext, useContext, useEffect } from 'react'

export interface ProgrammeChoice {
  code: string
  name: string
  /** False for a gift that is not switched on yet — a normal, and common, state. */
  isActive?: boolean
}

export interface PinnedGift { code: string; name: string }

export interface ProgrammeScope {
  /** Every gift this caller may look at, from the scopes endpoint. Server-ordered. */
  choices: readonly ProgrammeChoice[]
  /** The selected gift's code, or `''` when it is not yet known. NEVER guessed. */
  chosen: string
  /** The selected gift, or null. */
  programme: ProgrammeChoice | null
  /** True when there is more than one LIVE gift to choose between — the page should say so. */
  ambiguous: boolean
  /** The live gifts only — what a money page may offer (a draft cannot be paid from). */
  live: readonly ProgrammeChoice[]
  select: (code: string) => void
  /**
   * Re-fetch the list of gifts this caller may open.
   *
   * ⚠ WHY THIS HAD TO EXIST (owner, live use, 2026-09-07). The shell fetches the scopes ONCE per
   * console session, so a gift CREATED during that session was unknown to this list — and the
   * guard in the provider then did exactly its job: refused to resolve a code it did not
   * recognise. The result was a screen that asked which gift, forever, with every click a no-op.
   *
   * ⚠ THE FIX IS TO REFRESH THE LIST, NEVER TO LOOSEN THE GUARD. Accepting an unknown code is the
   * 2026-09-03 defect (it showed the owner a different programme's settings); falling back to the
   * only gift is the same defect wearing a hat. Stale data is the bug — the refusal is correct.
   */
  reload: () => Promise<void>
  /**
   * True while a DETAIL page has pinned the gift it is showing (`usePinProgramme`). The crumb
   * reads it to drop its switch: on a run or an application the gift is a fact about the record,
   * so a control offering another one could only change the crumb and never the page.
   */
  pinned: boolean
  /** The pinned record's gift NAME from its payload — the crumb's label when the code is not in
   *  `choices` (list failed, or a gift created or renamed this session). `''` when not pinned. */
  pinnedName: string
  /** Pin (`on`) or release a gift. Use `usePinProgramme`; this is its plumbing. */
  setPin: (gift: PinnedGift, on: boolean) => void
  /**
   * Has the shell's scopes fetch come back — answered OR failed? Until it has, `ambiguous` is
   * `false` because `choices` is empty, which is "we have not asked", not "one gift". A page
   * that ACTS on "several and none chosen" (the money pages redirect on it, 2026-09-28) must
   * wait for this, or it would act on every page load before the list arrived. A FAILED fetch
   * settles too: the list is furniture, and a page must never wait on it for ever.
   */
  settled: boolean
}

const EMPTY: ProgrammeScope = {
  choices: [], chosen: '', programme: null, ambiguous: false, live: [], select: () => {},
  reload: async () => {}, pinned: false, pinnedName: '', setPin: () => {},
  // Outside the shell there is no list to wait for, so a harness mount behaves as it always has.
  settled: true,
}

/** THE one context. The provider in `programmeScope.tsx` supplies it; nothing else creates one. */
export const ProgrammeScopeCtx = createContext<ProgrammeScope>(EMPTY)

export function useProgrammeScope(): ProgrammeScope {
  return useContext(ProgrammeScopeCtx)
}

/**
 * Tell the breadcrumb which gift this DETAIL page is showing. Pass the record's own gift from the
 * server payload — the run's or the application's `programme` (`{code, name}`) — and `undefined`
 * until it has loaded (or `null` when the record has none), which pins nothing and leaves the
 * crumb as it was. Released on unmount and whenever the gift changes; never selects.
 */
export function usePinProgramme(gift: PinnedGift | null | undefined): void {
  const { setPin } = useProgrammeScope()
  const code = gift?.code ?? ''
  const name = gift?.name ?? ''
  useEffect(() => {
    if (!code) return undefined
    const g = { code, name }
    setPin(g, true)
    return () => setPin(g, false)
  }, [code, name, setPin])
}
