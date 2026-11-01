'use client'

/**
 * THE APPLY DRAFT — Mobile M4, owner ruling 2026-11-01 ("option 1: this tab only").
 *
 * The apply form commits NOTHING to the server until submit (decisions.md, 2026-05-24). On a phone
 * that meant an iOS tab kill — the student checks WhatsApp, the camera, a payslip — threw away five
 * steps of typing. So the half-filled form is kept in THIS TAB's sessionStorage:
 *
 *   * WHAT: the form, MINUS the IC number, the typed declaration signature and the consent switch
 *     (`DRAFT_EXCLUDED`). The IC comes back from the profile (the sign-in gate guarantees one); the
 *     signature and the consent are always given afresh, in the session that submits. What remains is
 *     still personal (income, the parent's name and phone), which is why it never leaves the tab.
 *   * BOUND TO: her user id, the programme the form is for, a format version and a 24-hour age. Any
 *     mismatch → no draft, and the stored one is deleted. Another person signing in on the same tab
 *     can never be handed it (and sign-out / any SIGNED_OUT wipes every `halatuju_` tab key anyway).
 *   * WRITTEN: shortly after each change, and at once when the tab is hidden (`useApplyDraft`) — the
 *     moment iOS reclaims it. Only once she has changed something.
 *   * CLEARED: on a successful submit, when the server says she has already applied or the programme
 *     has closed, on sign-out (`clearAll`), on any SIGNED_OUT (`clearStudentTab`), when unreadable,
 *     and by the browser when the tab closes.
 *   * NEVER SENT. This module imports nothing that talks to the network (guarded in
 *     `applyDraft.test.ts`); the server sees the form only through the submit, as before.
 */
import { useEffect, useRef } from 'react'
import { APPLY_STASH_KEY, safeSession } from './applyReturn'
import type { ApplyFormState } from './scholarship'

// ⚠ WRITTEN SMALL ON PURPOSE: this rides on /scholarship/apply, which had 0.59 kB of first-load room
// before M4 (never raise a budget). Storage and time are the browser's own (tests use jsdom's
// sessionStorage and jest's clock); every check below is still one the tests bite.
export const APPLY_DRAFT_KEY = APPLY_STASH_KEY
/** The pre-M4 whole-form stash (IC and signature included). Nothing writes it now; deleted on sight. */
const LEGACY_STASH_KEY = 'halatuju_apply_stash'
export const APPLY_DRAFT_MAX_AGE_MS = 864e5   // 24 hours
/** Never stored — see the header. */
export const DRAFT_EXCLUDED = ['nric', 'declarationName', 'consentToContact'] as const
export type DraftForm = Omit<ApplyFormState, typeof DRAFT_EXCLUDED[number]>

interface Envelope { v: number; uid: string; programme: string; savedAt: number; step: string; form: ApplyFormState }

export interface DraftOwner {
  /** The signed-in student's user id (`session.user.id`). No id → nothing is read or written. */
  uid: string | null | undefined
  /** The programme code the form is for ('' when the form names none). */
  programme: string
}

export function strip(form: ApplyFormState): DraftForm {
  const out: Partial<ApplyFormState> = { ...form }
  for (const k of DRAFT_EXCLUDED) delete out[k]
  return out as DraftForm
}

export function writeApplyDraft(form: ApplyFormState, owner: DraftOwner, step: string): void {
  if (!owner.uid) return
  try {
    safeSession()?.setItem(APPLY_DRAFT_KEY, JSON.stringify({ v: 1, uid: owner.uid, programme: owner.programme,
      savedAt: Date.now(), step, form: strip(form) }))
  } catch { /* full or blocked: the form still works, it just keeps no draft */ }
}

export function clearApplyDraft(): void {
  try { const s = safeSession(); s?.removeItem(APPLY_DRAFT_KEY); s?.removeItem(LEGACY_STASH_KEY) } catch { /* none */ }
}

/** The stored envelope when it is well-formed and between 0 and 24 hours old (a minute of clock skew
 *  forgiven), else null. Anything unreadable throws inside the try and is null too. */
export function parse(): Envelope | null {
  try {
    const e = JSON.parse(safeSession()?.getItem(APPLY_DRAFT_KEY) || 'null')
    const age = Date.now() - e.savedAt
    return e.v === 1 && typeof e.uid === 'string' && typeof e.form === 'object' && e.form
      && age >= -6e4 && age <= APPLY_DRAFT_MAX_AGE_MS ? e : null
  } catch {
    return null
  }
}

/**
 * Her draft for THIS programme, or null. Anything that is not hers — another user id, an old format,
 * older than 24 h, unreadable — is DELETED, never returned. Her own draft for ANOTHER programme is
 * not returned either, but kept: she may go back to that programme (the chooser's "Change"). The
 * excluded fields are dropped again on the way out, so a hand-edited value cannot smuggle them in.
 */
export function readApplyDraft(owner: DraftOwner): { form: DraftForm; step: string } | null {
  const e = parse()
  if (!e || !owner.uid || e.uid !== owner.uid) { clearApplyDraft(); return null }
  return e.programme === owner.programme ? { form: strip(e.form), step: String(e.step || '') } : null
}

/**
 * Keep the draft as she types. `enabled` false (not yet populated, nothing changed, already sent) →
 * nothing is written. Writes ~0.5 s after the last change, and AT ONCE when the tab is hidden or the
 * page is being put away (`visibilitychange` / `pagehide`) — iOS reclaims a hidden tab, and a timer
 * that has not fired by then never will.
 */
export function useApplyDraft(form: ApplyFormState, uid: string | null | undefined, programme: string,
  step: string, enabled: boolean): void {
  const latest = useRef(() => {})
  latest.current = () => { if (enabled) writeApplyDraft(form, { uid, programme }, step) }
  useEffect(() => {
    const id = setTimeout(() => latest.current(), 500)
    return () => clearTimeout(id)
  }, [form, uid, programme, step, enabled])
  useEffect(() => {
    const flush = () => latest.current()
    const hidden = () => { if (document.visibilityState === 'hidden') flush() }
    document.addEventListener('visibilitychange', hidden)
    window.addEventListener('pagehide', flush)
    return () => { document.removeEventListener('visibilitychange', hidden); window.removeEventListener('pagehide', flush) }
  }, [])
}
