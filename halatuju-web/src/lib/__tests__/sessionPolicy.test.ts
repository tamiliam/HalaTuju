// Node test env (no jsdom) — provide a tiny in-memory localStorage the policy can use.
const _store: Record<string, string> = {}
;(global as unknown as { localStorage: Storage }).localStorage = {
  getItem: (k: string) => (k in _store ? _store[k] : null),
  setItem: (k: string, v: string) => { _store[k] = v },
  removeItem: (k: string) => { delete _store[k] },
  clear: () => { for (const k of Object.keys(_store)) delete _store[k] },
  key: () => null, length: 0,
} as Storage

import { enforceSingleScope, consumeSuperseded, wasScopeSuperseded } from '../sessionPolicy'

const sponsorSignOut = jest.fn()
const adminSignOut = jest.fn()
let sponsorSession: { access_token: string } | null = { access_token: 'x' }
let adminSession: { access_token: string } | null = { access_token: 'y' }

jest.mock('../sponsor-supabase', () => ({
  getSponsorSupabase: () => ({
    auth: {
      getSession: async () => ({ data: { session: sponsorSession } }),
      signOut: (opts: unknown) => { sponsorSignOut(opts); sponsorSession = null; return Promise.resolve({ error: null }) },
    },
  }),
}))
jest.mock('../admin-supabase', () => ({
  getAdminSupabase: () => ({
    auth: {
      getSession: async () => ({ data: { session: adminSession } }),
      signOut: (opts: unknown) => { adminSignOut(opts); adminSession = null; return Promise.resolve({ error: null }) },
    },
  }),
}))

beforeEach(() => {
  localStorage.clear()
  sponsorSignOut.mockClear(); adminSignOut.mockClear()
  sponsorSession = { access_token: 'x' }; adminSession = { access_token: 'y' }
})

describe('enforceSingleScope — one privileged scope per identity, super exempt', () => {
  test('a super admin keeps BOTH scopes (no kick)', async () => {
    await enforceSingleScope('admin', { token: 't', isSuper: true })
    expect(sponsorSignOut).not.toHaveBeenCalled()
    expect(wasScopeSuperseded('sponsor')).toBe(false)
  })

  test('a non-super admin login ends the active sponsor session + flags it', async () => {
    await enforceSingleScope('admin', { token: 't', isSuper: false })
    expect(sponsorSignOut).toHaveBeenCalledWith({ scope: 'local' })
    expect(wasScopeSuperseded('sponsor')).toBe(true)
  })

  test('no other-scope session → no signout, no flag', async () => {
    sponsorSession = null
    await enforceSingleScope('admin', { token: 't', isSuper: false })
    expect(sponsorSignOut).not.toHaveBeenCalled()
    expect(wasScopeSuperseded('sponsor')).toBe(false)
  })

  test('sponsor side resolves super via /admin/role/ and exempts a super admin', async () => {
    global.fetch = jest.fn(async () => ({ json: async () => ({ is_super_admin: true }) })) as unknown as typeof fetch
    await enforceSingleScope('sponsor', { token: 't' })
    expect(adminSignOut).not.toHaveBeenCalled()
  })

  test('sponsor side ends the admin session when the identity is not super', async () => {
    global.fetch = jest.fn(async () => ({ json: async () => ({ is_admin: false }) })) as unknown as typeof fetch
    await enforceSingleScope('sponsor', { token: 't' })
    expect(adminSignOut).toHaveBeenCalledWith({ scope: 'local' })
    expect(wasScopeSuperseded('admin')).toBe(true)
  })
})

describe('consumeSuperseded', () => {
  test('reads the flag once, then clears it', () => {
    localStorage.setItem('halatuju_scope_superseded', 'sponsor')
    expect(wasScopeSuperseded('sponsor')).toBe(true)
    expect(consumeSuperseded('sponsor')).toBe(true)
    expect(consumeSuperseded('sponsor')).toBe(false)
  })
})
