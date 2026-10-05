'use client'

/**
 * MAY SHE START AN APPLICATION HERE? — asked of the SERVER, before the form (2026-10-05, TD-337).
 *
 * The owner's ruling: one application in process, or one award, for each organisation — and never
 * the same round twice (as built: one in process ANYWHERE until roadmap M2, because the student side
 * cannot yet carry two live applications). The rule lives in ONE place, `halatuju_api/apps/scholarship/services/
 * apply_gate.py`, which the submit also reads. Until this sprint the apply page kept its own,
 * stricter rule (`mustLeaveApplyPage` — a non-expired application in ANY round); the web now keeps NO copy —
 * it asks `GET /scholarship/apply-gate/` and obeys the answer:
 *
 *   • `application_in_progress` → she is sent to her application (`/scholarship/application`) —
 *     even on a CLOSED gift's link or a bare visit with nothing open: the server answers the
 *     in-play half without needing an open round;
 *   • `already_applied` (a finished application in this very round) → the page shows a small card;
 *   • allowed, or the request FAILED → the form (the server still refuses at submit).
 *
 * ⚠ ASKED AGAIN WHENEVER THE GIFT IN FORCE CHANGES — a pick, "Change", the closed card's link to the
 * open programmes. `named` is the URL's code, which the server resolves exactly as the intake does
 * (a retired alias, the one open round on a bare visit), so the question is never the served code.
 * Until the answer for THAT code arrives the state reads 'pending' — never the previous gift's verdict.
 *
 * ⚠ A SIGNED-OUT VISITOR IS NEVER ASKED: the state is 'idle' and no request is made.
 *
 * ⚠ THIS HOOK NEVER REDIRECTS. Where the page sends her is decided in ONE place, `applyPageExit`
 * below, which the page runs once the intake has settled and this gate is not pending (round 2:
 * the intake's "nothing open → /scholarship" and this gate's "in progress → her application" used
 * to be two redirects racing, and the last one won).
 */
import { useCallback, useEffect, useState } from 'react'

import { getApplyGate } from '@/lib/api'

export type ApplyGateState = 'idle' | 'pending' | 'allowed' | 'application_in_progress' | 'already_applied'

/** One of the gate's two refusals, or undefined — an unknown reason is no reason to hide the form. */
const refusal = (code?: string) =>
  (['application_in_progress', 'already_applied'] as const).find((r) => r === code)

export interface ApplyGate {
  state: ApplyGateState
  /** A refused SUBMIT carrying one of the gate's own codes: adopt it (true), else false. */
  adopt: (err: unknown) => boolean
}

/**
 * Where the apply page sends her — the ONE decision, in a fixed order:
 *   1. `application_in_progress` → her application. First whatever the intake says, so it is taken
 *      the moment the gate answers (an intake that never answers must not trap her here);
 *   2. else a bare visit with nothing open → the landing (`/scholarship`, which says closed) — only
 *      once BOTH the intake has settled and the gate is not pending (auth still loading counts as
 *      pending): a signed-in student is never sent to the landing before the gate has answered;
 *   3. else stay (the closed card, the chooser, the sign-in gate, the already-applied card, the form).
 * null = stay, or not yet decided.
 */
export function applyPageExit(s: {
  settled: boolean; noneOpen: boolean; authLoading: boolean; gate: ApplyGateState
}): '/scholarship/application' | '/scholarship' | null {
  if (s.gate === 'application_in_progress') return '/scholarship/application'
  if (!s.settled || s.authLoading || s.gate === 'pending') return null
  return s.noneOpen ? '/scholarship' : null
}

export function useApplyGate(token: string | null, named: string | null): ApplyGate {
  // The answer, and the code it answers for — so a stale answer is never read for a new gift.
  const [answer, setAnswer] = useState<{ code: string; state: ApplyGateState } | null>(null)

  useEffect(() => {
    if (!token || named === null) return
    let active = true
    getApplyGate(named, { token })
      .then((r) => { if (active) setAnswer({ code: named, state: (!r.allowed && refusal(r.reason)) || 'allowed' }) })
      .catch(() => { if (active) setAnswer({ code: named, state: 'allowed' }) })   // the submit still refuses
    return () => { active = false }
  }, [token, named])

  const adopt = useCallback((err: unknown) => {
    const hit = refusal((err as { bodyCode?: string } | null)?.bodyCode)
    if (hit && named !== null) setAnswer({ code: named, state: hit })
    return !!hit
  }, [named])

  const state: ApplyGateState = !token ? 'idle'
    : answer && answer.code === named ? answer.state : 'pending'
  return { state, adopt }
}
