/**
 * The Mobile Standard's static guards (Mobile M0, 2026-10-31). The rules: `docs/mobile-standard.md`.
 *
 * Students use HalaTuju on phones almost all the time. Each block below counts how often the code
 * breaks one rule that can be read from source, and holds that count to a FLOOR.
 *
 * ⚠ EVERY FLOOR IS A RATCHET THAT MAY ONLY GO DOWN. It is today's exact count of offenders, not a
 * target. When you fix one, the count drops below the floor and this suite tells you to LOWER the
 * number — do it in the same change, so the room you made cannot be spent by the next person. Never
 * RAISE a floor: a new offender is fixed, not counted. (The same rule `code-standards.json` keeps.)
 * Every failure prints the offenders, so you can see exactly which line to change.
 *
 * What is scanned: every `.ts`/`.tsx` under `src/`, less
 *   - tests (`__tests__/`, `*.test.*`) and `src/test/` — they hold examples of the very patterns
 *     they forbid;
 *   - the design sandbox (`src/sandbox/`, `*.sandbox.tsx`) — compiled OUT of production
 *     (next.config.js), and its picker chrome is not a product screen. The REAL screens it mounts
 *     are scanned where they live.
 *
 * What a source scan cannot see — inherited font sizes, computed tap sizes, real overflow — the
 * browser check `npm run mobile-check` measures. The reader's own limits are in `src/test/mobileScan.ts`.
 */
import * as fs from 'fs'
import * as path from 'path'
import { readWeb, walkFloor, WEB_ROOT } from '@/test/sourceGuard'
import {
  attr, classText, constResolver, literalsIn, openTags, scanFiles, tokens, where,
  type Offender, type Scanned,
} from '@/test/mobileScan'
import { MOBILE_CLASS, routeOfPage } from '@/lib/mobileClass'

// ── The corpus ────────────────────────────────────────────────────────────────────────────────
/** 627 `.ts`/`.tsx` files under src/ on 2026-10-31; a MINIMUM, so new files stay green. */
const WHY_SRC = 'every rule below counts offenders across the whole web source; a walk that found '
  + 'nothing would count zero and pass for ever'
const ALL = walkFloor(path.join(WEB_ROOT, 'src'), 600, WHY_SRC, { exts: ['.ts', '.tsx'] })
const isExcluded = (rel: string) => /(^|\/)__tests__\//.test(rel) || /\.test\.tsx?$/.test(rel)
  || rel.startsWith('src/test/') || rel.startsWith('src/sandbox/') || rel.endsWith('.sandbox.tsx')
const FILES: Scanned[] = scanFiles(ALL).filter((f) => !isExcluded(f.rel))
const TSX = FILES.filter((f) => f.rel.endsWith('.tsx'))
const resolve = constResolver(FILES)

/** The assertion every ratchet shares: at or under the floor, with the offenders in the message. */
function ratchet(name: string, offenders: Offender[], floor: number): void {
  const n = offenders.length
  const listing = offenders.map((o) => `    ${o}`).join('\n')
  if (n > floor) {
    throw new Error(`${name}: ${n} found, the floor is ${floor}. A NEW offender — fix it, never `
      + `raise the floor (docs/mobile-standard.md says how).\n${listing}`)
  }
  if (n < floor) {
    throw new Error(`${name}: ${n} found, the floor is ${floor}. You fixed some — LOWER the floor `
      + `in mobileStandard.test.ts to ${n} in this same change, so the room cannot be re-spent.\n${listing}`)
  }
}

/** Every string literal in a file's code, with where it starts (comments are already blank). */
function literalsWithIndex(file: Scanned): Array<{ text: string; index: number }> {
  const out: Array<{ text: string; index: number }> = []
  for (const m of Array.from(file.code.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g))) {
    for (const text of literalsIn(m[0])) out.push({ text, index: m.index ?? 0 })
  }
  return out
}

