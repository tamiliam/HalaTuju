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
  attr, blankComments, classText, constResolver, literalsIn, literalsWithIndex, openTags, scanFiles,
  tokens, where, withoutLiterals,
  type Offender, type Scanned,
} from '@/test/mobileScan'
import { MOBILE_CLASS, routeOfPage } from '@/lib/mobileClass'
import { sandboxSlugs } from '../../../mobile-check/targets'

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

describe('the corpus this file depends on is really there', () => {
  test('hundreds of source files, most of them components', () => {
    expect(FILES.length).toBeGreaterThanOrEqual(500)
    expect(TSX.length).toBeGreaterThanOrEqual(300)
  })
})

// ── Rule 2: text fields at 16 px on phones ────────────────────────────────────────────────────
/**
 * A text field under 16 px makes iPhone Safari ZOOM THE PAGE when it is tapped, and the page stays
 * zoomed. The offence is a small size that APPLIES ON A PHONE: `text-sm`, `text-xs`, `text-[<16px]`
 * (also `text-[length:14px]`, `text-sm/6`, `!text-sm`), bare or behind a variant that still applies
 * at phone width — `max-md:`, `max-sm:`, `max-[…]:`, and state variants such as `focus:` or `dark:`
 * (a field that shrinks on focus zooms on tap just the same). A MIN-width breakpoint (`sm:`, `md:`,
 * `lg:`, `xl:`, `2xl:`, `min-[…]:`) starts above every phone in the standard, so `md:text-sm` is
 * fine; so are `placeholder:`/`file:` sizes, which do not size the field. Checkboxes, radios,
 * hidden, file, range and button-like inputs take no typing and are skipped; an `type={…}`
 * expression counts as text unless every literal in it is one of those.
 *
 * ⚠ LIMITS (best effort, stable, honest). A control with NO size class inherits its parent's size
 * (Tailwind's preflight sets `font-size: 100%`), which only the browser check can see. A class
 * built from props or a constant the reader cannot resolve is not judged.
 */
const NOT_TEXT = new Set(['checkbox', 'radio', 'hidden', 'file', 'range', 'color', 'submit', 'button',
  'reset', 'image'])
/** Variants that switch a class OFF at phone width, or point it at something other than the field. */
const NOT_ON_PHONE = /^(?:sm|md|lg|xl|2xl|min-\[[^\]]*\]|placeholder|file)$/

