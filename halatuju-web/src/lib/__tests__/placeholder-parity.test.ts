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

  // TD-306 review F4. The subset rule above lets a translation DROP a placeholder — ms losing
  // `{amount}` stayed green, and the student would read a sentence with the figure missing. So,
  // per key, the non-AUTO placeholders of ms and ta must EQUAL en's. AUTO_TOKENS are left out on
  // purpose: `t()` fills them on every render, and a translator may name the organisation where en
  // names the programme (four keys do today).
  it.each([['ms', ms], ['ta', ta]] as const)(
    "%s: every value's non-AUTO placeholders = en's (none dropped, none added)",
    (loc, msgs) => {
      const flat = flatten(msgs)
      const own = (s: string) => [...placeholders(s)].filter((p) => !AUTO.has(p)).sort().join(',')
      const viol: string[] = []
      let compared = 0
      for (const [k, v] of Object.entries(enFlat)) {
        const want = own(v)
        if (want) compared++
        const got = k in flat ? own(flat[k]) : want   // a missing key is the i18n gate's to report
        if (got !== want) viol.push(`${loc}:${k}: en {${want}} vs {${got}}`)
      }
      expect(viol).toEqual([])
      expect(compared).toBeGreaterThanOrEqual(300)   // floor: 313 en keys carry one on 2026-09-29
    },
  )

  it('AUTO_TOKENS holds the five injected branding params', () => {
    expect([...AUTO].sort()).toEqual([
      'displayDomain', 'orgShortName', 'personaName', 'programmeName', 'supportEmail',
    ])
  })
})
