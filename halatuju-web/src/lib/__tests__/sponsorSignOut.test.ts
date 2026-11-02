/**
 * @jest-environment jsdom
 *
 * The ONE sponsor sign-out path (`sponsorSignOut`, called by `SponsorLogOut`): it ends the sponsor
 * session only (`scope: 'local'` on the sponsor's own client) and — Mobile M5 review, shared phones —
 * removes the registration form's stash (name, phone) from this tab, whatever the sign-out returns.
 */
import { KEY_SPONSOR_PENDING, KEY_SPONSOR_REF } from '@/lib/storage'
import { sponsorSignOut } from '@/lib/sponsor-supabase'

const signOut = jest.fn()
jest.mock('@/lib/supabaseAuthClient', () => ({ createAuthOnlyClient: () => ({ auth: { signOut } }) }))
jest.mock('@/lib/turnstile', () => ({ getTurnstileToken: jest.fn() }))

// Read when the client is first built (at the first call), not at import.
process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://example.invalid'
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'anon'


beforeEach(() => {
  signOut.mockReset()
  sessionStorage.clear()
  sessionStorage.setItem(KEY_SPONSOR_PENDING, JSON.stringify({ name: 'Puan Contoh', phone: '0123456789' }))
  sessionStorage.setItem(KEY_SPONSOR_REF, 'INVITE1')
})

it('removes the registration stash and ends the sponsor session only', async () => {
  signOut.mockResolvedValue({ error: null })
  await sponsorSignOut()
  expect(sessionStorage.getItem(KEY_SPONSOR_PENDING)).toBeNull()
  expect(signOut).toHaveBeenCalledWith({ scope: 'local' })
  // The invite code holds no person's details; it stays.
  expect(sessionStorage.getItem(KEY_SPONSOR_REF)).toBe('INVITE1')
})

it('removes the stash even when the sign-out reports a failure', async () => {
  signOut.mockResolvedValue({ error: new Error('network') })
  const { error } = await sponsorSignOut()
  expect(error).toBeTruthy()
  expect(sessionStorage.getItem(KEY_SPONSOR_PENDING)).toBeNull()
})
