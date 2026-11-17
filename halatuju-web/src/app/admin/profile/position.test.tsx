/**
 * @jest-environment jsdom
 *
 * Request #69 (2026-11-17, board 1): "Highest position held" on My Profile — its own select directly
 * under Job title (an empty cell under Name keeps it there in the two-column grid), with "Choose one"
 * as the empty state that clears the answer, the hint and the note, optional, and saved through
 * `PATCH admin/me/`. (The completion item's link is `CompletionCard.test.tsx`.)
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import ProfilePage from './page'
import { ME } from '@/components/source/testFixtures'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k}(${Object.values(v).join('|')})` : k), locale: 'en', setLocale: jest.fn() }),
  LOCALE_LABELS: { en: 'English', ms: 'Bahasa Melayu', ta: 'தமிழ்' }, LOCALE_SHORT_LABELS: { en: 'English', ms: 'B. Melayu', ta: 'தமிழ்' },
}))
let mockAuth: Record<string, unknown> = {}
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => mockAuth }))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/lib/admin-supabase', () => ({ getAdminSupabase: () => ({ auth: {} }), adminSignInWithPassword: jest.fn() }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const P = 'admin.myProfile'
const STAFF_ME: api.AdminMe = { ...ME, name: 'Sample Person', role: 'admin', source: null,
  permissions: ['see_all'], phone: '12-345 6789', job_title: 'Officer', highest_position: '', completion: null }

beforeEach(() => {
  jest.clearAllMocks()
  mockAuth = {
    token: 'tok', refreshRole: jest.fn(() => Promise.resolve()), setPhotoUrl: jest.fn(), setProfileCompletion: jest.fn(),
    session: { user: { app_metadata: { providers: ['email'] } } },
    role: { role: 'admin', is_admin: true, is_super_admin: false, permissions: [], reviewer_profile_complete: true },
  }
  mockApi.getAdminMe.mockResolvedValue(STAFF_ME)
  mockApi.updateAdminMe.mockImplementation((data) => Promise.resolve({ ...STAFF_ME, ...data }))
  mockApi.getMyActivity.mockResolvedValue({ results: [], next: null })
})

const select = async () => (await screen.findByLabelText(`${P}.highestPosition`)) as HTMLSelectElement

it('sits under Job title and above About, "Choose one" first, then the four choices, with the hint and the note', async () => {
  render(<ProfilePage />)
  const sel = await select()
  expect(Array.from(sel.options).map((o) => [o.value, o.textContent])).toEqual([
    ['', `${P}.chooseOne`], ['c_level', 'admin.position.c_level'], ['head', 'admin.position.head'],
    ['manager', 'admin.position.manager'], ['individual', 'admin.position.individual']])
  expect(sel.value).toBe('')
  expect(sel.required).toBe(false)
  const fields = Array.from(screen.getByTestId('profile-card-you').querySelectorAll('input, select, textarea'))
  const job = screen.getByLabelText(`${P}.jobTitle`)
  const about = screen.getByLabelText(`${P}.about`)
  expect(fields.indexOf(sel)).toBe(fields.indexOf(job) + 1)
  expect(fields.indexOf(about)).toBe(fields.indexOf(sel) + 1)
  // The empty cell under Name puts it under Job title in the two-column grid (and nothing on a phone).
  expect((sel.parentElement?.previousElementSibling as HTMLElement).className).toContain('hidden sm:block')
  const described = (sel.getAttribute('aria-describedby') ?? '').split(' ').map((id) => document.getElementById(id)?.textContent)
  expect(described).toEqual([`${P}.highestPositionHint`, `${P}.highestPositionNote`])
})

it('a choice saves through admin/me', async () => {
  render(<ProfilePage />)
  fireEvent.change(await select(), { target: { value: 'manager' } })
  fireEvent.click(screen.getByText('common.save'))
  await waitFor(() => expect(mockApi.updateAdminMe).toHaveBeenCalledWith({ highest_position: 'manager' }, { token: 'tok' }))
})

it('"Choose one" clears a saved answer', async () => {
  mockApi.getAdminMe.mockResolvedValue({ ...STAFF_ME, highest_position: 'head' })
  render(<ProfilePage />)
  const sel = await select()
  await waitFor(() => expect(sel.value).toBe('head'))
  fireEvent.change(sel, { target: { value: '' } })
  fireEvent.click(screen.getByText('common.save'))
  await waitFor(() => expect(mockApi.updateAdminMe).toHaveBeenCalledWith({ highest_position: '' }, { token: 'tok' }))
})

it('a refusal reads in its own words', async () => {
  mockApi.updateAdminMe.mockRejectedValue(Object.assign(new Error('x'), { code: 'bad_highest_position' }))
  render(<ProfilePage />)
  fireEvent.change(await select(), { target: { value: 'head' } })
  fireEvent.click(screen.getByText('common.save'))
  expect(await screen.findByText(`${P}.error.bad_highest_position`)).toBeTruthy()
})