describe('the corpus this file depends on is really there', () => {
  test('hundreds of source files, most of them components', () => {
    expect(FILES.length).toBeGreaterThanOrEqual(500)
    expect(TSX.length).toBeGreaterThanOrEqual(300)
  })
})

// ── Rule 2: text fields at 16 px on phones ────────────────────────────────────────────────────
/**
 * A text field under 16 px makes iPhone Safari ZOOM THE PAGE when it is tapped, and the page stays
 * zoomed. `md:text-sm` (tablet up) is fine; an UNPREFIXED `text-sm`, `text-xs` or `text-[<16px]`
 * on a text-entry control is the offence. Checkboxes, radios, hidden, file, range and button-like
 * inputs take no typing and are skipped; an `type={…}` expression counts as text unless every
 * literal in it is one of those.
 *
 * ⚠ LIMITS (best effort, stable, honest). A control with NO size class inherits its parent's size
 * (Tailwind's preflight sets `font-size: 100%`), which only the browser check can see. A class
 * built from props or a constant the reader cannot resolve is not judged.
 */
const NOT_TEXT = new Set(['checkbox', 'radio', 'hidden', 'file', 'range', 'color', 'submit', 'button',
  'reset', 'image'])

function smallTextToken(cls: string[]): string | undefined {
  return cls.find((t) => {
    if (t === 'text-xs' || t === 'text-sm') return true
    const m = t.match(/^text-\[(\d*\.?\d+)(px|rem|em)\]$/)
    if (!m) return false
    const n = parseFloat(m[1])
    return m[2] === 'px' ? n < 16 : n < 1
  })
}

function isTextEntry(tag: { name: string; attrs: string }): boolean {
  if (tag.name !== 'input') return true
  const type = attr(tag.attrs, 'type')
  if (!type) return true
  if ('literal' in type) return !NOT_TEXT.has(type.literal)
  const lits = literalsIn(type.expr)
  return !(lits.length > 0 && lits.every((l) => NOT_TEXT.has(l)))
}

describe('rule 2 — text fields are 16 px on phones (no iOS zoom)', () => {
  const controls = TSX.flatMap((f) => ['input', 'select', 'textarea']
    .flatMap((name) => openTags(f.code, name).map((tag) => ({ f, tag }))))
    .filter(({ tag }) => isTextEntry(tag))

  test('the reader finds the text-entry controls at all', () => {
    // ~300 on 2026-10-31. A reader that stopped finding tags would report no offenders.
    expect(controls.length).toBeGreaterThanOrEqual(250)
  })

  test('small-text text fields: at or under the floor', () => {
    const offenders = controls.flatMap(({ f, tag }) => {
      const small = smallTextToken(tokens(classText(f, tag, resolve)))
      return small ? [where(f, tag.start, `<${tag.name} … ${small}`)] : []
    })
    ratchet('text fields with an unprefixed small font', offenders, 182)
  })
})

// ── Rule 9: file inputs are sr-only, never hidden ─────────────────────────────────────────────
/**
 * Some phone browsers will not open the picker for a `display: none` input when its label is
 * tapped. `sr-only` keeps it in the layout, invisible — the pattern in
 * `src/components/ScholarshipDocuments/cards.tsx`. Counts `type="file"` inputs whose class carries
 * `hidden` (unprefixed).
 */
describe('rule 9 — file inputs are sr-only, never hidden', () => {
  test('hidden file inputs: at or under the floor', () => {
    const files = TSX.flatMap((f) => openTags(f.code, 'input').map((tag) => ({ f, tag })))
      .filter(({ tag }) => {
        const type = attr(tag.attrs, 'type')
        return !!type && 'literal' in type && type.literal === 'file'
      })
    expect(files.length).toBeGreaterThanOrEqual(5)
    const offenders = files
      .filter(({ f, tag }) => tokens(classText(f, tag, resolve)).includes('hidden'))
      .map(({ f, tag }) => where(f, tag.start, '<input type="file" … hidden'))
    ratchet('file inputs hidden with `hidden`', offenders, 6)
  })
})

