/**
 * THE ONE BUMIPUTERA RULE in the browser (Bumi coverage Sprint B, owner ruling 2026-10-28).
 *
 * The answer is COURSE-GUIDE ONLY: it unlocks Bumiputera-only courses (UiTM, MARA) in the
 * eligibility check and the course searches, and nothing else reads it. A foreign student is
 * never Bumi, and an unanswered question (null / absent) reads as "no". The server applies the
 * same rule again (`resolve_bumiputera`), so this is the honest half, not the guarantee.
 */

interface Demographics {
  nationality?: string | null
  bumiputera?: boolean | null
}

/** Foreign only when the profile says so; the app's default nationality is Malaysian. */
export function isMalaysian(nationality: string | null | undefined): boolean {
  return nationality !== 'non_malaysian' && nationality !== 'Bukan Warganegara'
}

/** True only for a Malaysian who answered yes. */
export function isBumiputera(p: Demographics | null | undefined): boolean {
  return !!p && p.bumiputera === true && isMalaysian(p.nationality)
}