/** True when this class token sets a font size under 16 px that is in force on a phone. */
function smallOnPhone(token: string): boolean {
  // Split variants on `:` OUTSIDE brackets — `text-[length:14px]` holds one inside its value.
  const parts = token.split(/:(?![^[]*\])/)
  const utility = (parts.pop() ?? '').replace(/^!/, '')
  if (parts.some((v) => NOT_ON_PHONE.test(v.replace(/^!/, '')))) return false
  const size = utility.replace(/\/[\w.[\]-]+$/, '')            // drop a `/leading` suffix
  if (size === 'text-xs' || size === 'text-sm') return true
  const m = size.match(/^text-\[(?:length:)?(\d*\.?\d+)(px|rem|em)\]$/)
  if (!m) return false
  const n = parseFloat(m[1])
  return m[2] === 'px' ? n < 16 : n < 1
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

  /**
   * ⚠ SINCE MOBILE M1a THE FIX IS ONE RULE, SO THE GUARD CHANGED SHAPE. Before M1a this test counted
   * every field with a small size on a phone (floor 208 after the M0 review, 182 before it) and the
   * plan was to fix them one by one. M1a fixed them all at once: a rule in `globals.css` sets 16 px
   * on every text-entry control below `md`, and it outranks any ordinary utility. Counting `text-sm`
   * fields now would count fields that are NOT small on a phone, so the guard is two things instead:
   *   1. the rule exists, below `md`, OUTSIDE every `@layer` (inside `@layer base` it would lose to
   *      `text-sm` — the very thing it exists to beat), and with the exclusions that keep it from
   *      touching checkboxes, radios and file pickers;
   *   2. the sizes it CANNOT beat stay at zero — an `!important` small size (`!text-sm`) wins over
   *      any selector without `!important`, so a field carrying one would zoom again.
   * The browser check measures the outcome on every page: `smallInputs` is 0 in every cell.
   */
  test('the global 16 px rule exists, below md, outside every @layer', () => {
    const css = readWeb('src/app/globals.css', 'the one rule that makes text fields 16 px on phones')
      .replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, ' '))
    const at = css.indexOf('@media (max-width: 767.98px)')
    expect(at).toBeGreaterThan(-1)
    let depth = 0
    for (const c of css.slice(0, at)) depth += c === '{' ? 1 : c === '}' ? -1 : 0
    expect(`brace depth before the rule: ${depth}`).toBe('brace depth before the rule: 0')
    const rule = css.slice(at, css.indexOf('\n}', at))
    expect(rule).toMatch(/font-size:\s*16px/)
    for (const t of ['checkbox', 'radio', 'range', 'file', 'hidden']) expect(rule).toContain(`[type='${t}']`)
    expect(rule).toMatch(/^\s*select:not/m)
    expect(rule).toMatch(/^\s*textarea:not/m)
  })

  test('no text field carries a small size the global rule cannot beat (!important)', () => {
    const offenders = controls.flatMap(({ f, tag }) => {
      const small = tokens(classText(f, tag, resolve))
        .find((t) => smallOnPhone(t) && /(^|:)!/.test(t))
      return small ? [where(f, tag.start, `<${tag.name} … ${small}`)] : []
    })
    // Mobile M1a: was 208 small-text fields (M0 review: reader fixed, was 182); the global rule
    // covers all of those, so this counts only what it cannot cover. 0 on 2026-10-31.
    ratchet('text fields with an !important small font', offenders, 0)
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
    // Mobile M1a: 6 -> 0. All six moved to `sr-only` (the two opened by a button's ref.click()
    // also take tabIndex={-1}, so the invisible input is not a second, silent tab stop).
    ratchet('file inputs hidden with `hidden`', offenders, 0)
  })
})

// ── Rule 10: keyboards and autofill — phone fields take the NATIONAL number ──────────────────
/**
 * Every phone field here holds a LOCAL number ("012-345 6789"; the +60 is a fixed prefix or added
 * by the server), and `formatPhone` keeps 11 digits. `autoComplete="tel"` makes the browser fill
 * the INTERNATIONAL form ("+60 12-345 6789"): the profile page then rejected the number the browser
 * itself filled, and an 011 number lost its last digit (M1b adversarial review). So: `tel-national`
 * for the person's own number, `off` for somebody else's (an admin inviting a source must not get
 * their OWN number filled in).
 */
describe('rule 10 — a phone field never autofills the international number', () => {
  test('no autoComplete="tel" anywhere in the web source', () => {
    const offenders = TSX.flatMap((f) => openTags(f.code, 'input')
      .filter((tag) => {
        const ac = attr(tag.attrs, 'autoComplete')
        return !!ac && 'literal' in ac && ac.literal === 'tel'
      })
      .map((tag) => where(f, tag.start, '<input autoComplete="tel"')))
    ratchet('phone fields that autofill the international number', offenders, 0)
  })
})

// ── Rule 5: one shared Sheet, no hand-rolled overlays ─────────────────────────────────────────
/**
 * Every hand-rolled `fixed inset-0` overlay re-decided max height, inner scroll, the close target
 * and the safe area — and several decided wrong (buttons hidden behind the iPhone keyboard). Since
 * Mobile M1b the shared `Sheet` (src/components/Sheet.tsx) is the ONE home of an overlay. The 18
 * that existed moved onto it in M1b part 2, except the three below, which are not dialogs and say
 * why. This is now a POSITIVE guard, not a floor: a `fixed inset-0` anywhere else FAILS — use Sheet.
 * Counted per class string holding both tokens, in `.ts` and `.tsx`.
 */
const OVERLAY_HOMES: string[] = ['src/components/Sheet.tsx']

