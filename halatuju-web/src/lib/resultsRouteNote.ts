/**
 * Which results note Step 3 of /scholarship/apply shows (TD-773), or null for none. `routes` is the
 * server's `results_routes`:
 *  * 'post_spm' + an SPM-only holder -> the warning (A);
 *  * 'both' (each on their own results) + a post-SPM holder (STPM, Matriculation, Asasi, Diploma) ->
 *    the one hint (B): "we check your PNGK, not your SPM grades".
 * 'spm', 'either' and null show nothing; neither does a student with no results yet (that card
 * already asks for them).
 *
 * Kept apart from the lazy wrapper on purpose: the page needs only this decision in its first-load JS;
 * the note, its wrapper and its words ride a chunk (`LazyApplyNotice` -> `LazyResultsRouteNote`).
 */
import type { ResultsRoutes } from '@/lib/api'
import type { Qualification } from '@/lib/qualification'
import type { ResultsNoteKind } from '@/components/scholarship/ResultsRouteNote'   // a type only: erased

export function resultsRouteNote(routes: ResultsRoutes | undefined, examType: Qualification,
  hasData: boolean): ResultsNoteKind | null {
  if (!hasData) return null
  if (routes === 'post_spm') return examType === 'spm' ? 'needsPostSpm' : null
  return routes === 'both' && examType !== 'spm' ? 'pngkOnly' : null   // a Qualification is spm, stpm or a third route
}
