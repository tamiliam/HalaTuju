/**
 * The 409 `programme_required` is recognisable after it has crossed `apiRequest` (apply gift
 * clarity, 2026-10-05).
 *
 * The server's refusal body is `{error: '<sentence>', code: 'programme_required'}`. `apiRequest`
 * puts `error` first into `err.code` (so that is the SENTENCE), which is why the body's own code is
 * carried separately as `bodyCode`. The apply page answers this one refusal by asking which gift
 * again instead of showing a dead-end error — so the wire shape is pinned here, through the real
 * fetch helper, not a hand-built error object.
 */
import { submitScholarshipApplication } from '@/lib/api'
import { isProgrammeRequired } from '@/lib/useApplyGift'

const realFetch = global.fetch
afterEach(() => { global.fetch = realFetch })

function reply(status: number, body: unknown) {
  global.fetch = jest.fn(async () => ({
    ok: status < 400, status, json: async () => body,
  }) as Response) as unknown as typeof fetch
}

async function refusal(): Promise<unknown> {
  try {
    await submitScholarshipApplication({}, 'en', { token: 't' })
  } catch (err) {
    return err
  }
  throw new Error('expected the submit to be refused')
}

it("recognises the server's own 409 programme_required body", async () => {
  reply(409, { error: 'We could not tell which programme this application is for.', code: 'programme_required' })
  expect(isProgrammeRequired(await refusal())).toBe(true)
})

it('does not mistake any other refusal for it', async () => {
  reply(409, { error: 'No open application round is currently available.' })
  expect(isProgrammeRequired(await refusal())).toBe(false)
  reply(409, { error: 'applications_closed', code: 'applications_closed' })
  expect(isProgrammeRequired(await refusal())).toBe(false)
  expect(isProgrammeRequired(null)).toBe(false)
  expect(isProgrammeRequired(new Error('network'))).toBe(false)
})