/** Full-screen panels that are NOT dialogs. Each was made phone-correct in M1b and says why it stays. */
const OVERLAY_EXEMPT: Record<string, string> = {
  'src/components/DocViewer.tsx':
    'a document viewer needs the whole screen (full screen on a phone, framed on a desktop), not a '
    + 'bottom sheet capped at 90 % — dvh, notch padding and a 44 px close since M1b',
  'src/components/admin/AppShell.tsx':
    'the console’s phone navigation drawer, sliding from the left edge — a side panel, not a '
    + 'dialog; safe-area padded (M1a) and closed by Escape, the backdrop or a choice',
  'src/components/admin/CommandPalette.tsx':
    'a type-to-search command palette reached by Ctrl/⌘-K: the box sits at the top so results grow '
    + 'DOWN under it while typing (a bottom sheet would hide them behind the keyboard); its own '
    + 'tested focus, arrow-key and Escape handling',
}

describe('rule 5 — overlays come from the shared Sheet', () => {
  test('the home and every exemption are real files that really hold an overlay', () => {
    // An exemption for a file that no longer holds the overlay would excuse nothing and hide a move.
    for (const rel of [...OVERLAY_HOMES, ...Object.keys(OVERLAY_EXEMPT)]) {
      const f = FILES.find((x) => x.rel === rel)
      expect(`${rel}: ${!!f && /fixed inset-0/.test(f.code)}`).toBe(`${rel}: true`)
    }
  })

  test('no fixed inset-0 overlay outside Sheet.tsx and the named exemptions', () => {
    // Mobile M1b part 2: was a floor of 18; now none may be added. A new overlay uses Sheet.
    const offenders = FILES
      .filter((f) => !OVERLAY_HOMES.includes(f.rel) && !(f.rel in OVERLAY_EXEMPT))
      .flatMap((f) => literalsWithIndex(f.code)
        .filter(({ text }) => tokens(text).includes('fixed') && tokens(text).includes('inset-0'))
        .map(({ index }) => where(f, index, 'fixed inset-0')))
    expect(offenders).toEqual([])
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
    const offenders = FILES.flatMap((f) => literalsWithIndex(f.code).flatMap(({ text, index }) => {
      // A style VALUE is matched whole (`calc(100vh - 4rem)` has spaces); class tokens one by one.
      const style = text.trim()
      const hits = [
        ...tokens(text).filter((t) => VH_TOKEN.test(t)),
        ...(VH_STYLE.test(style) ? [style] : tokens(text).filter((t) => VH_STYLE.test(t))),
      ]
      return hits.map((t) => where(f, index, t))
    }))
    // Mobile M1b part 2: 3 -> 1. AuthGateModal's max-h-[90vh] went with its shell (Sheet), and
    // DocViewer's 92vh is 92dvh; the one left is the contracts template preview (desktop-only).
    ratchet('vh-based heights', offenders, 1)
  })

  test('min-h-screen: at or under its own floor', () => {
    const offenders = FILES.flatMap((f) => literalsWithIndex(f.code).flatMap(({ text, index }) =>
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
/** The element's content; null when the reader cannot find its closing tag — an UNKNOWN, which
 *  is never counted as an offender (it would be a guess, and a guess must not fail a build). */
function contentOf(code: string, tag: { name: string; end: number; selfClosing: boolean }): string | null {
  if (tag.selfClosing) return ''
  const close = code.indexOf(`</${tag.name}>`, tag.end)
  return close === -1 ? null : code.slice(tag.end + 1, close)
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

/**
 * Files that serve ONLY desktop-only routes (`mobileClass.ts`, class `desktop`). Below `md` those
 * routes show the "works best on a computer" panel (rule 13), so a phone never reaches these
 * controls and a hover hint there is acceptable. Each entry names its route; a stale one fails below.
 */
const DESKTOP_ONLY_FILES: Record<string, string> = {
  'src/components/contracts/ClauseEditor.tsx':
    "the clause editor's icon toolbar (insert, indent, move, remove) — only on /admin/contracts/[id]",
}

describe('rule 4 — no title= as the only explanation on an icon-only control', () => {
  test('a desktop-only exemption names a real file used only by a desktop route', () => {
    for (const rel of Object.keys(DESKTOP_ONLY_FILES)) {
      expect(`${rel}: ${FILES.some((f) => f.rel === rel)}`).toBe(`${rel}: true`)
    }
    expect(MOBILE_CLASS['/admin/contracts/[id]'].cls).toBe('desktop')
  })

  test('icon-only controls explained only by title=: at or under the floor', () => {
    const offenders = TSX.filter((f) => !(f.rel in DESKTOP_ONLY_FILES)).flatMap((f) => ['button', 'a', 'Link'].flatMap((name) =>
      openTags(f.code, name)
        .filter((tag) => /(?:^|\s)title=/.test(tag.attrs))
        .filter((tag) => {
          const content = contentOf(f.code, tag)
          return content !== null && isIconOnly(content)
        })
        .map((tag) => where(f, tag.start, `<${name} title=… (icon only)`))))
    // Mobile M1a: 7 -> 0. Six were ClauseEditor's toolbar, now exempt above (desktop-only route);
    // the seventh, the course-interest remove button, has an aria-label and a 44 px target.
    // VerifiedTick (a role="img" span, which this rule never counted) is tappable too since M1a.
    ratchet('icon-only controls with title=', offenders, 0)
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
    // The SAME reader the browser check uses (SURFACES block only, one `render:` per slug), so the
    // ledger and the check cannot disagree about which surfaces exist.
    const slugs = sandboxSlugs()
    expect(slugs.length).toBeGreaterThanOrEqual(15)
    for (const [route, e] of Object.entries(MOBILE_CLASS)) {
      if (e.redirect) expect(`${route} → ${pages.includes(e.redirect.split('?')[0])}`).toBe(`${route} → true`)
      for (const s of e.surfaces ?? []) expect(`${route} → ${s}: ${slugs.includes(s)}`).toBe(`${route} → ${s}: true`)
    }
  })
})

// ── The reader itself (M0 review) ─────────────────────────────────────────────────────────────
/**
 * Each case below is a shape the first reader got WRONG, found by the M0 code review. They pin the
 * reader, not the product: if one fails, a floor above has silently started counting something else.
 */
describe('the reader sees what the review said it missed', () => {
  const scanned = (rel: string, raw: string): Scanned => ({ rel, raw, code: blankComments(raw) })

  test('a URL or a `//` in JSX text is not a comment; a real comment still is', () => {
    expect(blankComments("<a href={u}>https://halatuju.example/x className='text-sm'</a>"))
      .toContain("className='text-sm'")
    expect(blankComments('<p>a // b</p>')).toContain('// b')
    expect(blankComments("const x = 1 // className='text-sm'")).not.toContain('text-sm')
  })

  test('an aliased import resolves by the name it was EXPORTED under', () => {
    const lib = scanned('src/x/fields.ts', "export const INPUT = 'w-full text-sm'")
    const page = scanned('src/x/page.tsx', "import { INPUT as fieldCls } from './fields'\n"
      + '<input className={fieldCls} />')
    const tag = openTags(page.code, 'input')[0]
    expect(classText(page, tag, constResolver([lib, page]))).toContain('text-sm')
  })

  test('a constant inside a template hole is resolved', () => {
    expect(withoutLiterals('`${inputCls} w-full`')).toContain('inputCls')
    const page = scanned('src/x/p.tsx', "const inputCls = 'text-xs'\n<input className={`${inputCls} w-28`} />")
    expect(classText(page, openTags(page.code, 'input')[0], constResolver([page]))).toContain('text-xs')
  })

  test('a small size counts when it applies on a phone, and only then', () => {
    for (const t of ['text-sm', 'max-md:text-sm', 'max-sm:text-xs', '!text-sm', 'focus:text-sm',
      'text-[length:14px]', 'text-[13.5px]', 'text-sm/6', 'max-[500px]:text-xs']) {
      expect(`${t}: ${smallOnPhone(t)}`).toBe(`${t}: true`)
    }
    for (const t of ['md:text-sm', 'sm:text-xs', 'lg:!text-sm', 'min-[640px]:text-sm',
      'placeholder:text-sm', 'text-base', 'text-[16px]', 'text-[1rem]', 'md:max-lg:text-sm']) {
      expect(`${t}: ${smallOnPhone(t)}`).toBe(`${t}: false`)
    }
  })

  test('a vh style value is matched whole, spaces and all', () => {
    expect(VH_STYLE.test('calc(100vh - 4rem)')).toBe(true)
    expect(VH_STYLE.test('100vh')).toBe(true)
    expect(VH_STYLE.test('calc(100dvh - 4rem)')).toBe(false)
  })
})
