/**
 * SWITCHING FROM STPM (OR HIGHER) TO SPM — the browser's half (pre-U sprint, 2026-11-26).
 *
 * The server keeps a student's held STPM / Matriculation / Asasi / Diploma results against every
 * write that would demote them (the never-demote guard). The ONE way they are removed is an
 * explicit `clear_held_results: true`, sent beside a completed SPM save. This file decides when the
 * browser may send it:
 *
 *  1. They tap SPM on /onboarding/exam-type while holding tertiary results → the dialog. "Yes,
 *     continue with SPM" records `confirmed` with the time (`confirmSpmSwitch`). Back, the STPM card
 *     and the third-route card all forget it (`forgetSpmSwitch`).
 *  2. They save their SPM grades (the grades page's Continue) → `ready` (`markSpmSaved`). Only a
 *     FRESH `confirmed` flag moves; with none, or an expired one, nothing is recorded.
 *  3. The onboarding/profile sync — and ONLY that door, never the sign-in door — sends the clear
 *     when the flag is `ready` and still fresh AND the recorded completion is SPM (`applyHeldClear`).
 *     It also drops this browser's own STPM / third-route fields from that payload.
 *  4. After the sync, `settleHeldClear` forgets the flag; only when the server took the clear are
 *     this browser's STPM / third-route keys removed too, so the browser matches the server. When
 *     the server REFUSED it (an application rests on those results), `restoreAfterRefusedClear`
 *     puts this browser back on the results the server still holds, and the student is told.
 *
 * ⚠ THE FLAG IS SHORT-LIVED (review round 1): it lives in sessionStorage (one tab, gone when the
 * tab closes) and expires CONFIRM_TTL_MS after the dialog's yes. A grades save next week, without a
 * fresh yes, never sends the clear.
 *
 * Leaving midway changes nothing on the server: until step 3 succeeds, every write is guarded as
 * before. A student whose application rests on the held results is refused by the server (400,
 * `held_results_locked` on GET /profile); the dialog says so up front and offers only Back.
 */
import type { SyncProfileData } from '@/lib/api'
import { isTertiary } from '@/lib/qualification'
import { dropLocalHeldResults } from '@/lib/heldResultsLocal'
import { KEY_CLEAR_HELD_PENDING, KEY_EXAM_TYPE, KEY_RESULTS_EXAM_TYPE } from '@/lib/storage'

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

const CONFIRMED = 'confirmed'
const READY = 'ready'
/** How long the dialog's yes stays good: 30 minutes. */
export const CONFIRM_TTL_MS = 30 * 60 * 1000

/** The dialog shows only for a student the SERVER says holds tertiary results. */
export function needsSpmSwitchDialog(profile?: { results_held?: string | null } | null): boolean {
  return isTertiary(profile?.results_held)
}

/** The bold line in the dialog: the route's name and its score ("STPM", "STPM PNGK 3.42"). */
export function heldResultsSummary(
  profile: { results_held?: string | null; stpm_cgpa?: number | null; higher_cgpa?: number | null },
  thirdRouteName: (kind: string) => string,
): { route: string; summary: string } {
  const held = profile.results_held || ''
  if (held === 'stpm') {
    const cgpa = typeof profile.stpm_cgpa === 'number' ? profile.stpm_cgpa.toFixed(2) : ''
    return { route: 'STPM', summary: cgpa ? `STPM PNGK ${cgpa}` : 'STPM' }
  }
  const route = thirdRouteName(held)
  const cgpa = typeof profile.higher_cgpa === 'number' ? profile.higher_cgpa.toFixed(2) : ''
  return { route, summary: cgpa ? `${route} CGPA ${cgpa}` : route }
}

