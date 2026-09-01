/**
 * STPM subject codes: what each one is, which stream it belongs to, and how its chip is drawn.
 *
 * ⚠ ONE HOME, BECAUSE THERE USED TO BE TWO. Every export below existed twice — byte-identical —
 * in `app/course/[id]/page.tsx` and `app/pathway/stpm/page.tsx`, which is the shape F4 found in
 * the role palette: a codemod converts one copy and leaves the other, and the same subject then
 * renders differently on two pages a student moves between. Merged in Layer 1 F6.
 *
 * ── WHY THE CHIP IS GREY (Layer 1 F6, 2026-09-02) ────────────────────────────────────────────
 * There were seventeen codes on sixteen hues. Three things decided against carrying that into the
 * category family:
 *   1. The family has EIGHT swatches. Sixteen that also avoid green / blue / amber / red (so a
 *      category is never mistaken for a status) and still separate in dark mode do not exist.
 *   2. The colour carried nothing a reader could decode. Every chip is rendered beside its own
 *      full name — `BIO  Biology` — so the hue is decoration on a label that already says itself.
 *   3. Colouring by STREAM instead was considered and rejected: `filterSubjects` shows one stream
 *      at a time, so every chip on screen would have been the same colour anyway.
 * A category colour earns its place when a reader scans a set; here nobody was scanning one.
 */

/** Sat by every STPM candidate, so they say nothing about a school and are filtered out. */
const COMMON_SUBJECTS = new Set(['BI (MUET)', 'PA', 'BM'])

export const SCIENCE_SUBJECTS = new Set(['BIO', 'CHE', 'PHY', 'MT', 'MM'])
export const SOCIAL_SUBJECTS = new Set(
  ['EKO', 'SEJ', 'GEO', 'PP', 'PAKN', 'SS', 'SV', 'BT', 'BC', 'KMK', 'ICT', 'L.ENG'],
)

export const SUBJECT_NAMES: Record<string, string> = {
  BIO: 'Biology',
  CHE: 'Chemistry',
  PHY: 'Physics',
  MT: 'Mathematics (T)',
  MM: 'Mathematics (M)',
  EKO: 'Economics',
  SEJ: 'History',
  GEO: 'Geography',
  PP: 'Business Studies',
  PAKN: 'Accounting',
  SS: 'Literature',
  SV: 'Visual Arts',
  BT: 'Bahasa Tamil',
  BC: 'Bahasa Cina',
  KMK: 'Kesusasteraan Melayu Komunikatif',
  ICT: 'Information & Communication Technology',
  'L.ENG': 'Literature in English',
}

/** One chip class for every subject — see the header. Deliberately not a lookup table. */
export const SUBJECT_CHIP = 'bg-ground-100 text-ground-700'

/** The subjects worth showing for a school on a given stream: drop the ones everybody sits, and
 *  drop anything belonging to the other stream. */
export function filterSubjects(raw: string, stream: string): string[] {
  const relevant = stream === 'Sains' ? SCIENCE_SUBJECTS : SOCIAL_SUBJECTS
  return raw
    .split('; ')
    .filter((s) => !COMMON_SUBJECTS.has(s) && relevant.has(s))
}

/** The legend's order — science first, then the social-science list as a reader expects it. */
export function legendSubjects(stream: string): string[] {
  return stream === 'Sains'
    ? ['BIO', 'CHE', 'PHY', 'MT', 'MM']
    : ['EKO', 'PP', 'PAKN', 'SEJ', 'GEO', 'SS', 'SV', 'BT', 'BC', 'KMK', 'ICT', 'L.ENG']
}
