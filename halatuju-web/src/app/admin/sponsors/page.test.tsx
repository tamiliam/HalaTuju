/**
 * @jest-environment jsdom
 *
 * Sponsors list: the columns an admin actually scans (2026-07-27).
 *
 * Organisation was dropped — empty on all nine production rows, and it cost a quarter of the
 * table. Its space pays for Given and Last seen. These pin the swap (a future edit could
 * quietly restore a dead column) and the row link, which is the only way into the detail page.
 */
import { render, screen, waitFor } from '@testing-library/react'
import AdminSponsorsList from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const SPONSORS = [
  {
    id: 5, name: 'Bharathan Nair', email: 'nair@example.com', phone: '', source: '',
    organisation: 'Should Not Render Ltd', note: '', status: 'approved',
    reviewed_at: null, reviewed_by: '', created_at: '2026-07-15T00:00:00Z',
    given: '20000.00', last_seen_at: '2026-07-24T00:00:00Z',
  },
  {
    id: 6, name: 'Chong Lee Min', email: 'lee@example.com', phone: '', source: '',
    organisation: '', note: '', status: 'approved',
    reviewed_at: null, reviewed_by: '', created_at: '2026-07-08T00:00:00Z',
    given: '0.00', last_seen_at: null,
  },
] as unknown as api.AdminSponsor[]

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.listSponsors.mockResolvedValue({ sponsors: SPONSORS })
})

describe('sponsors list columns', () => {
  it('shows Given and Last seen, and no Organisation column', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())

    expect(screen.getByText('admin.sponsors.colGiven')).toBeTruthy()
    expect(screen.getByText('admin.sponsors.colLastSeen')).toBeTruthy()
    expect(screen.queryByText('admin.sponsors.organisation')).toBeNull()
    // The value must not leak through either — dropping the header alone would still render it.
    expect(screen.queryByText('Should Not Render Ltd')).toBeNull()
  })

  it('links each sponsor to their own record', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    expect(screen.getByText('Bharathan Nair').closest('a')!.getAttribute('href'))
      .toBe('/admin/sponsors/5')
  })

  it('formats a given total and dashes a sponsor who gave nothing', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    expect(screen.getByText('20,000.00')).toBeTruthy()
    // '0.00' would read as a real figure; a dash reads as "none".
    expect(screen.queryByText('0.00')).toBeNull()
  })

  it('calls out a sponsor who has never come back', async () => {
    // The signal that did not exist before this sprint: approved, then silence.
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Chong Lee Min')).toBeTruthy())
    expect(screen.getByText('admin.sponsors.seen.never')).toBeTruthy()
  })
})
