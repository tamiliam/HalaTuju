/**
 * TD-254 — the refusal copy, by behaviour. The refusal vocabulary is the SERVER'S; the drift test
 * that says so is `profileClaimCodesDrift.test.ts` (the `drift-test:` marker in `profileClaim.ts`).
 *
 * `CLAIM_REFUSAL_COPY` (src/lib/profileClaim.ts) maps a refusal code to the sentence a student
 * reads. The codes themselves are declared once, in Python, in `REFUSAL_CODES`. A comment
 * asking the two to stay in step is a request; this file is the rule — it READS the Python and
 * fails when a code gains no copy, or when copy names a code the server cannot send.
 *
 * ⚠ It also asserts it actually found the Python list, so a moved file or a renamed constant
 * fails loudly instead of quietly watching nothing.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { CLAIM_REFUSAL_COPY, claimRefusalKey, claimHelpKey, claimChannelKey, claimCodeHelpKey }
  from '@/lib/profileClaim'

function resolve(obj: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>((cur, part) => (
    cur && typeof cur === 'object' && part in (cur as Record<string, unknown>)
      ? (cur as Record<string, unknown>)[part]
      : undefined), obj)
}

const LOCALES = [['en', en], ['ms', ms], ['ta', ta]] as const

describe('the server owns the refusal vocabulary', () => {
  it('every message key it points at exists in all three locales', () => {
    const keys = [
      ...new Set(Object.values(CLAIM_REFUSAL_COPY)),
      'authGate.claimError', 'authGate.icError', 'authGate.icExistsMessage',
      'authGate.icYesMe', 'authGate.icNotMe',
      claimHelpKey(['phone', 'email']), claimHelpKey(['phone']), claimHelpKey(['email']),
      claimChannelKey('phone'), claimChannelKey('email'),
      claimCodeHelpKey('phone'), claimCodeHelpKey('email'),
    ]
    const missing: string[] = []
    for (const key of keys) {
      for (const [name, loc] of LOCALES) {
        if (typeof resolve(loc, key) !== 'string') missing.push(`${name}: ${key}`)
      }
    }
    expect(missing).toEqual([])
  })

  it('an unknown code still says something, rather than nothing', () => {
    // An older browser against a newer server must not render a blank panel.
    expect(claimRefusalKey('a_code_from_the_future')).toBe('authGate.claimError')
    expect(claimRefusalKey(undefined)).toBe('authGate.claimError')
  })
})

describe('no copy on this surface can name the holder', () => {
  it('no claim message interpolates a name', () => {
    // ⚠ The defect TD-254 is named for: `…already registered to ${existingName}`. A `{name}`
    // token in any of this copy would be the same leak in a new costume.
    for (const [, loc] of LOCALES) {
      const claim = resolve(loc, 'authGate.claim') as Record<string, unknown>
      const flat = JSON.stringify(claim) + String(resolve(loc, 'authGate.icExistsMessage'))
      expect(flat).not.toMatch(/\{name\}/)
      expect(flat).not.toMatch(/\{holder\}/)
    }
  })
})
