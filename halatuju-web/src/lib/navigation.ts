/**
 * The admin console's route registry and the ONE role predicate behind it.
 *
 * Pure: no React, no next/navigation, no fetch — node-testable exactly like `adminLanding.ts`.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THIS IS NOT THE SECURITY FENCE.
 * ─────────────────────────────────────────────────────────────────────────────
 * Hiding a link has never been access control. The fence is server-side:
 * `_AdminBase._org_scoped` / `_org_allows` in `apps/scholarship/views_admin.py`, plus the
 * per-endpoint role gates, plus each page's own guard. A user who types a URL still gets
 * that page's 403 and the endpoint still 404s cross-org. This registry only decides what is
 * worth SHOWING. The 2026-07-15 surface-partition sprint exists because the two were once
 * confused — `apps/courses/models.py` (PartnerAdmin docstring): "nav hid it, backend didn't".
 *
 * KEEP-IN-SYNC PAIR: `NavItem.roles` mirrors the authority in
 * `docs/scholarship/role-matrix.md` and `PartnerAdmin.ROLE_CHOICES`
 * (`halatuju_api/apps/courses/models.py`). A role's powers change in the matrix FIRST, then
 * here, then in the page guard — all in one commit. `navigation.test.ts` pins the role sets
 * as a snapshot so a change has to be deliberate.
 */

/** The scope a page belongs to. Platform → Organisation → Programme is the platform hierarchy
 *  (`apps/scholarship/models.py` Programme docstring); `utility` is "yours, not any scope's". */
export type NavScope = 'platform' | 'organisation' | 'programme' | 'utility'

/** Scopes the sidebar renders as groups (N2). `utility` lives in the help/account menus. */
export const SIDEBAR_SCOPES: readonly NavScope[] = ['platform', 'organisation', 'programme']

/** Mirrors PartnerAdmin.ROLE_CHOICES (halatuju_api/apps/courses/models.py). */
export type AdminRoleName =
  | 'super' | 'admin' | 'org_admin' | 'partner' | 'reviewer' | 'qc' | 'finance'

export const ROLE_NAMES: readonly AdminRoleName[] =
  ['super', 'admin', 'org_admin', 'partner', 'reviewer', 'qc', 'finance']

/** Dark-shipped features. One key per probe the shell runs; see `NavGate`. */
export type ProbeKey = 'requests' | 'billing'

/**
 * Counts the sidebar may render on an item, and the bell may repeat.
 *
 * A UNION rather than a second hardcoded prop (TD-205): the shell used to thread
 * `pendingSponsors: number` through three components and test `i.badge === 'pendingSponsors'` at
 * the render site, so a second badge meant a fourth place to remember. The shell now passes one
 * `Partial<Record<BadgeKey, number>>` and the row looks its own key up.
 */
export type BadgeKey = 'pendingSponsors' | 'requestsWaiting'
/** 'unknown' = not yet loaded, 'dark' = the endpoint 404d (flag off), 'live' = it answered. */
export type ProbeState = 'unknown' | 'live' | 'dark'

export type NavGate =
  | { mode: 'always' }
  /**
   * Dark-shipped: availability is inferred from the API answering, never from a client flag
   * (`REQUESTS_ENABLED` / `BILLING_USAGE_ENABLED` stay server-side env vars). `dark` says how
   * to render while not-live — 'hide' reproduces today's hidden Requests card, 'soon' the
   * disabled "Coming soon" Billing card (`admin/administration/page.tsx`).
   */
  | { mode: 'probe'; probe: ProbeKey; dark: 'hide' | 'soon' }

export interface NavItem {
  /** Stable id — the snapshot key and the ⌘K palette key. Never derived from the href. */
  id: string
  href: string
  /** Full i18n key. Must resolve in en/ms/ta or `scripts/check-i18n.js` fails the build. */
  labelKey: string
  scope: NavScope
  /** UX visibility only — see the module docstring. */
  roles: readonly AdminRoleName[]
  gate: NavGate
  /** Extra path prefixes that make this item the active one (sub-pages with no entry). */
  match?: readonly string[]
  /**
   * Match this href EXACTLY, never as a prefix. Set on the index route `/admin`, which is a
   * page rather than a section: its siblings are separate routes, not its children. Without
   * this, `/admin` prefixes every admin path, so an unrecognised route would resolve to the
   * dashboard and silently inherit ITS roles — inventing a block the registry never declared.
   */
  exact?: boolean
  badge?: BadgeKey
  /**
   * The second key of the `G`-then-X jump, upper-case, e.g. 'A' → Applications.
   *
   * OPTIONAL on purpose, inverting the usual "make a new dimension required" rule: most routes
   * will never earn a chord, and a required field would force a fake letter onto every one of
   * them. The guard is a test instead — `navigation.test.ts` asserts the letters are unique
   * across the WHOLE registry, single upper-case characters, and never on a placeholder.
   *
   * Uniqueness is global rather than per-role deliberately. Two roles seeing different pages
   * under one letter would make the sidebar's own hint wrong for somebody, and "what does G T
   * do" must have exactly one answer.
   */
  chord?: string
  /**
   * A reserved slot: the sidebar renders it disabled with a "soon" pill and it links nowhere.
   * These are the empty slots the programme-layer roadmap asks the shell to ship with (risk #6,
   * "each extraction sprint fills one — no second redesign"), so a later sprint fills a slot
   * rather than re-cutting the menu. A placeholder has no page, and the route-drift test knows
   * not to look for one.
   */
  placeholder?: boolean
}

