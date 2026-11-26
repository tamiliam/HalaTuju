/**
 * SWITCHING FROM STPM (OR HIGHER) TO SPM — the browser's half (pre-U sprint, 2026-11-26).
 *
 * The server keeps a student's held STPM / Matriculation / Asasi / Diploma results against every
 * write that would demote them (the never-demote guard). The ONE way they are removed is an
 * explicit `clear_held_results: true`, sent beside a completed SPM save. This file decides when the
 * browser may send it:
 *
 *  1. She taps SPM on /onboarding/exam-type while holding tertiary results → the dialog. "Yes,
 *     continue with SPM" records `confirmed` (`confirmSpmSwitch`). Back, the STPM card and the
 *     third-route card all forget it (`forgetSpmSwitch`).
 *  2. She saves her SPM grades (the grades page's Continue) → `ready` (`markSpmSaved`). Only a
 *     `confirmed` flag moves; with none, nothing is recorded.
 *  3. The onboarding/profile sync — and ONLY that door, never the sign-in door — sends the clear
 *     when the flag is `ready` AND the recorded completion is SPM (`applyHeldClear`). It also drops
 *     this browser's own STPM / third-route fields from that payload, so they cannot ride along.
 *  4. After the sync, `settleHeldClear` forgets the flag; only when the server took the clear are
 *     this browser's STPM / third-route keys removed too, so the browser matches the server.
 *
 * Leaving midway changes nothing on the server: until step 3 succeeds, every write is guarded as
 * before. A student with an application in play is refused by the server (400, `held_results_locked`
 * on GET /profile); the dialog says so up front and offers only Back.
 */
import type { SyncProfileData } from '@/lib/api'
import { isTertiary } from '@/lib/qualification'
import {
  KEY_CLEAR_HELD_PENDING, KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO, KEY_KOKO_SCORE,
  KEY_RESULTS_EXAM_TYPE, KEY_STPM_CGPA, KEY_STPM_GRADES, KEY_STPM_KOKO_CONFIRMED,
} from '@/lib/storage'

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

const CONFIRMED = 'confirmed'
const READY = 'ready'

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

export function confirmSpmSwitch(store: Store): void {
  try { store.setItem(KEY_CLEAR_HELD_PENDING, CONFIRMED) } catch { /* storage unavailable */ }
}

export function forgetSpmSwitch(store: Store): void {
  try { store.removeItem(KEY_CLEAR_HELD_PENDING) } catch { /* storage unavailable */ }
}

/** The SPM grades save: a confirmed switch becomes ready to send. Nothing else moves. */
export function markSpmSaved(store: Store): void {
  try {
    if (store.getItem(KEY_CLEAR_HELD_PENDING) === CONFIRMED) store.setItem(KEY_CLEAR_HELD_PENDING, READY)
  } catch { /* storage unavailable */ }
}

/** The payload fields this browser's STPM / third-route keys feed — never sent beside a clear. */
const HELD_PAYLOAD_FIELDS = [
  'stpm_grades', 'stpm_cgpa', 'stpm_koko', 'stpm_koko_confirmed',
  'higher_cgpa', 'higher_koko', 'higher_institution_type',
] as const

/**
 * The onboarding/profile door only: adds `clear_held_results: true` when she confirmed AND saved
 * her SPM grades (flag `ready`, recorded completion SPM). Returns whether it did.
 */
export function applyHeldClear(payload: SyncProfileData, store: Pick<Storage, 'getItem'>): boolean {
  let ready = false
  try {
    ready = store.getItem(KEY_CLEAR_HELD_PENDING) === READY
      && (store.getItem(KEY_RESULTS_EXAM_TYPE) || '').trim().toLowerCase() === 'spm'
  } catch { return false }
  if (!ready) return false
  const p = payload as Record<string, unknown>
  for (const f of HELD_PAYLOAD_FIELDS) delete p[f]
  payload.clear_held_results = true
  return true
}

/** This browser's copies of the results the clear removed on the server. */
const HELD_KEYS = [
  KEY_STPM_GRADES, KEY_STPM_CGPA, KEY_KOKO_SCORE, KEY_STPM_KOKO_CONFIRMED,
  KEY_HIGHER_CGPA, KEY_HIGHER_KOKO, KEY_HIGHER_INSTITUTION,
]

/**
 * After the onboarding/profile sync. `cleared` = the server took the clear (the sync succeeded and
 * still carried it — `syncProfileSafely` drops it when the server refuses it as locked).
 */
export function settleHeldClear(store: Store, cleared: boolean): void {
  try {
    if (cleared) HELD_KEYS.forEach((k) => store.removeItem(k))
    store.removeItem(KEY_CLEAR_HELD_PENDING)
  } catch { /* storage unavailable */ }
}
