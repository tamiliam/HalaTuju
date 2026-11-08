/**
 * A1.13b (TD-198): the four award-withdrawal calls, MAKER and CHECKER. Each POSTs to its own route
 * with its own body (the old super-only `withdraw-award/` route is gone), and a refusal keeps the
 * API's `code` so the card can say it in words.
 */
import {
  approveAwardWithdrawal, cancelAwardWithdrawal, refuseAwardWithdrawal, requestAwardWithdrawal,
} from '@/lib/admin-api'

describe('award withdrawal calls', () => {
  const orig = global.fetch
  afterEach(() => { global.fetch = orig })
  const call = () => (global.fetch as jest.Mock).mock.calls[0]
  const path = () => new URL(call()[0] as string, 'http://x').pathname
  const sent = () => {
    const init = call()[1] as RequestInit
    return { method: init.method, body: JSON.parse(String(init.body)), auth: (init.headers as Record<string, string>).Authorization }
  }
  const answer = (ok: boolean, status: number, body: unknown) => {
    global.fetch = jest.fn().mockResolvedValue({ ok, status, json: async () => body }) as unknown as typeof fetch
  }

  beforeEach(() => answer(true, 200, { id: 7 }))

  test('the maker asks on the case, with the explanation', async () => {
    await requestAwardWithdrawal(7, 'Dummy explanation', { token: 't' })
    expect(path()).toMatch(/\/api\/v1\/admin\/scholarship\/applications\/7\/withdrawal-request\/$/)
    expect(sent()).toEqual({ method: 'POST', body: { explanation: 'Dummy explanation' }, auth: 'Bearer t' })
  })

  test('a checker approves the request; an empty note is not sent', async () => {
    await approveAwardWithdrawal(31, '', { token: 't' })
    expect(path()).toMatch(/\/api\/v1\/admin\/scholarship\/withdrawal-requests\/31\/approve\/$/)
    expect(sent().body).toEqual({})
  })

  test('a note, when given, goes with the approval', async () => {
    await approveAwardWithdrawal(31, 'Dummy note', { token: 't' })
    expect(sent().body).toEqual({ note: 'Dummy note' })
  })

  test('a checker refuses with the reason', async () => {
    await refuseAwardWithdrawal(31, 'Dummy reason', { token: 't' })
    expect(path()).toMatch(/\/api\/v1\/admin\/scholarship\/withdrawal-requests\/31\/refuse\/$/)
    expect(sent().body).toEqual({ reason: 'Dummy reason' })
  })

  test('the maker cancels with an empty body', async () => {
    await cancelAwardWithdrawal(31, { token: 't' })
    expect(path()).toMatch(/\/api\/v1\/admin\/scholarship\/withdrawal-requests\/31\/cancel\/$/)
    expect(sent()).toEqual({ method: 'POST', body: {}, auth: 'Bearer t' })
  })

  test('the case detail comes back as served', async () => {
    await expect(cancelAwardWithdrawal(31, { token: 't' })).resolves.toEqual({ id: 7 })
  })

  test('a refusal keeps its code and status', async () => {
    answer(false, 403, { error: 'same_person', code: 'same_person' })
    await expect(approveAwardWithdrawal(31, '', { token: 't' })).rejects.toMatchObject({ code: 'same_person', status: 403 })
  })
})
