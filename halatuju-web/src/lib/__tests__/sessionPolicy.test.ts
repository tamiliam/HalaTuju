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

  // TD-360 (2026-10-21): the super check moved from `navigation.effectiveRole` to the leaf
  // `superRole.isSuperRole`, so this module (on every page) stops importing the admin route
  // registry. The two shapes the API can say "super" in must both still exempt.
  test('sponsor side also exempts a payload that says role: "super"', async () => {
    global.fetch = jest.fn(async () => ({ json: async () => ({ role: 'super' }) })) as unknown as typeof fetch
    await enforceSingleScope('sponsor', { token: 't' })
    expect(adminSignOut).not.toHaveBeenCalled()
  })

  test('an org admin is NOT super, so the sponsor side ends their admin session', async () => {
    global.fetch = jest.fn(async () => ({ json: async () => ({ role: 'admin', is_super_admin: false }) })) as unknown as typeof fetch
    await enforceSingleScope('sponsor', { token: 't' })
    expect(adminSignOut).toHaveBeenCalledWith({ scope: 'local' })
  })
})

describe('isSuperRole agrees with navigation.effectiveRole on every shape', () => {
  test('same answer for super, non-super, empty and missing payloads', () => {
    const { isSuperRole } = jest.requireActual('../superRole') as typeof import('../superRole')
    const { effectiveRole } = jest.requireActual('../navigation') as typeof import('../navigation')
    const shapes = [
      null, undefined, {}, { role: 'super' }, { is_super_admin: true }, { is_super_admin: false },
      { role: 'admin' }, { role: 'reviewer', is_super_admin: true }, { role: 'nonsense' },
    ]
    for (const s of shapes) expect(isSuperRole(s)).toBe(effectiveRole(s) === 'super')
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
