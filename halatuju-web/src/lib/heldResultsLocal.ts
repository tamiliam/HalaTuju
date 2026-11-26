/**
 * This browser's copies of the STPM / third-route results, and the one server state in which they
 * must go (pre-U sprint, review rounds 1 and 2). Apart from `lib/resultsSwitch` because the login
 * hydrate (`auth-context`, on every page) needs only these small helpers, not the switch's flag flow.
 */
import {
  KEY_EXAM_TYPE, KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO, KEY_KOKO_SCORE,
  KEY_RESULTS_COMPLETED_AT, KEY_RESULTS_EXAM_TYPE, KEY_STPM_CGPA, KEY_STPM_GRADES,
  KEY_STPM_KOKO_CONFIRMED,
} from '@/lib/storage'

/** What the switch's clear removes on the server, as this browser keeps it. */
const HELD_KEYS = [
  KEY_STPM_GRADES, KEY_STPM_CGPA, KEY_KOKO_SCORE, KEY_STPM_KOKO_CONFIRMED,
  KEY_HIGHER_CGPA, KEY_HIGHER_KOKO, KEY_HIGHER_INSTITUTION,
]

/** Removes this browser's STPM / third-route results (after the clear, or on the hydrate below). */
export function dropLocalHeldResults(store: Pick<Storage, 'removeItem'>): void {
  try { HELD_KEYS.forEach((k) => store.removeItem(k)) } catch { /* storage unavailable */ }
}

/**
 * True when the server's profile holds SPM only and no STPM / third-route results at all — the
 * state the switch leaves. The hydrate then clears this browser's stale copies, so no later sync
 * (this device or another) can send them back up.
 */
export function serverHoldsSpmOnly(profile: {
  results_held?: string | null; completed_qualifications?: unknown[] | null
  stpm_grades?: Record<string, unknown> | null; stpm_cgpa?: number | null; higher_cgpa?: number | null
} | null | undefined): boolean {
  if (!profile || profile.results_held !== 'spm') return false
  const list = Array.isArray(profile.completed_qualifications) ? profile.completed_qualifications : []
  if (list.length !== 1 || list[0] !== 'spm') return false
  return Object.keys(profile.stpm_grades || {}).length === 0
    && profile.stpm_cgpa == null && profile.higher_cgpa == null
}

/** The STPM / third-route form's Continue: when it was completed, beside KEY_RESULTS_EXAM_TYPE. */
export function markTertiaryCompleted(store: Pick<Storage, 'setItem'>): void {
  try { store.setItem(KEY_RESULTS_COMPLETED_AT, new Date().toISOString()) } catch { /* unavailable */ }
}

type ServerProfile = NonNullable<Parameters<typeof serverHoldsSpmOnly>[0]> & {
  held_results_cleared_at?: string | null; exam_type?: string | null; results_exam_type?: string | null
}

function setOrRemove(store: Pick<Storage, 'setItem' | 'removeItem'>, key: string, value?: string | null) {
  if (value) store.setItem(key, value)
  else store.removeItem(key)
}

/**
 * Review round 2 - RUN BEFORE THE HYDRATE'S PENDING-MOVE-UP CHECK. The server holds SPM only and
 * carries the switch's stamp (`held_results_cleared_at`), and this browser's tertiary form was not
 * completed after it (no completion time, or an older one): its STPM / third-route copies are
 * dropped and its exam and recorded completion reset to the server's, so it no longer reads as a
 * move up and no sync can send the cleared results back. An entry completed after the switch is
 * kept (a genuine move back). A profile never switched has no stamp: nothing changes.
 */
export function dropStaleLocalResults(
  store: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>, profile: ServerProfile | null | undefined,
): boolean {
  const stamp = Date.parse(profile?.held_results_cleared_at || '')
  if (!profile || Number.isNaN(stamp) || !serverHoldsSpmOnly(profile)) return false
  try {
    const done = Date.parse(store.getItem(KEY_RESULTS_COMPLETED_AT) || '')
    if (!Number.isNaN(done) && done > stamp) return false
    dropLocalHeldResults(store)
    store.removeItem(KEY_RESULTS_COMPLETED_AT)
    setOrRemove(store, KEY_EXAM_TYPE, profile.exam_type)
    setOrRemove(store, KEY_RESULTS_EXAM_TYPE, profile.results_exam_type)
    return true
  } catch { return false /* storage unavailable */ }
}
