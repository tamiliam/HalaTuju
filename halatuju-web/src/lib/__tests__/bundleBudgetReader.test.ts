/**
 * TD-304 (2026-10-04): the pure half of `scripts/bundle-budget.js` — how it maps the build's
 * `.next/app-build-manifest.json` onto the routes Next prints, and how it refuses to budget a
 * figure it cannot prove is the one Next printed.
 *
 * jest still cannot WEIGH anything (no build here); `npm run bundle-budget` does, in the deploy
 * gate. These rows hold the arithmetic the weighing relies on, on a synthetic manifest whose
 * chunk sizes are given rather than gzipped.
 */
import * as fs from 'fs'
import * as path from 'path'
import {
  exactRoutes, layoutEntries, manifestReadings, nearLine, NEAR_LINE_KB, printTolerance,
  routeOfEntry, SHRINK_SLACK_KB,
} from '../../../scripts/bundle-budget'

const SIZES: Record<string, number> = {
  'webpack.js': 2_000, 'main-app.js': 80_000, 'shared.js': 5_000,
  'root-layout.js': 9_000, 'root.css': 4_000,
  'admin-layout.js': 20_000, 'portal-layout.js': 3_000,
  'login-page.js': 600, 'admin-x-page.js': 140_000, 'portal-page.js': 1_000,
}
const MANIFEST = {
  pages: {
    '/layout': ['webpack.js', 'main-app.js', 'root.css', 'root-layout.js'],
    '/admin/layout': ['webpack.js', 'admin-layout.js'],
    '/sponsor/(portal)/layout': ['portal-layout.js'],
    '/login/page': ['webpack.js', 'main-app.js', 'shared.js', 'login-page.js'],
    '/admin/x/page': ['webpack.js', 'main-app.js', 'shared.js', 'admin-x-page.js'],
    '/sponsor/(portal)/home/page': ['webpack.js', 'main-app.js', 'portal-page.js'],
    '/page': ['webpack.js', 'main-app.js'],
  },
}
const sizeOf = (f: string) => SIZES[f]

describe('which manifest entries a printed route is made of', () => {
  test('a route group is not part of the printed route', () => {
    expect(routeOfEntry('/sponsor/(portal)/home/page')).toBe('/sponsor/home')
    expect(routeOfEntry('/admin/x/page')).toBe('/admin/x')
    expect(routeOfEntry('/page')).toBe('/')
  })

  test('every layout above a page, root first — the group layout included', () => {
    expect(layoutEntries('/admin/x/page', MANIFEST.pages)).toEqual(['/layout', '/admin/layout'])
    expect(layoutEntries('/sponsor/(portal)/home/page', MANIFEST.pages))
      .toEqual(['/layout', '/sponsor/(portal)/layout'])
    expect(layoutEntries('/login/page', MANIFEST.pages)).toEqual(['/layout'])
  })
})

describe('the two readings', () => {
  const readings = manifestReadings(MANIFEST, sizeOf)

  test('the PAGE figure is the page entry alone — what Next prints, in exact kB', () => {
    expect(readings.get('/login')?.page).toBeCloseTo(87.6, 6)
    expect(readings.get('/admin/x')?.page).toBeCloseTo(227, 6)
  })

  test('the FIRST-PAINT figure adds every layout, counts a shared chunk once and skips CSS', () => {
    // /login: page 87.6 + root layout's own 9.0 (webpack/main-app already counted; CSS skipped).
    expect(readings.get('/login')?.firstPaint).toBeCloseTo(96.6, 6)
    // /admin/x: + root layout 9.0 + admin layout 20.0.
    expect(readings.get('/admin/x')?.firstPaint).toBeCloseTo(256, 6)
    expect(readings.get('/sponsor/home')?.firstPaint).toBeCloseTo(83 + 9 + 3, 6)
  })
})