export interface NavGroup {
  scope: NavScope
  headingKey: string
  items: readonly NavItem[]
}

/**
 * Every route in the console, grouped by scope.
 *
 * Role sets reproduce the guards that exist on the pages themselves:
 *   payments  super/admin/org_admin/finance  (payments/page.tsx `allowed`)
 *   contracts super/org_admin                (contracts/page.tsx `allowed`)
 *   sources   super/org_admin/admin          (sources/page.tsx `canManage`)
 *   billing   super/org_admin                (billing/page.tsx)
 * `sponsors` and `requests` have NO client guard — they rely on the backend alone. Their role
 * sets here drive menu visibility only and add no client-side block.
 *
 * Items marked `placeholder` are the roadmap's reserved slots: they render disabled with a
 * "soon" pill and have no page behind them yet.
 */
export const NAV_GROUPS: readonly NavGroup[] = [
  {
    scope: 'platform',
    headingKey: 'admin.nav.group.platform',
    items: [
      // The platform base — the student account and the course selector. Super-only since the
      // surface-partition sprint (2026-07-15); `partner` is a referral-org rep, whose two pages
      // are platform pages, not any organisation's.
      { id: 'overview', href: '/admin', labelKey: 'common.dashboard', chord: 'D',
        scope: 'platform', roles: ['super', 'partner'], gate: { mode: 'always' },
        exact: true },
      { id: 'students', href: '/admin/students', labelKey: 'admin.students', chord: 'S',
        scope: 'platform', roles: ['super', 'partner'], gate: { mode: 'always' } },
      { id: 'courseData', href: '/admin/course-data', labelKey: 'admin.courseData.nav', chord: 'C',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' } },
      // Lifted out of the Administration hub in N3b. Creating a tenant and appointing its
      // org_admin are withheld from every ORGANISATION role (role matrix), so both are super.
      { id: 'organisations', href: '/admin/organisations', labelKey: 'admin.nav.organisations', chord: 'O',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' } },
      // A referral org is an attribution relationship, never an access scope — which is why it
      // sits in the PLATFORM scope rather than inside any organisation.
      { id: 'referralPartners', href: '/admin/partners', chord: 'R',
        labelKey: 'admin.nav.referralPartners',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' } },
      // Reserved. `billing_rates` shipped 2026-07-27 (super-only, 403 for org_admin — the margin
      // applied to a tenant is a commercial disclosure) but has no page yet.
      { id: 'billingRates', href: '/admin/billing-rates', labelKey: 'admin.nav.billingRates',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' }, placeholder: true },
    ],
  },
  {
    scope: 'organisation',
    headingKey: 'admin.nav.group.organisation',
    items: [
      // The security fence: staff, sponsors, money out, contracts, billing.
      // The old Administration hub is now this overview. `match` keeps the retired hub route
      // (a permanent redirect) highlighting here, so an old bookmark still lights the right row.
      // `exact` because /admin/organisation is a page, not a section — /admin/organisation/staff
      // is its sibling in the menu, not its child.
      { id: 'administration', href: '/admin/organisation', labelKey: 'admin.orgPage.nav', chord: 'V',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' }, exact: true, match: ['/admin/administration'] },
      // Renamed "Staff" → "Invitations" on 2026-08-03: reviewers moved to their own page in
      // request #10, and what is left is the asking. The ROUTE is unchanged deliberately — every
      // bookmark, the `/admin/invite` redirect and the highlight rules keep working; only the
      // label and the page moved.
      { id: 'staff', href: '/admin/organisation/staff', labelKey: 'admin.nav.invitations', chord: 'T',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' }, match: ['/admin/invite'] },
      // Sibling of Staff, and deliberately next to it: Staff invites and revokes, Reviewers is
      // where you LOOK at somebody. Same four roles, because Staff already shows all four who the
      // reviewers are. Organisation scope, not programme — a `PartnerAdmin` belongs to a tenant and
      // has no programme field at all (request #10, 2026-08-02).
      { id: 'reviewers', href: '/admin/organisation/reviewers', labelKey: 'admin.nav.reviewers',
        chord: 'E', scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' } },
      // Sabah S2b: the gifts this organisation runs, and where a new one is created. ORGANISATION
      // scope on purpose — creating a gift is an organisation-level act, and the Programme group is
      // for working INSIDE one gift. super + org_admin only: the endpoint refuses every other role.
      { id: 'programmes', href: '/admin/organisation/programmes', labelKey: 'admin.programmes.nav',
        scope: 'organisation', roles: ['super', 'org_admin'], gate: { mode: 'always' } },
      { id: 'sponsors', href: '/admin/sponsors', labelKey: 'admin.sponsors.nav', chord: 'P',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' }, badge: 'pendingSponsors' },
      { id: 'sources', href: '/admin/sources', labelKey: 'admin.sources.nav', chord: 'U',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin'], gate: { mode: 'always' } },
      { id: 'payments', href: '/admin/payments', labelKey: 'admin.payments.title', chord: 'Y',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' } },
      { id: 'contracts', href: '/admin/contracts', labelKey: 'admin.contracts.title', chord: 'K',
        scope: 'organisation', roles: ['super', 'org_admin'], gate: { mode: 'always' } },
      { id: 'billing', href: '/admin/billing', labelKey: 'admin.billing.title', chord: 'B',
        scope: 'organisation', roles: ['super', 'org_admin'],
        gate: { mode: 'probe', probe: 'billing', dark: 'soon' } },
      { id: 'requests', href: '/admin/requests', labelKey: 'admin.requests.nav', chord: 'Q',
        scope: 'organisation', roles: ['super', 'org_admin'],
        gate: { mode: 'probe', probe: 'requests', dark: 'hide' },
        badge: 'requestsWaiting' },
    ],
  },
  {
    scope: 'programme',
    headingKey: 'admin.nav.group.programme',
    items: [
      // The gift itself. `finance` is absent deliberately: it has no B40 scope at all
      // (`_b40_scope` -> 'none'), so an Applications link would only ever 403.
      // Layer 0 Sprint 5 (2026-08-30): the reserved "Overview" slot became the configuration
      // screen — what the programme ASKS FOR (documents + questions), Off / Optional / Required.
      // super + org_admin only: the page's endpoint refuses every other role, and a menu row that
      // opens a 403 is worse than no row. ⚠ Visibility only — the fence is the endpoint.
      { id: 'programmeConfig', href: '/admin/programme', labelKey: 'admin.programme.config.nav',
        chord: 'W', scope: 'programme', roles: ['super', 'org_admin'], gate: { mode: 'always' },
        exact: true },
      { id: 'applications', href: '/admin/scholarship', labelKey: 'admin.scholarship.nav', chord: 'A',
        scope: 'programme', roles: ['super', 'org_admin', 'admin', 'qc', 'reviewer'],
        gate: { mode: 'always' } },
      // Reserved slots the programme-layer roadmap owes: reviewer assignment/scoping, the intake
      // years beneath the gift, the fund, and the rules that currently live on the cohort.
      // ⚠ RENAMED, not repurposed (2026-08-02). This slot is SCOPING — binding a reviewer to one
      // programme — which is a different page from the Organisation → Reviewers directory that now
      // exists. It kept the label "Reviewers" until that directory shipped, at which point the
      // sidebar said Reviewers twice. The slot itself is untouched and stays reserved: scoping is
      // meaningless while there is one programme (owner, 2026-08-02).
      { id: 'reviewerScoping', href: '/admin/programme/reviewers',
        labelKey: 'admin.nav.reviewerScoping',
        scope: 'programme', roles: ['super', 'org_admin'],
        gate: { mode: 'always' }, placeholder: true },
      // Sabah S2b — the reserved slot is now the screen. One round of students per year beneath a
      // gift that never lapses; creating a year does NOT open it.
      { id: 'years', href: '/admin/programme/years', labelKey: 'admin.nav.years',
        scope: 'programme', roles: ['super', 'org_admin'],
        gate: { mode: 'always' } },
      { id: 'fund', href: '/admin/programme/fund', labelKey: 'admin.nav.fund',
        scope: 'programme', roles: ['super', 'org_admin', 'finance'],
        gate: { mode: 'always' }, placeholder: true },
      { id: 'rules', href: '/admin/programme/rules', labelKey: 'admin.nav.rules',
        scope: 'programme', roles: ['super', 'org_admin'],
        gate: { mode: 'always' }, placeholder: true },
    ],
  },
  {
    scope: 'utility',
    headingKey: 'admin.nav.group.utility',
    items: [
      // Yours, not any scope's — the sidebar skips this group (SIDEBAR_SCOPES) and the account
      // and help menus render it instead.
      { id: 'profile', href: '/admin/profile', labelKey: 'admin.profile',
        scope: 'utility', roles: ROLE_NAMES, gate: { mode: 'always' } },
      { id: 'guide', href: '/admin/guide', labelKey: 'admin.guideNav',
        scope: 'utility', roles: ['super', 'admin', 'org_admin', 'reviewer', 'qc', 'finance'],
        gate: { mode: 'always' } },
      { id: 'faq', href: '/admin/faq', labelKey: 'admin.faqNav',
        scope: 'utility', roles: ['super', 'admin', 'org_admin', 'reviewer', 'qc', 'finance'],
        gate: { mode: 'always' } },
    ],
  },
]

/** Flat view of the registry. */
export const NAV_ITEMS: readonly NavItem[] = NAV_GROUPS.flatMap((g) => g.items)

/** Routes that render WITHOUT the admin chrome (login / OAuth callback / set-password). */
export const CHROMELESS: readonly string[] = [
  '/admin/login', '/admin/auth/', '/admin/set-password',
]

export interface NavContext {
  role: AdminRoleName
  probes: Record<ProbeKey, ProbeState>
}

/** A context with nothing probed yet — the safe default (see `canSee`). */
export const NO_PROBES: Record<ProbeKey, ProbeState> = { requests: 'unknown', billing: 'unknown' }

/**
 * THE one place `is_super_admin ? 'super' : role` lives. It was written out eleven times
 * across the layout and the admin pages before this.
 *
 * Falls back to 'reviewer' for an unknown/missing role, preserving the previous behaviour of
 * `admin/layout.tsx` — the least-privileged role, so a payload we don't understand shows the
 * smallest menu rather than the largest.
 */
export function effectiveRole(
  role: { role?: string; is_super_admin?: boolean } | null | undefined,
): AdminRoleName {
  if (!role) return 'reviewer'
  if (role.is_super_admin || role.role === 'super') return 'super'
  return (ROLE_NAMES as readonly string[]).includes(role.role ?? '')
    ? (role.role as AdminRoleName)
    : 'reviewer'
}

/**
 * Visibility of ONE item.
 *
 * Probe semantics are exact: 'unknown' (not yet loaded) and 'dark' (404) BOTH mean not-live,
 * matching today's comment in `admin/administration/page.tsx` — "null = dark OR not yet
 * loaded". Treating 'unknown' as live would flash a dark feature in during the round trip.
 */
export function canSee(item: NavItem, ctx: NavContext): 'show' | 'soon' | 'hide' {
  if (!item.roles.includes(ctx.role)) return 'hide'
  if (item.gate.mode === 'probe') {
    return ctx.probes[item.gate.probe] === 'live' ? 'show' : item.gate.dark
  }
  return 'show'
}

export interface VisibleNavItem extends NavItem { state: 'show' | 'soon' }
export interface VisibleNavGroup extends Omit<NavGroup, 'items'> { items: VisibleNavItem[] }

/** Groups → the items this context may see, with empty groups dropped. */
export function visibleNav(ctx: NavContext): VisibleNavGroup[] {
  return NAV_GROUPS
    .map((g) => ({
      ...g,
      items: g.items
        .map((i) => ({ ...i, state: canSee(i, ctx) }))
        .filter((i): i is VisibleNavItem => i.state !== 'hide'),
    }))
    .filter((g) => g.items.length > 0)
}

/** True when `pathname` is `href` or sits underneath it. The boundary matters: without the
 *  trailing slash, '/admin/scholarshipX' would match '/admin/scholarship'. */
function under(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + '/')
}

/**
 * The registry item a path belongs to, by LONGEST match.
 *
 * Longest-match is load-bearing, not a nicety: '/admin' is a prefix of every admin route, so
 * a first-match implementation would resolve everything to the dashboard. Each href and each
 * `match` prefix is asserted individually in the tests.
 *
 * This replaces the hand-written `isActive` in `admin/layout.tsx`, which special-cased three
 * routes and forgot three others — `/admin/requests`, `/admin/sources` and `/admin/billing`
 * highlighted nothing at all.
 */
export function activeItem(pathname: string): NavItem | undefined {
  let best: NavItem | undefined
  let bestLen = -1
  for (const item of NAV_ITEMS) {
    // A reserved slot has no page, so nothing can be "inside" it.
    if (item.placeholder) continue
    for (const href of [item.href, ...(item.match ?? [])]) {
      const hit = item.exact ? pathname === href : under(pathname, href)
      if (hit && href.length > bestLen) {
        best = item
        bestLen = href.length
      }
    }
  }
  return best
}

/**
 * May this role open this route at all? Replaces the `isSuper` / `allowed` / `canManage`
 * expression each admin page derived for itself.
 *
 * Route-level only. Anything finer than "can you open the page" — `canCreate` on Payments,
 * `canManage` on Administration, `canWrite` / `canQc` / `canAssign` in `officerCockpit.ts` —
 * stays where it is. This registry is not a permission engine.
 *
 * An unknown route returns true: absence from the registry must never invent a new block.
 */
export function canAccess(href: string, role: AdminRoleName): boolean {
  const item = activeItem(href)
  return item ? item.roles.includes(role) : true
}

/** An item paired with its already-translated label, which is all the palette needs. */
export interface LabelledNavItem { item: NavItem; label: string }

/**
 * Rank navigable items for the ⌘K palette.
 *
 * Deliberately not a fuzzy-search dependency: there are ~20 reachable routes, and the ranking
 * that matters is "the word I typed starts this label" over "it appears somewhere in it".
 * Order: label starts with the query, then a word inside it starts with the query, then any
 * substring. Ties keep registry order, so a blank query lists the menu as the sidebar shows it.
 *
 * Reserved slots are excluded — offering to navigate somewhere that does not exist is worse
 * than not offering it.
 */
export function searchNav(query: string, items: readonly LabelledNavItem[]): NavItem[] {
  const q = query.trim().toLowerCase()
  const live = items.filter(({ item }) => !item.placeholder)
  if (!q) return live.map(({ item }) => item)

  const rank = ({ label }: LabelledNavItem): number => {
    const l = label.toLowerCase()
    if (l.startsWith(q)) return 0
    if (l.split(/\s+/).some((w) => w.startsWith(q))) return 1
    return l.includes(q) ? 2 : -1
  }

  return live
    .map((entry, i) => ({ entry, r: rank(entry), i }))
    .filter((x) => x.r >= 0)
    .sort((a, b) => (a.r - b.r) || (a.i - b.i))
    .map((x) => x.entry.item)
}

/** The first key of the jump. Held here so the listener, the hint chip and the tests agree. */
export const CHORD_PREFIX = 'g'

/**
 * The route a `G`-then-X jump should open, or undefined if that letter goes nowhere.
 *
 * Resolved against the VISIBLE groups rather than the whole registry, so a chord can never
 * carry someone to a page their sidebar does not offer. That is a courtesy, not a fence — the
 * page's own guard and the endpoint still refuse them (see the module docstring) — but a
 * shortcut that lands on a 403 is a worse experience than one that does nothing.
 *
 * A reserved slot is skipped for the same reason `searchNav` skips it: there is no page there.
 */
export function chordTarget(
  letter: string,
  groups: readonly VisibleNavGroup[],
): VisibleNavItem | undefined {
  const want = letter.toUpperCase()
  for (const group of groups) {
    for (const item of group.items) {
      if (item.placeholder || item.state !== 'show') continue
      if (item.chord === want) return item
    }
  }
  return undefined
}

/**
 * Where an authenticated admin lands after sign-in. `adminLanding()` delegates here, so the
 * rule has one home; the outputs are IDENTICAL to the previous implementation and its tests
 * pass unmodified.
 *
 * ⚠ Deliberately NOT `canAccess('/admin', r) ? … : …`, which reads better and is wrong: it
 * would send admin / org_admin / qc / finance straight to `/admin/scholarship`, whereas today
 * they land on `/admin` and are bounced by the page. Same destination, one hop fewer — but
 * that is a behaviour change, and this sprint ships the shell, not a new landing rule. The
 * double hop is worth removing later; it is not worth smuggling in here.
 */
export function defaultRoute(role: { role?: string; is_super_admin?: boolean } | null | undefined,
                             reviewerProfileComplete?: boolean): string {
  // A newly-invited reviewer is held on their profile until the compulsory fields are filled.
  // Checked as `=== false` so an OLD payload that omits the field never traps anyone.
  if (role?.role === 'reviewer' && reviewerProfileComplete === false) return '/admin/profile'
  // 'viewer' is a legacy value that is not a real role; it lands where a reviewer does.
  if (role?.role === 'reviewer' || role?.role === 'viewer') return '/admin/scholarship'
  return '/admin'
}
