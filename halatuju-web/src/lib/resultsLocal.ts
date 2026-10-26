/**
 * THIS BROWSER'S STORED RESULTS, CLEARED after two server actions (third results route
 * S3a/S3b, 2026-10-26, owner rulings D11/D13).
 *
 * The profile sync resends whatever this browser stored (`onboarding/profile`, `resultsSync`), so a
 * results change the server makes must also be applied to this browser's storage, or the next sync brings the old
 * results back:
 *
 *  - `keepOneHigherLocally` — ONE HIGHER QUALIFICATION AT A TIME. Completing the STPM form clears the
 *    third route's entries; completing the Matriculation / Asasi / Diploma form clears the STPM
 *    entries (the server does the same in `ProfileUpdateSerializer._one_higher_qualification`).
 *  - `clearHigherResultsLocally` — "Continue with SPM results only": every higher result goes, the
 *    SPM grades stay (and, like the server, the STPM page's SPM block becomes the SPM record when
 *    the SPM form was never filled in this browser).
 */
import {
  KEY_EXAM_TYPE, KEY_GRADES, KEY_HIGHER_CGPA, KEY_HIGHER_INSTITUTION, KEY_HIGHER_KOKO,
  KEY_RESULTS_EXAM_TYPE, KEY_SPM_PREREQ, KEY_STPM_CGPA, KEY_STPM_GRADES,
} from '@/lib/storage'

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

const STPM_KEYS = [KEY_STPM_GRADES, KEY_STPM_CGPA]
const THIRD_ROUTE_KEYS = [KEY_HIGHER_CGPA, KEY_HIGHER_KOKO, KEY_HIGHER_INSTITUTION]

/** The form just completed `kind`; drop the OTHER higher qualification's entries. */
export function keepOneHigherLocally(kind: 'stpm' | 'third', store: Store): void {
  for (const k of kind === 'stpm' ? THIRD_ROUTE_KEYS : STPM_KEYS) store.removeItem(k)
}

/** The server removed the higher results (SPM only); drop them from this browser too. */
export function clearHigherResultsLocally(store: Store): void {
  for (const k of [...STPM_KEYS, ...THIRD_ROUTE_KEYS]) store.removeItem(k)
  const grades = store.getItem(KEY_GRADES)
  const prereq = store.getItem(KEY_SPM_PREREQ)
  const empty = !grades || grades === '{}'
  if (empty && prereq && prereq !== '{}') store.setItem(KEY_GRADES, prereq)
  store.setItem(KEY_EXAM_TYPE, 'spm')
  if (!empty || (prereq && prereq !== '{}')) store.setItem(KEY_RESULTS_EXAM_TYPE, 'spm')
  else store.removeItem(KEY_RESULTS_EXAM_TYPE)
}