describe('the exact figure replaces the printed one only when they agree', () => {
  const readings = manifestReadings(MANIFEST, sizeOf)

  test('within the print\'s own rounding, the exact figure is budgeted', () => {
    const out = exactRoutes([{ route: '/admin/x', kb: 227 }, { route: '/login', kb: 87.6 }], readings)
    expect(out.map((r: { kb: number }) => r.kb)).toEqual([227, 87.6])
  })

  test('the rounding trap is gone: 272.6 exact is budgeted as 272.6, not the printed 273', () => {
    const r = new Map([['/a', { page: 272.6, firstPaint: 300 }]])
    expect(exactRoutes([{ route: '/a', kb: 273 }], r)[0].kb).toBe(272.6)
  })

  test('a manifest that disagrees with the print is REFUSED, never budgeted', () => {
    expect(() => exactRoutes([{ route: '/admin/x', kb: 240 }], readings))
      .toThrow(/does not match the route table/)
    expect(() => exactRoutes([{ route: '/gone', kb: 100 }], readings))
      .toThrow(/no page entry in the manifest/)
  })

  test('the tolerance is half the last printed digit', () => {
    expect(printTolerance(227)).toBe(0.5)
    expect(printTolerance(87.6)).toBe(0.05)
  })
})

/**
 * Consolidation Review 2026-10-06: three pushes passed here and were refused by the gate, whose
 * build reads ~0.06 kB heavier. A local run now fails with less than NEAR_LINE_KB of room.
 */
describe('the near-line check', () => {
  const LEDGER = { '/profile': 300, '/scholarship/application': 274 }

  test('a route with less than the margin of room is named; one with more is not', () => {
    // The shape of /profile 309.945 against 310, the push the gate refused at 310.007 (2026-10-05).
    const near = nearLine(new Map([['/profile', 299.945], ['/scholarship/application', 273.7]]),
      LEDGER, 228.0, 229)
    expect(near).toHaveLength(1)
    expect(near[0]).toMatch(/^\/profile: 299\.945 kB against its 300 kB line — 0\.055 kB of room$/)
  })

  test('the median is held to the same margin', () => {
    expect(nearLine(new Map(), {}, 228.9, 229)).toEqual(
      ['the median: 228.9 kB against its 229 kB line — 0.100 kB of room'])
    expect(nearLine(new Map(), {}, 228.0, 229)).toEqual([])
  })

  test('a route already OVER its line is not listed here — that is the failure above', () => {
    expect(nearLine(new Map([['/profile', 300.007]]), LEDGER, 228, 229)).toEqual([])
  })

  test('the margin covers the drift seen, and a freshly recorded line is never inside it', () => {
    // The gate read 0.062 kB heavier (2026-10-05). 0.15 is the floor recorded 2026-10-06 and a
    // ratchet: raise it (to 0.25 once TD-344 frees apply and application), never lower it.
    expect(NEAR_LINE_KB).toBeGreaterThanOrEqual(0.15)
    expect(NEAR_LINE_KB).toBeGreaterThan(2 * 0.062)
    // A line is recorded SHRINK_SLACK_KB over the build less the fraction (code-standards.json),
    // so it leaves at least SHRINK_SLACK_KB - 1 kB of room: the check must not fire on a fresh line.
    for (const build of [270.001, 272.655, 298.941, 299.999]) {
      const line = Math.floor(build) + SHRINK_SLACK_KB
      expect(nearLine(new Map([['/r', build]]), { '/r': line }, 0, 229)).toEqual([])
    }
  })

  test('⚠ only the deploy gate passes --gate; the one local command never does', () => {
    const web = path.resolve(__dirname, '../../..')
    const pkg = JSON.parse(fs.readFileSync(path.join(web, 'package.json'), 'utf8'))
    expect(pkg.scripts['bundle-budget']).not.toContain('--gate')
    expect(fs.readFileSync(path.join(web, 'cloudbuild.yaml'), 'utf8'))
      .toContain('npm run bundle-budget -- --gate')
  })
})
