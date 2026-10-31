/**
 * `getMyActivity` (common profile S5): the page size goes out as `?limit=`, the cursor only when
 * there is one (the My activity card asks for 6 rows first, 20 per Show older — owner, 2026-11-01).
 */
import { getMyActivity } from '@/lib/admin-api'

describe('getMyActivity', () => {
  const orig = global.fetch
  afterEach(() => { global.fetch = orig })
  const url = () => new URL((global.fetch as jest.Mock).mock.calls[0][0] as string, 'http://x')

  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ results: [], next: null }),
    }) as unknown as typeof fetch
  })

  test('the first page carries kind and limit, and no cursor', async () => {
    await getMyActivity('all', null, 6, { token: 't' })
    const u = url()
    expect(u.pathname).toContain('/api/v1/admin/me/activity/')
    expect(u.searchParams.get('kind')).toBe('all')
    expect(u.searchParams.get('limit')).toBe('6')
    expect(u.searchParams.has('cursor')).toBe(false)
  })

  test('an older page carries the cursor and its own limit', async () => {
    await getMyActivity('money', 'CUR1', 20, { token: 't' })
    const u = url()
    expect(u.searchParams.get('kind')).toBe('money')
    expect(u.searchParams.get('cursor')).toBe('CUR1')
    expect(u.searchParams.get('limit')).toBe('20')
  })
})