/** The flag's state when it is still fresh; '' when absent, malformed or expired. */
function freshState(store: Pick<Storage, 'getItem'>, now: number): string {
  const raw = store.getItem(KEY_CLEAR_HELD_PENDING)
  if (!raw) return ''
  try {
    const { state, at } = JSON.parse(raw) as { state?: unknown; at?: unknown }
    if (typeof state !== 'string' || typeof at !== 'number') return ''
    return now - at >= 0 && now - at <= CONFIRM_TTL_MS ? state : ''
  } catch { return '' }
}

export function confirmSpmSwitch(store: Store, now: number = Date.now()): void {
  try { store.setItem(KEY_CLEAR_HELD_PENDING, JSON.stringify({ state: CONFIRMED, at: now })) } catch { /* storage unavailable */ }
}

export function forgetSpmSwitch(store: Store): void {
  try { store.removeItem(KEY_CLEAR_HELD_PENDING) } catch { /* storage unavailable */ }
}

/** The SPM grades save: a FRESH confirmed switch becomes ready to send (keeping the yes's time).
 *  An expired one is forgotten. Nothing else moves. */
export function markSpmSaved(store: Store, now: number = Date.now()): void {
  try {
    const raw = store.getItem(KEY_CLEAR_HELD_PENDING)
    if (!raw) return
    if (freshState(store, now) !== CONFIRMED) { store.removeItem(KEY_CLEAR_HELD_PENDING); return }
    const { at } = JSON.parse(raw) as { at: number }
    store.setItem(KEY_CLEAR_HELD_PENDING, JSON.stringify({ state: READY, at }))
  } catch { /* storage unavailable */ }
}

/** The payload fields this browser's STPM / third-route keys feed — never sent beside a clear. */
const HELD_PAYLOAD_FIELDS = [
  'stpm_grades', 'stpm_cgpa', 'stpm_koko', 'stpm_koko_confirmed',
  'higher_cgpa', 'higher_koko', 'higher_institution_type',
] as const

/**
 * The onboarding/profile door only: adds `clear_held_results: true` when they confirmed AND saved
 * their SPM grades within the last 30 minutes (`flagStore`: sessionStorage) and the recorded
 * completion is SPM (`resultsStore`: localStorage). Returns whether it did.
 */
export function applyHeldClear(
  payload: SyncProfileData, flagStore: Pick<Storage, 'getItem'>, resultsStore: Pick<Storage, 'getItem'>,
  now: number = Date.now(),
): boolean {
  let ready = false
  try {
    ready = freshState(flagStore, now) === READY
      && (resultsStore.getItem(KEY_RESULTS_EXAM_TYPE) || '').trim().toLowerCase() === 'spm'
  } catch { return false }
  if (!ready) return false
  const p = payload as Record<string, unknown>
  for (const f of HELD_PAYLOAD_FIELDS) delete p[f]
  payload.clear_held_results = true
  return true
}

// The hydrate's two helpers live apart, so every page does not pay for this module (review round 1).
export { dropLocalHeldResults, serverHoldsSpmOnly } from '@/lib/heldResultsLocal'

/**
 * After the onboarding/profile sync. `cleared` = the server took the clear (the sync succeeded and
 * still carried it — `syncProfileSafely` drops it when the server refuses it as locked).
 */
export function settleHeldClear(flagStore: Store, resultsStore: Store, cleared: boolean): void {
  if (cleared) dropLocalHeldResults(resultsStore)
  forgetSpmSwitch(flagStore)
}

/**
 * The server REFUSED the clear: it still holds `held` (the route the dialog named). This browser
 * goes back to that route too, so it never reads as SPM while the server reads STPM (review round
 * 1). Its STPM / third-route keys were never removed, so only the exam and the completion move.
 */
export function restoreAfterRefusedClear(store: Store, held: string | null | undefined): void {
  if (!isTertiary(held)) return
  try {
    store.setItem(KEY_EXAM_TYPE, held as string)
    store.setItem(KEY_RESULTS_EXAM_TYPE, held as string)
  } catch { /* storage unavailable */ }
}
