/** THE ONE PLACE A CONSOLE PAGE'S WIDTH IS DECIDED (owner, 2026-09-08).
 *
 *  Before this, all thirty-five admin pages wrote their own limit and there were EIGHT different
 *  answers — `max-w-4xl` on Organisation, full-bleed on Reviewers, `max-w-5xl` on Sources, and so
 *  on. Two pages one click apart started their text in different places, and one page (the B40
 *  application cockpit) centred itself, which nothing else in the console did.
 *
 *  ⚠ THE WIDTH IS APPLIED BY THE SHELL, NOT BY THE PAGE. `AppShell` reads this map and wraps
 *  `children`. A page therefore CANNOT invent a ninth answer by writing its own `max-w-*` on its
 *  root — and `pageWidth.test.ts` fails if one tries. That is the whole point: a rule a page has to
 *  remember is a rule that drifts, and this one already had.
 *
 *  ── The rule (owner's words) ────────────────────────────────────────────────────────────────
 *  **Does the page lead with a TABLE?** Wide. Otherwise reading. Both start at the same left edge.
 *
 *  'reading' — forms, settings, detail pages. ~900px, the width long text stays readable at.
 *  'wide'    — pages whose first job is a table of many columns. 1280px.
 *
 *  Neither is centred. On a very wide monitor a reading page does leave space on the right; that
 *  reads as deliberate when every page does it and as a mistake when one page does.
 */
export type PageWidth = 'reading' | 'wide'

/** Tailwind classes per kind. `mx-auto` appears in NEITHER — see the module note. */
export const WIDTH_CLASS: Record<PageWidth, string> = {
  reading: 'max-w-4xl',   // 56rem / 896px
  wide: 'max-w-7xl',      // 80rem / 1280px
}

/** Routes whose first job is a TABLE. Longest match wins, so a detail page below a wide list
 *  (`/admin/payments/[id]`) can still be a reading page by being listed in READING_ROUTES. */
export const WIDE_ROUTES: readonly string[] = [
  '/admin/scholarship',              // Applications
  '/admin/organisation/reviewers',
  '/admin/organisation/staff',
  '/admin/organisation/programmes',  // gift list + intake years
  '/admin/programme/years',
  '/admin/sources',
  '/admin/sponsors',
  '/admin/students',
  '/admin/payments',
  '/admin/billing',
  '/admin/contracts',
  '/admin/course-data',
  '/admin/organisations',
  '/admin/partners',
  '/admin/administration',
]

/** Routes BELOW a wide route that are detail pages, not tables — they win by being longer. */
export const READING_ROUTES: readonly string[] = [
  '/admin/scholarship/',             // one application (the cockpit)
  '/admin/payments/',                // one payment run
  '/admin/sponsors/',                // one sponsor
  '/admin/students/',                // one student
  '/admin/contracts/',               // one contract template
  '/admin/organisation/reviewers/',  // one reviewer
]

/** The width for a pathname. Unlisted → 'reading', which is the safe default: a page that is
 *  mostly words is never harmed by being narrower, whereas a table given too little room is. */
export function pageWidthFor(pathname: string): PageWidth {
  const path = (pathname || '').replace(/\/+$/, '') || '/'
  // A reading route only wins when something FOLLOWS the prefix — '/admin/payments/' must not
  // match the list at '/admin/payments'.
  const readingMatch = READING_ROUTES
    .filter((r) => path.startsWith(r) && path.length > r.length)
    .sort((a, b) => b.length - a.length)[0]
  const wideMatch = WIDE_ROUTES
    .filter((r) => path === r || path.startsWith(`${r}/`))
    .sort((a, b) => b.length - a.length)[0]
  if (readingMatch && (!wideMatch || readingMatch.length >= wideMatch.length)) return 'reading'
  return wideMatch ? 'wide' : 'reading'
}
