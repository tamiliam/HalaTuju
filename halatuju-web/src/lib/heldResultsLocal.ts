/**
 * This browser's copies of the STPM / third-route results, and the one server state in which they
 * must go (pre-U sprint, review round 1). Apart from `lib/resultsSwitch` because the login hydrate
 * (`auth-context`, on every page) needs only these two small helpers, not the switch's flag flow.
 */
import {
  KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO, KEY_KOKO_SCORE, KEY_STPM_CGPA,
  KEY_STPM_GRADES, KEY_STPM_KOKO_CONFIRMED,
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
