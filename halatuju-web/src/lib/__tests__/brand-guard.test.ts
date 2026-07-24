/**
 * FE brand-guard (platform Sprint 6, decision D6 counterpart for the web app).
 *
 * After Sprint 6 the platform brand LITERALS ("BrightPath", "Cikgu Gopal", "halatuju.xyz") live in
 * exactly the sanctioned homes below; anywhere else — a message VALUE, or a comment-stripped source
 * string — is a leak that would ship a wrong brand to a tenant. This test fails on such a leak.
 *
 * Self-checking: it asserts it actually scanned a real corpus (thousands of message leaves, 150+
 * source files) so a broken scanner fails loudly instead of silently passing a leak.
 *
 * Documented allowlists:
 *  - MESSAGE VALUES: `admin.administration.tenantName` ("BrightPath Foundation") — the org's legal
 *    name, DEFERRED as tenant content this sprint.
 *  - SOURCE FILES: `lib/branding.ts` (the PLATFORM literal home), `content/manual/**` (tenant
 *    content), `app/layout.tsx` (platform metadata), `app/r/[code]/page.tsx` (platform OG url),
 *    and any test file.
 *  - i18n KEY paths that embed the token (e.g. `t('sponsorPool.verifiedByBrightPath')`) are NOT
 *    leaks — the source scan uses a word boundary so an identifier-embedded token is skipped.
 */
import * as fs from 'fs'
import * as path from 'path'

import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const FORBIDDEN = ['BrightPath', 'Cikgu Gopal', 'halatuju.xyz'] as const

const SRC_DIR = path.join(__dirname, '..', '..') // .../src

// ── message-value allowlist ──────────────────────────────────────────────────────────────────
const VALUE_ALLOW_PATHS = new Set<string>(['admin.administration.tenantName'])

// ── source-file allowlist ────────────────────────────────────────────────────────────────────
function isAllowlistedSource(rel: string): boolean {
  return (
    rel === 'lib/branding.ts' ||
    rel.startsWith('content/manual/') ||
    rel === 'app/layout.tsx' ||
    rel === 'app/r/[code]/page.tsx' ||
    rel.includes('__tests__') ||
    /\.test\.tsx?$/.test(rel)
  )
}

function flatten(obj: unknown, prefix = '', out: Record<string, string> = {}): Record<string, string> {
  if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      flatten(v, prefix ? `${prefix}.${k}` : k, out)
    }
  } else if (typeof obj === 'string') {
    out[prefix] = obj
  }
  return out
}

/** Remove /* … *\/ (incl JSX {/* … *\/}) and // … comments, but PRESERVE string-literal contents. */
function stripComments(src: string): string {
  let out = ''
  let i = 0
  const n = src.length
  let inStr: string | null = null
  while (i < n) {
    const c = src[i]
    if (inStr) {
      out += c
      if (c === '\\' && i + 1 < n) { out += src[i + 1]; i += 2; continue }
      if (c === inStr) inStr = null
      i++; continue
    }
    if (c === '"' || c === "'" || c === '`') { inStr = c; out += c; i++; continue }
    if (c === '/' && src[i + 1] === '*') { const j = src.indexOf('*/', i + 2); i = j === -1 ? n : j + 2; out += ' '; continue }
    if (c === '/' && src[i + 1] === '/') { const j = src.indexOf('\n', i); i = j === -1 ? n : j; out += ' '; continue }
    out += c; i++
  }
  return out
}

/** Forbidden tokens present as a WORD (not embedded in a longer identifier — so a t() key path
 *  like 'verifiedByBrightPath' is not a hit, but 'Verified by BrightPath' copy is). */
function forbiddenHits(text: string): string[] {
  const hits: string[] = []
  for (const tok of FORBIDDEN) {
    const re = new RegExp(`(?<![A-Za-z])${tok.replace(/[.]/g, '\\.')}`)
    if (re.test(text)) hits.push(tok)
  }
  return hits
}

function walkSources(dir: string, acc: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const abs = path.join(dir, entry.name)
    if (entry.isDirectory()) walkSources(abs, acc)
    else if (/\.(ts|tsx)$/.test(entry.name)) acc.push(abs)
  }
  return acc
}

describe('FE brand-guard', () => {
  it('no platform brand literal in any message VALUE (except allowlisted)', () => {
    const leaks: string[] = []
    let scanned = 0
    for (const [loc, msgs] of Object.entries({ en, ms, ta })) {
      const flat = flatten(msgs)
      for (const [p, v] of Object.entries(flat)) {
        scanned++
        if (VALUE_ALLOW_PATHS.has(p)) continue
        for (const tok of FORBIDDEN) {
          if (v.includes(tok)) leaks.push(`${loc}:${p}: ${tok!} in ${v.slice(0, 60)!}`)
        }
      }
    }
    expect(leaks).toEqual([])
    // Self-check: 3 locales × ~3.7k leaves. Floor well below the real ~11k, far above zero.
    expect(scanned).toBeGreaterThan(9000)
  })

  it('no platform brand literal in comment-stripped src/** (except allowlisted homes)', () => {
    const leaks: string[] = []
    let scannedFiles = 0
    let scannedChars = 0
    for (const abs of walkSources(SRC_DIR)) {
      const rel = path.relative(SRC_DIR, abs).split(path.sep).join('/')
      if (isAllowlistedSource(rel)) continue
      scannedFiles++
      const stripped = stripComments(fs.readFileSync(abs, 'utf8'))
      scannedChars += stripped.length
      for (const tok of forbiddenHits(stripped)) leaks.push(`${rel}: ${tok}`)
    }
    expect(leaks).toEqual([])
    // Self-check: 246 src files minus a handful allowlisted; floor far below, above zero.
    expect(scannedFiles).toBeGreaterThan(150)
    expect(scannedChars).toBeGreaterThan(200000)
  })

  it('the comment-stripper keeps string contents but drops comments (sanity)', () => {
    const s = `const a = 'keepBrightPath'; // dropBrightPath\n/* dropCikgu Gopal */ const b = "halatuju.xyz"`
    const out = stripComments(s)
    expect(out).toContain('keepBrightPath')
    expect(out).toContain('halatuju.xyz')
    expect(out).not.toContain('dropBrightPath')
    expect(out).not.toContain('dropCikgu Gopal')
  })

  it('the word-boundary matcher skips identifier-embedded tokens but catches real copy', () => {
    expect(forbiddenHits("t('sponsorPool.verifiedByBrightPath')")).toEqual([]) // key path — skipped
    expect(forbiddenHits('Verified by BrightPath')).toEqual(['BrightPath'])    // real copy — caught
    expect(forbiddenHits('email info@halatuju.xyz')).toEqual(['halatuju.xyz'])
  })
})
