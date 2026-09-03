/**
 * Guardrails for the admin route registry (`lib/navigation.ts`).
 *
 * Every collection here is DERIVED from the registry or read off disk, never hand-copied —
 * a test that enumerates what it guards freezes its own coverage the moment the source grows
 * (lessons.md, Finance role 2026-07-23). The two deliberate exceptions are the role snapshot
 * and the legacy-bar expectation: those encode facts OUTSIDE the registry (the permission
 * matrix, and the bar as it shipped before this sprint), so they must be literal — a change
 * there has to be typed out on purpose.
 *
 * Jest runs in node, so fs/path reads are fine.
 */
import * as fs from 'fs'
import * as path from 'path'

import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import {
  NAV_GROUPS, NAV_ITEMS, CHROMELESS, ROLE_NAMES, NO_PROBES, SIDEBAR_SCOPES,
  effectiveRole, canSee, visibleNav, activeItem, canAccess, searchNav, defaultRoute,
  chordTarget, CHORD_PREFIX,
  type AdminRoleName, type NavContext, type ProbeState, type LabelledNavItem,
} from '@/lib/navigation'

const ctx = (role: AdminRoleName, probes: Partial<Record<'requests' | 'billing', ProbeState>> = {}): NavContext =>
  ({ role, probes: { ...NO_PROBES, ...probes } })

const resolve = (msgs: Record<string, unknown>, key: string): unknown =>
  key.split('.').reduce<unknown>(
    (cur, part) => (cur && typeof cur === 'object' && part in cur
      ? (cur as Record<string, unknown>)[part] : undefined),
    msgs,
  )

// ── 1. i18n parity ───────────────────────────────────────────────────────────
describe('every registry label resolves in all three locales', () => {
  const keys = [
    ...NAV_ITEMS.map((i) => i.labelKey),
    ...NAV_GROUPS.map((g) => g.headingKey),
  ]

  it('has a key for every item and group (parse sanity — not a no-op)', () => {
    expect(keys.length).toBeGreaterThanOrEqual(14)
  })

  it.each([['en', en], ['ms', ms], ['ta', ta]] as const)('%s', (_locale, msgs) => {
    for (const key of keys) {
      const value = resolve(msgs as Record<string, unknown>, key)
      expect(typeof value).toBe('string')
      expect((value as string).trim()).not.toBe('')
    }
  })
})

// ── 2. Role snapshot ─────────────────────────────────────────────────────────
// The artefact that replaces the hardcoded ternary chain deleted from admin/layout.tsx.
// LITERAL on purpose: this is the permission matrix, not a copy of the registry. Changing a
// role's reach must be a deliberate edit here (docs/scholarship/role-matrix.md first).
describe('visibleNav per role', () => {
  const EXPECTED: Record<AdminRoleName, string[]> = {
    super: [
      'overview', 'students', 'courseData', 'organisations', 'referralPartners', 'billingRates',
      'administration', 'orgSettings', 'staff', 'reviewers', 'sponsors', 'sources', 'payments',
      'contracts', 'billing',
      'programmeConfig', 'applications',
      'profile', 'guide', 'faq',
    ],
    // Layer 0 Sprint 5 (2026-08-30): "What we ask for" replaces the Overview placeholder and is
    // an org_admin (+ super) power — configuration, not a fence. admin/qc lose the placeholder
    // slot they never had a page behind. role-matrix.md updated in the same change.
    //
    // ⚠ THE SHAPE SPRINT (2026-09-03) REMOVED FIVE ROWS AND ADDED ONE. `programmes` moved onto the
    // organisation OVERVIEW (the gifts a tenant runs are what it is, not a feature beside it), and
    // the Programme group's `reviewerScoping` / `years` / `fund` / `rules` were deleted rather than
    // filled — years and rules became TABS of `programmeConfig`, reviewer scoping is a field on a
    // reviewer's record, and the fund is a report. `orgSettings` is new and holds Colours, which
    // had been sitting on the Programme screen while writing a TENANT-wide row.
    //
    // Nobody GAINED reach: `orgSettings` carries exactly the roles the theme endpoint already
    // allowed (super + org_admin), and every deleted row was a page that did not exist. The one
    // real loss is `finance`, which is no longer offered the reserved `fund` slot — it never had a
    // page, so this removes a disabled row rather than a power.
    org_admin: [
      'administration', 'orgSettings', 'staff', 'reviewers', 'sponsors', 'sources', 'payments',
      'contracts', 'billing',
      'programmeConfig', 'applications',
      'profile', 'guide', 'faq',
    ],
    admin: [
      'administration', 'staff', 'reviewers', 'sponsors', 'sources', 'payments',
      'applications',
      'profile', 'guide', 'faq',
    ],
    finance: [
      'administration', 'staff', 'reviewers', 'sponsors', 'payments',
      'profile', 'guide', 'faq',
    ],
    qc: ['applications', 'profile', 'guide', 'faq'],
    reviewer: ['applications', 'profile', 'guide', 'faq'],
    partner: ['overview', 'students', 'profile'],
  }

  it('covers every role the backend defines', () => {
    expect(Object.keys(EXPECTED).sort()).toEqual([...ROLE_NAMES].sort())
  })

  it.each(ROLE_NAMES)('%s', (role) => {
    // Probes dark: Requests hides, Billing degrades to "soon" but still appears.
    const ids = visibleNav(ctx(role)).flatMap((g) => g.items.map((i) => i.id))
    expect(ids).toEqual(EXPECTED[role])
  })

  it('finance never reaches Applications — it has no B40 scope at all', () => {
    expect(canAccess('/admin/scholarship', 'finance')).toBe(false)
  })

  it('a reviewer reaches neither the organisation nor the platform scope', () => {
    const scopes = visibleNav(ctx('reviewer')).map((g) => g.scope)
    expect(scopes).toEqual(['programme', 'utility'])
  })
})

