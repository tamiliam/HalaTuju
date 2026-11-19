/**
 * Sources + witness-assignment admin-api client (Contract Go-Live T2).
 * Asserts each function hits the right URL / method / body and surfaces the
 * server error `code` — the endpoints are super/org_admin-fenced on the backend.
 */
import {
  getSources, updateSource, assignWitness, inviteSource, resendSourceUser, revokeSourceUser,
  getSourceApplications, getSourceAgreement, witnessAsSource, getSourceOverview, updateSourceProfile,
} from '@/lib/admin-api'

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

  // Source sign-in S2: a source is ADDED by inviting its person (the Sources POST is 410).
  test('inviteSource POSTs a source_partner invitation for an existing source', async () => {
    mockFetch(201, { id: 9, admin_id: 4, emailed: true, message: 'ok' })
    await inviteSource({ name: 'Kavi', email: 'k@example.org', source_id: 3 }, { token: 't' })
    const [url, init] = call()
    expect(url).toContain('/api/v1/admin/invitations/')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body!)).toEqual(
      { audience: 'source_partner', name: 'Kavi', email: 'k@example.org', source_id: 3 })
  })

  test('inviteSource carries a NEW source as source_name + source_code, and its refusal code', async () => {
    mockFetch(400, { error: 'code_taken', code: 'code_taken' })
    await expect(inviteSource({ name: 'Kavi', email: 'k@example.org', source_name: 'HSS',
                                source_code: 'hss' }, { token: 't' }))
      .rejects.toMatchObject({ code: 'code_taken', status: 400 })
    expect(JSON.parse(call()[1].body!)).toMatchObject({ source_name: 'HSS', source_code: 'hss' })
  })

  test('resend and revoke a source user POST their own endpoints', async () => {
    mockFetch(200, { message: 'ok', emailed: true })
    await resendSourceUser(4, { token: 't' })
    expect(call()[0]).toContain('/api/v1/admin/source-users/4/resend/')
    mockFetch(200, { id: 4, is_active: false, message: 'ok' })
    await revokeSourceUser(4, { token: 't' })
    expect(call()[0]).toContain('/api/v1/admin/source-users/4/revoke/')
    expect(call()[1].method).toBe('POST')
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

/**
 * The source console client (source sign-in S3 + S4): every call is under `admin/source/`, the
 * gift travels as `p`, and the PDF link is asked for only with `?link=1`.
 */
describe('Source console admin-api', () => {
  const orig = global.fetch
  afterEach(() => { global.fetch = orig })

  test('lists send p / q / stage / page and drop the blanks', async () => {
    mockFetch(200, { applications: [] })
    await getSourceApplications({ p: 'flag', q: 'Priya', stage: '', page: 2 }, { token: 't' })
    const url = call()[0]
    expect(url).toContain('/api/v1/admin/source/applications/?')
    expect(url).toContain('p=flag')
    expect(url).toContain('q=Priya')
    expect(url).toContain('page=2')
    expect(url).not.toContain('stage=')
    mockFetch(200, {})
    await getSourceOverview(undefined, { token: 't' })
    expect(call()[0]).toMatch(/\/api\/v1\/admin\/source\/overview\/$/)
  })

  test('the agreement mints a PDF link only when asked', async () => {
    mockFetch(200, {})
    await getSourceAgreement(5, { token: 't' })
    expect(call()[0]).toMatch(/\/admin\/source\/applications\/5\/agreement\/$/)
    await getSourceAgreement(5, { token: 't', link: true })
    expect((global.fetch as jest.Mock).mock.calls[1][0]).toContain('/agreement/?link=1')
  })

  test('the witness POST and the profile PATCH carry their bodies and refusal codes', async () => {
    mockFetch(409, { error: 'already_witnessed', code: 'already_witnessed' })
    await expect(witnessAsSource(5, { witness_name: 'Audrey', confirm: true }, { token: 't' }))
      .rejects.toMatchObject({ code: 'already_witnessed', status: 409 })
    expect(call()[0]).toContain('/api/v1/admin/source/applications/5/witness/')
    expect(JSON.parse(call()[1].body!)).toEqual({ witness_name: 'Audrey', confirm: true })
    mockFetch(200, {})
    await updateSourceProfile({ user: { name: 'Audrey' } }, { token: 't' })
    expect(call()[0]).toContain('/api/v1/admin/source/profile/')
    expect(call()[1].method).toBe('PATCH')
  })
})
