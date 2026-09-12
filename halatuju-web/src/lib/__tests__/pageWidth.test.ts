import fs from 'fs'
import path from 'path'
import { pageWidthFor, WIDE_ROUTES, WIDTH_CLASS } from '../pageWidth'

const ADMIN = path.join(process.cwd(), 'src', 'app', 'admin')
const COMPONENTS = path.join(process.cwd(), 'src', 'components', 'admin')
/** These render WITHOUT the shell, so they keep their own width. */
const CHROMELESS = ['login', 'set-password', 'callback']

/** Every `page.tsx` under /admin, as its route. */
function adminRoutes(dir = ADMIN, prefix = '/admin'): string[] {
  const out: string[] = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      out.push(...adminRoutes(full, `${prefix}/${entry.name}`))
    } else if (entry.name === 'page.tsx') {
      out.push(prefix)
    }
  }
  return out
}

/** Every .tsx under `dir` that is not a test, as [relative path, source]. */
function sources(dir: string): Array<[string, string]> {
  const out: Array<[string, string]> = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) { out.push(...sources(full)); continue }
    if (!entry.name.endsWith('.tsx') || entry.name.endsWith('.test.tsx')) continue
    const rel = path.relative(process.cwd(), full).split(path.sep).join('/')
    out.push([rel, fs.readFileSync(full, 'utf8')])
  }
  return out
}

describe('the rule: leads with a table? wide. otherwise reading.', () => {
  test('table pages are wide, everything else reads', () => {
    expect(pageWidthFor('/admin/organisation')).toBe('reading')
    expect(pageWidthFor('/admin/organisation/settings')).toBe('reading')
    expect(pageWidthFor('/admin/requests')).toBe('reading')
    expect(pageWidthFor('/admin/scholarship')).toBe('wide')
    // ⚠ SEVEN COLUMNS — merchant, category, determined by, transactions, total, last
    // transaction, determined on. It shipped at the READING width by oversight and the
    // owner spotted it: shop names wrapped and the last column fell off the right edge.
    expect(pageWidthFor('/admin/spending')).toBe('wide')
    expect(pageWidthFor('/admin/sources')).toBe('wide')
    expect(pageWidthFor('/admin/organisation/reviewers')).toBe('wide')
  })

  test('a detail page that runs DOWN the page reads — the longer match wins', () => {
    // Longest-prefix matching exists for this pair: a one-column profile below a table list.
    expect(pageWidthFor('/admin/organisation/reviewers')).toBe('wide')
    expect(pageWidthFor('/admin/organisation/reviewers/7')).toBe('reading')
    expect(pageWidthFor('/admin/students')).toBe('wide')
    expect(pageWidthFor('/admin/students/88')).toBe('reading')
  })

  test('being ONE of something is not the test — the layout is (owner review, 2026-09-08)', () => {
    // ⚠ THE REGRESSION THIS PINS. All three were forced to `reading` on the first pass because
    // they show a single record. The owner walked the console and found two of them cramped; the
    // third has two tables and would have been the next one spotted. The cockpit is the sharp
    // case: it had been 1152px for months, so "standardising" it to 900 made it narrower than it
    // had ever been.
    expect(pageWidthFor('/admin/payments/PR-2026-09-01-02')).toBe('wide')   // 8-column table
    expect(pageWidthFor('/admin/scholarship/143')).toBe('wide')             // dense card grid
    expect(pageWidthFor('/admin/sponsors/12')).toBe('wide')                 // two tables
  })

  test('a trailing slash and an unknown route both resolve', () => {
    expect(pageWidthFor('/admin/sources/')).toBe('wide')
    expect(pageWidthFor('/admin/something-new')).toBe('reading')
    expect(pageWidthFor('')).toBe('reading')
  })

  test('neither width centres — centring is what made the cockpit look like another console', () => {
    for (const cls of Object.values(WIDTH_CLASS)) {
      expect(cls).not.toContain('mx-auto')
    }
  })

  test('every wide route names a real page', () => {
    const routes = adminRoutes()
    for (const wide of WIDE_ROUTES) {
      expect(routes.some((r) => r === wide || r.startsWith(`${wide}/`))).toBe(true)
    }
  })
})

