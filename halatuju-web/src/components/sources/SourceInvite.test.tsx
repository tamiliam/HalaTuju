/**
 * @jest-environment jsdom
 *
 * Invitations → Source (source sign-in S2, 2026-10-30): inviting IS how a source is added now.
 *
 * Pinned: both shapes of the POST — an existing source (`source_id`) and a new one (`source_name` +
 * `source_code`, the old Add source's rules) — exactly as `source_users.invite_source` reads them;
 * every refusal code in plain words (and an unknown one in generic words); the roster's Resend /
 * Cancel, each only where the server says this caller may (`manageable`).
 *
 * Invitations I2 (owner ruling 2026-11-08, one person per source): a joined source leaves the
 * dropdown, a waiting one is greyed; the "Signed in" table and its Remove are gone (Remove is on the
 * Sources page now — `app/admin/sources/page.test.tsx`).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { SourceInviteForm, SourceRoster } from './SourceInvite'
import { TH } from '@/components/admin/TableFrame'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
const mockApi = api as jest.Mocked<typeof api>
const t = (k: string, vars?: Record<string, string>) => (vars ? `${k}|${Object.values(vars).join(',')}` : k)

const PAYLOAD = {
  kind: 'source', waiting: { admins: 0, reviewers: 0, source: 1, sponsors: 0 },
  totals: { admins: 0, reviewers: 0, source: 2, sponsors: 0 }, invitable_roles: [], programmes: [],
  invitations: [{
    id: 31, name: 'Shah Izzati Afzan', email: 'shah@example.org', role: 'source_partner',
    status: 'invited', sent_at: '2026-10-28', send_count: 1, last_send_ok: true,
    last_send_error: '', accepted_at: null, admin_id: 41, is_active: true, paused: false,
    programme: '', programme_name: '', source_id: 2, source_name: 'LearnifAI', source_code: 'learnifi',
  }],
  source_users: [
    { id: 41, name: 'Shah Izzati Afzan', email: 'shah@example.org', source_id: 2,
      source_name: 'LearnifAI', source_code: 'learnifi', organisation: 'harapan', is_active: true,
      first_seen_at: null, last_seen_at: null, manageable: true, invitation: null },
    { id: 42, name: 'Audrey Koh Sui Ean', email: 'muet@example.org', source_id: 3,
      source_name: 'MUETMyWay', source_code: 'muet', organisation: 'harapan', is_active: true,
      first_seen_at: '2026-10-20', last_seen_at: '2026-10-30', manageable: true,
      invitation: null },
    { id: 43, name: 'Gone', email: 'gone@example.org', source_id: 3, source_name: 'MUETMyWay',
      source_code: 'muet', organisation: 'harapan', is_active: false,
      first_seen_at: '2026-09-01', last_seen_at: null, manageable: true, invitation: null },
  ],
  sources: [
    { id: 1, code: 'hss', name: 'Hindu Sevai Sangam', organisation: 'harapan', sign_in: 'none', user_count: 0 },
    { id: 2, code: 'learnifi', name: 'LearnifAI', organisation: 'harapan', sign_in: 'invited', user_count: 1 },
    { id: 3, code: 'muet', name: 'MUETMyWay', organisation: 'harapan', sign_in: 'joined', user_count: 1 },
  ],
} as unknown as api.InvitationsPayload

const onDone = jest.fn()
beforeEach(() => {
  jest.clearAllMocks()
  mockApi.inviteSource.mockResolvedValue({ id: 1, admin_id: 2, emailed: true, message: '' })
})

const type = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } })

describe('the Source invite form', () => {
  it('invites a person for a source already on the list, showing each source\'s sign-in state', async () => {
    render(<SourceInviteForm data={PAYLOAD} token="tok" t={t} onDone={onDone} />)
    expect(screen.getByText('admin.invitations.source.option|Hindu Sevai Sangam,hss,admin.sources.signIn.none')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('admin.invitations.source.which'), { target: { value: '1' } })
    type('admin.invitations.source.personName', ' Kavi Amutha ')
    type('admin.emailLabel', 'kavi@example.org')
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSource).toHaveBeenCalledWith(
      { name: 'Kavi Amutha', email: 'kavi@example.org', source_id: 1 }, { token: 'tok' }))
    expect(onDone).toHaveBeenCalledWith({ type: 'success', text: 'admin.invitations.source.sent' })
  })

  // ⚠ CHANGED ON PURPOSE (I2, owner ruling 2026-11-08 + open point A): was "a joined source stays
  // on offer" (2026-10-30, several people per source).
  it('I2: one person per source — a joined source is not offered, a waiting one is greyed', () => {
    render(<SourceInviteForm data={PAYLOAD} token="tok" t={t} onDone={onDone} />)
    const select = screen.getByLabelText('admin.invitations.source.which') as HTMLSelectElement
    const options = Array.from(select.options)
    expect(options.map((o) => o.value)).toEqual(['', '1', '2'])
    expect(screen.queryByText(/MUETMyWay/)).toBeNull()
    const waiting = options.find((o) => o.value === '2')!
    expect(waiting.textContent).toBe('admin.invitations.source.optionWaiting|LearnifAI,learnifi')
    expect(waiting.disabled).toBe(true)
    expect(options.find((o) => o.value === '1')!.disabled).toBe(false)
    expect(screen.getByText(/admin\.invitations\.source\.help/)).toBeTruthy()
  })

  it('I2: opens on "new source" when every source has someone who joined', () => {
    const data = { ...PAYLOAD, sources: PAYLOAD.sources!.filter((s) => s.sign_in === 'joined') }
    render(<SourceInviteForm data={data} token="tok" t={t} onDone={onDone} />)
    expect(screen.getByLabelText('admin.invitations.source.newName')).toBeTruthy()
    expect(screen.queryByText('admin.invitations.source.pickExisting')).toBeNull()
  })

  it('M4: an account made but a letter that failed says so, with the way out — never "sent"', async () => {
    mockApi.inviteSource.mockResolvedValue({ id: 1, admin_id: 2, emailed: false, message: 'x' })
    render(<SourceInviteForm data={PAYLOAD} token="tok" t={t} onDone={onDone} />)
    fireEvent.change(screen.getByLabelText('admin.invitations.source.which'), { target: { value: '1' } })
    type('admin.invitations.source.personName', 'Kavi')
    type('admin.emailLabel', 'kavi@example.org')
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(
      { type: 'warning', text: 'admin.invitations.source.notEmailed|Kavi' }))
  })

  it('asks for a source before sending, rather than sending none', async () => {
    render(<SourceInviteForm data={PAYLOAD} token="tok" t={t} onDone={onDone} />)
    type('admin.invitations.source.personName', 'Kavi')
    type('admin.emailLabel', 'kavi@example.org')
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(screen.getByText('admin.invitations.source.chooseFirst')).toBeTruthy())
    expect(mockApi.inviteSource).not.toHaveBeenCalled()
  })

  it('adds a NEW source through the switch: name + short code (slugged) + optional contact', async () => {
    render(<SourceInviteForm data={PAYLOAD} token="tok" t={t} onDone={onDone} />)
    fireEvent.click(screen.getByText('admin.invitations.source.addNew'))
    type('admin.invitations.source.newName', 'Learn Hub')
    type('admin.invitations.source.newCode', 'Learn Hub!')
    expect(screen.getByDisplayValue('learnhub')).toBeTruthy()
    type('admin.invitations.source.contactPerson', 'Siva')
    type('admin.invitations.source.personName', 'Siva')
    type('admin.emailLabel', 'siva@example.org')
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSource).toHaveBeenCalledWith({
      name: 'Siva', email: 'siva@example.org', source_name: 'Learn Hub', source_code: 'learnhub',
      contact_person: 'Siva', phone: '',
    }, { token: 'tok' }))
    // …and back to the list on demand.
    expect(screen.queryByLabelText('admin.invitations.source.newName')).toBeNull()
  })

  it('opens on "new source" when the organisation has none to pick', () => {
    render(<SourceInviteForm data={{ ...PAYLOAD, sources: [] }} token="tok" t={t} onDone={onDone} />)
    expect(screen.getByLabelText('admin.invitations.source.newName')).toBeTruthy()
    expect(screen.queryByText('admin.invitations.source.pickExisting')).toBeNull()
  })

  it.each([
    'already_staff', 'source_has_person', 'code_taken', 'code_reserved', 'code_and_name_required', 'source_inactive',
    'bad_email', 'name_required', 'not_found', 'organisation_required', 'not_configured', 'create_failed',
  ])('shows the %s refusal in its own words', async (code) => {
    mockApi.inviteSource.mockRejectedValueOnce(Object.assign(new Error(code), { code }))
    render(<SourceInviteForm data={PAYLOAD} token="tok" t={t} onDone={onDone} />)
    fireEvent.change(screen.getByLabelText('admin.invitations.source.which'), { target: { value: '1' } })
    type('admin.invitations.source.personName', 'Kavi')
    type('admin.emailLabel', 'kavi@example.org')
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(screen.getByRole('alert').textContent)
      .toBe(`admin.invitations.source.error.${code}`))
    expect(onDone).not.toHaveBeenCalled()
  })

  it('I1: the form wears the one layout — the note under the fields, Send Invite at the left', () => {
    render(<SourceInviteForm data={PAYLOAD} token="tok" t={t} onDone={onDone} />)
    const foot = screen.getByTestId('invite-foot')
    expect(within(foot).getByTestId('invite-note').textContent).toBe('admin.invitations.source.note')
    expect(within(foot).getByText('admin.sendInvite').parentElement).toBe(foot)
    expect(foot.className).not.toContain('justify-between')
  })

  it('falls back to generic words for a refusal it does not know', async () => {
    mockApi.inviteSource.mockRejectedValueOnce(Object.assign(new Error('x'), { code: 'surprise' }))
    render(<SourceInviteForm data={PAYLOAD} token="tok" t={t} onDone={onDone} />)
    fireEvent.change(screen.getByLabelText('admin.invitations.source.which'), { target: { value: '1' } })
    type('admin.invitations.source.personName', 'Kavi')
    type('admin.emailLabel', 'kavi@example.org')
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(screen.getByRole('alert').textContent)
      .toBe('admin.invitations.source.error.generic'))
  })
})

describe('the Source roster', () => {
  const onCancel = jest.fn()
  const roster = (canManage = true, data = PAYLOAD) => render(
    <SourceRoster data={data} token="tok" t={t} canManage={canManage} onCancel={onCancel} onDone={onDone} />)

  // ⚠ CHANGED ON PURPOSE (I2, owner ruling 2026-11-08): the "Signed in" table and its Remove left
  // Invitations for the Sources page — the Source tab lists the waiting only, like every tab.
  it('I2: lists who is waiting only — no "Signed in" table, no Remove', () => {
    roster()
    expect(screen.getByTestId('source-waiting-31').textContent).toContain('LearnifAI')
    expect(screen.queryByText('Audrey Koh Sui Ean')).toBeNull()   // joined: shown on Sources now
    expect(screen.queryByText('admin.invitations.source.signedIn')).toBeNull()
    expect(screen.queryByText('admin.invitations.source.remove')).toBeNull()
    expect(screen.getAllByTestId('invitations-table')).toHaveLength(1)
  })

  it('Resend goes to the source-user endpoint; Cancel is the page\'s own', async () => {
    mockApi.resendSourceUser.mockResolvedValue({ message: '', emailed: true })
    roster()
    fireEvent.click(screen.getByText('admin.resend'))
    await waitFor(() => expect(mockApi.resendSourceUser).toHaveBeenCalledWith(41, { token: 'tok' }))
    expect(onDone).toHaveBeenCalledWith({ type: 'success', text: 'admin.invitations.resent' })
    // Cancel is disabled while the resend is busy; under load the click could land before `finally` clears it.
    await waitFor(() => expect((screen.getByText('admin.invitations.cancel') as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByText('admin.invitations.cancel'))
    expect(onCancel).toHaveBeenCalledWith(PAYLOAD.invitations[0])
  })

  it('I1: the waiting list is the one table — source as its lead column, TH headings, red Cancel', () => {
    roster()
    const table = screen.getByTestId('invitations-table')
    const heads = within(table).getAllByRole('columnheader')
    expect(heads.map((h) => h.textContent)).toEqual(['admin.invitations.source.col.source',
      'admin.nameHeader', 'admin.emailHeader', 'admin.statusHeader', 'admin.actionHeader'])
    for (const h of heads) expect(h.className).toBe(TH)
    const row = screen.getByTestId('source-waiting-31')
    expect(within(row).getByText(/^admin\.invitations\.status\.invited \(/)).toBeTruthy()
    expect(within(row).getByText('admin.invitations.cancel').className).toContain('text-critical-600')
    expect(table.querySelector('[data-phone-rows]')).toBeTruthy()
  })

  it.each([
    ['resend', 'already_joined', 'admin.resend', 'Shah Izzati Afzan'],
    ['resend', 'not_active', 'admin.resend', 'Shah Izzati Afzan'],
  ])('L6: a %s refused %s reads in its own words', async (_what, code, button, name) => {
    mockApi.resendSourceUser.mockRejectedValue(Object.assign(new Error(code), { code }))
    roster()
    fireEvent.click(screen.getByText(button))
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(
      { type: 'warning', text: `admin.invitations.source.refused.${code}|${name}` }))
  })

  it('offers no action to a viewer who may not manage, nor on a row the server says is not theirs', () => {
    roster(false)
    expect(screen.queryByText('admin.resend')).toBeNull()
    expect(screen.queryByText('admin.invitations.cancel')).toBeNull()
  })

  it('offers no action on a row the server marks not manageable', () => {
    const locked = { ...PAYLOAD, source_users: PAYLOAD.source_users!.map((u) => ({ ...u, manageable: false })) }
    roster(true, locked)
    expect(screen.queryByText('admin.resend')).toBeNull()
    expect(screen.queryByText('admin.invitations.cancel')).toBeNull()
  })
})