// ── 3. activeItem ────────────────────────────────────────────────────────────
describe('activeItem resolves by longest match', () => {
  // Reserved slots are excluded on purpose — they have no page, so nothing resolves to them
  // (asserted separately below).
  it.each(NAV_ITEMS.filter((i) => !i.placeholder).map((i) => [i.href, i.id]))(
    '%s -> %s', (href, id) => {
      expect(activeItem(href as string)?.id).toBe(id)
    })

  it.each(
    NAV_ITEMS.flatMap((i) => (i.match ?? []).map((m) => [m, i.id])),
  )('match prefix %s -> %s', (prefix, id) => {
    expect(activeItem(prefix as string)?.id).toBe(id)
  })

  it('keeps a nested detail page on its parent item', () => {
    expect(activeItem('/admin/scholarship/123')?.id).toBe('applications')
    expect(activeItem('/admin/payments/7')?.id).toBe('payments')
    expect(activeItem('/admin/students/42')?.id).toBe('students')
    expect(activeItem('/admin/contracts/9')?.id).toBe('contracts')
    expect(activeItem('/admin/requests/4')?.id).toBe('requests')
  })

  it('does not let /admin swallow its children (longest match is load-bearing)', () => {
    expect(activeItem('/admin')?.id).toBe('overview')
    expect(activeItem('/admin/students')?.id).toBe('students')
  })

  it('the index route matches exactly — an unknown route is unresolved, not the dashboard', () => {
    // Otherwise `/admin` prefixes everything and an unrecognised path inherits its roles,
    // which would have made canAccess refuse a reviewer on a route nobody declared.
    expect(activeItem('/admin/something-new')).toBeUndefined()
  })

  it('respects the path boundary, not the bare prefix', () => {
    // Without the trailing slash this would resolve to `applications`.
    expect(activeItem('/admin/scholarshipX')?.id).not.toBe('applications')
  })

  // This assertion IS the bug that shipped: layout.tsx's isActive special-cased payments,
  // contracts and sponsors and forgot requests, sources and billing, so those three pages
  // highlighted nothing at all.
  it('leaves no admin route unresolved — including the three that highlighted nothing', () => {
    for (const p of ['/admin/requests', '/admin/sources', '/admin/billing']) {
      expect(activeItem(p)).toBeDefined()
    }
  })

  // N1 shipped these as "hub" pages that highlighted Administration because they had no entry
  // of their own. The sidebar gives each one a row, so each now highlights ITSELF — which is
  // the whole reason the transitional chrome/hubParent fields could be deleted (TD-181).
  it('every previously-hub page now highlights itself', () => {
    for (const [p, id] of [
      ['/admin/payments', 'payments'], ['/admin/contracts', 'contracts'],
      ['/admin/sponsors', 'sponsors'], ['/admin/sources', 'sources'],
      ['/admin/billing', 'billing'], ['/admin/requests', 'requests'],
    ] as const) {
      expect(activeItem(p)?.id).toBe(id)
    }
    // Four permanent redirects, each pointing at the row it now belongs to. An old bookmark must
    // light the correct sidebar row, not merely land somewhere.
    expect(activeItem('/admin/administration')?.id).toBe('administration')  // → the org overview
    expect(activeItem('/admin/invite')?.id).toBe('staff')                   // → org staff
    // The shape sprint (2026-09-03). Both pages existed for exactly one sprint, so a bookmark is
    // young and a stale link is likelier than usual.
    expect(activeItem('/admin/organisation/programmes')?.id).toBe('administration')
    expect(activeItem('/admin/programme/years')?.id).toBe('programmeConfig')
  })

  it('the organisation overview is a page, not a section', () => {
    // /admin/organisation must not swallow /admin/organisation/staff, which is its SIBLING in
    // the menu rather than its child — the same boundary rule as the /admin index route.
    expect(activeItem('/admin/organisation')?.id).toBe('administration')
    expect(activeItem('/admin/organisation/staff')?.id).toBe('staff')
    // …and the new settings page is a sibling too, not something inside the overview.
    expect(activeItem('/admin/organisation/settings')?.id).toBe('orgSettings')
  })

  it('the programme screen is a page whose tabs are not routes', () => {
    // Rules, "What we ask for" and Intake year are TABS: one route, one registry row. A tab that
    // grew its own path would need its own entry, and the sidebar would say Programme twice.
    expect(activeItem('/admin/programme')?.id).toBe('programmeConfig')
    // The redirect above is matched exactly; nothing deeper claims the row by accident.
    expect(activeItem('/admin/programme/reviewers')).toBeUndefined()
  })

  it('a reserved slot never claims a path — it has no page to be inside', () => {
    for (const item of NAV_ITEMS.filter((i) => i.placeholder)) {
      expect(activeItem(item.href)).toBeUndefined()
    }
  })
})

