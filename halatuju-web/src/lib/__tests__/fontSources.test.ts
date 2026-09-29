/**
 * Static guard: a build needs NOTHING from Google Fonts (TD-305, 2026-09-29).
 *
 * The failure it prevents. `src/app/layout.tsx` loaded Lexend, Inter and IBM Plex Sans through
 * next/font's Google loader, which DOWNLOADS the font CSS and files inside `next build`. On
 * 2026-09-29 Google answered with something malformed, the loader's regex found no match, and the
 * Docker `Build` step died with `Cannot read properties of null (reading '1')` — every gate green,
 * a change that touched no font, ~12 build minutes lost, and an error that read like a code fault.
 * The fonts are now committed under `src/fonts/` and loaded with `next/font/local`.
 *
 * What this proves: no source file imports the Google loader; every font file the layout names is
 * present, is a real woff2, and is the exact audited byte-for-byte file (SHA-256 below, also in
 * src/fonts/README.md); the three CSS variables the product paints with are still declared; and
 * every `var(--font-…)` used anywhere resolves to one of them.
 *
 * What it does NOT prove: that the build succeeds offline (that was proved once, by hand, with the
 * network to Google blocked — see CHANGELOG TD-305), or how the text looks. A build that cannot
 * find a named file fails on its own, loudly; this guard exists so the same mistake goes red in
 * jest, seconds in, instead of minutes into a Cloud Build.
 */
import * as crypto from 'crypto'
import * as fs from 'fs'
import * as path from 'path'
import { WEB_ROOT, floorCount, readWeb, walkFloor } from '@/test/sourceGuard'

const LAYOUT = 'src/app/layout.tsx'
const layout = readWeb(LAYOUT,
  'the root layout declares the three self-hosted fonts; TD-305 moved them off the Google loader '
  + 'because a Google hiccup failed a deploy')

// Assembled, not written whole, so this file does not match its own scan.
const GOOGLE_LOADER = ['next', 'font', 'google'].join('/')

/**
 * The CSS variables the layout declared BEFORE TD-305, pinned as literals on purpose: the whole
 * product reaches the fonts through these names (`font-plex` in tailwind.config.ts, the sponsor
 * portal's inline style), so renaming one silently drops that surface to the fallback stack.
 */
const VARIABLES = ['--font-lexend', '--font-inter', '--font-ibm-plex-sans']

/**
 * The audited files: the latin subset each family was served as by the Google loader on
 * 2026-09-29 (byte-identical to what that build emitted). A different file here is a different
 * font on screen — replace it deliberately, update the hash and the README together.
 */
const FONT_FILES: Record<string, string> = {
  'src/fonts/lexend/lexend-latin-wght.woff2':
    '1ec8f6ee2750554b4bc59ff0b507d316a82a7ba37e0e5bebc41d3bd9b9faad46',
  'src/fonts/inter/inter-latin-wght.woff2':
    'c940764593d0fe5d596be327ca7558855e018039fb78509aa21921fd3644c3e4',
  'src/fonts/ibm-plex-sans/ibm-plex-sans-latin-wght.woff2':
    '056e4e2459f57a0033c8c9c844ff19d6e42ac8602027803d4345823bcc939818',
}

describe('the build fetches no fonts from Google', () => {
  it('no source file imports the Google font loader', () => {
    const files = walkFloor(path.join(WEB_ROOT, 'src'), 500,
      'every source file is scanned for an import of the Google font loader (TD-305)',
      { exts: ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.css'] })
    const importRe = new RegExp(
      `(?:from|import|require\\()\\s*['"]@?${GOOGLE_LOADER.replace(/\//g, '\\/')}['"]`)
    const offenders = files
      .filter((f) => importRe.test(fs.readFileSync(f, 'utf8')))
      .map((f) => path.relative(WEB_ROOT, f).split(path.sep).join('/'))
    expect(offenders).toEqual([])
  })

  it('the layout loads its fonts with next/font/local', () => {
    expect(layout).toMatch(/import localFont from 'next\/font\/local'/)
    const calls = floorCount(layout.match(/=\s*localFont\(\{/g) || [], 3, 'localFont() calls',
      'Lexend, Inter and IBM Plex Sans are each declared once in the root layout')
    expect(calls).toHaveLength(3)
  })
})

describe('every font file the layout names is present and audited', () => {
  // Every `'../fonts/…woff2'` literal in the layout, resolved the way next/font/local resolves it:
  // relative to the file that calls it.
  const named = floorCount(
    Array.from(new Set(Array.from(layout.matchAll(/'(\.\.\/fonts\/[^']+\.woff2)'/g), (m) => m[1]))),
    3, 'font file paths in the layout', 'each of the three families names its woff2 file')

  it.each(named)('%s exists, is a woff2, and is the audited file', (rel) => {
    const webRel = path.posix.join('src/app', rel)
    const full = path.join(WEB_ROOT, ...webRel.split('/'))
    expect(fs.existsSync(full)).toBe(true)
    const bytes = fs.readFileSync(full)
    expect(bytes.subarray(0, 4).toString('latin1')).toBe('wOF2')
    expect(Object.keys(FONT_FILES)).toContain(webRel)
    expect(crypto.createHash('sha256').update(bytes).digest('hex')).toBe(FONT_FILES[webRel])
  })

  it('names every audited file, and each family carries its licence', () => {
    for (const file of Object.keys(FONT_FILES)) {
      expect(named.map((r) => path.posix.join('src/app', r))).toContain(file)
      const licence = path.join(WEB_ROOT, ...path.posix.dirname(file).split('/'), 'OFL.txt')
      expect(fs.readFileSync(licence, 'utf8')).toMatch(/SIL Open Font License, Version 1\.1/)
    }
  })

  it('declares the two variable fonts over their full weight range', () => {
    // Without `weight: '100 900'` the @font-face says 400 only and the browser FAKES every bold
    // on the sponsor portal instead of using the font's own weights.
    expect((layout.match(/weight: '100 900'/g) || []).length).toBe(2)
  })
})

describe('the CSS variables the product paints with are still declared', () => {
  it.each(VARIABLES)('%s is declared', (name) => {
    expect(layout).toContain(`variable: '${name}'`)
  })

  it('applies all three to <html>', () => {
    expect(layout).toMatch(
      /className=\{`\$\{Lexend\.variable\} \$\{Inter\.variable\} \$\{IBM_Plex_Sans\.variable\}`\}/)
  })

  it('every var(--font-…) used in the tree is one the layout declares', () => {
    const files = [
      ...walkFloor(path.join(WEB_ROOT, 'src'), 500, 'every var(--font-…) consumer is checked',
        { exts: ['.ts', '.tsx', '.css'] }),
      path.join(WEB_ROOT, 'tailwind.config.ts'),
    ]
    const used = new Set<string>()
    for (const f of files) {
      for (const m of fs.readFileSync(f, 'utf8').matchAll(/var\((--font-[a-z0-9-]+)\)/g)) {
        used.add(m[1])
      }
    }
    // Two consumers on 2026-09-29: tailwind's `font-plex` and the sponsor portal's Inter.
    floorCount(Array.from(used), 2, 'var(--font-…) consumers',
      'the admin modules and the sponsor portal reach their fonts through these variables')
    // Against what the layout ACTUALLY declares, not the pinned list, so a rename on either side
    // leaves a consumer pointing at nothing and goes red here too.
    const declared = Array.from(layout.matchAll(/variable: '(--font-[a-z0-9-]+)'/g), (m) => m[1])
    for (const name of Array.from(used)) expect(declared).toContain(name)
  })
})
