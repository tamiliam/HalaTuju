/**
 * "Who referred you?" helpers (per-gift referral sources, Sprint 2, 2026-10-08) — and the DRIFT
 * TEST for the three fixed choices, which the server holds too (`gift_sources.FIXED_CODES`).
 *
 * The server accepts exactly blank, the fixed three, or a source the gift offers. If the web's
 * three drift from the server's, the form would either offer a choice the server refuses at
 * submit, or hide one the server accepts. So the two lists must be EQUAL, in order.
 */
import {
  FIXED_REFERRAL_CODES, isReferralNotOffered, offeredFixedCodes, referralLabel, referralOptions,
} from '@/lib/referralSources'
import { pySeq, readApi } from '@/test/apiSource'

const t = (k: string) => `T:${k}`

describe('the fixed three match the server (drift)', () => {
  it('equals `gift_sources.FIXED_CODES`, in order', () => {
    const server = pySeq(readApi('apps/scholarship/gift_sources.py'), 'FIXED_CODES')
    expect(server.length).toBe(3)                 // the read found the tuple, not nothing
    expect([...FIXED_REFERRAL_CODES]).toEqual(server)
  })

  it('the server lets a gift switch off exactly halatuju and social — never other (request #44)', () => {
    const line = readApi('apps/scholarship/gift_sources.py').split('\n')
      .find((l) => l.startsWith('SWITCHABLE_FIXED = {')) ?? ''
    const keys = Array.from(line.matchAll(/'(\w+)':/g)).map((m) => m[1])
    expect(keys).toEqual(['halatuju', 'social'])
  })
})

describe('referralOptions', () => {
  it('lists the served sources by their server name, then the fixed three', () => {
    expect(referralOptions([{ code: 'smc', name: 'Sri Murugan Centre' }], t)).toEqual([
      { code: 'smc', label: 'Sri Murugan Centre' },
      { code: 'halatuju', label: 'T:scholarship.apply.org.halatuju' },
      { code: 'social', label: 'T:scholarship.apply.org.social' },
      { code: 'other', label: 'T:scholarship.apply.org.other' },
    ])
  })

  it('keeps a fixed choice once, with its own label, when a source code collides', () => {
    const codes = referralOptions([{ code: 'other', name: 'A source called other' },
      { code: 'smc', name: 'SMC' }, { code: 'smc', name: 'SMC again' }], t).map((o) => o.code)
    expect(codes).toEqual(['smc', 'halatuju', 'social', 'other'])
  })

  it('is the fixed three alone when the intake sent no sources', () => {
    for (const none of [undefined, null, []]) {
      expect(referralOptions(none, t).map((o) => o.code)).toEqual(['halatuju', 'social', 'other'])
    }
  })

  // Request #44: the served `fixed_sources` narrows the fixed choices; absent → all three.
  it('offers only the served fixed choices, in the web order, with Other always', () => {
    const codes = (fixed?: string[] | null) => referralOptions([SMC_ROW], t, fixed).map((o) => o.code)
    expect(codes(['other', 'halatuju'])).toEqual(['smc', 'halatuju', 'other'])
    expect(codes(['other'])).toEqual(['smc', 'other'])
    expect(codes([])).toEqual(['smc', 'other'])                     // Other is never switched off
    expect(codes(['social', 'nope', 'other'])).toEqual(['smc', 'social', 'other'])   // unknown codes ignored
    for (const absent of [undefined, null]) expect(codes(absent)).toEqual(['smc', 'halatuju', 'social', 'other'])
    expect(offeredFixedCodes(undefined)).toEqual(['halatuju', 'social', 'other'])
  })

  it('drops a colliding source code even when that fixed choice is switched off', () => {
    expect(referralOptions([{ code: 'social', name: 'Fake' }], t, ['other']).map((o) => o.code))
      .toEqual(['other'])
  })
})

const SMC_ROW = { code: 'smc', name: 'SMC' }

describe('referralLabel', () => {
  it('reads a fixed code from i18n, a source from the names, else the bare code', () => {
    expect(referralLabel('social', t)).toBe('T:scholarship.apply.org.social')
    expect(referralLabel('smc', t, { smc: 'Sri Murugan Centre' })).toBe('Sri Murugan Centre')
    // A new source the screen has no name for yet: its code, never a raw message key.
    expect(referralLabel('newsrc', t, {})).toBe('newsrc')
    expect(referralLabel('', t)).toBe('')
    expect(referralLabel(null, t)).toBe('')
  })
})

it('recognises the server refusal by its code', () => {
  expect(isReferralNotOffered({ bodyCode: 'referral_source_not_offered' })).toBe(true)
  expect(isReferralNotOffered({ bodyCode: 'programme_required' })).toBe(false)
  expect(isReferralNotOffered(null)).toBe(false)
})
