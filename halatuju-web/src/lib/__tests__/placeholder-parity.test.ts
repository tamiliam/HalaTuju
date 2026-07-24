/**
 * Placeholder parity (platform Sprint 6). Every `{placeholder}` a ms/ta value uses must be one the
 * en value for that key also provides, OR a branding AUTO_TOKEN (which `t()` injects into every
 * render). This pins the auto-injection contract: a translator can safely use `{programmeName}` /
 * `{orgShortName}` / … even where en used a different one, but a STRAY `{foo}` en never supplies
 * would render a literal `{foo}` to a user — this catches that.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

import { AUTO_TOKENS } from '@/lib/branding'

const AUTO = new Set<string>(AUTO_TOKENS)

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

function placeholders(s: string): Set<string> {
  return new Set([...s.matchAll(/\{([a-zA-Z0-9_]+)\}/g)].map((m) => m[1]))
}

const enFlat = flatten(en)

describe('placeholder parity', () => {
  it.each([['ms', ms], ['ta', ta]] as const)(
    "%s: every value's placeholders ⊆ en's ∪ AUTO_TOKENS",
    (loc, msgs) => {
      const flat = flatten(msgs)
      const viol: string[] = []
      let scanned = 0
      for (const [k, v] of Object.entries(flat)) {
        scanned++
        const enPh = k in enFlat ? placeholders(enFlat[k]) : new Set<string>()
        for (const p of placeholders(v)) {
          if (!enPh.has(p) && !AUTO.has(p)) viol.push(`${loc}:${k}: {${p}}`)
        }
      }
      expect(viol).toEqual([])
      expect(scanned).toBeGreaterThan(3000) // self-check: real corpus scanned
    },
  )

  it('AUTO_TOKENS holds the five injected branding params', () => {
    expect([...AUTO].sort()).toEqual([
      'displayDomain', 'orgShortName', 'personaName', 'programmeName', 'supportEmail',
    ])
  })
})
