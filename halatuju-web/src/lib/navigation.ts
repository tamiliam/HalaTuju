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
   * TRANSITIONAL (N1 → N2). Where the item sits in TODAY's chrome:
   *   'top' — a top-bar entry.
   *   'hub' — no menu entry; reached from the /admin/administration card grid, and
   *           highlights `hubParent` in the bar.
   * N2 replaces the bar with the scope sidebar, where every item renders in its own group;
   * `chrome`, `hubParent` and `LEGACY_BAR_ORDER` are deleted then.
   */
  chrome: 'top' | 'hub'
  /** Item id to highlight in the legacy bar. Required when `chrome === 'hub'`. */
  hubParent?: string
}

export interface NavGroup {
  scope: NavScope
  headingKey: string
  items: readonly NavItem[]
}

/**
 * Every route in the console, grouped by scope.
 *
 * Role sets reproduce the guards that exist today, so N1 changes no behaviour:
 *   payments  super/admin/org_admin/finance  (payments/page.tsx `allowed`)
 *   contracts super/org_admin                (contracts/page.tsx `allowed`)
 *   sources   super/org_admin/admin          (sources/page.tsx `canManage`)
 *   billing   super/org_admin                (billing/page.tsx)
 * `sponsors` and `requests` have NO client guard today — they rely on the backend alone.
 * Their role sets here drive menu visibility only; N1 adds no new client-side block.
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
        exact: true, chrome: 'top' },
      { id: 'students', href: '/admin/students', labelKey: 'admin.students',
        scope: 'platform', roles: ['super', 'partner'], gate: { mode: 'always' }, chrome: 'top' },
      { id: 'courseData', href: '/admin/course-data', labelKey: 'admin.courseData.nav',
        scope: 'platform', roles: ['super'], gate: { mode: 'always' }, chrome: 'top' },
    ],
  },
  {
    scope: 'organisation',
    headingKey: 'admin.nav.group.organisation',
    items: [
      // The security fence: staff, sponsors, money out, contracts, billing.
      { id: 'administration', href: '/admin/administration', labelKey: 'admin.administration.nav',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' }, match: ['/admin/invite'], badge: 'pendingSponsors',
        chrome: 'top' },
      { id: 'sponsors', href: '/admin/sponsors', labelKey: 'admin.sponsors.nav',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' }, chrome: 'hub', hubParent: 'administration' },
      { id: 'payments', href: '/admin/payments', labelKey: 'admin.payments.title',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin', 'finance'],
        gate: { mode: 'always' }, chrome: 'hub', hubParent: 'administration' },
      { id: 'contracts', href: '/admin/contracts', labelKey: 'admin.contracts.title',
        scope: 'organisation', roles: ['super', 'org_admin'],
        gate: { mode: 'always' }, chrome: 'hub', hubParent: 'administration' },
      { id: 'sources', href: '/admin/sources', labelKey: 'admin.sources.nav',
        scope: 'organisation', roles: ['super', 'org_admin', 'admin'],
        gate: { mode: 'always' }, chrome: 'hub', hubParent: 'administration' },
      { id: 'billing', href: '/admin/billing', labelKey: 'admin.billing.title',
        scope: 'organisation', roles: ['super', 'org_admin'],
        gate: { mode: 'probe', probe: 'billing', dark: 'soon' },
        chrome: 'hub', hubParent: 'administration' },
      { id: 'requests', href: '/admin/requests', labelKey: 'admin.requests.nav',
        scope: 'organisation', roles: ['super', 'org_admin'],
        gate: { mode: 'probe', probe: 'requests', dark: 'hide' },
        chrome: 'hub', hubParent: 'administration' },
    ],
  },
  {
    scope: 'programme',
    headingKey: 'admin.nav.group.programme',
    items: [
      // The gift itself. `finance` is absent deliberately: it has no B40 scope at all
      // (`_b40_scope` -> 'none'), so an Applications link would only ever 403.
      { id: 'applications', href: '/admin/scholarship', labelKey: 'admin.scholarship.nav',
        scope: 'programme', roles: ['super', 'org_admin', 'admin', 'qc', 'reviewer'],
        gate: { mode: 'always' }, chrome: 'top' },
    ],
  },
  {
    scope: 'utility',
    headingKey: 'admin.nav.group.utility',
    items: [
      // Yours, not any scope's. N2 moves these into the help and account menus.
      { id: 'profile', href: '/admin/profile', labelKey: 'admin.profile',
        scope: 'utility', roles: ROLE_NAMES, gate: { mode: 'always' }, chrome: 'top' },
      { id: 'guide', href: '/admin/guide', labelKey: 'admin.guideNav',
        scope: 'utility', roles: ['super', 'admin', 'org_admin', 'reviewer', 'qc', 'finance'],
        gate: { mode: 'always' }, chrome: 'top' },
      { id: 'faq', href: '/admin/faq', labelKey: 'admin.faqNav',
        scope: 'utility', roles: ['super', 'admin', 'org_admin', 'reviewer', 'qc', 'finance'],
        gate: { mode: 'always' }, chrome: 'top' },
    ],
  },
]

/** Flat view of the registry. */
export const NAV_ITEMS: readonly NavItem[] = NAV_GROUPS.flatMap((g) => g.items)

/**
 * TRANSITIONAL (N1 → N2): the order of today's top bar, which is accretion rather than
 * meaning. Scope order is the target (see NAV_GROUPS) but reordering the live bar is not
 * this sprint's job, so N1 renders in exactly today's sequence. Deleted with `chrome` in N2.
 * `navigation.test.ts` asserts this list is COMPLETE against every `chrome: 'top'` item, so
 * it cannot silently fall behind the registry.
 */
export const LEGACY_BAR_ORDER: readonly string[] = [
  'overview', 'students', 'applications', 'courseData', 'administration',
  'profile', 'guide', 'faq',
]

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
 * Which item the LEGACY top bar should highlight for a path: a hub page (Payments, Sources,
 * …) has no bar entry of its own and highlights the hub it lives under.
 * TRANSITIONAL — deleted with `chrome` in N2, where every item highlights itself.
 */
export function legacyBarActiveId(pathname: string): string | undefined {
  const item = activeItem(pathname)
  if (!item) return undefined
  return item.chrome === 'hub' ? item.hubParent : item.id
}

/**
 * The legacy top bar for a context: today's items, in today's order.
 * TRANSITIONAL — N2's sidebar renders `visibleNav()` directly instead.
 */
export function legacyBarItems(ctx: NavContext): VisibleNavItem[] {
  const visible = new Map(
    visibleNav(ctx).flatMap((g) => g.items).map((i) => [i.id, i] as const),
  )
  return LEGACY_BAR_ORDER
    .map((id) => visible.get(id))
    .filter((i): i is VisibleNavItem => !!i && i.chrome === 'top' && i.state === 'show')
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
