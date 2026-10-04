/**
 * TD-304 (2026-10-04): the pure half of `scripts/bundle-budget.js` — how it maps the build's
 * `.next/app-build-manifest.json` onto the routes Next prints, and how it refuses to budget a
 * figure it cannot prove is the one Next printed.
 *
 * jest still cannot WEIGH anything (no build here); `npm run bundle-budget` does, in the deploy
 * gate. These rows hold the arithmetic the weighing relies on, on a synthetic manifest whose
 * chunk sizes are given rather than gzipped.
 */
import {
  exactRoutes, layoutEntries, manifestReadings, printTolerance, routeOfEntry,
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
