/**
 * Every route, classed for the phone (Mobile M0, 2026-10-31). The rules are in
 * `docs/mobile-standard.md`; the ledger `docs/mobile-ledger.md` is GENERATED from this file and the
 * browser baseline by `npm run mobile-ledger` — edit here, never there.
 *
 * The owner's rule: if we show it on a phone it must be perfect; if the work is desktop-only, do not
 * offer it on a phone (or reorganise it for the phone). So every `page.tsx` is one of:
 *
 *   - `must`    — students, sponsors, and the everyday screens of reviewers and org admins. Held to
 *                 every rule of the standard at 360–430 px, in English, Malay and Tamil.
 *   - `can`     — the rest of the admin console (lists and detail pages). Must work on a phone with
 *                 no sideways scroll and no zoom; a denser layout is acceptable.
 *   - `desktop` — work nobody should do on a phone. Below `md` these show the shared "works best on
 *                 a computer" panel (built in M7). Every one carries `why`, and the type will not
 *                 compile without it: a screen is desktop-only because somebody wrote the reason.
 *
 * `mobileStandard.test.ts` holds this as a CLOSED set against the `page.tsx` files on disk: a new
 * page with no entry fails, and so does an entry whose page has gone.
 *
 * Plain data and one pure function, nothing imported: `mobile-check/ledger.mjs` loads this file
 * straight into Node (type stripping), so it must stay free of enums, imports and other syntax
 * that is not simply erased.
 */

export type MobileClass = 'must' | 'can' | 'desktop'

/** The roadmap sprint (`docs/plans/2026-10-31-mobile-native-roadmap.md`) that fixes or gates it. */
export type MobileSprint = 'M1' | 'M2' | 'M3' | 'M4' | 'M5' | 'M6' | 'M7' | 'M8'

interface EntryBase {
  sprint: MobileSprint
  /** A redirect-only page: it draws nothing of its own and sends the visitor here. */
  redirect?: string
  /**
   * The URL `npm run mobile-check` opens for this route as an ANONYMOUS visitor. Only routes a
   * stranger can reach have one; the check never signs in. A dynamic route names one real id.
   */
  visit?: string
  /** Sandbox surfaces (`src/sandbox/surfaces.tsx` slugs) that mount this route's real screen. */
  surfaces?: readonly string[]
}

export type RouteEntry =
  | (EntryBase & { cls: 'must' | 'can' })
  | (EntryBase & { cls: 'desktop'; why: string })

/**
 * The route a `page.tsx` serves, from its path under `src/app/`: route groups such as `(portal)`
 * are dropped, exactly as Next drops them from the URL. `about/page.tsx` → `/about`.
 */
export function routeOfPage(pathUnderApp: string): string {
  const segments = pathUnderApp.split('/').slice(0, -1).filter((s) => !/^\(.*\)$/.test(s))
  return `/${segments.join('/')}`
}

