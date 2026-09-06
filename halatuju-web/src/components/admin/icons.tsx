/**
 * The console's icon set: one flat, single-colour stroke family.
 *
 * Every glyph is drawn in `currentColor`, so an icon takes the colour of the text beside it —
 * grey in a resting sidebar row, brand-coloured when that row is active, red inside a
 * destructive menu item. Nothing here carries a colour of its own.
 *
 * This replaces the emoji the rest of the console uses (owner, 2026-07-27): multicoloured
 * glyphs at 13–16px read as decoration rather than as interface, and they cannot follow a
 * theme — a tenant's brand ramp has no effect on 🎗️. Emoji stay where they already are
 * elsewhere; the shell is the single-colour surface.
 */

const PATHS: Record<string, string> = {
  // platform
  overview: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  students: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  courseData: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z',
  organisations: 'M3 21h18M5 21V7l8-4v18M19 21V11l-6-4M9 9h.01M9 12h.01M9 15h.01M9 18h.01',
  referralPartners: 'M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M16 6l-4-4-4 4M12 2v13',
  billingRates: 'M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8zM7 7h.01',
  // organisation
  administration: 'M3 21h18M4 21V10l8-6 8 6v11M9 21v-6h6v6',
  staff: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  sponsors: 'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1L12 21l7.7-7.7 1.1-1a5.5 5.5 0 0 0 0-7.8z',
  payments: 'M2 5h20v14H2zM2 10h20',
  contracts: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8',
  sources: 'M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7',
  billing: 'M3 3v18h18M7 16v-5M12 16V8M17 16v-3',
  requests: 'M22 12h-6l-2 3h-4l-2-3H2M5.4 5.5L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.4-6.5A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.8 1.5z',
  // Organisation → Settings. Sliders rather than the usual cog: the cog is the universal "system
  // preferences" mark and this screen is the tenant's own choices (its colours, its identity), one
  // level up from Programme → Configuration. Two rows with handles at different positions say
  // "things you set" without claiming to be the machine's settings.
  orgSettings: 'M4 6h10M18 6h2M4 12h2M10 12h10M4 18h10M18 18h2M16 4v4M8 10v4M16 16v4',
  // programme
  // "What we ask for" — a checklist (Layer 0 Sprint 5).
  programmeConfig: 'M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11',
  applications: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8',
  reviewers: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M17 11l2 2 4-4',
  years: 'M3 4h18v18H3zM3 10h18M8 2v4M16 2v4',
  fund: 'M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6',
  rules: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
  // shell furniture
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3',
  help: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01',
  bell: 'M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0',
  guide: 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2zM22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z',
  // FAQ. A speech bubble with a question mark — deliberately NOT `help`'s circled "?", which is
  // the shell's help MENU. The Guide is a book, the FAQ is somebody asking; three neighbours in
  // the utility group that must not read as the same thing.
  faq: 'M21 11.5a8.4 8.4 0 0 1-9 8.4 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.1A8.4 8.4 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5zM10.3 9.3a1.8 1.8 0 0 1 3.5.6c0 1.2-1.8 1.8-1.8 1.8M12 15.5h.01',
  profile: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
  signOut: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  menu: 'M4 6h16M4 12h16M4 18h16',
  // The rail pin. Two panels with the divider parked left (hover-open) or right (pinned open) —
  // a drawing of what the control does, rather than a pushpin, which says "favourite" to most
  // people and is already what a bookmark looks like elsewhere in the console.
  pin: 'M3 4h18v16H3zM9 4v16',
  pinned: 'M3 4h18v16H3zM9 4v16M5.5 8.5h1.5M5.5 12h1.5M5.5 15.5h1.5',
  chevron: 'M6 9l6 6 6-6',
  // ⚠ THE FALLBACK, AND IT STAYS. `Icon` renders this when a name is unknown, so a menu row added
  // without a glyph shows a dot instead of throwing inside the console shell — the right
  // behaviour in production, and the wrong one in development, because it is SILENT.
  //
  // It stayed silent for three days: `orgSettings` shipped on 2026-09-03 with no glyph and `faq`
  // had never had one, and both rendered as this dot until the owner noticed. Nothing failed,
  // because nothing was looking.
  //
  // So the loudness lives in a TEST, not here: `icons.test.ts` asserts every id in the navigation
  // registry has a glyph, deriving the list at runtime rather than restating it — a hand-written
  // list is the thing that falls behind (docs/lessons.md, F6/F7c: a guard is blind to whatever is
  // not in its scope). Do not "fix" this fallback by throwing; fix it by keeping that test.
  dot: 'M12 12h.01',
}

/** Names this set actually draws — the guard in `icons.test.ts` reads it. */
export const ICON_NAMES: readonly string[] = Object.keys(PATHS)

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 16, className }: {
  name: string
  size?: number
  className?: string
}) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d={PATHS[name] ?? PATHS.dot} />
    </svg>
  )
}
