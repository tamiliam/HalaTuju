/**
 * @jest-environment jsdom
 *
 * Programme → Configuration → Intake year, rendered (owner's live review, 2026-09-07).
 *
 * Four claims, and none of them can be seen by a source-shape guard:
 *
 *  1. THE RULE SITS ABOVE THE THING IT GOVERNS. The one-open-round caution rendered UNDER the
 *     table and was the only banner on the four Configuration screens that did.
 *  2. A ROUND CAN BE EDITED — its name and its window, and NOT its year or short code, because
 *     those are the two the endpoint has never accepted. A box the server ignores is worse than
 *     no box.
 *  3. THE DATES SPEAK. They rendered as a bare range that meant nothing, which is exactly the
 *     complaint that killed "Next: set the rules". Now they say where today sits.
 *  4. THEY WARN, AND THEY DO NOT REFUSE. Opening outside the stated window asks first and then
 *     goes ahead — because the window describes and the person decides (2026-09-06, re-affirmed
 *     2026-09-07). A test pins the going-ahead, not just the asking: a confirmation that could
 *     not be got past would be a client-side gate the server does not hold.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import IntakeYearTab from './IntakeYearTab'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const programme = (over: Partial<api.AdminProgramme> = {}): api.AdminProgramme => ({
  id: 1, code: 'bp', name_en: 'BrightPath Bursary', name_ms: '', name_ta: '',
  is_active: true, lifecycle: 'active', intake_years: 1, applications: 143, open_year: 2026,
  delete_blocked_by: 'has_applications', delete_blocked_count: 143, ...over,
})

const year = (over: Partial<api.AdminIntakeYear> = {}): api.AdminIntakeYear => ({
  id: 10, code: 'bp-2026', name: 'BrightPath Bursary Programme 2026', year: 2026,
  is_open: false, is_active: true, applications: 143,
  // ⚠ NULL IS THE PRODUCTION SHAPE — every round predating these columns has no stated window,
  // the live 2026 intake among them, and nothing was backfilled.
  opens_on: null, closes_on: null,
  // The four served fields the round badge and the finish dialog read. `state` is computed
  // server-side (`views_admin.round_state`) — never derived here.
  state: 'closed', finished_at: null, finished_by: '', unsubmitted: 0,
  requirements: {
    min_spm_a_count: 4, min_spm_bplus_count: 5, min_stpm_pngk: 2.9,
    min_merit_score: null, income_ceiling: 5860, per_capita_ceiling: 1584,
  },
  ...over,
})

const withYears = (years: api.AdminIntakeYear[]) => {
  mockApi.getAdminProgrammes.mockResolvedValue({ programmes: [programme()] })
  mockApi.getAdminIntakeYears.mockResolvedValue({
    programme: { id: 1, code: 'bp', name_en: 'BrightPath Bursary', is_active: true },
    years,
  })
}

/** Waits for the ROW, not the container — the table shell renders before the years arrive. */
const loaded = async (code = 'bp-2026') => {
  render(<IntakeYearTab />)
  await waitFor(() => expect(screen.getByTestId(`year-${code}`)).toBeTruthy())
}

/** ⚠ THE BADGE IS THE CONTROL NOW (2026-09-08). The loose Open/Close link is gone — it sat beside
 *  a two-month-old closed round for ever. Press the badge, then the move. */
const pressState = (code: string, action: 'openIt' | 'closeIt' | 'finishIt') => {
  fireEvent.click(screen.getByTestId(`state-${code}`))
  fireEvent.click(screen.getByText(`admin.years.state.${action}`))
}

beforeEach(() => {
  jest.clearAllMocks()
  withYears([year()])
  mockApi.updateAdminIntakeYear.mockResolvedValue(year())
  // Pin the clock. Every window assertion below is relative to this day, so a test that passes in
  // March and fails in May is not a thing that can happen here.
  jest.useFakeTimers().setSystemTime(new Date(2026, 8, 7))
})

afterEach(() => { jest.useRealTimers() })

