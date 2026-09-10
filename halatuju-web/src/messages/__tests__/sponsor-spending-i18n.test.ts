/**
 * Guardrail — the `sponsorPortal.myStudents.detail.spend.*` namespace (sponsor spending S5).
 *
 * ⚠ **PARITY IS NOT EXISTENCE.** en/ms/ta can agree perfectly about a key none of them has. The
 * card builds its category labels dynamically (`…spend.cat.${code}`), which a static scan cannot
 * see at all, so the ten codes are enumerated here against the values the server can actually
 * send. This is the surface that would show a Malay-reading sponsor a raw dotted string.
 *
 * ⚠ **AND THE NOTE HAS RULES OF ITS OWN** (brief §4d). It must never name a shop, never state the
 * RM8 / RM20 / three-visit thresholds — a number in prose rots the day it is tuned, so it says
 * "small amounts" — and never apologise. Those are asserted on the TEXT, in every language,
 * because they are the promise the note makes and no code path enforces them.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const NS = 'sponsorPortal.myStudents.detail.spend'

/** The ten codes the server can send, plus the folded bucket the card adds itself. */
const CODES = [
  'food', 'groceries', 'transport', 'study', 'phone',
  'hostel', 'health', 'clothing', 'transfer', 'unsorted',
]

const FLAT = [
  'title', 'asAt', 'promised', 'released', 'spent', 'left',
  'barLabel', 'chartLabel', 'other', 'none', 'noteTitle', 'note',
]

function resolve(obj: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>((cur, part) => {
    if (cur && typeof cur === 'object' && part in (cur as Record<string, unknown>)) {
      return (cur as Record<string, unknown>)[part]
    }
    return undefined
  }, obj)
}

function leafPaths(obj: Record<string, unknown>, prefix: string, out: string[]): void {
  Object.keys(obj).forEach((k) => {
    const p = prefix ? `${prefix}.${k}` : k
    const v = obj[k]
    if (v !== null && typeof v === 'object') leafPaths(v as Record<string, unknown>, p, out)
    else out.push(p)
  })
}

const LOCALES = [['en', en], ['ms', ms], ['ta', ta]] as const

describe('sponsorPortal…spend i18n hygiene', () => {
  test('every flat key exists in all three locales', () => {
    const missing: string[] = []
    for (const key of FLAT) {
      for (const [name, loc] of LOCALES) {
        if (typeof resolve(loc, `${NS}.${key}`) !== 'string') missing.push(`${name}: ${key}`)
      }
    }
    expect(missing).toEqual([])
  })

  test('every one of the ten category codes has a label in all three locales', () => {
    // ⚠ The half a static scan is blind to. A code added on the Python side surfaces here.
    const missing: string[] = []
    for (const code of CODES) {
      for (const [name, loc] of LOCALES) {
        if (typeof resolve(loc, `${NS}.cat.${code}`) !== 'string') missing.push(`${name}: ${code}`)
      }
    }
    expect(missing).toEqual([])
  })

  test('en / ms / ta key sets are identical under the namespace', () => {
    const sets = LOCALES.map(([, loc]) => {
      const out: string[] = []
      leafPaths((resolve(loc, NS) ?? {}) as Record<string, unknown>, '', out)
      return out.sort()
    })
    expect(sets[0].length).toBeGreaterThan(0)
    expect(sets[1]).toEqual(sets[0])
    expect(sets[2]).toEqual(sets[0])
  })

  test('the assumptions note states no threshold, in any language', () => {
    // ⚠ brief §4d: a number in prose rots the day it is tuned. It must say "small amounts".
    for (const [name, loc] of LOCALES) {
      const note = String(resolve(loc, `${NS}.note`) ?? '')
      expect(note).not.toMatch(/\d/)
      expect(note.toUpperCase()).not.toContain('RM')
      expect(note.length).toBeGreaterThan(80)     // it is a real explanation, not a stub
      expect(name).toBeTruthy()
    }
  })

  test('the note names no shop, in any language', () => {
    // Real merchants from the corpus. None of them, nor the word "merchant", belongs in copy a
    // sponsor reads — the whole privacy ruling is that a shop is never named to them.
    const SHOPS = ['SPEEDMART', 'KOPERASI', 'KTMB', 'ENGINEER', 'ECONSAVE', 'MYDIN']
    for (const [, loc] of LOCALES) {
      const note = String(resolve(loc, `${NS}.note`) ?? '').toUpperCase()
      for (const shop of SHOPS) expect(note).not.toContain(shop)
    }
  })

  test('the placeholder copy claiming the feature is "coming soon" is gone', () => {
    // ⚠ Copy asserting a capability's ABSENCE goes stale the day it ships, and this repo has been
    // caught by that three times. Removed from all three locales together so parity holds.
    for (const [, loc] of LOCALES) {
      expect(resolve(loc, 'sponsorPortal.myStudents.detail.spendingSoon')).toBeUndefined()
      expect(resolve(loc, 'sponsorPortal.myStudents.detail.soon')).toBeUndefined()
    }
  })

  test('the heading key it sits beside is still a STRING, not an object', () => {
    // The new block is a SIBLING called `spend`; turning `spending` into an object would break the
    // existing heading with no error anywhere.
    for (const [, loc] of LOCALES) {
      expect(typeof resolve(loc, 'sponsorPortal.myStudents.detail.spending')).toBe('string')
    }
  })
})
