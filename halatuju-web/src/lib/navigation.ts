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
  badge?: 'pendingSponsors'
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
      { id: 'overview', href: '/admin', labelKey: 'common.dashboard',
        scope: 'platform', roles: ['super', 'partner'], gate: { mode: 'always' },
        exact: true },
      { id: 'students', href: '/admin/students', labelKey: 'admin.students',
        scope: 'platform', roles: ['super', 'partner'], gate: { mode: 'always' } },
      { id: 'courseData', href: '/admin/course-data', labelKey: 'admin.courseData.nav',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' } },
      // Reserved. The tenant list + referral-partner management currently live as panels inside
      // the Administration hub; N3 lifts them out to their own platform pages.
      { id: 'organisations', href: '/admin/organisations', labelKey: 'admin.nav.organisations',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' }, placeholder: true },
      { id: 'referralPartners', href: '/admin/referral-partners',
        labelKey: 'admin.nav.referralPartners',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' }, placeholder: true },
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
      // Overview keeps /admin/administration for now: N2 ships the sidebar beside the live hub so
      // a rollback is one import. N3 splits the hub and this becomes /admin/organisation.
      { id: 'administration', href: '/admin/administration', labelKey: 'admin.administration.nav',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' }, match: ['/admin/invite'] },
      // Reserved. Staff management is a panel inside the hub today; N3 gives it a page.
      { id: 'staff', href: '/admin/organisation/staff', labelKey: 'admin.nav.staff',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' }, placeholder: true },
      { id: 'sponsors', href: '/admin/sponsors', labelKey: 'admin.sponsors.nav',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' }, badge: 'pendingSponsors' },
      { id: 'payments', href: '/admin/payments', labelKey: 'admin.payments.title',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' } },
      { id: 'contracts', href: '/admin/contracts', labelKey: 'admin.contracts.title',
        scope: 'organisation', roles: ['super', 'org_admin'], gate: { mode: 'always' } },
      { id: 'sources', href: '/admin/sources', labelKey: 'admin.sources.nav',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin'], gate: { mode: 'always' } },
      { id: 'billing', href: '/admin/billing', labelKey: 'admin.billing.title',
        scope: 'organisation', roles: ['super', 'org_admin'],
        gate: { mode: 'probe', probe: 'billing', dark: 'soon' } },
      { id: 'requests', href: '/admin/requests', labelKey: 'admin.requests.nav',
        scope: 'organisation', roles: ['super', 'org_admin'],
        gate: { mode: 'probe', probe: 'requests', dark: 'hide' } },
    ],
  },
  {
    scope: 'programme',
    headingKey: 'admin.nav.group.programme',
    items: [
      // The gift itself. `finance` is absent deliberately: it has no B40 scope at all
      // (`_b40_scope` -> 'none'), so an Applications link would only ever 403.
      // Reserved. The programme is the gift; its own overview lands when the Programme model is
      // read by the web app (nothing does yet).
      { id: 'programmeOverview', href: '/admin/programme', labelKey: 'admin.nav.programmeOverview',
        scope: 'programme', roles: ['super', 'org_admin', 'admin', 'qc'],
        gate: { mode: 'always' }, placeholder: true },
      { id: 'applications', href: '/admin/scholarship', labelKey: 'admin.scholarship.nav',
        scope: 'programme', roles: ['super', 'org_admin', 'admin', 'qc', 'reviewer'],
        gate: { mode: 'always' } },
      // Reserved slots the programme-layer roadmap owes: reviewer assignment/scoping, the intake
      // years beneath the gift, the fund, and the rules that currently live on the cohort.
      { id: 'reviewers', href: '/admin/programme/reviewers', labelKey: 'admin.nav.reviewers',
        scope: 'programme', roles: ['super', 'org_admin'],
        gate: { mode: 'always' }, placeholder: true },
      { id: 'years', href: '/admin/programme/years', labelKey: 'admin.nav.years',
        scope: 'programme', roles: ['super', 'org_admin'],
        gate: { mode: 'always' }, placeholder: true },
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