describe('the caution sits above the table', () => {
  it('renders the one-open-round warning before the rows, not after them', async () => {
    await loaded()
    const banner = screen.getByText('admin.years.oneOpen')
    const table = document.querySelector('table') as HTMLElement
    // DOCUMENT_POSITION_FOLLOWING: the table comes AFTER the banner in reading order.
    // eslint-disable-next-line no-bitwise
    expect(banner.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

describe('the window says where today sits', () => {
  it('renders a bare dash and NO state line for a round with no dates', async () => {
    await loaded()
    expect(screen.queryByTestId('window-bp-2026')).toBeNull()
  })

  it('names the state under the dates once a window is stated', async () => {
    withYears([year({ opens_on: '2026-10-01', closes_on: '2026-11-30' })])
    await loaded()
    const cell = screen.getByTestId('window-bp-2026')
    expect(cell.querySelector('[data-window-state]')?.getAttribute('data-window-state'))
      .toBe('before')
    expect(cell.textContent).toContain('admin.years.win.before')
    // The dates themselves survive — the line is added, never a replacement.
    expect(cell.textContent).toContain('01/10/2026')
  })

  it('reads "after" once the stated window has passed', async () => {
    withYears([year({ opens_on: '2026-03-01', closes_on: '2026-04-30' })])
    await loaded()
    expect(screen.getByTestId('window-bp-2026').textContent).toContain('admin.years.win.after')
  })
})

describe('editing a round', () => {
  it('offers the name and both dates, and refuses to offer the year or the code', async () => {
    withYears([year({ opens_on: '2026-03-01', closes_on: '2026-04-30' })])
    await loaded()
    fireEvent.click(screen.getByTestId('edit-bp-2026'))

    expect((document.getElementById('e-name') as HTMLInputElement).value)
      .toBe('BrightPath Bursary Programme 2026')
    expect((document.getElementById('e-opens') as HTMLInputElement).value).toBe('2026-03-01')
    expect((document.getElementById('e-closes') as HTMLInputElement).value).toBe('2026-04-30')
    // ⚠ NO box for either. `AdminIntakeYearDetailView.patch` accepts neither, so a box would be
    // a control that silently does nothing — the defect this whole review round is about.
    expect(document.getElementById('e-year')).toBeNull()
    expect(document.getElementById('e-code')).toBeNull()
    expect(screen.getByTestId('edit-year-dialog').textContent)
      .toContain('admin.years.editFixed|2026,bp-2026')
  })

  it('sends the new name and window, and nothing else', async () => {
    withYears([year()])
    await loaded()
    fireEvent.click(screen.getByTestId('edit-bp-2026'))
    fireEvent.change(document.getElementById('e-name') as HTMLInputElement,
      { target: { value: 'Intake 2026' } })
    fireEvent.change(document.getElementById('e-opens') as HTMLInputElement,
      { target: { value: '2026-10-01' } })
    fireEvent.click(screen.getByTestId('save-edit'))

    await waitFor(() => expect(mockApi.updateAdminIntakeYear).toHaveBeenCalled())
    expect(mockApi.updateAdminIntakeYear).toHaveBeenCalledWith(
      10, { name: 'Intake 2026', opens_on: '2026-10-01', closes_on: null }, { token: 'tok' })
  })

  // ⚠ CLEARING A DATE SENDS null, NOT ''. `_window_from` reads absent / empty / a date as three
  // different instructions, and null is the one that WITHDRAWS a stated window. Without this a
  // schedule could only ever be changed, never taken back.
  it('withdraws a window when the boxes are cleared', async () => {
    withYears([year({ opens_on: '2026-03-01', closes_on: '2026-04-30' })])
    await loaded()
    fireEvent.click(screen.getByTestId('edit-bp-2026'))
    fireEvent.change(document.getElementById('e-opens') as HTMLInputElement,
      { target: { value: '' } })
    fireEvent.change(document.getElementById('e-closes') as HTMLInputElement,
      { target: { value: '' } })
    fireEvent.click(screen.getByTestId('save-edit'))

    await waitFor(() => expect(mockApi.updateAdminIntakeYear).toHaveBeenCalled())
    expect(mockApi.updateAdminIntakeYear.mock.calls[0][1])
      .toEqual({ name: 'BrightPath Bursary Programme 2026', opens_on: null, closes_on: null })
  })

  // ⚠ THE PLATFORM RULE: A SAVE SLEEPS UNTIL THERE IS SOMETHING TO SAVE (owner, 2026-09-08:
  // *"the save is enabled even though no change has been made"*). Every other Configuration
  // screen already obeyed it via SaveBar; this dialog was the one that did not.
  it('sleeps until something is actually changed', async () => {
    withYears([year({ opens_on: '2026-03-01', closes_on: '2026-04-30' })])
    await loaded()
    fireEvent.click(screen.getByTestId('edit-bp-2026'))
    const save = screen.getByTestId('save-edit') as HTMLButtonElement
    expect(save.disabled).toBe(true)

    fireEvent.change(document.getElementById('e-closes') as HTMLInputElement,
      { target: { value: '2026-05-31' } })
    expect((screen.getByTestId('save-edit') as HTMLButtonElement).disabled).toBe(false)
  })

  // ⚠ COMPARED AS IT WILL BE SENT. `saveEdit` trims the name and turns a blank box into null, so
  // neither a trailing space nor an empty box against a null window is a change. A button that
  // woke up for those would send the server exactly what it already holds.
  it('stays asleep for a change that sends nothing new', async () => {
    withYears([year()])
    await loaded()
    fireEvent.click(screen.getByTestId('edit-bp-2026'))
    fireEvent.change(document.getElementById('e-name') as HTMLInputElement,
      { target: { value: 'BrightPath Bursary Programme 2026  ' } })
    expect((screen.getByTestId('save-edit') as HTMLButtonElement).disabled).toBe(true)
  })

  // Re-opening the dialog on a second round must not inherit the first round's dirtiness.
  it('wakes up, then sleeps again when the change is typed back out', async () => {
    withYears([year()])
    await loaded()
    fireEvent.click(screen.getByTestId('edit-bp-2026'))
    const name = document.getElementById('e-name') as HTMLInputElement
    fireEvent.change(name, { target: { value: 'Something else' } })
    expect((screen.getByTestId('save-edit') as HTMLButtonElement).disabled).toBe(false)
    fireEvent.change(name, { target: { value: 'BrightPath Bursary Programme 2026' } })
    expect((screen.getByTestId('save-edit') as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('opening a round against its own schedule', () => {
  it('opens straight away when there is no stated window', async () => {
    withYears([year()])
    await loaded()
    pressState('bp-2026', 'openIt')
    await waitFor(() => expect(mockApi.updateAdminIntakeYear).toHaveBeenCalled())
    expect(screen.queryByTestId('confirm-open-dialog')).toBeNull()
    expect(mockApi.updateAdminIntakeYear)
      .toHaveBeenCalledWith(10, { is_open: true }, { token: 'tok' })
  })

  it('opens straight away when today is inside the window', async () => {
    withYears([year({ opens_on: '2026-09-01', closes_on: '2026-09-30' })])
    await loaded()
    pressState('bp-2026', 'openIt')
    await waitFor(() => expect(mockApi.updateAdminIntakeYear).toHaveBeenCalled())
    expect(screen.queryByTestId('confirm-open-dialog')).toBeNull()
  })

  it('asks first when the window has not started, and names the date', async () => {
    withYears([year({ opens_on: '2026-10-01', closes_on: '2026-11-30' })])
    await loaded()
    pressState('bp-2026', 'openIt')
    expect(mockApi.updateAdminIntakeYear).not.toHaveBeenCalled()
    expect(screen.getByTestId('confirm-open-dialog').textContent)
      .toContain('admin.years.confirmOpenBefore|01/10/2026')
  })

  it('asks first when the window has ended, and names the date', async () => {
    withYears([year({ opens_on: '2026-03-01', closes_on: '2026-04-30' })])
    await loaded()
    pressState('bp-2026', 'openIt')
    expect(screen.getByTestId('confirm-open-dialog').textContent)
      .toContain('admin.years.confirmOpenAfter|30/04/2026')
  })

  // ⚠ THE ANSWER IS ALWAYS ALLOWED. This is the assertion that keeps the warning a warning: the
  // server accepts an out-of-window open deliberately, so a confirmation nobody could get past
  // would be a client-side rule the server does not hold.
  it('goes ahead and opens once the person confirms', async () => {
    withYears([year({ opens_on: '2026-10-01', closes_on: '2026-11-30' })])
    await loaded()
    pressState('bp-2026', 'openIt')
    fireEvent.click(screen.getByTestId('confirm-open-yes'))
    await waitFor(() => expect(mockApi.updateAdminIntakeYear).toHaveBeenCalled())
    expect(mockApi.updateAdminIntakeYear)
      .toHaveBeenCalledWith(10, { is_open: true }, { token: 'tok' })
    expect(screen.queryByTestId('confirm-open-dialog')).toBeNull()
  })

  // CLOSING never asks. There is nothing to protect a student from in stopping applications, and
  // an admin closing an overrunning round would meet a dialog every single time.
  it('never asks before CLOSING, whatever the window says', async () => {
    withYears([year({ state: 'open', is_open: true, opens_on: '2026-10-01', closes_on: '2026-11-30' })])
    await loaded()
    pressState('bp-2026', 'closeIt')
    await waitFor(() => expect(mockApi.updateAdminIntakeYear).toHaveBeenCalled())
    expect(screen.queryByTestId('confirm-open-dialog')).toBeNull()
    expect(mockApi.updateAdminIntakeYear)
      .toHaveBeenCalledWith(10, { is_open: false }, { token: 'tok' })
  })
})

/**
 * The round's four states, and the one that cannot be undone.
 *
 * ⚠⚠ CLOSED AND FINISHED ARE DIFFERENT THINGS, AND THE MENU IS THE ONLY PLACE THAT SAYS SO. A
 * closed round still lets anyone already started submit — the 2026 intake ran on exactly that
 * between 1 and 7 July, thirty students deep, and nothing on any screen mentioned it.
 */
describe('the round badge is the control', () => {
  const at = (state: api.AdminIntakeYear['state'], over = {}) => {
    withYears([year({ state, ...over })])
    return loaded()
  }

  it('renders each state in its own tone, and NONE of them is red', async () => {
    // ⚠ `critical` means something is WRONG. Every state here is a normal point in a round's
    // life, so a red badge would report a problem that does not exist — the gift card's ruling.
    for (const [state, tone] of [
      ['draft', 'bg-ground-100'], ['open', 'bg-positive-100'],
      ['closed', 'bg-caution-100'], ['finished', 'bg-info-100'],
    ] as const) {
      cleanup()
      jest.clearAllMocks()
      await at(state)
      const badge = screen.getByTestId('state-bp-2026')
      expect(badge.textContent).toContain(`admin.years.state.${state}`)
      expect(badge.className).toContain(tone)
      expect(badge.className).not.toContain('critical')
    }
  })

  it('says what CLOSED means — no new applications, but those started may still submit', async () => {
    await at('closed')
    fireEvent.click(screen.getByTestId('state-bp-2026'))
    expect(screen.getByText('admin.years.state.means.closed')).toBeTruthy()
  })

  it('offers "close for good" ONLY on a closed round', async () => {
    for (const state of ['draft', 'open', 'finished'] as const) {
      cleanup()
      jest.clearAllMocks()
      await at(state)
      fireEvent.click(screen.getByTestId('state-bp-2026'))
      expect(screen.queryByText('admin.years.state.finishIt')).toBeNull()
    }
    cleanup()
    jest.clearAllMocks()
    await at('closed')
    fireEvent.click(screen.getByTestId('state-bp-2026'))
    expect(screen.queryByText('admin.years.state.finishIt')).toBeTruthy()
  })

  // ⚠ THE OWNER'S RULING, ON SCREEN. A finished round offers NO move — not a greyed one, none.
  // The server refuses to reopen it too; this is the half a person can see.
  it('a FINISHED round offers no move at all, and says why', async () => {
    await at('finished', { finished_at: '2026-07-08T04:00:00Z' })
    fireEvent.click(screen.getByTestId('state-bp-2026'))
    expect(screen.getByText('admin.years.state.means.finished')).toBeTruthy()
    expect(screen.queryByText('admin.years.state.openIt')).toBeNull()
    expect(screen.queryByText('admin.years.state.closeIt')).toBeNull()
    expect(screen.queryByText('admin.years.state.finishIt')).toBeNull()
  })

  // ⚠ THE MENU MUST LEAVE THE TABLE (owner, 2026-09-08: *"Clicking the close opens something, but
  // it is hidden."*). The table's wrapper is `overflow-hidden` — it is what rounds the corners —
  // so a panel rendered inside the row was clipped to a sliver at the table's edge. The panel is
  // a portal now. Asserting it here as well as in Menu.test.tsx is the point: this table is the
  // clipping ancestor that proved the primitive was wrong.
  it('opens its menu OUTSIDE the table, where nothing can clip it', async () => {
    await at('closed')
    fireEvent.click(screen.getByTestId('state-bp-2026'))
    const panel = screen.getByRole('menu')
    expect((document.querySelector('table') as HTMLElement).contains(panel)).toBe(false)
    expect(document.querySelector('.overflow-hidden')?.contains(panel)).toBeFalsy()
    expect(panel.parentElement).toBe(document.body)
  })
})

describe('closing a round for good', () => {
  const openDialog = async (over = {}) => {
    withYears([year({ state: 'closed', ...over })])
    await loaded()
    fireEvent.click(screen.getByTestId('state-bp-2026'))
    fireEvent.click(screen.getByText('admin.years.state.finishIt'))
  }

  it('names how many applicants it would shut out', async () => {
    // The one fact the reader cannot see from the dialog. Silence would mean pressing this and
    // quietly locking two half-finished students out of an intake.
    await openDialog({ unsubmitted: 2 })
    expect(screen.getByTestId('finish-unsubmitted').textContent)
      .toBe('admin.years.finish.stranded|2')
  })

  it('says nothing about stranded applicants when there are none', async () => {
    await openDialog({ unsubmitted: 0 })
    expect(screen.queryByTestId('finish-unsubmitted')).toBeNull()
  })

  it('sleeps until the round code is typed, then sends it', async () => {
    mockApi.finishAdminIntakeYear.mockResolvedValue(year({ state: 'finished' }))
    await openDialog()
    const go = screen.getByTestId('finish-confirm-yes') as HTMLButtonElement
    expect(go.disabled).toBe(true)

    fireEvent.change(document.getElementById('finish-confirm') as HTMLInputElement,
      { target: { value: 'bp-wrong' } })
    expect((screen.getByTestId('finish-confirm-yes') as HTMLButtonElement).disabled).toBe(true)

    fireEvent.change(document.getElementById('finish-confirm') as HTMLInputElement,
      { target: { value: 'bp-2026' } })
    expect((screen.getByTestId('finish-confirm-yes') as HTMLButtonElement).disabled).toBe(false)

    fireEvent.click(screen.getByTestId('finish-confirm-yes'))
    await waitFor(() => expect(mockApi.finishAdminIntakeYear).toHaveBeenCalled())
    expect(mockApi.finishAdminIntakeYear).toHaveBeenCalledWith(10, 'bp-2026', { token: 'tok' })
  })

  // It is a confirmation, not a password. Refusing BP-2026 for bp-2026 would teach nothing.
  it('accepts the code in any case', async () => {
    mockApi.finishAdminIntakeYear.mockResolvedValue(year({ state: 'finished' }))
    await openDialog()
    fireEvent.change(document.getElementById('finish-confirm') as HTMLInputElement,
      { target: { value: 'BP-2026' } })
    expect((screen.getByTestId('finish-confirm-yes') as HTMLButtonElement).disabled).toBe(false)
  })
})

describe('the date boxes', () => {
  // ⚠ Chrome's year slot takes SIX digits, so typing over an existing value gives `07/07/202026`
  // — well-formed, absurd, and the server can only answer "enter a valid closing date".
  it('cap the year so a six-digit one cannot be typed', async () => {
    withYears([year()])
    await loaded()
    fireEvent.click(screen.getByTestId('edit-bp-2026'))
    for (const id of ['e-opens', 'e-closes']) {
      const box = document.getElementById(id) as HTMLInputElement
      expect(box.min).toBe('2000-01-01')
      expect(box.max).toBe('2099-12-31')
    }
  })
})
