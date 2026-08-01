/**
 * @jest-environment jsdom
 *
 * Sources page: two panels, one badge each (owner ruling, 2026-07-26).
 *
 * Organisations is the default and the registry is what you land on; Partner emails is a second
 * click. What these pin is the pair of choices that are easy to regress: the emails card must not
 * be MOUNTED until its badge is chosen (so each reveal re-reads the send log), and the registry
 * must be HIDDEN rather than unmounted (so a half-typed inline edit survives a trip and back).
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SourcesPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin', is_super_admin: false } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const SOURCES = [
  {
    id: 1, code: 'smc', name: 'Sekolah Menengah Cheras', contact_person: 'Aina',
    contact_email: '', phone: '', show_in_apply: true, student_count: 4,
  },
] as unknown as api.SourceItem[]

const EMAILS = {
  comms_enabled: true,
  organisations: [
    { id: 1, code: 'smc', name: 'Sekolah Menengah Cheras', students: 4, qualifies: false, is_house_org: false },
  ],
  templates: [
    {
      kind: 'weekly_summary', enabled: false, subject: 'S', body: 'B',
      last_sent_at: null, last_sent_orgs: 0, updated_at: '2026-07-26T00:00:00Z', updated_by_email: '',
    },
  ],
} as unknown as api.PartnerEmailsPayload

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getSources.mockResolvedValue({ sources: SOURCES } as Awaited<ReturnType<typeof api.getSources>>)
  mockApi.getPartnerEmails.mockResolvedValue(EMAILS)
})

/** The registry's wrapper — found via a cell, since only the wrapper carries `hidden`. */
const registryWrapper = () =>
  screen.getByText('Sekolah Menengah Cheras').closest('div[class*="overflow-x-auto"]')

describe('Sources page panels', () => {
  it('lands on Organisations with the emails card not yet mounted', async () => {
    render(<SourcesPage />)
    await waitFor(() => expect(screen.getByText('Sekolah Menengah Cheras')).toBeTruthy())

    expect(registryWrapper()!.hasAttribute('hidden')).toBe(false)
    expect(screen.queryByText('admin.sources.emails.title')).toBeNull()
    // Not merely unrendered — never fetched, so the card costs nothing until it is asked for.
    expect(mockApi.getPartnerEmails).not.toHaveBeenCalled()
    expect(screen.getByRole('tab', { name: 'admin.sources.tabOrganisations' }).getAttribute('aria-selected')).toBe('true')
  })

  it('swaps to the emails card and hides the registry without unmounting it', async () => {
    render(<SourcesPage />)
    await waitFor(() => expect(screen.getByText('Sekolah Menengah Cheras')).toBeTruthy())

    fireEvent.click(screen.getByRole('tab', { name: 'admin.sources.tabEmails' }))
    await waitFor(() => expect(screen.getByText('admin.sources.emails.title')).toBeTruthy())

    // Still in the DOM (so an in-progress edit survives), but out of the layout and the a11y tree.
    expect(registryWrapper()!.hasAttribute('hidden')).toBe(true)
    expect(screen.getByRole('tab', { name: 'admin.sources.tabEmails' }).getAttribute('aria-selected')).toBe('true')
  })

  it('hides Add source on the emails panel — there is nothing there to add', async () => {
    render(<SourcesPage />)
    await waitFor(() => expect(screen.getByText('Sekolah Menengah Cheras')).toBeTruthy())
    expect(screen.queryByText(/admin\.sources\.add/)).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'admin.sources.tabEmails' }))
    await waitFor(() => expect(screen.getByText('admin.sources.emails.title')).toBeTruthy())
    expect(screen.queryByText(/admin\.sources\.add/)).toBeNull()
  })

  it('keeps a half-finished add form across a trip to the emails panel and back', async () => {
    render(<SourcesPage />)
    await waitFor(() => expect(screen.getByText('Sekolah Menengah Cheras')).toBeTruthy())

    fireEvent.click(screen.getByText(/admin\.sources\.add/))
    fireEvent.change(screen.getByLabelText(/admin\.sources\.code/), { target: { value: 'halfway' } })

    fireEvent.click(screen.getByRole('tab', { name: 'admin.sources.tabEmails' }))
    await waitFor(() => expect(screen.getByText('admin.sources.emails.title')).toBeTruthy())
    fireEvent.click(screen.getByRole('tab', { name: 'admin.sources.tabOrganisations' }))

    expect(screen.getByDisplayValue('halfway')).toBeTruthy()
  })
})

