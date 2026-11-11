/**
 * @jest-environment jsdom
 *
 * M1a review fix 7 (owner O16): the group tables show no phone, but the platform's own staff screens
 * (Organisations, Partners) are not group tables and keep theirs — they ask the Admins endpoint for it
 * (`getAdmins(options, true)` → `?phones=1`). The Team page's Admins tab does not ask
 * (`organisation/team/page.test.tsx`).
 */
import { render, waitFor } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import OrganisationsPage from './organisations/page'
import PartnersPage from './partners/page'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'super', is_super_admin: true } }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getAdmins.mockResolvedValue({ admins: [] })
  mockApi.getOrgs.mockResolvedValue({ orgs: [] } as unknown as Awaited<ReturnType<typeof api.getOrgs>>)
})

it.each([
  ['Organisations', OrganisationsPage],
  ['Partners', PartnersPage],
])('the %s page asks the Admins endpoint for phones', async (_name, Page) => {
  render(<Page />)
  await waitFor(() => expect(mockApi.getAdmins).toHaveBeenCalledWith({ token: 'tok' }, true))
})
