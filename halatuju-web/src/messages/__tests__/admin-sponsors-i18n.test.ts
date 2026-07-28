/**
 * Guardrail — the `admin.sponsors.*` namespace (sponsor terms T2).
 *
 * ⚠ This guard did not exist before T2, which is why it is worth reading. The sponsor module had
 * grown to hundreds of leaves — the detail page, the credit UI, and all ~59 `admin.sponsors.emails.*`
 * keys from S3 — with NOTHING checking that a referenced key actually resolves. The only backstop
 * was `scripts/check-i18n.js`, which proves the three locales AGREE but says nothing about whether
 * a key the code asks for exists at all. That is exactly the hole L109 records: ~47 `sponsorPortal.*`
 * keys rendered as raw key paths for four sprints because all three locales were equally missing them.
 *
 * If this fails after ADDING a t('admin.sponsors.*') key: add it to all three message files.
 * After a RENAME: update both the code and the JSON.
 */
import * as fs from 'fs'
import * as path from 'path'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const SRC_DIR = path.join(__dirname, '..', '..') // .../src
const NS = 'admin.sponsors'

function collectSource(dir: string, acc: string[]): void {
  fs.readdirSync(dir, { withFileTypes: true }).forEach((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules') return
      collectSource(full, acc)
    } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
      // Co-located test files are NOT usages. `page.test.tsx` asserts that
      // `admin.sponsors.organisation` is absent (the dropped Organisation column) and that an
      // unmapped credit-error code falls back — both would otherwise read as missing keys.
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

// Strip comments before scanning. A key path named in a doc comment is PROSE, not a usage —
// `sponsorDetail.ts` documents its error fallback by naming a key that deliberately does NOT
// exist, and reading that as a reference would make this guard demand the very key it describes.
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/(^|[^:])\/\/[^\n]*/g, '$1')
}

const files: string[] = []
collectSource(SRC_DIR, files)
const blob = files.map((f) => stripComments(fs.readFileSync(f, 'utf8'))).join('\n')

const re = new RegExp(`['"\`](admin\\.sponsors\\.[\\w.]+?)(?=['"\`])`, 'g')
// A NAMESPACE passed as a prop is not a key reference. `TemplateEditor` takes
// prefix="admin.sponsors.emails" and builds `${prefix}.subject` itself, so that literal resolves
// to an object rather than a string. Excluding the namespaces themselves keeps this guard strict
// about LEAVES — which is what it is for — rather than failing on a prop doing its job.
const NAMESPACE_PROPS = ['admin.sponsors.emails']

const usedStatic = Array.from(new Set(captureGroup1(re, blob)))
  .filter((k) => !k.endsWith('.'))
  .filter((k) => !NAMESPACE_PROPS.includes(k))

describe('admin.sponsors i18n hygiene', () => {
  test('every referenced admin.sponsors key resolves in en.json (no missing keys)', () => {
    const missing = usedStatic.filter((k) => typeof resolve(en, k) !== 'string')
    expect(missing).toEqual([])
  })

  test('en / ms / ta key sets are identical under admin.sponsors', () => {
    const e: string[] = []; leafPaths((resolve(en, NS) ?? {}) as Record<string, unknown>, '', e)
    const m: string[] = []; leafPaths((resolve(ms, NS) ?? {}) as Record<string, unknown>, '', m)
    const t: string[] = []; leafPaths((resolve(ta, NS) ?? {}) as Record<string, unknown>, '', t)
    expect(e.length).toBeGreaterThan(0)
    expect(m.sort()).toEqual(e.slice().sort())
    expect(t.sort()).toEqual(e.slice().sort())
  })

  test('the three sponsor tab labels exist in every locale', () => {
    for (const loc of [en, ms, ta]) {
      for (const k of ['tabSponsors', 'tabEmails', 'tabTerms']) {
        expect(typeof resolve(loc, `admin.sponsors.${k}`)).toBe('string')
      }
    }
  })
})
