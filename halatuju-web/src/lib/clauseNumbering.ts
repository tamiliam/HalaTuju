// Contract clause numbering — MIRROR of `contracts.clause_numbers` / `contracts.normalise_levels`
// in the Django backend (apps/scholarship/contracts.py). The two must stay in lockstep; the paired
// test (`__tests__/clauseNumbering.test.ts`) checks a shared fixture. 3 levels:
//   0 -> "1.", "2."   1 -> "1.1", "1.2"   2 -> "i)", "ii)" (lowercase roman)

export const MAX_CLAUSE_LEVEL = 2

function roman(n: number): string {
  const map: Array<[number, string]> = [[10, 'x'], [9, 'ix'], [5, 'v'], [4, 'iv'], [1, 'i']]
  let out = ''
  for (const [v, s] of map) { while (n >= v) { out += s; n -= v } }
  return out
}

/** Clamp each level to 0..MAX and forbid SKIPPING: a clause may be at most one level deeper than
 *  the one before it (the first is forced to 0); going shallower is unrestricted. */
export function normaliseLevels(levels: number[]): number[] {
  const out: number[] = []
  let prev = -1
  for (const raw of levels) {
    let lv = Math.max(0, Math.min(MAX_CLAUSE_LEVEL, Math.trunc(Number(raw) || 0)))
    if (lv > prev + 1) lv = prev + 1
    out.push(lv)
    prev = lv
  }
  return out
}

/** Display label per clause from its level run. Assumes levels are already valid (normaliseLevels). */
export function clauseNumbers(levels: number[]): string[] {
  const counters = [0, 0, 0]
  return levels.map((raw) => {
    const lv = Math.max(0, Math.min(MAX_CLAUSE_LEVEL, Math.trunc(Number(raw) || 0)))
    counters[lv] += 1
    for (let d = lv + 1; d <= MAX_CLAUSE_LEVEL; d += 1) counters[d] = 0
    if (lv === 0) return `${counters[0]}.`
    if (lv === 1) return `${counters[0]}.${counters[1]}`
    return `${roman(counters[2])})`
  })
}

/** Can a clause at index i be indented one level deeper? Only if it wouldn't skip (i.e. its target
 *  level ≤ previous clause's level + 1) and it's below the max depth. */
export function canIndent(levels: number[], i: number): boolean {
  if (i <= 0) return false
  const target = levels[i] + 1
  return target <= MAX_CLAUSE_LEVEL && target <= levels[i - 1] + 1
}

export function canOutdent(levels: number[], i: number): boolean {
  return levels[i] > 0
}
