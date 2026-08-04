/**
 * @jest-environment jsdom
 *
 * The Emails tab on Organisation → Invitations — four letters, one per group (owner, 2026-08-04).
 *
 * The claims here are mostly ABSENCES, which a source-shape guard cannot see: the sponsor letter
 * carries no locked-access warning (it hands nobody an account), and only the source letter admits
 * that nothing sends it yet. Both would read as perfectly reasonable if they leaked onto the wrong
 * row, which is exactly why they are asserted rather than eyeballed.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import InvitationEmailsCard from './InvitationEmailsCard'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const tpl = (kind: string) => ({
  kind,
  enabled: true,
  subject: `Subject for ${kind}`,
  body: 'Dear {name}, {access} {login_link} {team_signoff}',
  updated_by_email: '',
  updated_at: '2026-08-04T00:00:00Z',
  to_student: false,
  last_sent_at: null,
  last_sent_orgs: 0,
})

const KINDS = ['invite_admin', 'invite_reviewer', 'invite_source', 'invite_sponsor']

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getInvitationEmails.mockResolvedValue(
    { templates: KINDS.map(tpl) } as unknown as api.PartnerEmailsPayload)
})

const t = (k: string) => k
const loaded = async () => {
  render(<InvitationEmailsCard token="tok" t={t} />)
  await waitFor(() =>
    expect(screen.getByText('admin.invitations.emails.kind.invite_admin')).toBeTruthy())
}

const rowFor = (kind: string) =>
  screen.getByText(`admin.invitations.emails.kind.${kind}`).closest('li')!

describe('the four letters', () => {
  it('lists one row per group', async () => {
    await loaded()
    for (const kind of KINDS) {
      expect(screen.getByText(`admin.invitations.emails.kind.${kind}`)).toBeTruthy()
    }
  })

  it('says plainly that these always send, with no switch', async () => {
    await loaded()
    expect(screen.getByText('admin.invitations.emails.alwaysSends')).toBeTruthy()
  })

  it('⚠ offers NO on/off toggle on any row', async () => {
    // The one difference from every other email card in the console. A tidy-up "for consistency"
    // would restore it, and an invitation that sends nothing strands the person it created.
    await loaded()
    expect(document.querySelectorAll('input[type="checkbox"]').length).toBe(0)
  })
})

describe('what each row admits about itself', () => {
  it('warns that the sign-in paragraph is locked on the three account letters', async () => {
    await loaded()
    for (const kind of ['invite_admin', 'invite_reviewer', 'invite_source']) {
      expect(
        within(rowFor(kind)).getByText('admin.invitations.emails.accessLocked'),
      ).toBeTruthy()
    }
  })

  it('⚠ does NOT warn about locked access on the sponsor letter', async () => {
    // It hands nobody an account — it links a stranger to the ordinary sign-up. The warning there
    // would describe a password that does not exist.
    await loaded()
    expect(
      within(rowFor('invite_sponsor')).queryByText('admin.invitations.emails.accessLocked'),
    ).toBeNull()
  })

  it('⚠ admits that ONLY the source letter is not sent by anything yet', async () => {
    await loaded()
    expect(within(rowFor('invite_source')).getByText(
      'admin.invitations.emails.notSentYet')).toBeTruthy()
    for (const kind of ['invite_admin', 'invite_reviewer', 'invite_sponsor']) {
      expect(within(rowFor(kind)).queryByText(
        'admin.invitations.emails.notSentYet')).toBeNull()
    }
  })
})
