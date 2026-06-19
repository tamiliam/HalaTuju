// Pure, node-testable helpers for the sponsor "Students" marketplace filters.
// Kept free of React so jest (node env) can unit-test the logic directly.

export interface SponsorPoolLike {
  field: string
  state: string
  academic: string
}

export interface PoolFilter {
  field?: string
  state?: string
  level?: string
}

/** Coarse study level derived from the academic band (e.g. "SPM · 7A 1B" → "SPM"). */
export function levelOf(academic: string): string {
  const a = (academic || '').trim()
  if (a.startsWith('SPM')) return 'SPM'
  if (a.startsWith('STPM')) return 'STPM'
  return ''
}

/** Filter pool cards by field / state / level. An empty filter value means "any". */
export function filterPool<T extends SponsorPoolLike>(rows: T[], f: PoolFilter): T[] {
  return rows.filter(
    (r) =>
      (!f.field || r.field === f.field) &&
      (!f.state || r.state === f.state) &&
      (!f.level || levelOf(r.academic) === f.level),
  )
}

/** Distinct, sorted facet values present in the pool — drives the filter dropdowns. */
export function poolFacets(rows: SponsorPoolLike[]): { fields: string[]; states: string[]; levels: string[] } {
  const uniq = (xs: string[]) => Array.from(new Set(xs.filter(Boolean))).sort()
  return {
    fields: uniq(rows.map((r) => r.field)),
    states: uniq(rows.map((r) => r.state)),
    levels: uniq(rows.map((r) => levelOf(r.academic))),
  }
}
