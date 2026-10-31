/**
 * @jest-environment jsdom
 *
 * The header photo in the admin auth context (common profile S2, review fix L6): ONE `admin/me/`
 * read per signed-in person; cleared on sign-out; a different person never sees the last one's photo.
 */
import { act, render, screen, waitFor } from '@testing-library/react'
import { AdminAuthProvider, useAdminAuth } from '@/lib/admin-auth-context'

type Cb = (event: string, session: { access_token: string } | null) => void
let authCb: Cb = () => {}
jest.mock('@/lib/admin-supabase', () => ({
  getAdminSession: () => Promise.resolve({ session: { access_token: 'tok-1' } }),
  getAdminSupabase: () => ({ auth: { onAuthStateChange: (cb: Cb) => {
    authCb = cb
    return { data: { subscription: { unsubscribe: () => {} } } }
  } } }),
}))

const PEOPLE: Record<string, { id: number; photo: string | null }> = {
  'tok-1': { id: 1, photo: 'https://signed/one.webp' },
  'tok-2': { id: 2, photo: null },
}

function Show() {
  const { photoUrl } = useAdminAuth()
  return <p data-testid="photo">{photoUrl ?? 'none'}</p>
}

beforeEach(() => {
  global.fetch = jest.fn((url: string, init?: { headers?: Record<string, string> }) => {
    const who = PEOPLE[(init?.headers?.Authorization ?? '').replace('Bearer ', '')]
    const body = String(url).endsWith('/admin/role/')
      ? { is_admin: true, admin_id: who.id, role: 'admin' }
      : { photo_url: who.photo }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
  }) as unknown as typeof fetch
})

const meCalls = () => (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).endsWith('/admin/me/')).length

it('reads the photo once, clears it on sign-out, and never shows it to the next person', async () => {
  render(<AdminAuthProvider><Show /></AdminAuthProvider>)
  await waitFor(() => expect(screen.getByTestId('photo').textContent).toBe('https://signed/one.webp'))
  expect(meCalls()).toBe(1)

  await act(async () => { authCb('SIGNED_OUT', null) })
  await waitFor(() => expect(screen.getByTestId('photo').textContent).toBe('none'))

  await act(async () => { authCb('SIGNED_IN', { access_token: 'tok-2' }) })
  await waitFor(() => expect(meCalls()).toBe(2))
  expect(screen.getByTestId('photo').textContent).toBe('none')        // person 2 has none
})

it('a token refresh for the same person does not read the photo again', async () => {
  render(<AdminAuthProvider><Show /></AdminAuthProvider>)
  await waitFor(() => expect(meCalls()).toBe(1))
  PEOPLE['tok-1b'] = PEOPLE['tok-1']
  await act(async () => { authCb('TOKEN_REFRESHED', { access_token: 'tok-1b' }) })
  await new Promise((r) => setTimeout(r, 20))
  expect(meCalls()).toBe(1)
  expect(screen.getByTestId('photo').textContent).toBe('https://signed/one.webp')
})
