/**
 * @jest-environment jsdom
 *
 * Staff nudges (2026-11-08): the completion bar on the Profile page, wired — it shows the SERVED
 * `completion` above every card, follows a save and a photo change, and hands each new answer to the
 * console (`setProfileCompletion`) so the top banner follows at once. A super is served none.
 * (The card itself is `components/adminProfile/CompletionCard.test.tsx`; this page's big suite is
 * `page.test.tsx`.)
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import ProfilePage from './page'
import { ME } from '@/components/source/testFixtures'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k}(${Object.values(v).join('|')})` : k), locale: 'en' }),
}))
let mockAuth: Record<string, unknown> = {}
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => mockAuth }))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/lib/admin-supabase', () => ({ getAdminSupabase: () => ({ auth: {} }), adminSignInWithPassword: jest.fn() }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const P = 'admin.myProfile.completion'
const setProfileCompletion = jest.fn()
const of = (done: number, missing: api.CompletionKey[]): api.ProfileCompletion => ({
  items: (['photo', 'name', 'job_title', 'about', 'phone'] as api.CompletionKey[])
    .map((key) => ({ key, done: !missing.includes(key) })),
  done, total: 5, percent: done * 20, important_missing: missing.filter((k) => k === 'photo' || k === 'phone'),
})
const STAFF_ME: api.AdminMe = { ...ME, name: 'Priya', role: 'admin', source: null,
  permissions: ['see_all'], phone: '12-345 6789', completion: of(3, ['photo', 'about']) }

function signIn(role: string) {
  mockAuth = {
    token: 'tok', refreshRole: jest.fn(() => Promise.resolve()), setPhotoUrl: jest.fn(), setProfileCompletion,
    session: { user: { app_metadata: { providers: ['email'] } } },
    role: { role, is_admin: true, is_super_admin: role === 'super', permissions: [], reviewer_profile_complete: true },
  }
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getAdminMe.mockResolvedValue(STAFF_ME)
  mockApi.getMyActivity.mockResolvedValue({ results: [], next: null })
})

it('shows the served completion above every card', async () => {
  signIn('admin')
  render(<ProfilePage />)
  const card = await screen.findByTestId('profile-completion')
  expect(card.textContent).toContain(`${P}.title(60)`)
  expect(card.textContent).toContain(`${P}.count(3|5)`)
  await screen.findByTestId('profile-card-you')
  const order = Array.from(screen.getByTestId('admin-profile').querySelectorAll('[data-testid^="profile-c"]'))
    .map((n) => n.getAttribute('data-testid'))
  expect(order[0]).toBe('profile-completion')
  expect(order[1]).toBe('profile-card-you')
})

it('a save hands the new completion to the card and to the console banner', async () => {
  signIn('admin')
  mockApi.updateAdminMe.mockResolvedValue({ ...STAFF_ME, about: 'Hi', completion: of(4, ['photo']) })
  render(<ProfilePage />)
  await screen.findByTestId('profile-completion')
  fireEvent.change(await screen.findByLabelText('admin.myProfile.about'), { target: { value: 'Hi' } })
  fireEvent.click(screen.getByText('common.save'))
  await waitFor(() => expect(setProfileCompletion).toHaveBeenCalledWith(of(4, ['photo'])))
  expect(screen.getByTestId('profile-completion').textContent).toContain(`${P}.count(4|5)`)
})

it('a photo change does too, from the photo answer', async () => {
  signIn('admin')
  mockApi.uploadAdminPhoto.mockResolvedValue({ photo_url: 'https://signed/p.webp', completion: of(4, ['about']) })
  render(<ProfilePage />)
  const input = await screen.findByTestId('photo-input')
  fireEvent.change(input, { target: { files: [new File(['x'], 'me.png', { type: 'image/png' })] } })
  await waitFor(() => expect(setProfileCompletion).toHaveBeenCalledWith(of(4, ['about'])))
  expect(screen.getByTestId('profile-completion').textContent).toContain(`${P}.count(4|5)`)
})

it('a super is served none and sees no bar', async () => {
  signIn('super')
  mockApi.getAdminMe.mockResolvedValue({ ...STAFF_ME, role: 'super', is_super: true, completion: null })
  render(<ProfilePage />)
  await screen.findByTestId('profile-card-you')
  expect(screen.queryByTestId('profile-completion')).toBeNull()
})
