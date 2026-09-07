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
  // The Rules and Intake-year tabs share this page now, and both ask which gift they are in.
  // ONE gift here on purpose: that is production today, and it is the path where nothing should
  // ask the reader anything (`useSelectedProgramme` resolves a single gift without a question).
  mockApi.getAdminProgrammes.mockResolvedValue({
    programmes: [{
      id: 1, code: 'bp', name_en: 'BrightPath Bursary', name_ms: '', name_ta: '',
      is_active: true, intake_years: 1, applications: 41, open_year: null,
      // ⚠ A GIFT WITH APPLICATIONS CANNOT BE DELETED, and the SERVER says so — the client
      // never derives it. This fixture is the production shape: 41 applications, held.
      delete_blocked_by: 'has_applications', delete_blocked_count: 41,
    }],
  })
  mockApi.getAdminIntakeYears.mockResolvedValue({
    programme: { id: 1, code: 'bp', name_en: 'BrightPath Bursary', is_active: true },
    years: [],
  })
  mockApi.getProgrammeConfiguration.mockResolvedValue(CONFIG)
  mockApi.saveProgrammeConfiguration.mockImplementation(async (items) => ({
    ...CONFIG,
    items: CONFIG.items.map((i) => {
      const c = items.find((x) => x.kind === i.kind && x.code === i.code)
      return c ? { ...i, state: c.state } : i
    }),
  }))
})

/**
 * ⚠ THE PAGE OPENS ON INTAKE YEAR (gift setup flow, 2026-09-06 — it was Rules from the shape
 * sprint, 2026-09-03), so every "what we ask for" assertion has to walk there first. That is not
 * test friction to route around — the tab ORDER is an owner decision, twice over, so a helper
 * that silently mounted the config tab in isolation would let it drift with nothing noticing. It
 * clicks the tab a person would click.
 */
const loaded = async () => {
  render(<AdminProgrammeConfigPage />)
  fireEvent.click(screen.getByTestId('tab-config'))
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
  // ⚠ THESE ASSERT ON EACH TAB'S SUBTITLE, NOT ITS HEADING, AND THE HEADINGS ARE WHY (2026-09-02).
  // Both tabs used to open with an <h2> restating the tab label — "What your programme asks for"
  // under a tab reading "What we ask for", and "Your colours" under one reading "Colours". With the
  // page title and the tabs, that was FOUR restatements above the first control. The headings are
  // deleted and their keys with them; the subtitle is now each tab's own marker.
  //
  // ⚠⚠ THIS ASSERTED `['tab-rules', 'tab-config', 'tab-year']` UNTIL 2026-09-06, AND THE REASON
  // IT GAVE WAS NOT WRONG — it is carried forward here rather than deleted with the assertion:
  //
  //   *"Rules first, because who qualifies precedes what they are asked to send."*
  //
  // That is true of READING a gift already running, and it stays true. It is not true of SETTING
  // ONE UP, which is what this screen is reached by: **the rules are COLUMNS ON THE INTAKE YEAR**,
  // so a gift created a minute ago has nothing for them to write to, and opening it on Rules
  // landed a person on the one screen that could not work yet. Setup order follows DATA order.
  //
  // Colours still LEFT the screen entirely (it writes a tenant-wide row and lives under
  // Organisation → Settings). Four sidebar rows collapsed into this one screen, so the tab list is
  // the artefact that has to be right.
  it('opens on Intake year, and offers exactly the three tabs in the owner order', () => {
    render(<AdminProgrammeConfigPage />)
    expect(screen.getByText('admin.programme.title')).toBeTruthy()
    expect(screen.getByText('admin.programme.subtitle')).toBeTruthy()

    const tabs = screen.getAllByRole('tab').map((el) => el.getAttribute('data-testid'))
    expect(tabs).toEqual(['tab-year', 'tab-rules', 'tab-config'])
    expect(screen.getByTestId('tab-year').getAttribute('aria-selected')).toBe('true')
    expect(screen.getByTestId('tab-rules').getAttribute('aria-selected')).toBe('false')
  })

  it('no longer carries Colours — that writes a tenant-wide row, not this gift', () => {
    render(<AdminProgrammeConfigPage />)
    expect(screen.queryByTestId('tab-colours')).toBeNull()
    expect(screen.queryByText('admin.orgSettings.colours.subtitle')).toBeNull()
  })

  it('switches between tabs, and each tab owns its own content', async () => {
    render(<AdminProgrammeConfigPage />)

    fireEvent.click(screen.getByTestId('tab-config'))
    await waitFor(() => expect(screen.getByText('admin.programme.config.subtitle')).toBeTruthy())
    expect(screen.queryByText('admin.rules.subtitle')).toBeNull()

    fireEvent.click(screen.getByTestId('tab-year'))
    expect(screen.getByTestId('tab-year').getAttribute('aria-selected')).toBe('true')
    expect(screen.queryByText('admin.programme.config.subtitle')).toBeNull()

    fireEvent.click(screen.getByTestId('tab-config'))
    await waitFor(() => expect(screen.getByText('admin.programme.config.subtitle')).toBeTruthy())
  })

  it('gives the page exactly ONE heading above the tabs, and no tab adds another', async () => {
    // The regression guard. Deleting a heading is a one-line change that a later "the tab looks
    // bare, add a title" would silently undo — and nothing else in the suite would notice, because
    // an extra <h2> breaks no behaviour. Section cards inside a tab (Documents, Questions, and the
    // colours panels) keep their own headings; those name real groups rather than repeating the tab.
    render(<AdminProgrammeConfigPage />)
    fireEvent.click(screen.getByTestId('tab-config'))
    await waitFor(() => expect(screen.getByText('admin.programme.config.subtitle')).toBeTruthy())

    // ⚠ `matches`, NOT `querySelectorAll`. The first draft collected headings INSIDE each child and
    // so never looked at the child itself — an <h2> sitting directly in the panel searched its own
    // empty insides and reported nothing. It passed with a heading deliberately injected. Written
    // wrong once here; the bite-check is the only reason that is not still true.
    const tabs = screen.getByRole('tablist')
    const panel = document.querySelector('[role=tabpanel]') as HTMLElement
    // `Array.from`, not a spread: an HTMLCollection is not iterable under this tsconfig's target,
    // and the spread put the project's `tsc` baseline up from 24 to 25 (TD-221 counts it).
    const loose = Array.from(panel.children)
      .filter((el) => el.matches('h1,h2,h3'))
      .map((el) => el.textContent)
    expect({ loose }).toEqual({ loose: [] })

    // And the page's own <h1> is the only top-level heading, sitting above the tabs.
    expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent))
      .toEqual(['admin.programme.title'])
    expect(tabs).toBeTruthy()
  })
})

