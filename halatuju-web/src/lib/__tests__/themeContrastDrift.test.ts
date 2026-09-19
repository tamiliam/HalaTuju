/**
 * THE DRIFT TEST for the theme and contrast mirrors — `branding.ts` and `contrast.ts`, named by
 * their `drift-test:` markers (code health H10).
 *
 * Three claims, and the reason they matter is the same in all three: **the browser's answer is a
 * courtesy, and a courtesy that disagrees with the server is worse than none at all.**
 *   • `TENANT_FAMILIES` — what a tenant may tint. If the web keeps a family the server refuses to
 *     store, the colour picker paints a preview that vanishes on save; if the web drops one the
 *     server allows, a tenant's own colour is silently not applied.
 *   • `PLATFORM_SURFACES` — the surfaces a colour is measured against. In light `white` and
 *     `ground-0` are the same; in dark they are nothing alike, which is exactly where a stale copy
 *     would stop being harmless.
 *   • The `PAIRS` table and the WCAG maths — the browser says "this colour is fine" as the person
 *     types, and then `apps/courses/contrast.py` refuses the save with a `400 unreadable`.
 *
 * Characterised first (the H8 rule): the pair table compared row by row (key, ink, surface, bar),
 * the surfaces compared per mode per channel, and the maths run on the three canonical rows the
 * api's own suite pins. They AGREE everywhere.
 */
import { applicableTokens, brandRamp } from '@/lib/branding'
import {
  PAIRS, AA_TEXT, AA_NON_TEXT, contrastRatio, relativeLuminance, checkColour,
} from '@/lib/contrast'
import { pySeq, readApi } from '@/test/apiSource'

const TOKENS = 'apps/courses/theme_tokens.py'
const CONTRAST = 'apps/courses/contrast.py'
const tokensSrc = readApi(TOKENS)
const contrastSrc = readApi(CONTRAST)

const tenantFamilies = pySeq(tokensSrc, 'TENANT_FAMILIES')
const platformFamilies = pySeq(tokensSrc, 'PLATFORM_FAMILIES')

/** `PLATFORM_SURFACES = {'light': {'white': (r, g, b), …}, 'dark': {…}}`, read as written. */
const backendSurfaces = (() => {
  const block = contrastSrc.match(/^PLATFORM_SURFACES\s*=\s*\{[\s\S]*?^\}/m)
  if (!block) throw new Error(`drift test: PLATFORM_SURFACES is no longer a dict literal in ${CONTRAST}`)
  const out: Record<string, Record<string, number[]>> = {}
  for (const line of block[0].split('\n')) {
    const mode = line.match(/^\s*'(light|dark)'\s*:/)
    if (!mode) continue
    const row: Record<string, number[]> = {}
    for (const m of line.matchAll(/'([a-z0-9-]+)'\s*:\s*\((\d+),\s*(\d+),\s*(\d+)\)/g)) {
      row[m[1]] = [Number(m[2]), Number(m[3]), Number(m[4])]
    }
    out[mode[1]] = row
  }
  return out
})()

/** `PAIRS = (Pair('key', 'ink', 'surface', BAR), …)` — the rows, in order. */
const backendPairs = (() => {
  const block = contrastSrc.match(/^PAIRS\s*=\s*\([\s\S]*?^\)/m)
  if (!block) throw new Error(`drift test: PAIRS is no longer a module-level tuple in ${CONTRAST}`)
  return [...block[0].matchAll(
    /Pair\(\s*'([a-z_]+)'\s*,\s*'([a-z0-9-]+)'\s*,\s*'([a-z0-9-]+)'\s*,\s*(AA_[A-Z_]+)\s*\)/g,
  )].map((m) => ({ key: m[1], ink: m[2], surface: m[3], bar: m[4] }))
})()

/**
 * The web writes a brand ramp step as a NUMBER (`ink: 700`) where the api writes the full token
 * (`'brand-700'`). Same reference, two notations, and neither side is wrong — so the comparison
 * normalises rather than demanding one side change.
 */
const asToken = (v: number | string) => (typeof v === 'number' ? `brand-${v}` : v)
const asBar = (min: number) => (min === AA_TEXT ? 'AA_TEXT' : min === AA_NON_TEXT ? 'AA_NON_TEXT' : `?${min}`)

describe('parse sanity — the api constants were really found', () => {
  test('the family allow-lists read as non-empty tuples', () => {
    expect(tenantFamilies.length).toBeGreaterThan(0)
    expect(platformFamilies).toContain('ground')
  })

  test('both modes of PLATFORM_SURFACES parsed, with three surfaces each', () => {
    expect(Object.keys(backendSurfaces).sort()).toEqual(['dark', 'light'])
    for (const mode of ['light', 'dark']) expect(Object.keys(backendSurfaces[mode]).length).toBe(3)
  })

  test('the pair table parsed every row', () => {
    expect(backendPairs.length).toBe(7)
    expect(backendPairs.map((p) => p.key)).toContain('ui_shape')
  })
})

