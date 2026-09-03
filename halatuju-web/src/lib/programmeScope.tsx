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
 */

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

export interface ProgrammeChoice {
  code: string
  name: string
  /** False for a gift that is not switched on yet — a normal, and common, state. */
  isActive?: boolean
}

export interface ProgrammeScope {
  /** Every gift this caller may look at, from the scopes endpoint. Server-ordered. */
  choices: readonly ProgrammeChoice[]
  /** The selected gift's code, or `''` when it is not yet known. NEVER guessed. */
  chosen: string
  /** The selected gift, or null. */
  programme: ProgrammeChoice | null
  /** True when there is more than one to choose between — the page should say so. */
  ambiguous: boolean
  select: (code: string) => void
}

const EMPTY: ProgrammeScope = {
  choices: [], chosen: '', programme: null, ambiguous: false, select: () => {},
}

const Ctx = createContext<ProgrammeScope>(EMPTY)

/**
 * Provided by the shell, so the choice survives moving between Configuration and Applications.
 * A page outside the shell (a test harness, the sandbox) gets `EMPTY` and simply behaves as it
 * did before this existed.
 */
export function ProgrammeScopeProvider(
  { choices, children }: { choices: readonly ProgrammeChoice[]; children: ReactNode },
) {
  const [picked, setPicked] = useState('')

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
    const known = choices.some((c) => c.code === picked)
    const chosen = picked
      ? (known ? picked : '')
      : (choices.length === 1 ? choices[0].code : '')
    return {
      choices,
      chosen,
      programme: choices.find((c) => c.code === chosen) ?? null,
      ambiguous: choices.length > 1,
      select: setPicked,
    }
  }, [choices, picked])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useProgrammeScope(): ProgrammeScope {
  return useContext(Ctx)
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
