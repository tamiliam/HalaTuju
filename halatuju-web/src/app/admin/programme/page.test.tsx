/**
 * @jest-environment jsdom
 *
 * "What we ask for" — rendered (Layer 0 Sprint 5, 2026-08-30).
 *
 * The pure helpers have their own tests; these pin what the SCREEN promises: a locked row is
 * drawn from the item's own core flag with its reason, the Save button is a COMPUTED diff (asleep
 * with nothing changed, awake on a real edit, asleep again on discard), the write sends only the
 * changed rows, and every outcome of a save has a line on screen — including the refusal.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import AdminProgrammeConfigPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const CONFIG: api.ProgrammeConfiguration = {
  programme: { code: 'bp', name: 'BrightPath Bursary', organisation: 'BrightPath' },
  live_applicants: 41,
  items: [
    { kind: 'document', code: 'ic', label_key: 'scholarship.docs.type.ic', is_core: true, default_state: 'required', state: 'required' },
    { kind: 'document', code: 'water_bill', label_key: 'scholarship.docs.type.water_bill', is_core: false, default_state: 'optional', state: 'optional' },
    { kind: 'document', code: 'electricity_bill', label_key: 'scholarship.docs.type.electricity_bill', is_core: false, default_state: 'optional', state: 'optional' },
    { kind: 'question', code: 'consent', label_key: 'admin.programme.question.consent', is_core: true, default_state: 'required', state: 'required' },
    { kind: 'question', code: 'fears', label_key: 'admin.programme.question.fears', is_core: false, default_state: 'required', state: 'required' },
  ],
}

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  mockApi.getProgrammeConfiguration.mockResolvedValue(CONFIG)
  mockApi.saveProgrammeConfiguration.mockImplementation(async (items) => ({
    ...CONFIG,
    items: CONFIG.items.map((i) => {
      const c = items.find((x) => x.kind === i.kind && x.code === i.code)
      return c ? { ...i, state: c.state } : i
    }),
  }))
})

const loaded = async () => {
  render(<AdminProgrammeConfigPage />)
  await waitFor(() => expect(screen.getByTestId('row-document:ic')).toBeTruthy())
}

const control = (key: string, state: string) =>
  screen.getByTestId(`row-${key}`).querySelector(`button[data-state="${state}"]`) as HTMLButtonElement

const saveButton = () => screen.getByText('admin.programme.config.save') as HTMLButtonElement

describe('what the screen shows', () => {
  it('names the live count above the controls, from the payload', async () => {
    await loaded()
    expect(screen.getByTestId('live-warning').textContent).toContain('liveWarning|41')
  })

  it('draws a locked row from its own core flag, visible, with the reason', async () => {
    await loaded()
    const ic = screen.getByTestId('row-document:ic')
    expect(ic.querySelector('[data-testid="always-required"]')).toBeTruthy()
    expect(control('document:ic', 'off').disabled).toBe(true)
    expect(control('document:ic', 'optional').disabled).toBe(true)
    expect(control('document:ic', 'required').getAttribute('aria-checked')).toBe('true')
    // …and an ordinary row is fully live, with no lock label.
    const wb = screen.getByTestId('row-document:water_bill')
    expect(wb.querySelector('[data-testid="always-required"]')).toBeNull()
    expect(control('document:water_bill', 'off').disabled).toBe(false)
  })

  it('refuses to render for a role the endpoint would refuse', async () => {
    viewerRole = { role: 'admin' }
    const { container } = render(<AdminProgrammeConfigPage />)
    await waitFor(() => expect(mockApi.getProgrammeConfiguration).not.toHaveBeenCalled())
    expect(container.innerHTML).toBe('')
  })
})

describe('the Save rule is a computed diff', () => {
  it('sleeps with nothing changed, wakes on a real edit, sleeps again on discard', async () => {
    await loaded()
    expect(saveButton().disabled).toBe(true)
    expect(screen.getByTestId('save-outcome').textContent).toBe('admin.programme.config.unchanged')
    fireEvent.click(control('document:water_bill', 'required'))
    expect(saveButton().disabled).toBe(false)
    expect(screen.getByTestId('save-outcome').textContent).toBe('admin.programme.config.changed|1')
    // Setting it BACK to what the server holds is not a change.
    fireEvent.click(control('document:water_bill', 'optional'))
    expect(saveButton().disabled).toBe(true)
    fireEvent.click(control('document:water_bill', 'required'))
    fireEvent.click(screen.getByText('admin.programme.config.discard'))
    expect(saveButton().disabled).toBe(true)
  })

  it('sends only the changed rows, and the neighbour is not in the write', async () => {
    await loaded()
    fireEvent.click(control('document:water_bill', 'required'))
    fireEvent.click(saveButton())
    await waitFor(() => expect(mockApi.saveProgrammeConfiguration).toHaveBeenCalledTimes(1))
    expect(mockApi.saveProgrammeConfiguration.mock.calls[0][0]).toEqual([
      { kind: 'document', code: 'water_bill', state: 'required' },
    ])
    await waitFor(() => expect(screen.getByTestId('save-outcome').textContent)
      .toBe('admin.programme.config.saved'))
    expect(saveButton().disabled).toBe(true)
    // The re-read is what the screen shows now.
    expect(control('document:water_bill', 'required').getAttribute('aria-checked')).toBe('true')
  })
})

describe('every outcome has a line on screen', () => {
  it('renders the core-item refusal by the item\'s name and keeps the draft', async () => {
    await loaded()
    mockApi.saveProgrammeConfiguration.mockRejectedValueOnce(Object.assign(new Error('x'), {
      body: { code: 'core_item', item: 'question:consent' },
    }))
    fireEvent.click(control('document:water_bill', 'required'))
    fireEvent.click(saveButton())
    await waitFor(() => expect(screen.getByTestId('save-outcome').textContent)
      .toBe('admin.programme.config.errorCore|admin.programme.question.consent'))
    // Nothing was saved, so the edit is still pending and Save is still awake.
    expect(saveButton().disabled).toBe(false)
  })

  it('renders a generic failure rather than silence', async () => {
    await loaded()
    mockApi.saveProgrammeConfiguration.mockRejectedValueOnce(new Error('boom'))
    fireEvent.click(control('question:fears', 'off'))
    fireEvent.click(saveButton())
    await waitFor(() => expect(screen.getByTestId('save-outcome').textContent)
      .toBe('admin.programme.config.errorGeneric'))
  })
})

/**
 * The tabbed shell (Layer 1 A2). Untested until now, which is why a screenshot could not settle
 * whether the heading and tabs were rendering at all — the honest answer to "is it there?" is a
 * test, not a third request for a screenshot.
 */
