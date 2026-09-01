/**
 * Institution TYPE and qualification LEVEL badges — the two chips at the top of every course card
 * and course header.
 *
 * ── TYPE IS A CATEGORY. LEVEL IS NOT. (Layer 1 F6, 2026-09-02) ───────────────────────────────
 *
 * `TYPE_SWATCH` is a CATEGORY PALETTE on the `category-N` family (F2c, owner decision
 * 2026-08-31): one swatch per institution type so a student can tell a Politeknik from an ILJTM
 * while scanning a grid of results. Never a tone — `poly` and `iljtm` were emerald and green, and
 * a family rename would have made both `positive`, which additionally claims a Polytechnic is a
 * "success". Eight types, eight DIFFERENT numbers.
 *
 * ⚠ THIS FILE IS THE ONLY HOME FOR institution-type → swatch. `RequirementsCard.tsx` described
 * the same six types independently until F6 and imports from here now. That is the F4 role-palette
 * lesson applied before it bit: a comment asking two files to agree is a request, not a mechanism,
 * and a student who saw a teal `Politeknik` in the search grid and an orange one on the course
 * page would blame the data. The numbers below are RequirementsCard's, kept byte-for-byte, so
 * nothing a student sees today moves; only `matric` and `stpm` (which that card never had) are new.
 *
 * `LEVEL_CHIP` is deliberately ONE neutral class for every level, not a palette. Three reasons,
 * in the order they decided it:
 *   1. The level chip sits IMMEDIATELY BESIDE the type chip on the same card. Both are categories,
 *      they need 8 + 5 = 13 distinct swatches, and the family has 8. Something had to give.
 *   2. The colour carried nothing: the chip's own text already reads "Diploma" / "Sijil" /
 *      "Ijazah Sarjana Muda", and `/search` has a Level dropdown, so nobody was decoding hue.
 *   3. An unrecognised level ALREADY rendered as a grey chip — grey level chips have been in the
 *      product all along, and this makes the recognised ones agree with them.
 * Widening `--category-*` from 8 to 16 was the alternative and was refused: the eight deliberately
 * avoid green / blue / amber / red so a category is never mistaken for a status, and sixteen hues
 * that dodge those four, stay apart from each other AND survive dark mode do not exist.
 */

export const TYPE_LABELS: Record<string, string> = {
  university: 'Universiti',
  ua: 'Universiti',
  asasi: 'Universiti',
  pismp: 'PISMP',
  poly: 'Politeknik',
  iljtm: 'ILJTM',
  ilkbs: 'ILKBS',
  kkom: 'Kolej Komuniti',
  matric: 'Matrikulasi',
  stpm: 'Tingkatan 6',
}

/** Institution type → its category swatch number. Eight types, eight distinct numbers.
 *  Keys are lower-case; `institutionTypeChip` folds case, because the API spells the training
 *  institutes `ILJTM`/`ILKBS` on one payload and `iljtm`/`ilkbs` on another. */
const TYPE_SWATCH: Record<string, number> = {
  university: 1,
  ua: 1,
  asasi: 1,
  poly: 2,
  ilkbs: 3,
  matric: 4,
  kkom: 5,
  iljtm: 6,
  pismp: 7,
  stpm: 8,
}

/** Complete literal class names, one per swatch, INDEXED rather than assembled.
 *  ⚠ Tailwind's JIT scanner reads source text, so `` `bg-category-${n}-surface` `` would compile,
 *  render, and ship with no styles at all — the exact trap `applicationStatus.ts` warns about.
 *  Writing the eight out and looking one up by number is what keeps the scanner able to see them. */
const TYPE_CHIP_CLASSES = [
  'bg-category-1-surface text-category-1-ink',
  'bg-category-2-surface text-category-2-ink',
  'bg-category-3-surface text-category-3-ink',
  'bg-category-4-surface text-category-4-ink',
  'bg-category-5-surface text-category-5-ink',
  'bg-category-6-surface text-category-6-ink',
  'bg-category-7-surface text-category-7-ink',
  'bg-category-8-surface text-category-8-ink',
] as const

/** The chip a course card, course header or requirements card paints an institution type with.
 *  An unknown type falls back to the ground, which is what it has always done. */
export function institutionTypeChip(type: string | null | undefined): string {
  const n = TYPE_SWATCH[String(type || '').toLowerCase()]
  return n ? TYPE_CHIP_CLASSES[n - 1] : 'bg-ground-100 text-ground-700'
}

/** One class for EVERY qualification level — see the header. Not a lookup table, because a
 *  lookup table whose values are all equal is a trap for the next reader. */
export const LEVEL_CHIP = 'bg-ground-100 text-ground-700'
