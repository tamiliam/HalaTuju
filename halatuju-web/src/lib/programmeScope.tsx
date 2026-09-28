'use client'

/**
 * WHICH GIFT AM I LOOKING AT — the breadcrumb switcher, made to mean something (TD-193).
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * ⚠ THIS IS STILL A DISPLAY PREFERENCE. IT IS NOT AN AUTH CONTEXT.
 * ─────────────────────────────────────────────────────────────────────────────
 * `ScopeSwitcher`'s docstring has said since N3a (2026-07-28) that the selection must never
 * travel as a header, a cookie or anything ambient, because that would relocate the organisation
 * fence into the client — the 2026-07-15 surface-partition incident in a new costume. Nothing
 * here changes that rule; it only stops the control being decorative.
 *
 * What changed is narrower than it looks. The selection is held in React state, read by the
 * Programme-scope pages, and passed to each endpoint as an EXPLICIT request value the server
 * re-fences on the caller's own `owning_organisation` — exactly the `?programme=<code>` contract
 * `AdminProgrammeConfigurationView` has always had. A client that ignores this reaches identical
 * data. The list itself comes from `GET admin/scholarship/scopes/`, derived server-side from the
 * same field the fence uses, so it can never offer a gift the caller may not open.
 *
 * ⚠ IT NEVER PICKS SILENTLY. One gift resolves to that gift; several and no choice resolves to
 * NOTHING, and the page asks. That is PF-1's rule (`resolve_open_cohort` RAISES rather than
 * choosing) applied to a screen: a wrong silent answer about which gift you are configuring is
 * worse than a question. `chosen` is therefore `''` until it is genuinely known.
 *
 * ⚠ NOT PERSISTED, deliberately. `uiPrefs` carries the rail's width and says in as many words not
 * to reach for it by default — and a stored gift code would outlive the tab, the tenant and the
 * person's memory of setting it, so a reload would silently reopen someone else's gift. A hard
 * reload resets to the same honest place a first visit does: the only gift, or a question.
 *
 * ⚠ A DETAIL PAGE PINS THE GIFT IT IS SHOWING (2026-09-28). A payment run belongs to exactly one
 * gift, and so does an application; before this, switching the crumb on a run page changed the
 * crumb and not the page — the crumb lied. `usePinProgramme(code)` is how such a page tells the
 * scope which gift it shows. The code comes from the SERVER payload (the run's or the
 * application's `programme.code` — the GIFT, never `chosen_programme`, which is the student's
 * course), so it survives a bookmark, a refresh and a new tab with nothing stored anywhere.
 * While pinned: the pinned code outranks the person's pick and the crumb names it WITH NO SWITCH.
 * A code not in `choices` resolves `chosen` to nothing — never to a wrong gift — and the crumb
 * shows the RECORD's own name from the payload (a server fact, not a guess).
 * ⚠ THE PIN NEVER SELECTS (adversarial review, 2026-09-28). The first cut did, and it narrowed the
 * all-gifts Applications list — a reviewer's only door — to one gift with no way back but a
 * reload. On unmount the person's previous choice returns exactly as it was, "none" included.
 *
 * ⚠ ONLY LIVE GIFTS MAKE A QUESTION. A draft cannot be paid from and the server auto-picks the one
 * LIVE gift, so `ambiguous` and the single-gift auto-resolve count active gifts (Sabah S2: a draft
 * changes nothing). The crumb's switcher still lists drafts, labelled, for Configuration.
 */

import { useCallback, useMemo, useState, type ReactNode } from 'react'

import {
  ProgrammeScopeCtx, useProgrammeScope, type PinnedGift, type ProgrammeChoice,
  type ProgrammeScope,
} from './programmeScopeCore'

// The context half lives in `programmeScopeCore` (so a detail page can pin without loading this
// provider — a first-load-JS measurement, see that file); re-exported so importers are unchanged.
export {
  ProgrammeScopeCtx, useProgrammeScope, usePinProgramme,
  type PinnedGift, type ProgrammeChoice, type ProgrammeScope,
} from './programmeScopeCore'