describe('the tabbed shell', () => {
  it('shows the page heading and BOTH tabs, with the config tab open first', async () => {
    render(<AdminProgrammeConfigPage />)
    expect(screen.getByText('admin.programme.title')).toBeTruthy()
    expect(screen.getByText('admin.programme.subtitle')).toBeTruthy()
    expect(screen.getByTestId('tab-config').getAttribute('aria-selected')).toBe('true')
    expect(screen.getByTestId('tab-colours').getAttribute('aria-selected')).toBe('false')
    // And the config tab's own heading, which sits between the tabs and its first card.
    await waitFor(() => expect(screen.getByText('admin.programme.config.title')).toBeTruthy())
  })

  it('switches to Colours and back, and each tab owns its own content', async () => {
    render(<AdminProgrammeConfigPage />)
    await waitFor(() => expect(screen.getByText('admin.programme.config.title')).toBeTruthy())

    fireEvent.click(screen.getByTestId('tab-colours'))
    expect(screen.getByTestId('tab-colours').getAttribute('aria-selected')).toBe('true')
    expect(screen.getByText('admin.programme.colours.title')).toBeTruthy()
    expect(screen.queryByText('admin.programme.config.title')).toBeNull()

    fireEvent.click(screen.getByTestId('tab-config'))
    await waitFor(() => expect(screen.getByText('admin.programme.config.title')).toBeTruthy())
    expect(screen.queryByText('admin.programme.colours.title')).toBeNull()
  })
})