// ── 4. Dark-ship probe semantics ─────────────────────────────────────────────
describe('probe gating reproduces the 404-means-invisible contract', () => {
  const item = (id: string) => NAV_ITEMS.find((i) => i.id === id)!

  it('an unloaded probe is NOT live — a dark feature must never flash in', () => {
    expect(canSee(item('requests'), ctx('super'))).toBe('hide')
    expect(canSee(item('billing'), ctx('super'))).toBe('soon')
  })

  it('a 404 keeps it dark', () => {
    expect(canSee(item('requests'), ctx('super', { requests: 'dark' }))).toBe('hide')
    expect(canSee(item('billing'), ctx('super', { billing: 'dark' }))).toBe('soon')
  })

  it('an answering endpoint turns it on', () => {
    expect(canSee(item('requests'), ctx('super', { requests: 'live' }))).toBe('show')
    expect(canSee(item('billing'), ctx('super', { billing: 'live' }))).toBe('show')
  })

  it('the role check still wins — a live probe cannot reveal it to the wrong role', () => {
    expect(canSee(item('billing'), ctx('finance', { billing: 'live' }))).toBe('hide')
    expect(canSee(item('requests'), ctx('reviewer', { requests: 'live' }))).toBe('hide')
  })
})

// ── 5. Route drift ───────────────────────────────────────────────────────────
// Reads the app router off disk. This is what stops the next six orphaned routes: a new admin
// page with no registry entry fails here rather than quietly having no menu home.
describe('the registry and the app router agree', () => {
  const ADMIN_DIR = path.join(__dirname, '..', '..', 'app', 'admin')

  /** Top-level route segments that own a page.tsx, e.g. 'payments'. */
  function routeDirs(): string[] {
    return fs.readdirSync(ADMIN_DIR, { withFileTypes: true })
      .filter((d) => d.isDirectory() && !d.name.startsWith('['))
      .filter((d) => fs.existsSync(path.join(ADMIN_DIR, d.name, 'page.tsx')))
      .map((d) => d.name)
  }

  const dirs = routeDirs()

  it('found the router (parse sanity — not a no-op)', () => {
    expect(dirs.length).toBeGreaterThanOrEqual(14)
    expect(fs.existsSync(path.join(ADMIN_DIR, 'page.tsx'))).toBe(true)
  })

  it('every rendered admin page has a registry entry', () => {
    const chromeless = (href: string) => CHROMELESS.some((c) => href === c || href.startsWith(c))
    const orphans = dirs
      .map((d) => `/admin/${d}`)
      .filter((href) => !chromeless(href))
      .filter((href) => activeItem(href) === undefined)
    expect(orphans).toEqual([])
  })

  it('every NON-reserved registry href has a page behind it', () => {
    const missing = NAV_ITEMS.filter((i) => !i.placeholder).filter((i) => {
      const seg = i.href.replace(/^\/admin\/?/, '')
      const file = seg === ''
        ? path.join(ADMIN_DIR, 'page.tsx')
        : path.join(ADMIN_DIR, seg, 'page.tsx')
      return !fs.existsSync(file)
    })
    expect(missing.map((i) => i.href)).toEqual([])
  })

  // The other direction of the same guard: a slot must stay reserved only while it is genuinely
  // empty. Build the page and forget to drop the flag, and it would render disabled forever.
  it('every RESERVED slot is genuinely empty — build the page and the flag must go', () => {
    const built = NAV_ITEMS.filter((i) => i.placeholder).filter((i) => {
      const seg = i.href.replace(/^\/admin\/?/, '')
      return fs.existsSync(path.join(ADMIN_DIR, seg, 'page.tsx'))
    })
    expect(built.map((i) => i.href)).toEqual([])
  })
})

