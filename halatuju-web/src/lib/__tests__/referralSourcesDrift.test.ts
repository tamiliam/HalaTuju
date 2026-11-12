/**
 * Referral sources DRIFT — the three fixed choices, which the server holds too
 * (`gift_sources.FIXED_CODES`).
 *
 * The server accepts exactly blank, the fixed three, or a source the gift offers. If the web's
 * three drift from the server's, the form would either offer a choice the server refuses at
 * submit, or hide one the server accepts. So the two lists must be EQUAL, in order. The helpers'
 * behaviour is `referralSources.test.ts`.
 */
import { FIXED_REFERRAL_CODES } from '@/lib/referralSources'
import { pySeq, readApi } from '@/test/apiSource'

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
