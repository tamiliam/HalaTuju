/**
 * @jest-environment jsdom
 *
 * Sponsors list: the columns an admin actually scans (2026-07-27).
 *
 * Organisation was dropped — empty on all nine production rows, and it cost a quarter of the
 * table. Its space pays for Given and Last seen. These pin the swap (a future edit could
 * quietly restore a dead column) and the row link, which is the only way into the detail page.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import AdminSponsorsList from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/components/sponsors/SponsorEmailsCard', () => ({
  __esModule: true,
  default: () => <div>EMAILS PANEL</div>,
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const SPONSORS = [
  {
    id: 5, name: 'Bharathan Nair', email: 'nair@example.com', phone: '', source: '',
    organisation: 'Should Not Render Ltd', note: '', status: 'approved',
    reviewed_at: null, reviewed_by: '', created_at: '2026-07-15T00:00:00Z',
    given: '20000.00', students: 6, last_seen_at: '2026-07-24T00:00:00Z',
  },
  {
    id: 6, name: 'Chong Lee Min', email: 'lee@example.com', phone: '', source: '',
    organisation: '', note: '', status: 'approved',
    reviewed_at: null, reviewed_by: '', created_at: '2026-07-08T00:00:00Z',
    given: '0.00', students: 0, last_seen_at: null,
  },
] as unknown as api.AdminSponsor[]

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  mockApi.listSponsors.mockResolvedValue({ sponsors: SPONSORS })
})

describe('sponsors list columns', () => {
  it('shows Given and Last seen, and no Organisation column', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())

    expect(screen.getByText('admin.sponsors.colGiven')).toBeTruthy()
    expect(screen.getByText('admin.sponsors.colStudents')).toBeTruthy()
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

  it('shows how many students a sponsor is holding money for', async () => {
    // Money in says what they have given; students says what it is DOING. A large balance
    // with no students is the case an admin most needs to spot, so a zero dashes.
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    expect(screen.getByText('6')).toBeTruthy()
    expect(screen.queryByText('0')).toBeNull()
  })

  it('says there is NO RECORD of a sign-in, not that they never came back', async () => {
    // `last_seen_at` has only been recorded since 2026-07-27, so a null means we do not
    // know — the earlier copy ("Not since joining") asserted history this field lacks.
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Chong Lee Min')).toBeTruthy())
    const cell = screen.getByText('admin.sponsors.seen.never')
    expect(cell).toBeTruthy()
    expect(cell.getAttribute('title')).toBe('admin.sponsors.seen.neverHint')
  })
})

// ── the badge pair (S3) ───────────────────────────────────────────────────────
// Held back from S1 deliberately: a badge that opens nothing is the failure the partner-comms
// card exists to avoid. The Emails panel IS S3, so the badges arrive with it.

describe('the Sponsors | Emails badges', () => {
  it('lands on the vetting list, not the emails panel', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    expect(screen.queryByText('EMAILS PANEL')).toBeNull()
  })

  it('swaps to the emails panel and hides the list', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    fireEvent.click(screen.getByRole('tab', { name: 'admin.sponsors.tabEmails' }))
    expect(screen.getByText('EMAILS PANEL')).toBeTruthy()
    expect(screen.queryByText('Bharathan Nair')).toBeNull()
  })

  it('is not offered to finance, which may read sponsors but not write their emails', async () => {
    viewerRole = { role: 'finance' }
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    expect(screen.queryByRole('tab', { name: 'admin.sponsors.tabEmails' })).toBeNull()
  })
})

// ── sorting + pagination (2026-07-28) ─────────────────────────────────────────
// Client-side: the page sorts and slices what the server already sent, so these tests are the
// whole proof — there is no server behaviour behind them to fall back on.

const many = (n: number) => Array.from({ length: n }, (_, i) => ({
  id: i + 100, name: `Sponsor ${String(i).padStart(3, '0')}`, email: `s${i}@x.com`,
  phone: '', source: '', organisation: '', note: '', status: 'approved',
  reviewed_at: null, reviewed_by: '', created_at: '2026-07-01T00:00:00Z',
  given: '1000.00', students: 1, last_seen_at: null,
})) as unknown as api.AdminSponsor[]

describe('sortable headers', () => {
  it('offers a sort control on every column except Actions', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    for (const key of ['name', 'status', 'colGiven', 'colStudents', 'colLastSeen', 'registered']) {
      expect(screen.getByRole('button', { name: new RegExp(key) })).toBeTruthy()
    }
    // Actions is a plain header — there is nothing to order it by.
    expect(screen.queryByRole('button', { name: /admin\.sponsors\.actions/ })).toBeNull()
  })

  it('sorts by money as a number, so 20,000 leads 0.00', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: /colGiven/ }))
    const rows = screen.getAllByRole('row').slice(1)          // drop the header row
    expect(rows[0].textContent).toContain('Bharathan Nair')   // 20,000.00
  })

  it('flips direction when the same header is clicked twice', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    const given = screen.getByRole('button', { name: /colGiven/ })
    fireEvent.click(given)
    expect(screen.getAllByRole('row')[1].textContent).toContain('Bharathan Nair')
    fireEvent.click(given)
    expect(screen.getAllByRole('row')[1].textContent).toContain('Chong Lee Min')
  })

  it('marks the sorted column for a screen reader', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: /^admin\.sponsors\.name/ }))
    const header = screen.getByRole('button', { name: /^admin\.sponsors\.name/ }).closest('th')!
    expect(header.getAttribute('aria-sort')).toBe('ascending')
  })
})

describe('pagination', () => {
  it('shows no footer for the nine sponsors on production today', async () => {
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
    expect(screen.queryByText('admin.pageOf')).toBeNull()
  })

  it('stays hidden at exactly ten rows and appears at eleven', async () => {
    mockApi.listSponsors.mockResolvedValue({ sponsors: many(10) })
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Sponsor 000')).toBeTruthy())
    expect(screen.queryByText('admin.pageOf')).toBeNull()

    mockApi.listSponsors.mockResolvedValue({ sponsors: many(11) })
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getAllByText('Sponsor 000').length).toBeGreaterThan(0))
    expect(screen.getAllByText('admin.pageOf').length).toBeGreaterThan(0)
  })

  it('renders one page of ten and moves to the next', async () => {
    mockApi.listSponsors.mockResolvedValue({ sponsors: many(25) })
    render(<AdminSponsorsList />)
    await waitFor(() => expect(screen.getByText('Sponsor 000')).toBeTruthy())
    expect(screen.getAllByRole('row').slice(1)).toHaveLength(10)
    expect(screen.queryByText('Sponsor 010')).toBeNull()

    // The control renders a mobile and a desktop copy (hidden by CSS, both in the DOM), so take
    // the desktop one rather than assuming there is only ever a single Next.
    const nexts = screen.getAllByRole('button', { name: 'admin.next' })
    fireEvent.click(nexts[nexts.length - 1])
    expect(screen.getByText('Sponsor 010')).toBeTruthy()
    expect(screen.queryByText('Sponsor 000')).toBeNull()
  })
})