// ── 6. effectiveRole ─────────────────────────────────────────────────────────
describe('effectiveRole', () => {
  it('lets the super flag win over the role column', () => {
    expect(effectiveRole({ role: 'reviewer', is_super_admin: true })).toBe('super')
    expect(effectiveRole({ role: 'super', is_super_admin: false })).toBe('super')
  })

  it('passes a known role through', () => {
    for (const r of ROLE_NAMES) expect(effectiveRole({ role: r })).toBe(r)
  })

  it('falls back to the least-privileged role, preserving the old layout behaviour', () => {
    expect(effectiveRole(null)).toBe('reviewer')
    expect(effectiveRole(undefined)).toBe('reviewer')
    expect(effectiveRole({})).toBe('reviewer')
    expect(effectiveRole({ role: 'viewer' })).toBe('reviewer')  // legacy value, not a real role
  })
})

// ── 7. The sidebar shape the shell renders ──────────────────────────
describe('visibleNav groups', () => {
  it('orders groups by scope hierarchy, platform outermost', () => {
    expect(visibleNav(ctx('super')).map((g) => g.scope))
      .toEqual(['platform', 'organisation', 'programme', 'utility'])
  })

  it('drops a scope a role cannot reach rather than showing an empty heading', () => {
    expect(visibleNav(ctx('reviewer')).map((g) => g.scope)).toEqual(['programme', 'utility'])
    expect(visibleNav(ctx('partner')).map((g) => g.scope)).toEqual(['platform', 'utility'])
  })

  it('the sidebar renders three scopes; utility belongs to the account and help menus', () => {
    expect(SIDEBAR_SCOPES).toEqual(['platform', 'organisation', 'programme'])
    expect(SIDEBAR_SCOPES).not.toContain('utility')
  })

  // Request #10 shipped Organisation → Reviewers while Programme still reserved a slot called
  // "Reviewers" for per-programme SCOPING. Two rows with one name is not a naming quibble: one is
  // live and one renders disabled with a "Soon" pill, so the reader concludes the feature is
  // half-broken. The rename is the fix; this is the guard that keeps any future pair apart.
  it('no two menu rows carry the same label', () => {
    const keys = NAV_ITEMS.map((i) => i.labelKey)
    expect(keys.filter((k, i) => keys.indexOf(k) !== i)).toEqual([])
  })

  // Request #10 shipped Organisation → Reviewers while Programme reserved a second row for
  // per-programme SCOPING. The shape sprint deleted that slot rather than renaming it again:
  // which gift a reviewer covers is a FIELD on that reviewer, so it belongs on their record here.
  it('there is ONE reviewer row, and it is the organisation directory', () => {
    const rows = NAV_ITEMS.filter((i) => i.href.includes('reviewers'))
    expect(rows.map((i) => i.id)).toEqual(['reviewers'])
    expect(rows[0].href).toBe('/admin/organisation/reviewers')
    expect(rows[0].scope).toBe('organisation')
    expect(rows[0].placeholder).toBeFalsy()
  })

  // ⚠ THE ASSERTION IS THE COUNT, not the contents. Everything a person SETS about a gift is one
  // screen with tabs; a third row here means somebody has promoted a tab back into a page, which
  // is the drift this sprint removed. Applications is the only other thing you DO to a gift.
  it('the programme scope is two rows: configure it, and work through it', () => {
    const prog = visibleNav(ctx('org_admin')).find((g) => g.scope === 'programme')!
    expect(prog.items.map((i) => i.id)).toEqual(['programmeConfig', 'applications'])
    expect(prog.items.every((i) => !i.placeholder)).toBe(true)
  })

  it('marks reserved slots so the sidebar can disable them', () => {
    const platform = visibleNav(ctx('super')).find((g) => g.scope === 'platform')!
    expect(platform.items.find((i) => i.id === 'students')!.placeholder).toBeFalsy()
    expect(platform.items.find((i) => i.id === 'billingRates')!.placeholder).toBe(true)
  })

  // ⚠ LITERAL ON PURPOSE, like the role matrix. A reserved slot is a promise about where a thing
  // will live, and three of the four that existed guessed the shape wrongly (see the `placeholder`
  // note in navigation.ts). `billingRates` survives because its endpoint SHIPPED and only the page
  // is missing. Adding a fifth slot should cost somebody a deliberate edit here and a reason.
  it('reserves exactly one slot, and it is the one with a shipped endpoint behind it', () => {
    expect(NAV_ITEMS.filter((i) => i.placeholder).map((i) => i.id)).toEqual(['billingRates'])
  })
})