describe('no page may invent a ninth width', () => {
  // ⚠ THE GUARD THIS SPRINT EXISTS FOR. Thirty-five pages each wrote their own limit and there
  // were EIGHT different answers. The width now comes from AppShell; a page that writes its own
  // on its root container silently opts out of the standard, and nothing on screen would say so.
  // ⚠ EVERY `return (` IN THE FILE, NOT JUST THE FIRST. The first version of this guard read one
  // match per file and so was blind in exactly the same way the conversion script was: a page with
  // an early return — a loading state, a "coming soon" branch, a not-allowed message — hid its real
  // root behind it. FOUR pages kept their own width that way (sponsors/[id] at max-w-5xl, faq,
  // and billing twice), and the owner found the first of them by looking at the screen. A guard
  // that shares a blind spot with the change it is guarding is not a second opinion.
  test('no admin page sets max-w-* on ANY of its return roots', () => {
    const offenders: string[] = []
    for (const [rel, src] of sources(ADMIN)) {
      if (!rel.endsWith('page.tsx')) continue
      if (CHROMELESS.some((c) => rel.includes(c))) continue
      const roots = src.match(/return \(\s*\n\s*<\w+[^>]*?className="[^"]*"/g) || []
      roots.forEach((root) => {
        const cls = (root.match(/className="([^"]*)"/) || ['', ''])[1]
        if (/max-w-/.test(cls)) offenders.push(`${rel} → "${cls}"`)
      })
    }
    expect(offenders).toEqual([])
  })

  test('no admin page centres itself', () => {
    const offenders = sources(ADMIN)
      .filter(([rel]) => !CHROMELESS.some((c) => rel.includes(c)))
      .filter(([, src]) => /\bmx-auto\b/.test(src))
      .map(([rel]) => rel)
    expect(offenders).toEqual([])
  })
})

describe('every table sits in the shared frame', () => {
  // The promise: a table never clips, always keeps a floor, and says when there is more to the
  // right. A raw <table> outside TableFrame keeps none of those by default.
  // ⚠ COUNTED, NOT just "the file mentions TableFrame somewhere". The first version of this guard
  // asked only whether the name appeared in the source, and a deliberate fault — putting Intake
  // years back into a clipping card — SAILED PAST IT, because the import line still said
  // "TableFrame". A guard that a file can satisfy by importing something is not a guard.
  const openTags = (src: string, tag: string) => (src.match(new RegExp(`<${tag}\\b`, 'g')) || []).length

  // ⚠ A LABEL THAT DOES NOT RESOLVE IS INVISIBLY WRONG. `label` becomes the scrolling region's
  // accessible name; a missing key renders the raw dotted string, which nobody SEES and a screen
  // reader reads aloud. i18n parity cannot catch it either — the key would be absent from all
  // three locales identically. Five of my own labels were invented before this test existed.
  test('every TableFrame label names a real string', () => {
    const en = JSON.parse(fs.readFileSync(
      path.join(process.cwd(), 'src', 'messages', 'en.json'), 'utf8'))
    const resolve = (key: string) =>
      key.split('.').reduce<unknown>(
        (o, part) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[part] : undefined),
        en)
    // `matchAll` / spreading a Set both need a newer target than this tsconfig sets (TD-221),
    // so the keys are gathered the way the rest of this file does it — plain match + map.
    const used: string[] = []
    for (const [, src] of [...sources(ADMIN), ...sources(COMPONENTS)]) {
      if (!/TableFrame/.test(src)) continue
      const hits = src.match(/label=\{t\('[^']+'\)\}/g) || []
      hits.forEach((h) => {
        const key = h.replace(/^label=\{t\('/, '').replace(/'\)\}$/, '')
        if (used.indexOf(key) === -1) used.push(key)
      })
    }
    expect(used.length).toBeGreaterThan(10)
    expect(used.filter((k) => typeof resolve(k) !== 'string')).toEqual([])
  })

  // ⚠ A LIST SURFACE OWES A PHONE LAYOUT (owner, 2026-09-08). The frame made every table SAFE on
  // a phone — it scrolls and says when there is more — but safe is not the same as good: a
  // seven-column table dragged sideways is still the wrong shape for the screen people check
  // things on. Each list below draws the same rows as cards under `md`.
  //
  // The EXEMPT list is the point of this test: staying table-only has to be a decision somebody
  // wrote down, not something that happened because nobody looked.
  const EXEMPT: Record<string, string> = {
    'src/app/admin/billing/page.tsx':
      'four short columns (service · calls · tokens in · tokens out) — it already fits, and cards '
      + 'would be taller than the table without adding a thing',
    'src/app/admin/course-data/page.tsx':
      'an internal coverage panel, four narrow columns, not a list of people',
    'src/app/admin/contracts/page.tsx':
      'template versions — read at a desk when authoring, never on a phone',
    'src/app/admin/payments/[id]/page.tsx':
      'has its own cards (data-testid="payment-cards"); this file also holds the skipped-list table',
    'src/app/admin/sponsors/[id]/page.tsx':
      'two short tables INSIDE a detail card, four columns each',
    'src/components/admin/InvitationsTable.tsx':
      'five columns and the next in line — TD raised rather than done blind, because the actions '
      + 'differ per kind and the owner reviews each list',
    'src/app/admin/students/page.tsx':
      'already had cards before this work (the pattern everything else copied)',
  }

  test('every list surface has phone cards, or a written reason not to', () => {
    const offenders = [...sources(ADMIN), ...sources(COMPONENTS)]
      .filter(([, src]) => /<TableFrame/.test(src))
      .filter(([rel]) => !(rel in EXEMPT))
      .filter(([, src]) => !/md:hidden/.test(src))
      .map(([rel]) => rel)
    expect(offenders).toEqual([])
  })

  test('an exemption names a file that still exists and still has a table', () => {
    // A stale exemption is worse than none: it silently excuses a file that may have changed.
    const seen = new Set([...sources(ADMIN), ...sources(COMPONENTS)]
      .filter(([, src]) => /<TableFrame/.test(src))
      .map(([rel]) => rel))
    expect(Object.keys(EXEMPT).filter((rel) => !seen.has(rel))).toEqual([])
  })

  test('every <table> has a frame around it', () => {
    const offenders = [...sources(ADMIN), ...sources(COMPONENTS)]
      .map(([rel, src]) => [rel, openTags(src, 'table'), openTags(src, 'TableFrame')] as const)
      .filter(([, tables, frames]) => tables > 0 && frames < tables)
      .map(([rel, tables, frames]) => `${rel}: ${tables} table(s), ${frames} frame(s)`)
    expect(offenders).toEqual([])
  })
})
