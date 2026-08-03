/**
 * @jest-environment jsdom
 *
 * Organisation → Invitations, rendered.
 *
 * The page exists because the old one structurally could not answer its own question: an
 * invitation was not a record, so a person invited five minutes ago and a colleague of a year both
 * read "Active". These tests pin the three things that fixes.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import OrganisationStaffPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const inv = (over: Partial<NonNullable<api.AdminItem['invitation']>> = {}) => ({
  status: 'invited' as const, sent_at: '2026-08-01T00:00:00Z', send_count: 1,
  last_send_ok: true, last_send_error: '', expires_at: null, credential_issued: true, ...over,
})

const row = (over: Partial<api.AdminItem>): api.AdminItem => ({
  id: 1, name: 'Someone', email: 's@example.org', is_super_admin: false, role: 'reviewer',
  is_active: true, org_name: null, created_at: '2026-01-01T00:00:00Z',
  invitation: null, ...over,
} as api.AdminItem)

const ROWS: api.AdminItem[] = [
  row({ id: 1, name: 'Arrived Reviewer', role: 'reviewer',
        last_seen_at: new Date().toISOString(), invitation: inv({ status: 'accepted' }) }),
  row({ id: 2, name: 'Quality Person', role: 'qc',
        last_seen_at: new Date().toISOString(), invitation: inv({ status: 'accepted' }) }),
  row({ id: 3, name: 'Money Person', role: 'finance',
        last_seen_at: new Date().toISOString(), invitation: inv({ status: 'accepted' }) }),
  row({ id: 4, name: 'Lapsed Person', role: 'admin',
        invitation: inv({ status: 'expired', credential_issued: true }) }),
  row({ id: 5, name: 'Silent Person', role: 'reviewer',
        invitation: inv({ status: 'no_reply', credential_issued: false }) }),
]

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  mockApi.getAdmins.mockResolvedValue({ admins: ROWS })
})

const loaded = async () => {
  render(<OrganisationStaffPage />)
  await waitFor(() => expect(screen.getByText('Arrived Reviewer')).toBeTruthy())
}

describe('the invitations still waiting', () => {
  it('leads with them, above the people', async () => {
    await loaded()
    expect(screen.getByText('admin.invitations.outstandingHeading')).toBeTruthy()
    expect(screen.getByText('Lapsed Person')).toBeTruthy()
    expect(screen.getByText('Silent Person')).toBeTruthy()
  })

  it('⚠ tells a lapsed password apart from somebody who simply never came', async () => {
    // The whole point. "Expired" means re-send; "no reply" means nothing was ever issued, so
    // saying "expired" would send an org_admin hunting a credential that never existed.
    await loaded()
    expect(screen.getByText('admin.invitations.status.expired')).toBeTruthy()
    expect(screen.getByText('admin.invitations.status.no_reply')).toBeTruthy()
  })

  it('shows what happened to the email — the owner\'s third ask', async () => {
    await loaded()
    expect(screen.getAllByText('admin.invitations.send.sent').length).toBeGreaterThan(0)
  })

  it('says so plainly when there is nothing outstanding', async () => {
    mockApi.getAdmins.mockResolvedValue({ admins: [ROWS[0]] })
    render(<OrganisationStaffPage />)
    await waitFor(() => expect(screen.getByText('admin.invitations.noneOutstanding')).toBeTruthy())
  })

  it('shows a waiting person ONCE, at the top, and not again in the roster', async () => {
    // Listing them in both places would put one person on screen twice and inflate the category
    // counts with people who have never signed in.
    await loaded()
    const table = screen.getByText('admin.invitations.sentHeader').closest('table') as HTMLElement
    expect(within(table).getByText('Lapsed Person')).toBeTruthy()
    expect(within(table).queryByText('Arrived Reviewer')).toBeNull()
    expect(screen.getAllByText('Lapsed Person')).toHaveLength(1)
  })
})

describe('the two categories', () => {
  it('groups reviewers and admins separately', async () => {
    await loaded()
    expect(screen.getByText('admin.invitations.category.reviewers')).toBeTruthy()
    expect(screen.getByText('admin.invitations.category.admins')).toBeTruthy()
  })

  it('files QC with the reviewers and finance with the admins', async () => {
    await loaded()
    // Each category renders as one section: a heading and its table inside a single wrapper.
    const section = (cat: string) =>
      screen.getByText(`admin.invitations.category.${cat}`).closest('div') as HTMLElement
    expect(within(section('reviewers')).getByText('Quality Person')).toBeTruthy()
    expect(within(section('reviewers')).queryByText('Money Person')).toBeNull()
    expect(within(section('admins')).getByText('Money Person')).toBeTruthy()
  })
})

describe('who may act', () => {
  it('offers the invite form to an org_admin', async () => {
    await loaded()
    expect(screen.getByText('admin.sendInvite')).toBeTruthy()
  })

  it('shows finance the page read-only, with no invite form', async () => {
    // Deciding who joins is staff management, not finance's business (role matrix).
    viewerRole = { role: 'finance' }
    render(<OrganisationStaffPage />)
    await waitFor(() => expect(screen.getByText('Arrived Reviewer')).toBeTruthy())
    expect(screen.queryByText('admin.sendInvite')).toBeNull()
    expect(screen.getByText('admin.administration.viewOnlyNote')).toBeTruthy()
  })
})