// ── 7b. searchNav (the palette ranking) ────────────────────────────
describe('searchNav', () => {
  const L = (id: string, label: string): LabelledNavItem =>
    ({ item: NAV_ITEMS.find((i) => i.id === id)!, label })
  const items = [
    L('overview', 'Dashboard'), L('students', 'Students'),
    L('payments', 'Payments'), L('applications', 'B40 Applications'),
    L('billingRates', 'Billing rates'),      // reserved
  ]

  it('an empty query lists everything navigable, in registry order', () => {
    expect(searchNav('', items).map((i) => i.id))
      .toEqual(['overview', 'students', 'payments', 'applications'])
  })

  it('never offers a reserved slot — there is nowhere to go', () => {
    expect(searchNav('billing rates', items)).toEqual([])
  })

  it('ranks a prefix hit above a word hit above a bare substring', () => {
    // "App" starts B40 Applications' second WORD; it is a bare substring of nothing else here.
    expect(searchNav('app', items).map((i) => i.id)).toEqual(['applications'])
    // "s" starts Students, and appears inside Applications and Payments.
    const ids = searchNav('s', items).map((i) => i.id)
    expect(ids[0]).toBe('students')
  })

  it('is case-insensitive and ignores surrounding space', () => {
    expect(searchNav('  PAYM '.trim(), items).map((i) => i.id)).toEqual(['payments'])
  })

  it('returns nothing rather than everything when nothing matches', () => {
    expect(searchNav('zzzz', items)).toEqual([])
  })
})

// ── 7c. defaultRoute ───────────────────────────────────────
// Byte-identical to the adminLanding() it replaces — adminLanding.test.ts is unmodified and
// still passes. See the docstring for why this is NOT written in terms of canAccess.
describe('defaultRoute', () => {
  it('holds an incomplete reviewer on their profile', () => {
    expect(defaultRoute({ role: 'reviewer' }, false)).toBe('/admin/profile')
  })
  it('sends a reviewer and the legacy viewer to the workspace', () => {
    expect(defaultRoute({ role: 'reviewer' }, true)).toBe('/admin/scholarship')
    expect(defaultRoute({ role: 'viewer' })).toBe('/admin/scholarship')
  })
  it('sends everyone else to /admin, which bounces them if they may not see it', () => {
    for (const r of ['super', 'admin', 'org_admin', 'qc', 'finance', 'partner'] as const) {
      expect(defaultRoute({ role: r })).toBe('/admin')
    }
  })
  it('never traps on an OLD payload that omits the completeness flag', () => {
    expect(defaultRoute({ role: 'reviewer' })).toBe('/admin/scholarship')
  })
})