describe('TENANT_FAMILIES — what a tenant may tint', () => {
  test('the web keeps exactly the families the server stores', () => {
    const tokens = {
      light: Object.fromEntries(
        [...tenantFamilies, ...platformFamilies].map((f) => [`${f}-500`, '1 2 3']),
      ),
      dark: Object.fromEntries(
        [...tenantFamilies, ...platformFamilies].map((f) => [`${f}-500`, '4 5 6']),
      ),
    }
    const kept = applicableTokens(tokens)
    expect(kept).not.toBeNull()
    const families = [...new Set(Object.keys(kept!.light).map((k) => k.split('-')[0]))].sort()
    expect(families).toEqual([...tenantFamilies].sort())
  })

  test('not one platform family survives the filter — red must keep meaning "broken"', () => {
    const kept = applicableTokens({
      light: Object.fromEntries(platformFamilies.map((f) => [`${f}-500`, '1 2 3'])),
      dark: {},
    })
    expect(Object.keys(kept?.light || {})).toEqual([])
  })

  test('the two api lists do not overlap — a family cannot be both', () => {
    expect(tenantFamilies.filter((f) => platformFamilies.includes(f))).toEqual([])
  })
})

describe('PLATFORM_SURFACES — the surfaces a colour is measured against', () => {
  /**
   * `SURFACES` is module-private in `contrast.ts` on purpose, so this reads it the way the product
   * does — through `checkColour`, whose reported ratio is the ink against the surface. Rebuilding
   * that ratio from the API's OWN surface RGB and the web's own ramp means a surface that differed
   * by a single channel would move the number the screen shows.
   */
  test.each(['light', 'dark'] as const)('%s: every pair measures against the api\'s surface', (mode) => {
    const HEX = '#137fec'            // the platform brand — the one colour both suites use
    const ramp = brandRamp(HEX, mode)
    const rows = checkColour(HEX, mode)
    let compared = 0
    for (const pair of PAIRS) {
      const surfaceRgb = backendSurfaces[mode][pair.surface as string]
      if (!surfaceRgb || typeof pair.ink !== 'number') continue   // only ramp-ink × platform-surface
      const ink = ramp[pair.ink].split(' ').map(Number) as [number, number, number]
      const expected = Math.round(
        contrastRatio(ink, surfaceRgb as [number, number, number]) * 100) / 100
      expect(rows.find((r) => r.key === pair.key)!.ratio).toBe(expected)
      compared += 1
    }
    // Parse sanity: if the pair table stops carrying a ramp-ink-on-platform-surface row, this test
    // would pass vacuously. It must compare at least the two link rows.
    expect(compared).toBeGreaterThanOrEqual(2)
  })

  test('light and dark really do differ, so a per-mode table is not ceremony', () => {
    expect(backendSurfaces.light['ground-0']).toEqual([255, 255, 255])
    expect(backendSurfaces.dark['ground-0']).not.toEqual(backendSurfaces.light['ground-0'])
    // `white` is the same in both — the reason it is a separate entry from `ground-0` at all.
    expect(backendSurfaces.dark.white).toEqual(backendSurfaces.light.white)
  })
})

describe('the PAIRS table — what the browser checks and what the server refuses on', () => {
  test('the same rows, in the same order, with the same ink, surface and bar', () => {
    expect(PAIRS.map((p) => ({
      key: p.key, ink: asToken(p.ink), surface: asToken(p.surface), bar: asBar(p.min),
    }))).toEqual(backendPairs)
  })

  test('the two bars are WCAG\'s, and the api names them the same way', () => {
    expect(AA_TEXT).toBe(4.5)
    expect(AA_NON_TEXT).toBe(3.0)
    expect(contrastSrc).toMatch(/^AA_TEXT\s*=\s*4\.5/m)
    expect(contrastSrc).toMatch(/^AA_NON_TEXT\s*=\s*3\.0/m)
  })

  test('`ui_shape` is the only non-text row — moving it would refuse the platform\'s own colour', () => {
    const nonText = backendPairs.filter((p) => p.bar === 'AA_NON_TEXT').map((p) => p.key)
    expect(nonText.sort()).toEqual(['filled_button_visible', 'ui_shape'])
    expect(PAIRS.filter((p) => p.min === AA_NON_TEXT).map((p) => p.key).sort())
      .toEqual(nonText.sort())
  })
})

describe('the WCAG maths — the three rows the api\'s own suite pins', () => {
  // `apps/courses/tests/test_contrast.py::TestTheMaths`. Same inputs, same expected values, so a
  // change to either implementation fails on the side that drifted.
  test('the two ratios everybody knows', () => {
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21.0, 4)
    expect(contrastRatio([255, 255, 255], [255, 255, 255])).toBeCloseTo(1.0, 4)
  })

  test('it is symmetric — order never matters', () => {
    expect(contrastRatio([19, 127, 236], [255, 255, 255]))
      .toBe(contrastRatio([255, 255, 255], [19, 127, 236]))
  })

  test('the linearisation uses the low branch for a very dark channel', () => {
    expect(relativeLuminance([0, 0, 0])).toBeCloseTo(0, 6)
    // 0.2126 + 0.7152 + 0.0722 = 1, so a grey channel of 10 lands on the low branch exactly.
    expect(relativeLuminance([10, 10, 10])).toBeCloseTo(10 / 255 / 12.92, 6)
    expect(contrastSrc).toMatch(/0\.03928/)
  })
})
