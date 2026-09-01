/**
 * Matriculation tracks: the four streams a student picks between, and the chip each is drawn with.
 *
 * ⚠ ONE HOME, BECAUSE THERE USED TO BE TWO. The colours and labels were declared identically in
 * `app/pathway/matric/page.tsx` and `app/course/[id]/page.tsx` — the second copy of the F4
 * role-palette shape found in this sprint. A student moves between exactly those two pages while
 * comparing tracks, so a drift would have shown the same track in two colours.
 *
 * A CATEGORY PALETTE on the `category-N` family (F2c, owner decision 2026-08-31): four tracks,
 * four DIFFERENT numbers, never a tone. `sains` was green and `sains_komputer` blue, so a family
 * rename would have made them `positive` and `info` — claiming that one track is a success and
 * another is a notice, and putting them beside real status chips wearing the same colours.
 */

export type TrackId = 'sains' | 'sains_komputer' | 'kejuruteraan' | 'perakaunan'

/** Course id → track. The catalogue spells a matriculation course `matric-<track>`. */
export const MATRIC_TRACK_MAP: Record<string, TrackId> = {
  'matric-sains': 'sains',
  'matric-sains_komputer': 'sains_komputer',
  'matric-kejuruteraan': 'kejuruteraan',
  'matric-perakaunan': 'perakaunan',
}

/** Complete literal class names — never assembled from a number, because Tailwind's JIT scanner
 *  reads source text and would find nothing to generate. */
export const TRACK_CHIP: Record<TrackId, string> = {
  sains: 'bg-category-6-surface text-category-6-ink',
  sains_komputer: 'bg-category-5-surface text-category-5-ink',
  kejuruteraan: 'bg-category-3-surface text-category-3-ink',
  perakaunan: 'bg-category-1-surface text-category-1-ink',
}

export const TRACK_LABELS: Record<TrackId, string> = {
  sains: 'Sains',
  sains_komputer: 'Sains Komputer',
  kejuruteraan: 'Kejuruteraan',
  perakaunan: 'Perakaunan',
}
