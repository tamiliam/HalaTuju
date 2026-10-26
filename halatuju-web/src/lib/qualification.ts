/**
 * THE RESULTS ROUTES, on the web — one leaf every student and admin screen asks (third results
 * route S2b, 2026-10-26).
 *
 * The server decides which results a student HOLDS (`exam_questions.results_held`) and serves it;
 * nothing here re-derives that answer. What this module owns is the VOCABULARY the web shares with
 * the server — the five codes a results form can complete — and three small rules that only make
 * sense in the browser:
 *
 *  - `isTertiary` — "STPM-equivalent" (STPM, Matriculation, Asasi, Diploma). Every web branch that
 *    used to ask `=== 'stpm'` to mean "a CGPA student, no SPM pathway step" asks this instead, so a
 *    Matriculation student is never silently treated as an SPM leaver (roadmap §6, the 20-file risk).
 *  - `completedQualificationsFor` — the list the profile sync sends WITH `results_exam_type`. The
 *    server REPLACES `completed_qualifications` on every sync and ranks "highest" over it, so the
 *    web sends the WHOLE list each time, and it is exactly what the last completed results form
 *    completed: the SPM page completes SPM; the STPM page and the third-route page complete their
 *    own qualification AND the SPM block they now require (ruling D4). It is deliberately NOT a
 *    running union of every form ever finished in this browser — a union would PROMOTE on data a
 *    browser merely kept (#15: presence never promotes). The server prunes any entry with no
 *    results behind it. ⚠ It does not DEMOTE either: since the S2b review the server keeps a
 *    profile on tertiary results it still holds (`_never_demote_held_results`), so an STPM holder
 *    who completes the SPM form stays STPM — including a Form Six explorer the server already
 *    reads as STPM from typed STPM data; only clearing that data moves her (decisions.md, finding A).
 *  - `resultsEditPath` — which results form edits the results this student holds.
 *
 * ⚠ The codes are the server's `exam_questions.QUALIFICATIONS` / `THIRD_ROUTE`; `qualificationDrift.test.ts`
 * reads that file and fails if the two lists part (drift-test: halatuju-web/src/lib/__tests__/qualificationDrift.test.ts).
 */

import { KEY_RESULTS_EXAM_TYPE } from '@/lib/storage'

/** Matriculation / Asasi (Foundation) / Diploma — the third results route, STPM-equivalent. */
export const THIRD_ROUTE = ['matric', 'asasi', 'diploma'] as const
export type ThirdRouteKind = (typeof THIRD_ROUTE)[number]
/** Every qualification a results form can complete, lowest first. */
export type Qualification = 'spm' | 'stpm' | ThirdRouteKind

export function isThirdRoute(q: unknown): q is ThirdRouteKind {
  return typeof q === 'string' && (THIRD_ROUTE as readonly string[]).includes(q)
}

/** STPM or the third route: faces the CGPA floor, ranks on a CGPA, picks a degree directly. */
export function isTertiary(q: unknown): boolean {
  return q === 'stpm' || isThirdRoute(q)
}

/** A served / stored code as a `Qualification`; anything unknown (or blank) reads as SPM. */
export function asQualification(q: unknown): Qualification {
  const v = typeof q === 'string' ? q.trim().toLowerCase() : ''
  return v === 'stpm' || isThirdRoute(v) ? (v as Qualification) : 'spm'
}

/** What a completed results form of this kind completed (see the module note). [] when unknown. */
export function completedQualificationsFor(recorded: unknown): Qualification[] {
  const v = typeof recorded === 'string' ? recorded.trim().toLowerCase() : ''
  if (v === 'spm') return ['spm']
  if (v === 'stpm' || isThirdRoute(v)) return ['spm', v as Qualification]
  return []
}

/** The results form that edits these results. */
export function resultsEditPath(q: unknown): string {
  const v = asQualification(q)
  if (v === 'stpm') return '/onboarding/stpm-grades'
  if (isThirdRoute(v)) return '/onboarding/higher-grades'
  return '/onboarding/grades'
}

/**
 * This browser completed a TERTIARY results form (STPM / the third route) and the server holds no
 * tertiary results — a move UP not yet synced (round 2, finding B). The sign-in door then sends it,
 * and the login hydrate must not overwrite it with the server's older answer first. Here, in the
 * leaf, because the auth provider rides on every page (resultsSync would bring the api client).
 */
export function browserMovesUp(store: Pick<Storage, 'getItem'>, serverHeld: string | null | undefined): boolean {
  const recorded = (store.getItem(KEY_RESULTS_EXAM_TYPE) || '').trim().toLowerCase()
  return isTertiary(recorded) && !isTertiary(serverHeld)
}