// ── Rule 5: one shared Sheet, no hand-rolled overlays ─────────────────────────────────────────
/**
 * Every hand-rolled `fixed inset-0` overlay re-decides max height, inner scroll, the close target and
 * the safe area — and several decided wrong (buttons hidden behind the iPhone keyboard). M1 builds
 * the shared `Sheet`; it will be the one allowed home and goes in `OVERLAY_HOMES`. Counted per class
 * string holding both tokens, in `.ts` and `.tsx`.
 */
const OVERLAY_HOMES: string[] = []

describe('rule 5 — overlays come from the shared Sheet', () => {
  test('hand-rolled fixed inset-0 overlays: at or under the floor', () => {
    const offenders = FILES.filter((f) => !OVERLAY_HOMES.includes(f.rel))
      .flatMap((f) => literalsWithIndex(f)
        .filter(({ text }) => tokens(text).includes('fixed') && tokens(text).includes('inset-0'))
        .map(({ index }) => where(f, index, 'fixed inset-0')))
    ratchet('hand-rolled `fixed inset-0` overlays', offenders, 18)
  })
})

// ── Rule 6: dvh, never vh ─────────────────────────────────────────────────────────────────────
/**
 * On iPhone `100vh` is the height with the address bar HIDDEN, so a `vh` box is taller than the
 * screen while the bar shows and its bottom (often the main button) sits off-screen. `dvh` follows
 * the bar. Counted: a height utility with a `vh` value (`h-[70vh]`, `max-h-[90vh]`, `min-h-[80vh]`),
 * `h-screen` and `max-h-screen`, and a bare `NNvh` / `calc(…vh…)` string (an inline style). A `vh`
 * PADDING or offset (`pt-[12vh]`) is not counted: it moves a box a little, it does not make one
 * taller than the visible screen, which is the bug.
 *
 * `min-h-screen` is counted SEPARATELY, with its own floor: as a minimum it only makes a page at
 * least a screen tall, which is mostly harmless (the page scrolls), but it still over-measures on
 * iPhone and belongs on `min-h-dvh` in time.
 */
const VH_TOKEN = /^(?:[\w-]+:)*(?:(?:h|max-h)-screen|(?:h|min-h|max-h)-\[[^\]]*\dvh[^\]]*\])$/
const VH_STYLE = /^(?:\d*\.?\d+vh|calc\(.*\dvh.*\))$/
const MIN_SCREEN = /^(?:[\w-]+:)*min-h-screen$/

describe('rule 6 — heights use dvh, never vh', () => {
  test('vh heights: at or under the floor', () => {
    const offenders = FILES.flatMap((f) => literalsWithIndex(f).flatMap(({ text, index }) => {
      const hits = tokens(text).filter((t) => VH_TOKEN.test(t) || VH_STYLE.test(t))
      return hits.map((t) => where(f, index, t))
    }))
    ratchet('vh-based heights', offenders, 3)
  })

  test('min-h-screen: at or under its own floor', () => {
    const offenders = FILES.flatMap((f) => literalsWithIndex(f).flatMap(({ text, index }) =>
      tokens(text).filter((t) => MIN_SCREEN.test(t)).map((t) => where(f, index, t))))
    ratchet('min-h-screen', offenders, 71)
  })
})

// ── Rule 4: no hover-only explanation on an icon-only control ─────────────────────────────────
/**
 * A phone has no hover, so a `title=` tooltip is never seen there. On a control with words it is
 * a spare; on an ICON-ONLY control it is the only explanation, and the tap target is a mystery.
 * Counted: `<button>`, `<a>` and `<Link>` that carry `title=` and whose content has no words.
 *
 * ⚠ BEST EFFORT, AND WHICH WAY IT LEANS. "No words" means: once `<svg>…</svg>` and every tag are
 * removed, no letters or digits remain, and every `{…}` left holds JSX (an icon) rather than a
 * value. An expression the reader cannot judge (`{label}`) is taken to be words — so this UNDER-
 * counts rather than over-counts. `role="button"` elements and custom components are not seen.
 */
