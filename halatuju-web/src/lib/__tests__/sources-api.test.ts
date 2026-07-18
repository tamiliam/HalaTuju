/**
 * Sources + witness-assignment admin-api client (Contract Go-Live T2).
 * Asserts each function hits the right URL / method / body and surfaces the
 * server error `code` — the endpoints are super/org_admin-fenced on the backend.
 */
import { getSources, createSource, updateSource, assignWitness } from '@/lib/admin-api'

type Init = { method?: string; headers?: Record<string, string>; body?: string }
const call = (n = 0): [string, Init] => {
  const c = (global.fetch as jest.Mock).mock.calls[n]
  return [c[0] as string, (c[1] || {}) as Init]
}
function mockFetch(status: number, body: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status < 400, status, json: async () => body,
  }) as unknown as typeof fetch
}

describe('Sources admin-api', () => {
  const orig = global.fetch
  afterEach(() => { global.fetch = orig })

  test('getSources GETs the sources endpoint with the bearer token', async () => {
    mockFetch(200, { sources: [{ id: 1, code: 'smc', name: 'SMC', contact_person: '', contact_email: '', phone: '', show_in_apply: true, is_active: true, student_count: 9 }] })
    const d = await getSources({ token: 't' })
    expect(d.sources[0].code).toBe('smc')
    const [url, init] = call()
    expect(url).toContain('/api/v1/admin/scholarship/sources/')
    expect(init.headers?.Authorization).toBe('Bearer t')
  })

  test('createSource POSTs code + name', async () => {
    mockFetch(201, { id: 2, code: 'new', name: 'New' })
    await createSource({ code: 'new', name: 'New', phone: '012' }, { token: 't' })
    const [url, init] = call()
    expect(url).toContain('/api/v1/admin/scholarship/sources/')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body!)).toMatchObject({ code: 'new', name: 'New', phone: '012' })
  })

  test('createSource surfaces the code_taken error code on 400', async () => {
    mockFetch(400, { error: 'code_taken', code: 'code_taken' })
    await expect(createSource({ code: 'smc', name: 'X' }, { token: 't' }))
      .rejects.toMatchObject({ code: 'code_taken' })
  })

  test('updateSource PATCHes the id-scoped endpoint', async () => {
    mockFetch(200, { id: 5, show_in_apply: false })
    await updateSource(5, { show_in_apply: false }, { token: 't' })
    const [url, init] = call()
    expect(url).toContain('/api/v1/admin/scholarship/sources/5/')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body!)).toEqual({ show_in_apply: false })
  })

  test('assignWitness PATCHes the witness endpoint with a code, then clears with null', async () => {
    mockFetch(200, { id: 7, witness_org: 'smc', witness_org_name: 'SMC' })
    await assignWitness(7, 'smc', { token: 't' })
    let [url, init] = call()
    expect(url).toContain('/api/v1/admin/scholarship/applications/7/witness/')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body!).witness_org).toBe('smc')

    mockFetch(200, { id: 7, witness_org: null, witness_org_name: null })
    await assignWitness(7, null, { token: 't' })
    ;[url, init] = call()
    expect(JSON.parse(init.body!).witness_org).toBeNull()
  })
})
