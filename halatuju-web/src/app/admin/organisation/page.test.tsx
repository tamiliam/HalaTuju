/**
 * @jest-environment jsdom
 *
 * Organisation → Overview, rendered. New on 2026-09-09, and it exists because of one live fault
 * the owner reported: the staff tile printed **"1 invited, not yet accepted"** over somebody who
 * had accepted in June and been REVOKED afterwards, and who therefore appeared nowhere on the
 * Invitations page he was being sent to.
 *
 * The number was `all staff − active staff`, which measures who has been switched off — not who
 * has yet to reply. Nothing rendered this page in a test, so nothing could see it.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import OrganisationOverviewPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let viewerRole: Record<string, unknown> = { role: 'org_admin', owning_org_name: 'BrightPath' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')
// The gifts section calls its own endpoint and is not what this file is about.
jest.mock('@/components/admin/GiftProgrammes', () => ({
  __esModule: true, default: () => <div data-testid="gifts" />,
}))

const mockApi = api as jest.Mocked<typeof api>

/** BrightPath's real shape on the day of the report: 15 active staff, and ONE revoked admin
 *  (Shanti, who accepted on 2026-06-15). Nobody at all is waiting to reply. */
const STAFF = [
  ...Array.from({ length: 15 }, (_, i) => ({
    id: i + 1, name: `Person ${i + 1}`, email: `p${i + 1}@example.org`,
    role: i < 13 ? 'reviewer' : 'admin', is_active: true, is_super_admin: false,
  })),
  { id: 99, name: 'Shanti Subramaniam', email: 'shanti@example.org', role: 'admin',
    is_active: false, is_super_admin: false },
] as unknown as api.AdminItem[]

const invitations = (waiting: Record<string, number>) => ({
  kind: 'admins', invitations: [], invitable_roles: [], programmes: [],
  waiting, totals: waiting,
} as unknown as api.InvitationsPayload)

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin', owning_org_name: 'BrightPath' }
  mockApi.getAdmins.mockResolvedValue({ admins: STAFF })
  mockApi.getPendingSponsorCount.mockResolvedValue({ count: 0 })
  // The two sponsors who really are waiting — and the reason the old tile was wrong twice: it
  // only ever looked at STAFF, so it could not have seen these at all.
  mockApi.getInvitations.mockResolvedValue(
    invitations({ admins: 0, reviewers: 0, source: 0, sponsors: 2 }))
})

/** A tile, found by its heading. */
const tile = (key: string) => within(screen.getByText(key).closest('a, div') as HTMLElement)

const loaded = async () => {
  render(<OrganisationOverviewPage />)
  await waitFor(() => expect(screen.getByText('admin.nav.invitations')).toBeTruthy())
}

describe('the waiting count', () => {
  it('⚠ counts what the SERVER calls waiting, across every kind', async () => {
    // Two sponsors are waiting and no staff are. The old arithmetic would have said 1 — the
    // revoked admin — and missed both sponsors.
    await loaded()
    await waitFor(() => expect(tile('admin.nav.invitations').getByText('2')).toBeTruthy())
  })

  it('⚠ says NOBODY is waiting when nobody is, even with a revoked admin on the books',
    async () => {
      // The exact case the owner reported, as a test. Shanti is switched off and is still in
      // STAFF; that must not become a person to chase.
      mockApi.getInvitations.mockResolvedValue(
        invitations({ admins: 0, reviewers: 0, source: 0, sponsors: 0 }))
      await loaded()
      await waitFor(() => expect(tile('admin.nav.invitations').getByText('0')).toBeTruthy())
    })

  it('shows a dash until the answer arrives, rather than a confident zero', async () => {
    mockApi.getInvitations.mockReturnValue(new Promise(() => {}) as never)
    render(<OrganisationOverviewPage />)
    await waitFor(() => expect(tile('admin.nav.invitations').getByText('—')).toBeTruthy())
  })
})

describe('the people tile', () => {
  it('counts the staff who are IN', async () => {
    await loaded()
    await waitFor(() => expect(tile('admin.nav.reviewers').getByText('15')).toBeTruthy())
  })

  it('⚠ reports the revoked one under its own name, not as somebody who has not replied',
    async () => {
      await loaded()
      await waitFor(() =>
        expect(tile('admin.nav.reviewers').getByText('admin.orgPage.revokedStaff')).toBeTruthy())
    })

  it('⚠ points at People, where those 15 actually are', async () => {
    // It used to link to Invitations: the count of people who are IN sent you to the page about
    // people who are not.
    await loaded()
    expect(screen.getByText('admin.nav.reviewers').closest('a')!.getAttribute('href'))
      .toBe('/admin/organisation/reviewers')
  })

  it('says nothing about revoked staff when nobody is revoked', async () => {
    // Drive over the bump: a line that always rendered would pass the assertion above.
    mockApi.getAdmins.mockResolvedValue({ admins: STAFF.filter((a) => a.is_active) })
    await loaded()
    await waitFor(() => expect(tile('admin.nav.reviewers').getByText('15')).toBeTruthy())
    expect(screen.queryByText('admin.orgPage.revokedStaff')).toBeNull()
  })
})