/**
 * The setup TRAIL (gift setup flow, 2026-09-06).
 *
 * The owner's report was that the flow is "disconnected": pressing Create left you on a list, and
 * opening a brand-new gift landed you on Rules — the one tab that cannot work before an intake
 * year exists, since the rules ARE columns on that row. It said so in prose and offered no button.
 *
 * These pin the two ends a person actually walks: arriving on the tab a caller pointed at, and
 * being offered the way out of the empty state instead of being told to go and find it.
 */
describe('the setup trail', () => {
  const at = (search: string) => {
    window.history.replaceState({}, '', `/admin/programme${search}`)
  }

  afterEach(() => at(''))

  it('opens on the tab `?tab=` names, so anything can point at one', () => {
    at('?tab=config')
    render(<AdminProgrammeConfigPage />)
    expect(screen.getByTestId('tab-config').getAttribute('aria-selected')).toBe('true')
    expect(screen.getByTestId('tab-year').getAttribute('aria-selected')).toBe('false')
  })

  it('ignores a `?tab=` that names nothing, rather than rendering an empty panel', () => {
    at('?tab=colours')
    render(<AdminProgrammeConfigPage />)
    expect(screen.getByTestId('tab-year').getAttribute('aria-selected')).toBe('true')
  })

  it('⚠ offers a BUTTON out of the Rules empty state, not just a sentence naming the tab', async () => {
    // The message has always named the Intake year tab in words. A dead end that TELLS you where
    // to go is still a dead end — the person has to re-read it, find the tab and cross the screen.
    render(<AdminProgrammeConfigPage />)
    fireEvent.click(screen.getByTestId('tab-rules'))
    await waitFor(() => expect(screen.getByText('admin.rules.noYear')).toBeTruthy())

    fireEvent.click(screen.getByTestId('rules-go-to-year'))
    expect(screen.getByTestId('tab-year').getAttribute('aria-selected')).toBe('true')
  })

  it('⚠ points ONWARD to Rules only once a year exists — before that there is nowhere to go', async () => {
    render(<AdminProgrammeConfigPage />)
    await waitFor(() => expect(screen.getByTestId('tab-year').getAttribute('aria-selected')).toBe('true'))
    // No years in the default fixture → no onward pointer, because the rules live on a year row.
    expect(screen.queryByTestId('year-go-to-rules')).toBeNull()
  })
})

describe('what we ask for, in the order a student meets it', () => {
  it('⚠ renders QUESTIONS before DOCUMENTS (owner, 2026-09-06)', async () => {
    await loaded()
    const headings = Array.from(document.querySelectorAll('[id^=section-]'))
      .map((el) => el.id)
    // Order only — no write and no rule moves with it; the Save diff reads the draft, not this.
    expect(headings).toEqual(['section-questions', 'section-documents'])
  })
})
