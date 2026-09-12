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
 *  ── The rule ────────────────────────────────────────────────────────────────────────────────
 *  **Does the page lay its content out in MULTIPLE COLUMNS?** Wide. Otherwise reading. Both start
 *  at the same left edge.
 *
 *  ⚠ THIS WAS FIRST WRITTEN AS "does the page lead with a TABLE?", and the owner's review found
 *  the wording too narrow (2026-09-08). A table was only ever the commonest case of the real
 *  question, which is whether the content is laid out ACROSS the page or DOWN it. The B40
 *  application cockpit leads with no table at all — it is twelve two-column cards and a
 *  three-column grid — and at the reading width its addresses wrapped and its grade chips broke
 *  onto three rows. It had been 1152px before this arc; the first rule made it NARROWER than it
 *  had ever been, which is a regression dressed as a standard.
 *
 *  'reading' — one column of prose, form fields or stacked panels. ~900px, where long text stays
 *              readable and a form does not sprawl.
 *  'wide'    — a table of many columns, or a dense card grid. 1280px.
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

/** Routes laid out ACROSS the page. Longest match wins, so a page below a wide list can still
 *  read narrow by being listed in READING_ROUTES — `/admin/students/<id>` is the shape. */
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
  // ⚠ ADDED 2026-09-12, and it should have been here from the day the page shipped. The
  // owner asked why Spending is narrow when Payments beside it is wide: the merchant table
  // is SEVEN columns and was being drawn at the reading width, so the shop names wrapped
  // onto two lines and the last column was cut off the right-hand edge. It is the rule's
  // own central case — content laid out ACROSS the page — and it was simply missed.
  '/admin/spending',
  '/admin/billing',
  '/admin/contracts',
  '/admin/course-data',
  '/admin/organisations',
  '/admin/partners',
  '/admin/administration',
]

/** Routes BELOW a wide route that read DOWN the page rather than across — they win by being
 *  longer. Being a detail page is not the test; the layout is.
 *
 *  ⚠ THREE ROUTES LEFT THIS LIST ON 2026-09-08, after the owner walked the console. Each was here
 *  because it shows ONE of something, which is not the question:
 *    · `/admin/payments/<run>` leads with an EIGHT-column table (name, NRIC, e-wallet, approved,
 *      paid, to be paid, include). It answered the original rule and I overrode it anyway.
 *    · `/admin/scholarship/<id>` is the cockpit — twelve two-column cards and a three-column
 *      grid. No table, and denser than most pages that have one.
 *    · `/admin/sponsors/<id>` carries two tables of its own.
 *  What is left genuinely runs down the page in one column.
 */
export const READING_ROUTES: readonly string[] = [
  '/admin/students/',                // one student — a profile, read downwards
  '/admin/contracts/',               // one contract template — a long document
  '/admin/organisation/reviewers/',  // one reviewer — a profile and a short history
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
