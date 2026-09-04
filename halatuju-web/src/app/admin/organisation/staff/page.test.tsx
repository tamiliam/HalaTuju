/**
 * @jest-environment jsdom
 *
 * Organisation → Invitations, rendered. Owner's four-kind shape, 2026-08-03.
 *
 * The claims that matter here are mostly about ABSENCE, which a source-shape guard cannot see:
 * org_admin is listed but not offered; a sponsor row has no Revoke; Source offers no invite form.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import OrganisationInvitationsPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const row = (over: Partial<api.InvitationRow>): api.InvitationRow => ({
  id: 1, name: 'Someone', email: 's@example.org', role: 'admin', status: 'accepted',
  sent_at: '2026-07-21T00:00:00Z', send_count: 1, last_send_ok: true, last_send_error: '',
  accepted_at: '2026-07-22T00:00:00Z', admin_id: 10, is_active: true, paused: false,
  // Blank = EVERY gift, which is what a staff invitation carries and what every row written
  // before the column existed reads as.
  programme: '', programme_name: '', ...over,
})

const WAITING = { admins: 1, reviewers: 0, source: 0, sponsors: 2 }

/** The organisation's ACTIVE gifts. Default one — today's BrightPath shape, where the invite
 *  form asks nothing. Tests that need the picker pass two. */
let giftChoices: api.InvitationsPayload['programmes'] =
  [{ id: 7, code: 'flagship', name: 'BrightPath Bursary' }]

const payloadFor = (kind: api.InvitationKind): api.InvitationsPayload => {
  if (kind === 'admins') {
    return {
      kind, waiting: WAITING, invitable_roles: ['admin', 'finance'],
      programmes: giftChoices,
      invitations: [
        row({ id: 1, name: 'Yeoh Liew Se', role: 'admin', status: 'no_reply',
              accepted_at: null, admin_id: 10 }),
        row({ id: 2, name: 'Suresh', role: 'org_admin', status: 'accepted', admin_id: 11 }),
      ],
    }
  }
  if (kind === 'sponsors') {
    return {
      kind, waiting: WAITING, invitable_roles: [], programmes: giftChoices,
      invitations: [row({ id: 3, name: 'Donor', role: '', status: 'invited',
                          accepted_at: null, admin_id: null, is_active: null,
                          programme: 'flagship', programme_name: 'BrightPath Bursary' })],
    }
  }
  return { kind, waiting: WAITING, invitable_roles: kind === 'reviewers' ? ['reviewer', 'qc'] : [],
           programmes: giftChoices, invitations: [] }
}

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  giftChoices = [{ id: 7, code: 'flagship', name: 'BrightPath Bursary' }]
  mockApi.getInvitations.mockImplementation(async (kind) => payloadFor(kind))
  // `useStaffAdmin` still owns invite/resend/revoke, and loads the staff list on mount; the
  // auto-mock must answer it or the hook throws before anything renders.
  mockApi.getAdmins.mockResolvedValue({ admins: [] })
  mockApi.getInvitationEmails.mockResolvedValue(
    { templates: [] } as unknown as api.PartnerEmailsPayload)
})

const loaded = async () => {
  render(<OrganisationInvitationsPage />)
  await waitFor(() => expect(screen.getByText('Yeoh Liew Se')).toBeTruthy())
}

const pick = async (kind: string) => {
  fireEvent.click(screen.getByText(`admin.invitations.kindOne.${kind}`).closest('button')!)
  await waitFor(() => expect(mockApi.getInvitations).toHaveBeenCalledWith(kind, expect.anything()))
}

describe('the four kinds', () => {
  it('offers all four', async () => {
    await loaded()
    for (const k of ['admins', 'reviewers', 'source', 'sponsors']) {
      expect(screen.getByText(`admin.invitations.kindOne.${k}`)).toBeTruthy()
    }
  })

  it('⚠ names the BUTTON in the singular and the TABLE in the plural', async () => {
    // Owner, 2026-08-04. The button completes "Invite as … Admin"; the heading sits above a list.
    // Asserted together because the temptation is to collapse them back onto one key.
    await loaded()
    expect(screen.getByText('admin.invitations.kindOne.admins')).toBeTruthy()
    expect(screen.getByText('admin.invitations.kind.admins')).toBeTruthy()
  })

  it('⚠ shows the waiting count for kinds NOT on screen', async () => {
    // Only one table is visible, so without this an invitation waiting elsewhere is invisible —
    // the exact failure the page exists to end.
    await loaded()
    const sponsors = screen.getByText('admin.invitations.kindOne.sponsors').closest('button')!
    expect(within(sponsors).getByText('2')).toBeTruthy()
  })

  it('shows one kind at a time', async () => {
    await loaded()
    expect(screen.getByText('Yeoh Liew Se')).toBeTruthy()
    await pick('sponsors')
    await waitFor(() => expect(screen.queryByText('Yeoh Liew Se')).toBeNull())
    expect(screen.getByText('Donor')).toBeTruthy()
  })
})