/**
 * Provided by the shell, so the choice survives moving between Configuration and Applications.
 * A page outside the shell (a test harness, the sandbox) gets `EMPTY` and simply behaves as it
 * did before this existed.
 */
export function ProgrammeScopeProvider(
  { choices, children, onReload, settled = true }: {
    choices: readonly ProgrammeChoice[]
    children: ReactNode
    /** Ask the shell to re-fetch the scopes. Optional so a harness can mount without one. */
    onReload?: () => Promise<void>
    /** The shell's fetch has answered or failed. Defaults to true for a harness with a list. */
    settled?: boolean
  },
) {
  const [picked, setPicked] = useState('')
  const [pinGift, setPinState] = useState<PinnedGift | null>(null)
  const pin = pinGift?.code ?? ''
  const reload = useCallback(async () => { await onReload?.() }, [onReload])
  // Release only the code we were asked to release, so a page mounting as another unmounts can
  // never have its fresh pin wiped by the old page's cleanup. `picked` is never touched.
  const setPin = useCallback((gift: PinnedGift, on: boolean) => {
    setPinState((was) => (on ? gift : (was?.code === gift.code ? null : was)))
  }, [])

  const value = useMemo<ProgrammeScope>(() => {
    /*
     * ⚠ A DISCARDED PICK RESOLVES TO NOTHING — IT MUST NEVER FALL THROUGH TO "THE ONLY ONE".
     *
     * The first cut wrote `valid || (choices.length === 1 ? choices[0].code : '')`, which reads as
     * one expression and is two rules welded together: "drop a code we do not recognise" and
     * "resolve a single gift when nobody has chosen". Fine while they cannot both fire — and they
     * both fired on the owner's first real use. They created a second gift, pressed into it, and
     * the code was not in the list (the scopes endpoint was returning ACTIVE programmes only), so
     * it was dropped and the fallback then handed them the one active gift instead. **The console
     * silently showed them a different programme's settings than the one they had opened.**
     *
     * The endpoint is fixed too, but this is the half that turns "we do not know that gift" into
     * "here is a different gift", and that substitution must be impossible however the list is
     * populated. Not recognised now means ASK — the same refusal `resolve_open_cohort` makes.
     */
    // A pin outranks the pick, and goes through the SAME guard: a pinned code we do not
    // recognise resolves to nothing — the question — and never to the pick or the only gift.
    const want = pin || picked
    const known = choices.some((c) => c.code === want)
    // The single-gift resolve counts LIVE gifts (a draft beside one live gift changes nothing);
    // a tenant whose only gift is a draft still resolves to it, as it always has.
    const live = choices.filter((c) => c.isActive !== false)
    const only = live.length === 1 ? live[0] : (choices.length === 1 ? choices[0] : null)
    const chosen = want ? (known ? want : '') : (only?.code ?? '')
    return {
      choices,
      chosen,
      programme: choices.find((c) => c.code === chosen) ?? null,
      ambiguous: live.length > 1,
      live,
      select: setPicked,
      reload,
      pinned: pin !== '',
      pinnedName: pinGift?.name ?? '',
      setPin,
      settled,
    }
  }, [choices, picked, pin, pinGift, reload, setPin, settled])

  return <ProgrammeScopeCtx.Provider value={value}>{children}</ProgrammeScopeCtx.Provider>
}

/**
 * The value to send with a request, or `undefined` to send nothing.
 *
 * `undefined` is not a failure: with one gift the server resolves it, and with several it answers
 * `programme_required` carrying the list — which is the behaviour that existed before this module
 * and the reason a missing value can only ever produce a question, never a wrong answer.
 */
export function useProgrammeParam(): string | undefined {
  const { chosen } = useProgrammeScope()
  return chosen || undefined
}

/** Stable helper for a page that wants to react to a change without re-deriving the guard. */
export function useSelectProgramme(): (code: string) => void {
  const { select } = useProgrammeScope()
  return useCallback((code: string) => select(code), [select])
}
