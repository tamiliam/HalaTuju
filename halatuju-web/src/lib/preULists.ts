/**
 * The "Pre-U institution" FIELD's own helpers (pre-U sprint, 2026-11-26): the route chips, which
 * chip opens first, and the lists. Imported only by `PreUStudiedAtField`, which arrives on demand
 * (`LazyPreUStudiedAtField`).
 *
 * ⚠ Kept apart from `lib/preUStudiedAt.ts` on purpose. That module holds the two small rules the
 * apply page and `lib/scholarship.ts` need at first load; webpack decides which exports a module
 * keeps across the WHOLE app, not per chunk, so anything the field uses that lived there rode in
 * `/scholarship/apply`'s first-load JS and pushed it over its budget.
 */
export type PreURoute = 'form6' | 'matric' | 'university' | 'poly'
export const PRE_U_ROUTES: PreURoute[] = ['form6', 'matric', 'university', 'poly']

/** The chip that opens first, from the results they hold. */
export function firstPreURoute(resultsHeld: unknown): PreURoute {
  if (resultsHeld === 'matric') return 'matric'
  if (resultsHeld === 'asasi') return 'university'
  if (resultsHeld === 'diploma') return 'poly'
  return 'form6'
}

export interface PreUOption { name: string; hint?: string; keywords?: string }
export type PreULists = Record<PreURoute, PreUOption[]>

/**
 * The four lists, fetched when the field is drawn (never in a route's first-load JS: the Form 6
 * list alone is ~15 kB gz — the `LazyStpmSchoolPicker` reason). The specifiers are LITERALS so the
 * bundler emits real chunks.
 */
export async function loadPreULists(): Promise<PreULists> {
  const [f6, km, uni, poly] = await Promise.all([
    import(/* webpackChunkName: 'sp' */ '@/data/stpm-schools'),
    import(/* webpackChunkName: 'sp' */ '@/data/matric-colleges'),
    import(/* webpackChunkName: 'pu' */ '@/data/pre-u-universities'),
    import(/* webpackChunkName: 'pu' */ '@/data/polytechnics'),
  ])
  return {
    form6: f6.STPM_SCHOOLS.map((s) => ({ name: s.name, hint: s.state })),
    matric: km.MATRIC_COLLEGES.map((c) => ({ name: c.name, hint: c.state })),
    university: uni.PRE_U_UNIVERSITIES.map((u) => ({ name: u.name, hint: u.hint, keywords: u.keywords })),
    poly: poly.POLYTECHNICS.map((p) => ({ name: p.name, hint: p.hint })),
  }
}