describe('listed is not the same as invitable', () => {
  it('lists an organisation admin in the Admins table', async () => {
    await loaded()
    expect(screen.getByText('Suresh')).toBeTruthy()
  })

  it('⚠ never OFFERS organisation admin in the selector', async () => {
    // Appointing one is a platform act a super performs. Offering it here would let an org_admin
    // appoint their own successor.
    //
    // Asserted as the EXACT set rather than by querying for an org_admin label: no such label
    // exists, and naming one in a test conjures a key the i18n hygiene guard then demands — which
    // is how a phantom string gets added to satisfy a test rather than a screen.
    await loaded()
    const chips = Array.from(document.querySelectorAll('button'))
      .map((b) => b.textContent || '')
      .filter((s) => s.startsWith('admin.administration.staffRole.'))
    expect(chips).toEqual([
      'admin.administration.staffRole.admin',
      'admin.administration.staffRole.finance',
    ])
  })
})

describe('what each kind can do', () => {
  it('offers Resend to somebody still waiting, and Revoke to somebody who arrived', async () => {
    await loaded()
    expect(screen.getByText('admin.resend')).toBeTruthy()
    expect(screen.getByText('admin.revoke')).toBeTruthy()
  })

  it('⚠ offers NO revoke on a sponsor invitation, which has no account behind it', async () => {
    await loaded()
    await pick('sponsors')
    await waitFor(() => expect(screen.getByText('Donor')).toBeTruthy())
    expect(screen.queryByText('admin.revoke')).toBeNull()
  })

  it('says Source is coming soon and offers no way to invite one', async () => {
    await loaded()
    await pick('source')
    await waitFor(() =>
      expect(screen.getAllByText('admin.invitations.sourceComingSoon').length).toBeGreaterThan(0))
    expect(screen.queryByText('admin.sendInvite')).toBeNull()
  })
})

/**
 * Which gift a sponsor invitation is for (S-ASSIGN, 2026-09-04).
 *
 * Until now this form asked for an email, a name and a note and never asked which gift, so a
 * benefactor invited for Sabah would have registered straight into the flagship, silently —
 * and their credit would then have been refused `sponsor_not_in_programme`.
 */
describe('which gift a sponsor is invited into', () => {
  const inviteSponsorNamed = () => {
    fireEvent.change(screen.getByPlaceholderText('admin.name'), { target: { value: 'Donor' } })
    fireEvent.change(screen.getByPlaceholderText('admin.emailLabel'),
      { target: { value: 'donor@example.org' } })
  }

  it('⚠ asks NOTHING when the organisation runs one gift — today’s BrightPath form', async () => {
    await loaded()
    await pick('sponsors')
    expect(screen.queryByText('admin.invitations.giftLabel')).toBeNull()
  })

  it('sends no gift in that case, and the server takes the sole one', async () => {
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 'donor@example.org', name: 'Donor', note: '' }, { token: 'tok' }))
  })

  it('asks once there are two, and starts BLANK — never a silent default', async () => {
    giftChoices = [
      { id: 7, code: 'flagship', name: 'BrightPath Bursary' },
      { id: 9, code: 'sabah', name: 'Sabah Bursary' },
    ]
    await loaded()
    await pick('sponsors')
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('')
    expect(select.required).toBe(true)
  })

  it('sends the chosen gift', async () => {
    giftChoices = [
      { id: 7, code: 'flagship', name: 'BrightPath Bursary' },
      { id: 9, code: 'sabah', name: 'Sabah Bursary' },
    ]
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '9' } })
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 'donor@example.org', name: 'Donor', note: '', programme_id: 9 },
      { token: 'tok' }))
  })

  it('shows which gift an existing invitation was for', async () => {
    await loaded()
    await pick('sponsors')
    await waitFor(() => expect(screen.getByText('Donor')).toBeTruthy())
    expect(screen.getByText('BrightPath Bursary')).toBeTruthy()
  })

  it('⚠ prints nothing for a staff invitation, which carries no gift', async () => {
    // A blank means EVERY gift. An empty line under a staff row would read as a missing value.
    await loaded()
    const row = screen.getByText('Yeoh Liew Se').closest('td')!
    expect(row.querySelectorAll('div').length).toBe(0)
  })
})

describe('the page shell', () => {
  it('carries the Invitations and Emails tabs', async () => {
    await loaded()
    expect(screen.getByText('admin.invitations.tab.invitations')).toBeTruthy()
    expect(screen.getByText('admin.invitations.tab.emails')).toBeTruthy()
  })

  it('shows finance the page with no invite form', async () => {
    viewerRole = { role: 'finance' }
    render(<OrganisationInvitationsPage />)
    await waitFor(() => expect(screen.getByText('Yeoh Liew Se')).toBeTruthy())
    expect(screen.queryByText('admin.sendInvite')).toBeNull()
    expect(screen.getByText('admin.administration.viewOnlyNote')).toBeTruthy()
  })
})
