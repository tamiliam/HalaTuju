/**
 * Guardrail (R7 / TD-132): every sponsor-portal i18n key REFERENCED in code must RESOLVE.
 *
 * The redesign (R1–R6) shipped with ~47 keys (sponsorPortal.impact/journey/activity/
 * community/statement/students/account.*) referenced by the My Giving / Students / Account
 * pages but NEVER added to the message files — so those pages rendered the raw key path.
 * It went undetected because: i18n parity only checks en===ms===ta (all three were equally
 * missing), and `next build` / jest don't validate that t() keys exist. This test closes
 * that gap for the `sponsorPortal` / `sponsorPool` / `sponsorLanding` namespaces:
 *
 *   1. NO MISSING KEYS — every static `t('sponsor*.<path>')` resolves to a string in en.json.
 *      (Template-literal / concatenated keys like `t(`…activity.${type}`)` are dynamic and
 *       skipped; their leaves are covered by the parity check below.)
 *   2. PARITY — en / ms / ta hold the identical key set under each sponsor namespace.
 *
 * If this fails after you ADD a t() key: add it to all three message files. If it fails after
 * a RENAME: update both the code and the JSON.
 */
import * as fs from 'fs'
import * as path from 'path'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const SRC_DIR = path.join(__dirname, '..', '..') // .../src
const NAMESPACES = ['sponsorPortal', 'sponsorPool', 'sponsorLanding']

function collectSource(dir: string, acc: string[]): void {
  fs.readdirSync(dir, { withFileTypes: true }).forEach((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules') return
      collectSource(full, acc)
    } else if (/\.tsx?$/.test(entry.name)) {
      acc.push(full)
    }
  })
}

function captureGroup1(re: RegExp, s: string): string[] {
  const out: string[] = []
  s.replace(re, (_full: string, g1: string): string => { out.push(g1); return _full })
  return out
}

function leafPaths(obj: Record<string, unknown>, prefix: string, out: string[]): void {
  Object.keys(obj).forEach((k) => {
    const p = prefix ? `${prefix}.${k}` : k
    const v = obj[k]
    if (v !== null && typeof v === 'object') leafPaths(v as Record<string, unknown>, p, out)
    else out.push(p)
  })
}

function resolve(obj: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>((cur, part) => {
    if (cur && typeof cur === 'object' && part in (cur as Record<string, unknown>)) {
      return (cur as Record<string, unknown>)[part]
    }
    return undefined
  }, obj)
}

const files: string[] = []
collectSource(SRC_DIR, files)
const blob = files.map((f) => fs.readFileSync(f, 'utf8')).join('\n')

// Static keys: a sponsor namespace + dotted path ending right at a CLOSING QUOTE. A key
// followed by `${` (e.g. `…activity.${type}`) or `<letter>${i}` is a dynamic template — it
// won't end at a quote, so it's naturally excluded (its leaves are covered by the parity test).
const re = new RegExp(`['"\`]((?:${NAMESPACES.join('|')})\\.[\\w.]+?)(?=['"\`])`, 'g')
const usedStatic = Array.from(new Set(captureGroup1(re, blob))).filter((k) => !k.endsWith('.'))

describe('sponsor i18n hygiene', () => {
  test('every referenced sponsor key resolves in en.json (no missing keys)', () => {
    const missing = usedStatic.filter((k) => typeof resolve(en, k) !== 'string')
    expect(missing).toEqual([])
  })

  test('en / ms / ta key sets are identical under each sponsor namespace', () => {
    NAMESPACES.forEach((ns) => {
      const e: string[] = []; leafPaths(((en as never)[ns] ?? {}) as Record<string, unknown>, '', e)
      const m: string[] = []; leafPaths(((ms as never)[ns] ?? {}) as Record<string, unknown>, '', m)
      const t: string[] = []; leafPaths(((ta as never)[ns] ?? {}) as Record<string, unknown>, '', t)
      expect(m.sort()).toEqual(e.slice().sort())
      expect(t.sort()).toEqual(e.slice().sort())
    })
  })
})
