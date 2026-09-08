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
    expect(pageWidthFor('/admin/sources')).toBe('wide')
    expect(pageWidthFor('/admin/organisation/reviewers')).toBe('wide')
  })

  test('a DETAIL page below a table page reads — the longer match wins', () => {
    // The B40 cockpit is one application, not a list of them. This pair is the whole reason
    // matching is longest-prefix rather than first-hit.
    expect(pageWidthFor('/admin/scholarship')).toBe('wide')
    expect(pageWidthFor('/admin/scholarship/143')).toBe('reading')
    expect(pageWidthFor('/admin/payments')).toBe('wide')
    expect(pageWidthFor('/admin/payments/PR-2026-09-01-03')).toBe('reading')
    expect(pageWidthFor('/admin/organisation/reviewers')).toBe('wide')
    expect(pageWidthFor('/admin/organisation/reviewers/7')).toBe('reading')
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
  test('no admin page sets max-w-* on its root container', () => {
    const offenders = sources(ADMIN)
      .filter(([rel]) => rel.endsWith('page.tsx'))
      .filter(([rel]) => !CHROMELESS.some((c) => rel.includes(c)))
      .map(([rel, src]) => [rel, src.match(/return \(\s*\n\s*<\w+\s+className="([^"]*)"/)] as const)
      .filter(([, m]) => m && /max-w-/.test(m[1]))
      .map(([rel, m]) => `${rel} → "${m![1]}"`)
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

  test('every <table> has a frame around it', () => {
    const offenders = [...sources(ADMIN), ...sources(COMPONENTS)]
      .map(([rel, src]) => [rel, openTags(src, 'table'), openTags(src, 'TableFrame')] as const)
      .filter(([, tables, frames]) => tables > 0 && frames < tables)
      .map(([rel, tables, frames]) => `${rel}: ${tables} table(s), ${frames} frame(s)`)
    expect(offenders).toEqual([])
  })
})
