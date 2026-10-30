/**
 * @jest-environment jsdom
 *
 * Set your password → in through THE landing rule (source sign-in, roadmap C9).
 *
 * The page used to hand-roll its redirect — reviewer → Applications, everyone else → `/admin`, the
 * super-only platform dashboard — so an org_admin, a finance admin and (since S2) a newly invited
 * SOURCE user would each land on a page that bounced them. It now asks `adminLanding`, the one
 * home of the rule, with the role the server serves after the password is set.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import AdminSetPasswordPage from './page'
import * as api from '@/lib/admin-api'

const replace = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/BrandLogo', () => () => null)
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const session = { access_token: 'tok', user: { email: 'kavi@example.org' } }
jest.mock('@/lib/admin-supabase', () => ({
  getAdminSupabase: () => ({
    auth: {
      getSession: async () => ({ data: { session } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
    },
  }),
}))

function servedRole(role: Record<string, unknown>) {
  global.fetch = jest.fn().mockResolvedValue({ json: async () => ({ is_admin: true, ...role }) }) as
    unknown as typeof fetch
}

async function setPassword() {
  render(<AdminSetPasswordPage />)
  await waitFor(() => expect(screen.getByDisplayValue('kavi@example.org')).toBeTruthy())
  const boxes = document.querySelectorAll('input[type="password"]')
  fireEvent.change(boxes[0], { target: { value: 'a-good-password' } })
  fireEvent.change(boxes[1], { target: { value: 'a-good-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'admin.setPasswordCta' }))
}

beforeEach(() => {
  replace.mockReset()
  mockApi.adminSetPassword.mockResolvedValue(undefined as never)
})

it.each([
  [{ role: 'source_partner', source_name: 'MUETMyWay' }, '/admin/programme/overview'],
  [{ role: 'org_admin' }, '/admin/organisation'],
  [{ role: 'finance' }, '/admin/organisation'],
  [{ role: 'reviewer', reviewer_profile_complete: false }, '/admin/profile'],
  [{ role: 'super', is_super_admin: true }, '/admin'],
])('lands %j on %s', async (role, where) => {
  servedRole(role)
  await setPassword()
  await waitFor(() => expect(replace).toHaveBeenCalledWith(where))
  expect(mockApi.adminSetPassword).toHaveBeenCalledWith('a-good-password', { token: 'tok' })
})