function contentOf(code: string, tag: { name: string; end: number; selfClosing: boolean }): string {
  if (tag.selfClosing) return ''
  const close = code.indexOf(`</${tag.name}>`, tag.end)
  return close === -1 ? '' : code.slice(tag.end + 1, close)
}

function isIconOnly(content: string): boolean {
  const noSvg = content.replace(/<svg[\s\S]*?<\/svg>/g, ' ')
  const exprs: string[] = []
  // Pull out top-level `{…}` expressions, then strip tags from what is left.
  let rest = ''
  let depth = 0
  let cur = ''
  for (const c of noSvg) {
    if (c === '{') { if (depth === 0) cur = ''; else cur += c; depth++; continue }
    if (c === '}') { depth--; if (depth === 0) exprs.push(cur); else cur += c; continue }
    if (depth > 0) cur += c
    else rest += c
  }
  const text = rest.replace(/<[^>]*>/g, ' ').replace(/&[a-z]+;|&#\d+;/g, ' ')
  if (/[\p{L}\p{N}]/u.test(text)) return false
  return exprs.every((e) => !e.trim() || (/</.test(e) && !/'[^']*'|"[^"]*"|\bt\(/.test(e)))
}

describe('rule 4 — no title= as the only explanation on an icon-only control', () => {
  test('icon-only controls explained only by title=: at or under the floor', () => {
    const offenders = TSX.flatMap((f) => ['button', 'a', 'Link'].flatMap((name) =>
      openTags(f.code, name)
        .filter((tag) => /(?:^|\s)title=/.test(tag.attrs))
        .filter((tag) => isIconOnly(contentOf(f.code, tag)))
        .map((tag) => where(f, tag.start, `<${name} title=… (icon only)`))))
    ratchet('icon-only controls with title=', offenders, 7)
  })
})

// ── The viewport: safe areas on, zoom never off ───────────────────────────────────────────────
describe('the root layout sets the phone viewport', () => {
  const layout = readWeb('src/app/layout.tsx',
    'the viewport export lives in the root layout; Next only reads it from a layout or page')
  const block = (layout.match(/export const viewport[^=]*=\s*\{([\s\S]*?)\n\}/) ?? ['', ''])[1]

  test('exports `viewport` with viewportFit cover, so env(safe-area-inset-*) works', () => {
    expect(block).not.toBe('')
    expect(block).toMatch(/viewportFit:\s*'cover'/)
    expect(block).toMatch(/width:\s*'device-width'/)
    expect(block).toMatch(/initialScale:\s*1\b/)
  })

  test('never blocks zoom — a person who needs bigger text must be able to pinch', () => {
    expect(block).not.toMatch(/maximumScale|userScalable/)
  })

  test('the browser-bar colours are the header’s own token, --ground-0, in each mode', () => {
    // A hex here would fail the theme guard; an `rgb()` that drifted from the token would not, so
    // the two are compared. Light is the `:root` block, dark the `[data-theme='dark']` block.
    const css = readWeb('src/app/globals.css', 'the colour tokens the theme colour must equal')
    const dark = css.indexOf("[data-theme='dark']")
    const token = (from: number) => (css.slice(from).match(/--ground-0:\s*([\d ]+);/) ?? ['', ''])[1].trim()
    expect(block).toContain(`'(prefers-color-scheme: light)', color: 'rgb(${token(0)})'`)
    expect(block).toContain(`'(prefers-color-scheme: dark)', color: 'rgb(${token(dark)})'`)
  })
})

// ── The home-screen app: a manifest and real icons, nothing more ──────────────────────────────
describe('HalaTuju installs as a home-screen app', () => {
  /** A PNG's width and height, from its IHDR chunk (bytes 16–23). */
  const pngSize = (rel: string): string => {
    const buf = fs.readFileSync(path.join(WEB_ROOT, ...rel.split('/')))
    return `${buf.readUInt32BE(16)}x${buf.readUInt32BE(20)}`
  }
  const manifest = readWeb('src/app/manifest.ts', 'Next serves the web app manifest from this file')

  // 'browser' until M8: an iPhone standalone app has no back button and storage apart from Safari,
  // so a sign-in link would land in Safari and the app would never see it (see manifest.ts).
  test('the manifest opens in the browser, not standalone, at the home page', () => {
    expect(manifest).toMatch(/display:\s*'browser'/)
    expect(manifest).toMatch(/start_url:\s*'\/'/)
  })

  test('every icon the manifest names is on disk, at the size it claims', () => {
    const icons = Array.from(manifest.matchAll(/src:\s*'([^']+)',\s*sizes:\s*'([^']+)'/g), (m) => [m[1], m[2]])
    expect(icons.length).toBeGreaterThanOrEqual(3)
    expect(manifest).toMatch(/purpose:\s*'maskable'/)
    for (const [src, sizes] of icons) expect(`${src} ${pngSize(`public${src}`)}`).toBe(`${src} ${sizes}`)
  })

  test('the iPhone home-screen icon is 180 px', () => {
    expect(pngSize('src/app/apple-icon.png')).toBe('180x180')
  })

  test('no service worker — an installed HalaTuju is the live site, never a stale copy', () => {
    const sw = FILES.filter((f) => /serviceWorker\.register|navigator\.serviceWorker/.test(f.code))
    expect(sw.map((f) => f.rel)).toEqual([])
  })
})

// ── Every route is classed (the ledger's source) ──────────────────────────────────────────────
/**
 * ⚠ A CLOSED SET, ON PURPOSE. `src/lib/mobileClass.ts` must name every `page.tsx` route and nothing
 * else. One extra file IS the defect here: a new page with no class has had nobody decide whether
 * a phone may see it, and a stale entry keeps a ledger row for a screen that no longer exists.
 * `page.sandbox.tsx` is not a route in production and is not classed.
 */
describe('every route has a phone class', () => {
  const APP = path.join(WEB_ROOT, 'src', 'app')
  const pages = walkFloor(APP, 90, 'every page.tsx is a route that must carry a phone class; 93 '
    + 'routes on 2026-10-31', { exts: ['page.tsx'] })
    .filter((full) => path.basename(full) === 'page.tsx')
    .map((full) => routeOfPage(path.relative(APP, full).split(path.sep).join('/')))
    .sort()

  test('the classification and the pages on disk are the same set', () => {
    const classed = Object.keys(MOBILE_CLASS).sort()
    expect({ unclassed: pages.filter((r) => !(r in MOBILE_CLASS)),
      stale: classed.filter((r) => !pages.includes(r)) })
      .toEqual({ unclassed: [], stale: [] })
  })

  test('every desktop-only route says why, in words', () => {
    for (const [route, e] of Object.entries(MOBILE_CLASS)) {
      if (e.cls === 'desktop') expect(`${route}: ${e.why.trim().length > 20}`).toBe(`${route}: true`)
    }
  })

  test('a redirect names a route that exists, and a surface names a real sandbox slug', () => {
    const surfaces = readWeb('src/sandbox/surfaces.tsx', 'the ledger maps routes to the sandbox '
      + 'surfaces that mount them; a slug that no longer exists would claim a measurement')
    const slugs = Array.from(surfaces.matchAll(/^ {4}slug: '([^']+)'/gm), (m) => m[1])
    expect(slugs.length).toBeGreaterThanOrEqual(15)
    for (const [route, e] of Object.entries(MOBILE_CLASS)) {
      if (e.redirect) expect(`${route} → ${pages.includes(e.redirect.split('?')[0])}`).toBe(`${route} → true`)
      for (const s of e.surfaces ?? []) expect(`${route} → ${s}: ${slugs.includes(s)}`).toBe(`${route} → ${s}: true`)
    }
  })
})