export const MOBILE_CLASS: Record<string, RouteEntry> = {
  // ── Public pages — a stranger can open these, so the browser check measures them ──────────────
  '/': { cls: 'must', sprint: 'M2', visit: '/' },
  '/about': { cls: 'must', sprint: 'M2', visit: '/about' },
  '/contact': { cls: 'must', sprint: 'M1', visit: '/contact' },
  '/cookies': { cls: 'must', sprint: 'M2', visit: '/cookies' },
  '/privacy': { cls: 'must', sprint: 'M2', visit: '/privacy' },
  '/terms': { cls: 'must', sprint: 'M2', visit: '/terms' },
  '/get-started': { cls: 'must', sprint: 'M2', visit: '/get-started' },
  '/login': { cls: 'must', sprint: 'M2', redirect: '/', visit: '/login' },
  '/search': { cls: 'must', sprint: 'M3', visit: '/search' },
  '/stpm/search': {
    cls: 'must', sprint: 'M3', redirect: '/search?qualification=STPM', visit: '/stpm/search',
  },
  // POLY-DIP-019 is Diploma Kejuruteraan Mekanikal at the polytechnics — in every year's catalogue.
  '/course/[id]': { cls: 'must', sprint: 'M3', visit: '/course/POLY-DIP-019' },
  '/stpm/[id]': { cls: 'must', sprint: 'M3' },
  '/scholarship': { cls: 'must', sprint: 'M4', visit: '/scholarship' },
  '/scholarship/apply': {
    cls: 'must', sprint: 'M4', visit: '/scholarship/apply',
    surfaces: ['apply-results', 'apply-results-stpm', 'apply-results-form-six'],
  },
  '/sponsor': { cls: 'must', sprint: 'M5', visit: '/sponsor', surfaces: ['sponsor-landing'] },
  '/sponsor/register': { cls: 'must', sprint: 'M5', visit: '/sponsor/register' },
  '/sponsor/login': { cls: 'must', sprint: 'M5', visit: '/sponsor/login' },
  '/admin/login': { cls: 'must', sprint: 'M6', visit: '/admin/login' },

  // ── Students, signed in ───────────────────────────────────────────────────────────────────────
  '/dashboard': { cls: 'must', sprint: 'M2' },
  '/profile': { cls: 'must', sprint: 'M2' },
  '/settings': { cls: 'must', sprint: 'M2' },
  '/verify-email': { cls: 'must', sprint: 'M2' },
  '/auth/callback': { cls: 'must', sprint: 'M2' },
  '/r/[code]': { cls: 'must', sprint: 'M2', redirect: '/' },
  '/onboarding/exam-type': { cls: 'must', sprint: 'M2' },
  '/onboarding/grades': { cls: 'must', sprint: 'M2' },
  '/onboarding/higher-grades': { cls: 'must', sprint: 'M2' },
  '/onboarding/stpm-grades': { cls: 'must', sprint: 'M2' },
  '/onboarding/profile': { cls: 'must', sprint: 'M2' },
  '/onboarding/ic': { cls: 'must', sprint: 'M2', redirect: '/dashboard' },
  '/saved': { cls: 'must', sprint: 'M3' },
  '/quiz': { cls: 'must', sprint: 'M3' },
  '/stpm/quiz': { cls: 'must', sprint: 'M3' },
  '/pathway/matric': { cls: 'must', sprint: 'M3' },
  '/pathway/stpm': { cls: 'must', sprint: 'M3' },
  '/report/[id]': { cls: 'must', sprint: 'M3' },
  '/scholarship/application': {
    cls: 'must', sprint: 'M4',
    surfaces: ['documents', 'documents-lean', 'application-steps', 'application-steps-lean',
      'action-centre', 'action-centre-clear'],
  },
  '/scholarship/award': { cls: 'must', sprint: 'M4' },
  '/scholarship/bursary': { cls: 'must', sprint: 'M4' },
  '/scholarship/onboarding': { cls: 'must', sprint: 'M4' },
  '/scholarship/in-programme': { cls: 'must', sprint: 'M4', redirect: '/scholarship/bursary' },

  // ── Sponsors, signed in (the portal) and their auth pages ─────────────────────────────────────
  '/sponsor/students': { cls: 'must', sprint: 'M5', surfaces: ['sponsor-browse'] },
  '/sponsor/students/[id]': { cls: 'must', sprint: 'M5' },
  '/sponsor/my-students/[id]': { cls: 'must', sprint: 'M5' },
  '/sponsor/account': { cls: 'must', sprint: 'M5' },
  '/sponsor/terms': { cls: 'must', sprint: 'M5' },
  '/sponsor/trust': { cls: 'must', sprint: 'M5' },
  '/sponsor/[...notFound]': { cls: 'must', sprint: 'M5' },
  '/sponsor/auth/callback': { cls: 'must', sprint: 'M5' },
  '/sponsor/auth/confirm': { cls: 'must', sprint: 'M5' },
  '/sponsor/auth/reset': { cls: 'must', sprint: 'M5' },
  '/sponsor/pool/[id]': { cls: 'must', sprint: 'M5', redirect: '/sponsor/students/[id]' },

  // ── Reviewers and org admins: the everyday screens ────────────────────────────────────────────
  '/admin/set-password': { cls: 'must', sprint: 'M6' },
  '/admin/auth/callback': { cls: 'must', sprint: 'M6' },
  '/admin/profile': { cls: 'must', sprint: 'M6' },
  '/admin/guide': { cls: 'must', sprint: 'M6' },
  '/admin/faq': { cls: 'must', sprint: 'M6' },
  '/admin/programme/overview': { cls: 'must', sprint: 'M6' },
  '/admin/scholarship': { cls: 'must', sprint: 'M6' },
  '/admin/scholarship/[id]': { cls: 'must', sprint: 'M6', surfaces: ['officer-cockpit'] },
  '/admin/organisation': { cls: 'must', sprint: 'M6' },
  '/admin/administration': { cls: 'must', sprint: 'M6', redirect: '/admin/organisation' },
  '/admin/organisation/programmes': { cls: 'must', sprint: 'M6', redirect: '/admin/organisation' },
  '/admin/[...notFound]': { cls: 'must', sprint: 'M6' },

  // ── The rest of the admin console: lists and detail pages ─────────────────────────────────────
  '/admin': { cls: 'can', sprint: 'M7' },
  '/admin/students': { cls: 'can', sprint: 'M7' },
  '/admin/students/[id]': { cls: 'can', sprint: 'M7' },
  '/admin/scholars': { cls: 'can', sprint: 'M7' },
  '/admin/scholars/[id]': { cls: 'can', sprint: 'M7' },
  '/admin/sponsors': { cls: 'can', sprint: 'M7' },
  '/admin/sponsors/[id]': { cls: 'can', sprint: 'M7' },
  '/admin/payments': { cls: 'can', sprint: 'M7' },
  '/admin/payments/[id]': { cls: 'can', sprint: 'M7' },
  '/admin/spending': { cls: 'can', sprint: 'M7' },
  '/admin/sources': { cls: 'can', sprint: 'M7' },
  '/admin/partners': { cls: 'can', sprint: 'M7' },
  '/admin/requests': { cls: 'can', sprint: 'M7' },
  '/admin/requests/[id]': { cls: 'can', sprint: 'M7' },
  '/admin/organisations': { cls: 'can', sprint: 'M7' },
  '/admin/organisation/staff': { cls: 'can', sprint: 'M7' },
  '/admin/organisation/settings': { cls: 'can', sprint: 'M7' },
  '/admin/organisation/reviewers': { cls: 'can', sprint: 'M7' },
  '/admin/organisation/reviewers/[id]': { cls: 'can', sprint: 'M7' },
  '/admin/organisation/reviewers/admins/[id]': { cls: 'can', sprint: 'M7' },
  '/admin/programme': {
    cls: 'can', sprint: 'M7',
    surfaces: ['programme-config', 'programme-config-lean', 'programme-config-two-gifts'],
  },
  '/admin/programme/years': { cls: 'can', sprint: 'M7', redirect: '/admin/programme' },
  '/admin/invite': { cls: 'can', sprint: 'M7', redirect: '/admin/organisation/staff' },

  // ── Desktop-only: gated below `md` with the shared panel in M7 ────────────────────────────────
  '/admin/billing-rates': {
    cls: 'desktop', sprint: 'M7',
    why: 'platform super-admin sets per-service rates in a wide table — rare, and done at a desk',
  },
  '/admin/billing': {
    cls: 'desktop', sprint: 'M7',
    why: 'month-end usage and invoices for an organisation — wide figures checked against records',
  },
  '/admin/course-data': {
    cls: 'desktop', sprint: 'M7',
    why: 'an internal coverage panel for the course catalogue, used by the platform team only',
  },
  '/admin/contracts': {
    cls: 'desktop', sprint: 'M7',
    why: 'contract template versions — authored and compared at a desk, never on a phone',
  },
  '/admin/contracts/[id]': {
    cls: 'desktop', sprint: 'M7',
    why: 'the clause editor: long legal text in three languages, edited side by side',
  },
  '/admin/sponsors/terms/[id]': {
    cls: 'desktop', sprint: 'M7',
    why: 'authoring a sponsor’s terms document — long-form editing, not a phone task',
  },
}
