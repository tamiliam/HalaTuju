/**
 * @jest-environment jsdom
 *
 * TD-502: the Overview's "sponsors to vet" card opens /admin/sponsors?status=pending, and the
 * list must open already narrowed to the pending sponsors (parity with the card's count).
 */
import { render, waitFor } from '@testing-library/react'
import AdminSponsorsList from './page'
import * as api from '@/lib/admin-api'

let query = 'status=pending'
jest.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(query) }))
jest.mock('next/link', () => ({ __esModule: true, default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }) }))
jest.mock('@/components/sponsors/SponsorEmailsCard', () => ({ __esModule: true, default: () => null }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.listSponsors.mockResolvedValue({ sponsors: [] })
})

it('opens narrowed to pending when the card link carries ?status=pending', async () => {
  query = 'status=pending'
  render(<AdminSponsorsList />)
  await waitFor(() => expect(mockApi.listSponsors).toHaveBeenCalled())
  expect(mockApi.listSponsors.mock.calls[0][0]).toBe('pending')
})

it('ignores an unknown status and stays unfiltered', async () => {
  query = 'status=bogus'
  render(<AdminSponsorsList />)
  await waitFor(() => expect(mockApi.listSponsors).toHaveBeenCalled())
  expect(mockApi.listSponsors.mock.calls[0][0]).toBeUndefined()
})
