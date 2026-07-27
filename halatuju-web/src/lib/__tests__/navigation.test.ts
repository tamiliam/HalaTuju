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
  NAV_GROUPS, NAV_ITEMS, LEGACY_BAR_ORDER, CHROMELESS, ROLE_NAMES, NO_PROBES,
  effectiveRole, canSee, visibleNav, activeItem, canAccess, legacyBarItems, legacyBarActiveId,
  type AdminRoleName, type NavContext, type ProbeState,
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
      'overview', 'students', 'courseData',
      'administration', 'sponsors', 'payments', 'contracts', 'sources', 'billing',
      'applications',
      'profile', 'guide', 'faq',
    ],
    org_admin: [
      'administration', 'sponsors', 'payments', 'contracts', 'sources', 'billing',
      'applications',
      'profile', 'guide', 'faq',
    ],
    admin: [
      'administration', 'sponsors', 'payments', 'sources',
      'applications',
      'profile', 'guide', 'faq',
    ],
    finance: [
      'administration', 'sponsors', 'payments',
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
  it.each(NAV_ITEMS.map((i) => [i.href, i.id]))('%s -> %s', (href, id) => {
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

  it('highlights the hub parent for a page with no bar entry of its own', () => {
    for (const p of ['/admin/payments', '/admin/contracts', '/admin/sponsors',
      '/admin/sources', '/admin/billing', '/admin/requests', '/admin/invite']) {
      expect(legacyBarActiveId(p)).toBe('administration')
    }
    expect(legacyBarActiveId('/admin/scholarship/12')).toBe('applications')
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

  it('every registry href has a page behind it', () => {
    const missing = NAV_ITEMS.filter((i) => {
      const seg = i.href.replace(/^\/admin\/?/, '')
      const file = seg === ''
        ? path.join(ADMIN_DIR, 'page.tsx')
        : path.join(ADMIN_DIR, seg, 'page.tsx')
      return !fs.existsSync(file)
    })
    expect(missing.map((i) => i.href)).toEqual([])
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

// ── 7. The legacy bar is byte-for-byte what shipped before this sprint ───────
// LITERAL on purpose: this is the OLD behaviour, an external fact, and it is the whole ship
// criterion for N1 — the menu must not move.
describe('legacyBarItems reproduces the pre-sprint top bar exactly', () => {
  const BEFORE: Record<AdminRoleName, string[]> = {
    super: ['overview', 'students', 'applications', 'courseData', 'administration',
      'profile', 'guide', 'faq'],
    admin: ['applications', 'administration', 'profile', 'guide', 'faq'],
    org_admin: ['applications', 'administration', 'profile', 'guide', 'faq'],
    finance: ['administration', 'profile', 'guide', 'faq'],
    qc: ['applications', 'profile', 'guide', 'faq'],
    reviewer: ['applications', 'profile', 'guide', 'faq'],
    partner: ['overview', 'students', 'profile'],
  }

  it.each(ROLE_NAMES)('%s', (role) => {
    expect(legacyBarItems(ctx(role)).map((i) => i.id)).toEqual(BEFORE[role])
  })

  it('LEGACY_BAR_ORDER is complete against the registry, in both directions', () => {
    const topIds = NAV_ITEMS.filter((i) => i.chrome === 'top').map((i) => i.id).sort()
    expect([...LEGACY_BAR_ORDER].sort()).toEqual(topIds)
  })

  it('every hub item names a real parent that is itself a bar entry', () => {
    for (const i of NAV_ITEMS.filter((x) => x.chrome === 'hub')) {
      const parent = NAV_ITEMS.find((x) => x.id === i.hubParent)
      expect(parent).toBeDefined()
      expect(parent!.chrome).toBe('top')
    }
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