// ── 8. canAccess mirrors the guards the pages used to derive themselves ──────
describe('canAccess', () => {
  it.each([
    ['/admin/payments', ['super', 'admin', 'org_admin', 'finance']],
    ['/admin/contracts', ['super', 'org_admin']],
    ['/admin/sources', ['super', 'org_admin', 'admin']],
    ['/admin/billing', ['super', 'org_admin']],
    ['/admin/students', ['super', 'partner']],
    ['/admin/course-data', ['super']],
  ] as const)('%s', (href, allowed) => {
    for (const role of ROLE_NAMES) {
      expect(canAccess(href, role)).toBe((allowed as readonly string[]).includes(role))
    }
  })

  it('never invents a block for a route it does not know', () => {
    expect(canAccess('/admin/something-new', 'reviewer')).toBe(true)
  })
})

// ── 9. chords ────────────────────────────────────────────────────────────────
//
// The N1 lesson was that a matching rule needs an exception for the root of its namespace;
// the same shape of bug here is a COLLISION — two routes claiming one letter. `chord` is
// deliberately optional (most routes will never earn one), so these tests, not the type, are
// the guard. Everything is derived from the registry: adding a route with a duplicate letter
// fails without anyone having to remember this file exists.
describe('chords', () => {
  const chorded = NAV_ITEMS.filter((i) => i.chord)

  it('gives every chord to exactly one route', () => {
    const letters = chorded.map((i) => i.chord)
    const dupes = letters.filter((l, i) => letters.indexOf(l) !== i)
    expect(dupes).toEqual([])
  })

  it('uses a single upper-case letter, never a word or a symbol', () => {
    for (const item of chorded) expect(item.chord).toMatch(/^[A-Z]$/)
  })

  it('never chords a reserved slot — there is no page to land on', () => {
    expect(NAV_ITEMS.filter((i) => i.placeholder && i.chord)).toEqual([])
  })

  it('never collides with the prefix that arms it', () => {
    expect(chorded.map((i) => i.chord?.toLowerCase())).not.toContain(CHORD_PREFIX)
  })

  it('chords the routes people live in', () => {
    // A short literal list on purpose: it asserts the FEATURE is wired to the pages that
    // matter, which no derivation from the registry can tell you.
    const byId = Object.fromEntries(NAV_ITEMS.map((i) => [i.id, i.chord]))
    expect(byId.applications).toBe('A')
    expect(byId.sponsors).toBe('P')
    expect(byId.staff).toBe('T')
  })
})

describe('chordTarget', () => {
  const groups = (role: AdminRoleName, probes: Partial<Record<'requests' | 'billing', ProbeState>> = {}) =>
    visibleNav(ctx(role, probes))

  it('resolves a letter to its route, either case', () => {
    expect(chordTarget('A', groups('super'))?.href).toBe('/admin/scholarship')
    expect(chordTarget('a', groups('super'))?.href).toBe('/admin/scholarship')
  })

  it('returns nothing for a letter nobody claims', () => {
    expect(chordTarget('Z', groups('super'))).toBeUndefined()
  })

  it('never carries someone to a page their own menu does not offer', () => {
    // A reviewer sees Applications and nothing else; Sponsors (P) must not be reachable.
    expect(chordTarget('A', groups('reviewer'))?.href).toBe('/admin/scholarship')
    expect(chordTarget('P', groups('reviewer'))).toBeUndefined()
    expect(chordTarget('D', groups('reviewer'))).toBeUndefined()
  })

  it('respects a dark-shipped gate — Requests is unreachable until the API answers', () => {
    expect(chordTarget('Q', groups('org_admin'))).toBeUndefined()
    expect(chordTarget('Q', groups('org_admin', { requests: 'live' }))?.href).toBe('/admin/requests')
  })

  it('does not fire for a gate rendering as "soon" — the page is not there yet', () => {
    // Billing dark renders disabled with a pill; a chord to it would land on nothing.
    expect(chordTarget('B', groups('org_admin'))).toBeUndefined()
    expect(chordTarget('B', groups('org_admin', { billing: 'live' }))?.href).toBe('/admin/billing')
  })

  it('every chord in the registry is reachable by SOMEBODY', () => {
    // Catches a letter assigned to a route no role can see — a shortcut nobody can press.
    const everyone = ROLE_NAMES.flatMap((r) => groups(r, { requests: 'live', billing: 'live' }))
    for (const item of NAV_ITEMS.filter((i) => i.chord)) {
      expect(chordTarget(item.chord as string, everyone)?.id).toBe(item.id)
    }
  })
})
