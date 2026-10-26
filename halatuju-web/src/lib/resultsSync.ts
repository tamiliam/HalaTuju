/**
 * THE RESULTS HALF OF A PROFILE SYNC — read once from this browser, sent by both sync doors
 * (`onboarding/profile/page.tsx` on finishing onboarding, `AuthGateModal` on signing in).
 * Third results route S2b, 2026-10-26.
 *
 * ⚠ THESE FIELDS TRAVEL AS A SET. The server REPLACES `completed_qualifications` on every sync and
 * ranks "highest" over it (`exam_questions.results_held`), so a sync that sent `results_exam_type`
 * without the list — or a list built from somewhere else — could promote or demote a student. The
 * list is therefore DERIVED from the recorded completion, here, every time
 * (`completedQualificationsFor`), and sent only beside it. A browser that never completed a
 * results form sends neither, and the server keeps what it has (a blank list = the old rule, D1).
 *
 * The third route's own fields (`higher_*`) are sent only when the recorded completion IS a
 * third-route kind: an SPM or STPM student's sync never touches them.
 */
import { syncProfile, type SyncProfileData } from '@/lib/api'
import { browserMovesUp, completedQualificationsFor, isThirdRoute } from '@/lib/qualification'
import {
  KEY_EXAM_TYPE, KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO, KEY_RESULTS_EXAM_TYPE,
} from '@/lib/storage'

type Readable = Pick<Storage, 'getItem'>

function num(raw: string | null): number | null {
  if (raw == null || raw.trim() === '') return null
  const n = parseFloat(raw)
  return Number.isFinite(n) ? n : null
}

export function resultsSyncFields(store: Readable): Partial<SyncProfileData> {
  const out: Partial<SyncProfileData> = {}
  const examType = store.getItem(KEY_EXAM_TYPE)
  if (examType) out.exam_type = examType
  const recorded = (store.getItem(KEY_RESULTS_EXAM_TYPE) || '').trim().toLowerCase()
  const completed = completedQualificationsFor(recorded)
  if (completed.length === 0) return out
  out.results_exam_type = recorded
  out.completed_qualifications = completed
  if (isThirdRoute(recorded)) {
    out.higher_cgpa = num(store.getItem(KEY_HIGHER_CGPA))
    const diploma = recorded === 'diploma'
    out.higher_koko = diploma ? null : num(store.getItem(KEY_HIGHER_KOKO))
    out.higher_institution_type = diploma ? (store.getItem(KEY_HIGHER_INSTITUTION) || '') : ''
  }
  return out
}

/**
 * ⚠ THE SIGN-IN DOOR (S2b adversarial review, HIGH). Signing in syncs whatever THIS browser holds,
 * and a browser can be stale: it may last have seen `'spm'` while another device recorded STPM, or
 * the reverse. So at sign-in the results set is sent ONLY when the server records no completion
 * yet (blank `results_exam_type` and an empty `completed_qualifications`) — an anonymous student's
 * first onboarding reaching the server. A recorded completion is never overwritten from here:
 * never demoted, never moved sideways — with ONE exception (round 2, finding B): a form completed
 * in this browser that moves her UP (held SPM → STPM / Matriculation / Asasi / Diploma) is sent,
 * or a returning SPM student who entered new results while signed out would lose them. A move
 * between two tertiary kinds is NOT sent: we cannot tell which form is newer. The results forms
 * themselves (`onboarding/profile`) still send it.
 * `server` = the profile GET; null when it could not be read — then nothing is sent (we cannot
 * tell, and the cautious answer leaves the server alone). The server guards demotion too
 * (`ProfileUpdateSerializer._never_demote_held_results`); this is the belt to its braces.
 */
export function signInResultsFields(
  store: Readable,
  server: {
    results_exam_type?: string | null; completed_qualifications?: unknown[] | null
    results_held?: string | null
  } | null,
): Partial<SyncProfileData> {
  if (!server) return {}
  const recorded = (server.results_exam_type || '').trim()
  const list = Array.isArray(server.completed_qualifications) ? server.completed_qualifications : []
  if ((recorded || list.length > 0) && !browserMovesUp(store, server.results_held)) return {}
  return resultsSyncFields(store)
}


/** The fields a shut third route (`THIRD_ROUTE_OPEN` off: 400 `third_route_closed`) refuses. */
const THIRD_ROUTE_SYNC_FIELDS = [
  'higher_cgpa', 'higher_koko', 'higher_institution_type', 'completed_qualifications',
] as const

function isThirdRouteClosed(err: unknown): boolean {
  const e = err as { status?: number; fieldErrors?: unknown; code?: unknown } | null
  if (!e || e.status !== 400) return false
  return JSON.stringify(e.fieldErrors ?? e.code ?? '').includes('third_route_closed')
}

/**
 * ⚠ RELEASE SAFETY (S2b review). The profile sync, with ONE retry if the api refuses the third
 * route as shut (an api revision or env switch behind this web release): the third-route fields,
 * the completed list and any third-route exam / marker are dropped and the REST of the sync is
 * sent again — her name, grades and family details are never lost to a switch. Logged, so the
 * mismatch is visible. Any other failure is thrown as before.
 */
export async function syncProfileSafely(data: SyncProfileData, options: { token: string }) {
  try {
    return await syncProfile(data, options)
  } catch (err) {
    if (!isThirdRouteClosed(err)) throw err
    const rest: SyncProfileData = { ...data }
    for (const f of THIRD_ROUTE_SYNC_FIELDS) delete rest[f]
    if (isThirdRoute(rest.exam_type)) delete rest.exam_type
    if (isThirdRoute(rest.results_exam_type)) delete rest.results_exam_type
    console.warn('profile sync: third_route_closed — resent without the third-route results')
    return syncProfile(rest, options)
  }
}
