/**
 * @jest-environment jsdom
 *
 * TD-228 (2026-10-05): the ORGANISATION crumb narrows the Requests list. The page reads the crumb's
 * choice from `lib/orgScope` (the shell provides it) and sends it as `?org=`; with nothing chosen
 * it sends none, and the list is exactly what the caller's fence allows. The server re-fences it.
 */
import { render, waitFor } from '@testing-library/react'

import AdminRequestsPage from './page'
import * as api from '@/lib/admin-api'
import { OrgScopeProvider } from '@/lib/orgScope'

jest.mock('@/lib/admin-api')
jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'test-token', role: { role: 'super', is_super_admin: true } }),
}))

const mockApi = api as jest.Mocked<typeof api>

beforeEach(() => {
  jest.clearAllMocks()
  window.history.replaceState({}, '', '/admin/requests')
  // Requests list R1: the list is a page in the shared envelope.
  mockApi.getOrgRequests.mockResolvedValue({
    count: 0, total_pages: 1, page: 1, page_size: 25, requests: [], ids: [],
    summary: { action: 0, progress: 0, closed: 0, all: 0 },
  })
})

const lastFilters = () => mockApi.getOrgRequests.mock.calls.at(-1)?.[0]

describe('the organisation crumb on Requests (TD-228)', () => {
  it('sends the chosen organisation', async () => {
    render(
      <OrgScopeProvider value={{ selected: 'inspire', select: () => {} }}>
        <AdminRequestsPage />
      </OrgScopeProvider>,
    )
    await waitFor(() => expect(mockApi.getOrgRequests).toHaveBeenCalled())
    // The landing tab (Needs action, D9) and no filter — plus the crumb.
    expect(lastFilters()).toEqual({ group: 'action', kind: '', q: '', page: 1, org: 'inspire' })
  })

  it('sends none when nothing is chosen — the list the fence allows, as before', async () => {
    render(<AdminRequestsPage />)
    await waitFor(() => expect(mockApi.getOrgRequests).toHaveBeenCalled())
    expect(lastFilters()?.org).toBeUndefined()
  })

  it('asks again when the crumb changes', async () => {
    const tree = (code: string) => (
      <OrgScopeProvider value={{ selected: code, select: () => {} }}>
        <AdminRequestsPage />
      </OrgScopeProvider>
    )
    const { rerender } = render(tree('brightpath'))
    await waitFor(() => expect(lastFilters()?.org).toBe('brightpath'))
    rerender(tree('inspire'))
    await waitFor(() => expect(lastFilters()?.org).toBe('inspire'))
  })
})
