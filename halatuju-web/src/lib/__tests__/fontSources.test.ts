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
import tailwindConfig from '../../../tailwind.config'

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
const VARIABLES = ['--font-lexend', '--font-inter', '--font-ibm-plex-sans', '--font-tamil']

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
  // Mobile M1a: the TAMIL subset of Mukta Malar, byte-identical to SJKTConnect's
  // frontend/app/fonts/mukta-malar/ (owner, 2026-10-31).
  'src/fonts/mukta-malar/MuktaMalar-Tamil-400.woff2':
    '0d7af641f651bcb741e2a45fb53f46a5032ae1b1f7bb4c268866f73baf9ae66c',
  'src/fonts/mukta-malar/MuktaMalar-Tamil-600.woff2':
    'ffa2f0f9e2c5be8d70405238eee090352abe1ac1a16dcc2692379f3ffccf32fd',
  'src/fonts/mukta-malar/MuktaMalar-Tamil-700.woff2':
    'a3007075cf034e8483430b28326d6a10266fb9fc6d420ba60f97e459a47ec475',
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
    const calls = floorCount(layout.match(/=\s*localFont\(\{/g) || [], 4, 'localFont() calls',
      'Lexend, Inter, IBM Plex Sans and (since Mobile M1a) Mukta Malar are each declared once')
    expect(calls).toHaveLength(4)
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

/**
 * TD-310 (2026-09-29): the product said Lexend for months and painted system-ui. Tailwind's
 * `font-sans` began with the plain name 'Lexend', which nothing on the page provides (next/font
 * registers the face as `__Lexend_<hash>` behind `--font-lexend`), and the Google `@import` meant
 * to supply the plain name sat after other rules, where every browser ignores it. Both halves
 * read as correct in review. These tests pin the working shape.
 */
describe('Lexend actually paints (TD-310)', () => {
  const GLOBALS = 'src/app/globals.css'
  const globals = readWeb(GLOBALS, 'the stylesheet that once imported Lexend from Google, dead')

  it('font-sans leads with the self-hosted variable, not a family name nothing provides', () => {
    const families = tailwindConfig.theme?.extend?.fontFamily as Record<string, string[]>
    // Mobile M1a: the Tamil face comes first — it is Tamil-only (unicode-range), so Latin still
    // reaches Lexend second. Lexend must stay the first LATIN face.
    expect(families.sans.slice(0, 2)).toEqual(['var(--font-tamil)', 'var(--font-lexend)'])
  })

  it('the base html rule reads the same stack from the config', () => {
    expect(globals).toMatch(/html\s*\{[^}]*font-family:\s*theme\('fontFamily\.sans'\)/)
  })

  it('no stylesheet or source file imports a font from Google at run time', () => {
    const files = walkFloor(path.join(WEB_ROOT, 'src'), 500,
      'every source file is scanned for a Google Fonts @import or <link> (TD-310)',
      { exts: ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.css'] })
    // Assembled, not written whole, so this file does not match its own scan.
    const host = ['fonts', 'googleapis', 'com'].join('\\.')
    const re = new RegExp(`@import\\s+url\\(\\s*['"]?https?://${host}|href=['"{]\\s*['"\`]?https?://${host}`)
    const offenders = files
      .filter((f) => re.test(fs.readFileSync(f, 'utf8')))
      .map((f) => path.relative(WEB_ROOT, f).split(path.sep).join('/'))
    expect(offenders).toEqual([])
  })

  it('money columns paint in a face with tabular figures, because Lexend has none', () => {
    // Lexend's GSUB has no `tnum` and its digits are 500–620 units wide; Plex's are all 600.
    expect(globals).toMatch(/--figures-face:\s*var\(--font-tamil\),\s*var\(--font-ibm-plex-sans\)/)
    expect(globals).toMatch(/\.tabular-nums:not\(\.font-mono\)\s*\{\s*font-family:\s*var\(--figures-face\);\s*\}/)
    // The sponsor portal is on Inter, which HAS tabular figures — it keeps its own face.
    const sponsor = readWeb('src/app/sponsor/(portal)/layout.tsx',
      'the sponsor portal sets its figures face to Inter')
    expect(sponsor).toMatch(/'--figures-face': 'var\(--font-tamil\), var\(--font-inter\)/)
  })
})

describe('the CSS variables the product paints with are still declared', () => {
  it.each(VARIABLES)('%s is declared', (name) => {
    expect(layout).toContain(`variable: '${name}'`)
  })

  it('applies all four to <html>', () => {
    expect(layout).toMatch(
      /className=\{`\$\{Lexend\.variable\} \$\{Inter\.variable\} \$\{IBM_Plex_Sans\.variable\} \$\{Mukta_Malar\.variable\}`\}/)
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

/**
 * Mobile M1a (owner, 2026-10-31): Tamil paints in Mukta Malar on every device. Each option below
 * is load-bearing — drop one and either English text changes face or English pages download Tamil:
 * the unicode-range keeps the face off Latin letters and digits, `preload: false` keeps English
 * pages from fetching it, and `fallback: []` + `adjustFontFallback: false` stop next/font adding an
 * UN-ranged fallback face that would sit first in the stack and restyle English. Measured in the
 * browser (CHANGELOG Mobile M1a): Tamil glyphs render in Mukta Malar, Latin in Lexend, and an
 * English page requests no Mukta file.
 */
describe('Tamil paints in Mukta Malar, and only Tamil (Mobile M1a)', () => {
  const block = (layout.match(/const Mukta_Malar = localFont\(\{([\s\S]*?)\n\}\)/) ?? ['', ''])[1]

  it('is declared Tamil-only, never preloaded, with no fallback face', () => {
    expect(block).not.toBe('')
    expect(block).toContain("variable: '--font-tamil'")
    expect(block).toMatch(/preload: false/)
    expect(block).toMatch(/fallback: \[\]/)
    expect(block).toMatch(/adjustFontFallback: false/)
    expect(block).toContain("{ prop: 'unicode-range', value: 'U+0964-0965, U+0B82-0BFA, U+200C-200D, U+25CC' }")
  })

  it('sits first in every stack the product paints with', () => {
    const families = tailwindConfig.theme?.extend?.fontFamily as Record<string, string[]>
    expect(families.sans[0]).toBe('var(--font-tamil)')
    expect(families.plex[0]).toBe('var(--font-tamil)')
    const sponsor = readWeb('src/app/sponsor/(portal)/layout.tsx', 'the sponsor portal sets its own stack')
    expect(sponsor).toMatch(/fontFamily: 'var\(--font-tamil\), var\(--font-inter\)/)
  })
})