/**
 * Request #6, widened by the owner to the whole console: a Save that would write nothing stays
 * inactive. ⚠ The dangerous direction is the OPPOSITE of the reported one — a button wrongly
 * disabled strands real work with no way to keep it — so the WAKING half is tested first and
 * matters more than the sleeping half.
 */
describe('the source Save reflects whether the row was edited', () => {
  const openEditor = async () => {
    render(<SourcesPage />)
    await waitFor(() => expect(screen.getByText('Sekolah Menengah Cheras')).toBeTruthy())
    fireEvent.click(screen.getByText('admin.sources.edit'))
    return screen.getByText('admin.sources.save').closest('button') as HTMLButtonElement
  }

  it('WAKES when a field is genuinely changed', async () => {
    const btn = await openEditor()
    fireEvent.change(screen.getByDisplayValue('Aina'), { target: { value: 'Aina binti Rahman' } })
    expect(btn.disabled).toBe(false)
  })

  it('starts inactive on a freshly opened row', async () => {
    const btn = await openEditor()
    expect(btn.disabled).toBe(true)
    expect(btn.title).toBe('common.nothingToSave')
  })

  it('goes back to sleep when the edit is undone', async () => {
    const btn = await openEditor()
    const field = screen.getByDisplayValue('Aina')
    fireEvent.change(field, { target: { value: 'Aina binti Rahman' } })
    expect(btn.disabled).toBe(false)
    fireEvent.change(field, { target: { value: 'Aina' } })
    expect(btn.disabled).toBe(true)
  })

  it('does not send anything while it is inactive', async () => {
    const btn = await openEditor()
    fireEvent.click(btn)
    expect(mockApi.updateSource).not.toHaveBeenCalled()
  })
})


/**
 * Request #3. The card is titled "Partner emails" and every row but one goes to an organisation.
 * The exception goes to the STUDENT, so the screen has to say so — and it must not let the
 * platform-wide "partner emails are off" banner imply that row has stopped too, because it has not.
 */
describe('the row that goes to the student, not the partner', () => {
  const withStudentRow = (comms_enabled: boolean) => ({
    ...EMAILS,
    comms_enabled,
    templates: [
      { kind: 'assigned', enabled: true, to_student: false, subject: 'S', body: 'B',
        last_sent_at: null, last_sent_orgs: 0, updated_at: null, updated_by_email: '' },
      { kind: 'student_assigned', enabled: true, to_student: true, subject: 'S', body: 'B',
        last_sent_at: null, last_sent_orgs: 0, updated_at: null, updated_by_email: '' },
    ],
  }) as unknown as api.PartnerEmailsPayload

  const openEmails = async () => {
    render(<SourcesPage />)
    fireEvent.click(screen.getByRole('tab', { name: 'admin.sources.tabEmails' }))
    await screen.findByText('admin.sources.emails.kind.student_assigned')
  }

  it('labels its recipient, and only that row', async () => {
    mockApi.getPartnerEmails.mockResolvedValue(withStudentRow(true))
    await openEmails()
    expect(screen.getAllByText('admin.sources.emails.toStudent')).toHaveLength(1)
  })

  it('says it is STILL SENDING when partner emails are off platform-wide', async () => {
    mockApi.getPartnerEmails.mockResolvedValue(withStudentRow(false))
    await openEmails()
    expect(screen.getByText('admin.sources.emails.studentUnaffected')).toBeTruthy()
  })

  it('says nothing of the sort while partner emails are on — there is nothing to explain', async () => {
    mockApi.getPartnerEmails.mockResolvedValue(withStudentRow(true))
    await openEmails()
    expect(screen.queryByText('admin.sources.emails.studentUnaffected')).toBeNull()
  })
})
