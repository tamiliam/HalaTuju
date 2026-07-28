/**
 * @jest-environment jsdom
 *
 * The Emails panel (S3, 2026-07-28) — and the shared TemplateEditor behind it, which had no
 * runtime coverage in either family before this file.
 *
 * What matters here is HONESTY, not layout. The panel is the surface an org_admin uses to decide
 * what every donor is told, so the two things it must never do are imply a switch works when the
 * platform gate is shut, and show "off" against an email that is demonstrably going out today.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SponsorEmailsCard from './SponsorEmailsCard'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const tpl = (kind: string, over: Partial<api.SponsorEmailTemplate> = {}): api.SponsorEmailTemplate => ({
  kind, label: kind, enabled: false,
  subject: 'Subject for ' + kind, body: 'Dear {sponsor_name},\n\nHello.',
  placeholders: ['sponsor_name', 'programme_name', 'team_signoff'],
  updated_by_email: '', updated_at: null, last_sent_at: null, last_sent_count: 0,
  ...over,
})

const payload = (over: Partial<api.SponsorEmailsPayload> = {}): api.SponsorEmailsPayload => ({
  templates: [tpl('welcome'), tpl('approved'), tpl('weekly_digest')],
  comms_enabled: false,
  seeded: 9,
  expected: 9,
  sponsor_count: 9,
  ...over,
})

const t = (k: string) => k

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getSponsorEmails.mockResolvedValue(payload())
})

const open = async (p?: api.SponsorEmailsPayload) => {
  if (p) mockApi.getSponsorEmails.mockResolvedValue(p)
  render(<SponsorEmailsCard token="tok" t={t} />)
  await waitFor(() => expect(screen.getByText('admin.sponsors.emails.title')).toBeTruthy())
}

describe('honesty about what is actually sending', () => {
  it('says plainly that the switches are inert while the platform gate is shut', async () => {
    await open()
    expect(screen.getByText('admin.sponsors.emails.flagOffTitle')).toBeTruthy()
  })

  it('drops that banner once the platform gate is open', async () => {
    await open(payload({ comms_enabled: true }))
    expect(screen.queryByText('admin.sponsors.emails.flagOffTitle')).toBeNull()
  })

  it('marks a kind that is ALREADY reaching sponsors through its pre-S3 sender', async () => {
    // weekly_digest is live today with its template off. An unqualified "off" would be false.
    await open()
    expect(screen.getByText('admin.sponsors.emails.alreadyLive')).toBeTruthy()
  })

  it('does not mark a brand-new kind as sending', async () => {
    await open(payload({ templates: [tpl('welcome')] }))
    expect(screen.queryByText('admin.sponsors.emails.alreadyLive')).toBeNull()
  })

  it('warns when the seed step has not been run', async () => {
    await open(payload({ seeded: 3 }))
    expect(screen.getByText(/notSeeded/)).toBeTruthy()
  })
})

describe('switching one on', () => {
  it('calls the endpoint for that kind', async () => {
    mockApi.updateSponsorEmail.mockResolvedValue(tpl('welcome', { enabled: true }))
    await open()
    fireEvent.click(screen.getByRole('switch', { name: 'admin.sponsors.emails.kind.welcome' }))
    await waitFor(() => expect(mockApi.updateSponsorEmail)
      .toHaveBeenCalledWith('welcome', { enabled: true }, { token: 'tok' }))
  })

  it('rolls the switch back when the server refuses', async () => {
    mockApi.updateSponsorEmail.mockRejectedValue(new Error('nope'))
    await open()
    fireEvent.click(screen.getByRole('switch', { name: 'admin.sponsors.emails.kind.welcome' }))
    await waitFor(() => expect(screen.getByText('admin.actionFailed')).toBeTruthy())
  })
})

describe('the shared template editor', () => {
  it('saves the edited wording through this family’s endpoint', async () => {
    mockApi.updateSponsorEmail.mockResolvedValue(tpl('welcome', { subject: 'Edited' }))
    await open()
    fireEvent.click(screen.getAllByText('admin.sponsors.emails.edit')[0])

    const subject = screen.getByDisplayValue('Subject for welcome')
    fireEvent.change(subject, { target: { value: 'Edited' } })
    fireEvent.click(screen.getByRole('button', { name: 'admin.sources.save' }))

    await waitFor(() => expect(mockApi.updateSponsorEmail).toHaveBeenCalledWith(
      'welcome', { subject: 'Edited', body: 'Dear {sponsor_name},\n\nHello.' }, { token: 'tok' }))
  })

  it('will not save until something has changed', async () => {
    await open()
    fireEvent.click(screen.getAllByText('admin.sponsors.emails.edit')[0])
    expect((screen.getByRole('button', { name: 'admin.sources.save' }) as HTMLButtonElement).disabled)
      .toBe(true)
  })

  it('names the offending token when the allowlist refuses the copy', async () => {
    // The allowlist is a privacy control as much as a rendering one, so the message has to say
    // WHICH token — telling an admin to go and find it is how a guard gets worked around.
    const err = Object.assign(new Error('bad'), {
      code: 'unknown_placeholder', body: { placeholders: ['student_cards'] },
    })
    mockApi.updateSponsorEmail.mockRejectedValue(err)
    await open()
    fireEvent.click(screen.getAllByText('admin.sponsors.emails.edit')[0])
    fireEvent.change(screen.getByDisplayValue('Subject for welcome'), { target: { value: 'X' } })
    fireEvent.click(screen.getByRole('button', { name: 'admin.sources.save' }))

    await waitFor(() => expect(
      screen.getByText('admin.sponsors.emails.error.unknownPlaceholder')).toBeTruthy())
  })

  it('drops a placeholder chip into the body at the cursor', async () => {
    await open()
    fireEvent.click(screen.getAllByText('admin.sponsors.emails.edit')[0])
    fireEvent.click(screen.getByRole('button', { name: '{programme_name}' }))
    expect(screen.getByDisplayValue(/\{programme_name\}/)).toBeTruthy()
  })
})
