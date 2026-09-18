/**
 * @jest-environment jsdom
 *
 * The Programme Overview, rendered — and what this file is really guarding is the ROLE SHAPE.
 *
 * ⚠⚠ **THE SIDE DOOR IS THE HARM.** The menu withholds Payments and Spending from a reviewer and
 * a QC, and withholds Applications from finance. An Overview that fetched everything and drew a
 * subset would hand all of it back through a different route — so the server chooses the key set
 * (`programme_overview.SECTIONS_BY_ROLE`, pinned by `test_the_key_set_per_role_is_exact`) and the
 * page renders by PRESENCE. The tests below therefore assert ABSENCE from the DOM, not a hidden
 * class: `queryByTestId('overview-money')` must be null for a reviewer, because a node that is in
 * the document is in the page source, whatever CSS says about it.
 *
 * ⚠ **THE GIFT MUST REACH THE ENDPOINT.** A page that describes one gift while the breadcrumb
 * names another is the 2026-09-03 defect; it is asserted from the outside, on the call.
 *
 * ⚠ **SEVERAL GIFTS AND NONE CHOSEN IS A REAL STATE.** It gets a neutral heading — never
 * `ChooseProgramme` — because this page reads, and describing everything the fence allows is a
 * true answer, just a less specific one.
 *
 * ⚠ No jest-dom matchers exist in this project: `toBeNull` / `not.toBeNull` / `toEqual`.
 */
import { render, screen, waitFor, within } from '@testing-library/react'

import ProgrammeOverviewPage from './page'
import * as api from '@/lib/admin-api'
import { APPLICATION_STATUSES } from '@/lib/applicationStatus'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    (vars ? `${k}|${Object.values(vars).join(',')}` : k), locale: 'en' }),
}))

// Re-pointed per test, so the page's own role guard can be exercised from the outside.
let authRole: { role: string } = { role: 'admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: authRole }),
}))
jest.mock('@/lib/admin-api')

// The breadcrumb's chosen gift, re-pointed per test — the page reads the same context the crumb
// does, which is why the two can never disagree about which gift is open.
let chosen: string | undefined
jest.mock('@/lib/programmeScope', () => ({
  useProgrammeScope: () => ({ chosen: chosen ?? '', programme: null, choices: [],
                              ambiguous: true, select: () => {}, reload: async () => {} }),
  useProgrammeParam: () => chosen,
}))

const mockApi = api as jest.Mocked<typeof api>

const zeroed = (): Record<string, number> => {
  const out: Record<string, number> = {}
  for (const status of APPLICATION_STATUSES) out[status] = 0
  return out
}

const CATEGORIES: api.OverviewCategory[] = [
  { code: 'food', total: '3738.00', transactions: 610 },
  { code: 'groceries', total: '2404.00', transactions: 210 },
  { code: 'transport', total: '0.00', transactions: 0 },
  { code: 'study', total: '0.00', transactions: 0 },
  { code: 'phone', total: '0.00', transactions: 0 },
  { code: 'hostel', total: '0.00', transactions: 0 },
  { code: 'health', total: '0.00', transactions: 0 },
  { code: 'clothing', total: '0.00', transactions: 0 },
  { code: 'transfer', total: '0.00', transactions: 0 },
  { code: 'unsorted', total: '0.00', transactions: 0 },
  // ⚠ "Nothing has looked at this row yet" — a DIFFERENT state from "the sorter looked and could
  // not place it". At zero it is HIDDEN (owner, 2026-09-18); with money it must appear.
  { code: 'none', total: '0.00', transactions: 0 },
]

const MONEY: api.OverviewMoney = {
  students: 66, committed: '396000.00', paid: '52800.00',
  remaining: '343200.00', spent: '13353.03',
}

const MONEY_SERIES = {
  money_per_month: [
    { month: '2026-05', released: '52800.00', spent: '1180.40',
      released_cum: '52800.00', spent_cum: '1180.40', gap: '51619.60' },
    { month: '2026-06', released: '0.00', spent: '3410.25',
      released_cum: '52800.00', spent_cum: '4590.65', gap: '48209.35' },
  ],
  per_student_per_week: [
    { week: '2026-05-04', students: 44, spent: '853.60', transactions: 106,
      spent_per_transaction: '8.05', transactions_per_student: '2.4' },
    { week: '2026-05-11', students: 44, spent: '900.00', transactions: 110,
      spent_per_transaction: '8.18', transactions_per_student: '2.5' },
    { week: '2026-06-01', students: 50, spent: '1000.00', transactions: 120,
      spent_per_transaction: '8.33', transactions_per_student: '2.4' },
  ],
  per_student_overall: {
    students: 58, weeks: 3, spent: '13353.03', transactions: 1597,
    spent_per_transaction: '8.36', weekly_transactions_per_student: '9.2',
  },
  by_category: CATEGORIES,
}

const INTAKE: api.OverviewIntake = {
  code: '2026', name: 'Intake 2026', is_open: false,
  opens_on: '2026-03-02', closes_on: '2026-04-30', finished_at: '2026-07-31',
}

const ADMIN_PAYLOAD: api.ProgrammeOverview = {
  programme: { code: 'b40', name: 'Test Gift' },
  generated_at: '2026-09-15T10:00:00+08:00',
  data_to: '2026-09-06',
  sections: ['funnel', 'money', 'attention', 'applications_series', 'money_series', 'intake'],
  funnel: { total: 143, by_status: { ...zeroed(), awarded: 66, rejected: 42, expired: 31 } },
  money: MONEY,
  attention: { unassigned: 0, with_reviewer: 2, due_soon: 1, overdue: 0, awaiting_qc: 2 },
  applications_series: {
    applications_per_week: [{ week: '2026-03-02', count: 15 }, { week: '2026-03-09', count: 36 }],
    awards_per_month: [{ month: '2026-05', count: 19 }, { month: '2026-06', count: 30 }],
  },
  money_series: MONEY_SERIES,
  intake: INTAKE,
}

const FINANCE_PAYLOAD: api.ProgrammeOverview = {
  programme: { code: 'b40', name: 'Test Gift' },
  generated_at: '2026-09-15T10:00:00+08:00',
  data_to: '2026-09-06',
  sections: ['money', 'money_series', 'intake'],
  money: MONEY,
  money_series: MONEY_SERIES,
  intake: INTAKE,
}

const REVIEWER_PAYLOAD: api.ProgrammeOverview = {
  programme: { code: 'b40', name: 'Test Gift' },
  generated_at: '2026-09-15T10:00:00+08:00',
  data_to: null,
  sections: ['mine', 'intake'],
  mine: {
    open: 3, due_soon: 1, overdue: 0,
    cases: [{ id: 13, ref: 'B40-0113', applicant_name: 'NURUL TEST', status: 'interviewing',
              assigned_at: '2026-09-04T02:00:00+08:00', due_at: '2026-09-16T02:00:00+08:00',
              band: 'due_soon' }],
    pace: { completed: 6, turnaround_days: 7.5 },
  },
  intake: INTAKE,
}

const QC_PAYLOAD: api.ProgrammeOverview = {
  programme: { code: 'b40', name: 'Test Gift' },
  generated_at: '2026-09-15T10:00:00+08:00',
  data_to: null,
  sections: ['qc', 'intake'],
  qc: {
    awaiting: 2, oldest_waiting_days: 4,
    cases: [{ id: 21, ref: 'B40-0121', applicant_name: 'AMIR TEST', status: 'interviewed',
              since: '2026-09-11T02:00:00+08:00', waiting_days: 4 }],
    pace: { completed: 9, turnaround_days: 1.5 },
  },
  intake: INTAKE,
}

beforeEach(() => {
  jest.clearAllMocks()
  authRole = { role: 'admin' }
  chosen = 'b40'
  mockApi.getProgrammeOverview.mockResolvedValue(ADMIN_PAYLOAD)
})

const heading = () => screen.getByRole('heading', { level: 1 }).textContent

describe('an org admin sees the whole gift', () => {
  it('renders every section it was sent', async () => {
    render(<ProgrammeOverviewPage />)
    await screen.findByTestId('overview-funnel')
    for (const id of ['overview-money', 'overview-attention', 'overview-applications-series',
                      'overview-money-series', 'overview-intake']) {
      expect(screen.queryByTestId(id)).not.toBeNull()
    }
    // …and nothing built for somebody else.
    expect(screen.queryByTestId('overview-mine')).toBeNull()
    expect(screen.queryByTestId('overview-qc')).toBeNull()
  })

  it('states the report date at the top, as the Spending page does', async () => {
    render(<ProgrammeOverviewPage />)
    const stamp = await screen.findByTestId('overview-data-to')
    // Every spending figure on the page stops here; it is a fact about the page, not a section.
    expect(stamp.textContent).toBe('admin.programmeOverview.asAt|06/09/2026')
  })

  it('names the gift it is describing', async () => {
    render(<ProgrammeOverviewPage />)
    await waitFor(() => expect(heading()).toBe('admin.programmeOverview.titleFor|Test Gift'))
  })

  /* ⚠ ELEVEN SLICES, AND THE ONE NOBODY HAS LOOKED AT IS LISTED AT ZERO. Hiding a zero slice is
   * what would let the other ten read as complete when they are not — `by_category` sends all
   * eleven deliberately, and "not yet sorted: RM0.00" is an answer. */
  it('lists a real category even at zero', async () => {
    render(<ProgrammeOverviewPage />)
    const legend = await screen.findByTestId('chart-by-category-figures')
    // "Nothing on health" is an answer — the ten real categories are always listed.
    expect(legend.textContent).toContain('admin.programmeOverview.category.health')
    expect(legend.textContent).toContain('RM0.00')
  })

  /* ⚠ THREE FIGURES, NOT A TABLE (owner, 2026-09-15). The totals are the LAST month's running
   * figures read straight off the server — never summed in the browser. */
  it('prints payments, spending and balance to date beneath the money chart, and no table', async () => {
    render(<ProgrammeOverviewPage />)
    const totals = await screen.findByTestId('money-totals')
    expect(totals.textContent).toContain('admin.programmeOverview.series.payments')
    expect(totals.textContent).toContain('RM52,800.00')   // released_cum of the last month
    expect(totals.textContent).toContain('RM4,590.65')    // spent_cum of the last month
    expect(totals.textContent).toContain('RM48,209.35')   // gap of the last month
    const section = screen.getByTestId('overview-money-series')
    expect(within(section).queryByRole('table')).toBeNull()
    expect(screen.queryByTestId('money-month-cards')).toBeNull()
  })

  /* ⚠ MONTHS ARE NAMED, NOT NUMBERED — through the locale, so "Jul" in English is "Jul" in
   * Malay and "ஜூலை" in Tamil, and never "07/2026". */
  it('labels the money chart\'s axis with month names from the locale', async () => {
    render(<ProgrammeOverviewPage />)
    const chart = await screen.findByTestId('chart-money-per-month')
    const ticks = within(chart).getByTestId('chart-ticks')
    expect(ticks.textContent).toContain('admin.programmeOverview.months.5')
    expect(ticks.textContent).toContain('admin.programmeOverview.months.6')
    expect(chart.textContent).not.toContain('05/2026')
  })

  /* ⚠ THE WEEKLY LINES KEEP THEIR WEEKS AND NAME THEIR MONTHS. Three weekly columns spanning
   * May and June give two month ticks; the figure beneath is the WHOLE-PERIOD one, not three
   * weekly values — that list was the clutter the owner asked to remove. */
  it('names months under the weekly lines, and prints one whole-period figure beneath each', async () => {
    render(<ProgrammeOverviewPage />)
    const average = await screen.findByTestId('chart-average-per-student')
    const ticks = within(average).getByTestId('chart-ticks')
    expect(ticks.querySelectorAll('text').length).toBe(2)
    expect(ticks.textContent).toContain('admin.programmeOverview.months.5')
    expect(ticks.textContent).toContain('admin.programmeOverview.months.6')
    // ⚠ Ringgit per TRANSACTION over the whole period (owner, 2026-09-18) — not per student, and
    // not any single week's value.
    const figures = within(average).getByTestId('chart-average-per-student-figures')
    expect(figures.querySelectorAll('li').length).toBe(1)
    expect(figures.textContent).toContain('admin.programmeOverview.series.overallAverage')
    expect(figures.textContent).toContain('RM8.36')
    expect(figures.textContent).not.toContain('RM8.05')
    // …and n is named beneath it.
    expect(screen.getByText('admin.programmeOverview.series.ofStudentsOverall|58')).not.toBeNull()
    // The second line says TRANSACTIONS, carries a y-axis like the first, and prints the
    // average WEEKLY transactions per student — not the whole-period count.
    const transactions = screen.getByTestId('chart-transactions-per-student')
    expect(within(transactions).getByTestId('chart-y-axis').textContent)
      .toContain('admin.programmeOverview.chart.yTransactions')
    const tFigures = within(transactions).getByTestId('chart-transactions-per-student-figures')
    expect(tFigures.textContent).toContain('admin.programmeOverview.series.overallTransactions')
    expect(tFigures.textContent).toContain('9.2')
    expect(screen.queryByTestId('chart-purchases-per-student')).toBeNull()
  })

  /* ⚠ THE HOVER VALUE IS THE WEEK'S OWN FIGURE, and the total under the ring is the money
   * strip's `spent` — the server's figure, never the rows summed in the browser. */
  it('offers each week on hover, and prints the total spending beneath the category ring', async () => {
    render(<ProgrammeOverviewPage />)
    const average = await screen.findByTestId('chart-average-per-student')
    const points = within(average).getAllByTestId('chart-point')
    expect(points.length).toBe(3)
    // ⚠ THE VALUE ALONE (owner, 2026-09-18: "skip the dates").
    expect(points[0].querySelector('title')?.textContent).toBe('RM8.05')
    const transactions = screen.getByTestId('chart-transactions-per-student')
    expect(within(transactions).getAllByTestId('chart-point')[2].querySelector('title')?.textContent)
      .toBe('2.4')
    const total = screen.getByTestId('chart-by-category-total')
    expect(total.textContent).toContain('admin.programmeOverview.series.spendingTotal')
    expect(total.textContent).toContain('RM13,353.03')   // MONEY.spent, not a sum of the slices
  })

  /* ⚠ THE MONEY CHART LISTS NOTHING BENEATH; every bar and point answers on hover, the y-axis
   * is the bars' scale, and the three totals double as the legend with a swatch each. */
  it('answers the money chart on hover, with a y-axis, swatches, and no list beneath', async () => {
    render(<ProgrammeOverviewPage />)
    const chart = await screen.findByTestId('chart-money-per-month')
    expect(within(chart).queryByTestId('chart-money-per-month-figures')).toBeNull()
    const bars = within(chart).getAllByTestId('chart-bar')
    expect(bars.length).toBe(4)                                   // 2 months × 2 series
    expect(bars[0].querySelector('title')?.textContent).toBe('RM52,800.00')   // May released
    expect(bars[3].querySelector('title')?.textContent).toBe('RM3,410.25')    // June spent
    const points = within(chart).getAllByTestId('chart-point')
    expect(points[1].querySelector('title')?.textContent).toBe('RM48,209.35') // June balance
    expect(within(chart).getByTestId('chart-y-axis').textContent).toContain('RM52,800')
    const totals = screen.getByTestId('money-totals')
    expect(within(totals).getByTestId('swatch-payments').getAttribute('class')).toContain('bg-brand-shape')
    expect(within(totals).getByTestId('swatch-spending').getAttribute('class')).toContain('bg-ground-300')
    expect(within(totals).getByTestId('swatch-balance').getAttribute('class')).toContain('border-dotted')
  })

  /* ⚠ THE TWO SMALL BAR CHARTS: values on hover, a y-axis, months on the weekly one, nothing
   * beneath. */
  it('gives the applications and awards charts a y-axis and hover values, and months under the weeks', async () => {
    render(<ProgrammeOverviewPage />)
    const apps = await screen.findByTestId('chart-applications-per-week')
    expect(within(apps).queryByTestId('chart-applications-per-week-figures')).toBeNull()
    expect(within(apps).getAllByTestId('chart-bar')[1].querySelector('title')?.textContent).toBe('36')
    expect(within(apps).getByTestId('chart-y-axis').textContent)
      .toContain('admin.programmeOverview.chart.yApplications')
    // Two March weeks → one tick, "Mar" (months.3); no DD/MM on the axis.
    const ticks = within(apps).getByTestId('chart-ticks')
    expect(ticks.textContent).toBe('admin.programmeOverview.months.3')
    expect(apps.textContent).not.toContain('02/03')
    const awards = screen.getByTestId('chart-awards-per-month')
    expect(within(awards).queryByTestId('chart-awards-per-month-figures')).toBeNull()
    expect(within(awards).getAllByTestId('chart-bar')[1].querySelector('title')?.textContent).toBe('30')
    expect(within(awards).getByTestId('chart-y-axis').textContent)
      .toContain('admin.programmeOverview.chart.yAwards')
  })

  /* ⚠ LARGEST FIRST, "NOT CATEGORISED" LAST, AND "NOT YET SORTED" HIDDEN AT ZERO (owner,
   * 2026-09-18). The ten real categories are all listed, zero or not. */
  it('orders the category legend by money and hides "not yet sorted" while it is zero', async () => {
    render(<ProgrammeOverviewPage />)
    const legend = await screen.findByTestId('chart-by-category-figures')
    const codes = Array.from(legend.querySelectorAll('li')).map((li) => li.textContent ?? '')
    expect(codes.length).toBe(10)
    expect(codes[0]).toContain('admin.programmeOverview.category.food')       // RM3,738.00
    expect(codes[1]).toContain('admin.programmeOverview.category.groceries')  // RM2,404.00
    expect(codes[9]).toContain('admin.programmeOverview.category.unsorted')
    expect(legend.textContent).not.toContain('admin.programmeOverview.category.none')
  })

  it('shows "not yet sorted" the moment it carries money — last, after "not categorised"', async () => {
    mockApi.getProgrammeOverview.mockResolvedValue({
      ...ADMIN_PAYLOAD,
      money_series: {
        ...MONEY_SERIES,
        by_category: CATEGORIES.map((c) => (c.code === 'none'
          ? { ...c, total: '4076.12', transactions: 300 } : c)),
      },
    })
    render(<ProgrammeOverviewPage />)
    const legend = await screen.findByTestId('chart-by-category-figures')
    const codes = Array.from(legend.querySelectorAll('li')).map((li) => li.textContent ?? '')
    expect(codes.length).toBe(11)
    expect(codes[10]).toContain('admin.programmeOverview.category.none')
    expect(codes[10]).toContain('RM4,076.12')
  })
})

describe('a reviewer sees their own cases and no money at all', () => {
  beforeEach(() => {
    authRole = { role: 'reviewer' }
    mockApi.getProgrammeOverview.mockResolvedValue(REVIEWER_PAYLOAD)
  })

  it('shows the cases', async () => {
    render(<ProgrammeOverviewPage />)
    await screen.findByTestId('overview-mine')
    expect(screen.getAllByText(/B40-0113/).length > 0).toBe(true)
  })

  /* ⚠ THE ABSENCE IS THE ASSERTION. A hidden money node would still be in the page source. */
  it('has no money node in the DOM, and no programme-wide funnel either', async () => {
    render(<ProgrammeOverviewPage />)
    await screen.findByTestId('overview-mine')
    expect(screen.queryByTestId('overview-money')).toBeNull()
    expect(screen.queryByTestId('overview-money-series')).toBeNull()
    expect(screen.queryByTestId('overview-funnel')).toBeNull()
    expect(screen.queryByTestId('overview-attention')).toBeNull()
  })

  /* ⚠ NO SCORE, NO PERCENTILE, AND THE TURNAROUND IS THE STUDENT'S WAIT (`reviewerDetail.ts`).
   * These are unpaid volunteers; a figure that invites a ranking has to earn its place. */
  it('phrases the pace as how long a student waited', async () => {
    render(<ProgrammeOverviewPage />)
    await screen.findByTestId('overview-mine')
    expect(screen.getAllByText('admin.programmeOverview.mine.turnaround|7.5').length).toBe(1)
  })
})

describe('finance sees the money and none of the people', () => {
  beforeEach(() => {
    authRole = { role: 'finance' }
    mockApi.getProgrammeOverview.mockResolvedValue(FINANCE_PAYLOAD)
  })

  it('shows the money strip and the money charts', async () => {
    render(<ProgrammeOverviewPage />)
    await screen.findByTestId('overview-money')
    expect(screen.queryByTestId('overview-money-series')).not.toBeNull()
  })

  it('shows no funnel and nothing that needs attention', async () => {
    render(<ProgrammeOverviewPage />)
    await screen.findByTestId('overview-money')
    expect(screen.queryByTestId('overview-funnel')).toBeNull()
    expect(screen.queryByTestId('overview-attention')).toBeNull()
    expect(screen.queryByTestId('overview-mine')).toBeNull()
  })
})

describe('a QC sees the queue and nothing else', () => {
  beforeEach(() => {
    authRole = { role: 'qc' }
    mockApi.getProgrammeOverview.mockResolvedValue(QC_PAYLOAD)
  })

  it('shows the waiting queue, and no money or funnel', async () => {
    render(<ProgrammeOverviewPage />)
    await screen.findByTestId('overview-qc')
    expect(screen.getAllByText(/B40-0121/).length > 0).toBe(true)
    expect(screen.queryByTestId('overview-money')).toBeNull()
    expect(screen.queryByTestId('overview-funnel')).toBeNull()
    expect(screen.queryByTestId('overview-mine')).toBeNull()
  })
})

describe('a partner is refused', () => {
  it('shows the refusal and never calls the endpoint', async () => {
    // A referral organisation is an attribution relationship, never a scope — it has no gift.
    authRole = { role: 'partner' }
    render(<ProgrammeOverviewPage />)
    expect(screen.getByText('apiErrors.superAdminRequired')).not.toBeNull()
    await waitFor(() => expect(mockApi.getProgrammeOverview).not.toHaveBeenCalled())
  })
})

describe('the switcher reaches the endpoint', () => {
  it('sends the chosen gift so the server can narrow the figures', async () => {
    render(<ProgrammeOverviewPage />)
    await waitFor(() => expect(mockApi.getProgrammeOverview).toHaveBeenCalled())
    expect(mockApi.getProgrammeOverview.mock.calls[0][0]).toEqual('b40')
  })

  it('sends NO gift when none is chosen, and keeps the heading neutral', async () => {
    // ⚠ Undefined, never an empty string: sending nothing is what says "no narrowing was asked
    // for" rather than "narrow to nothing". And the heading must not name a gift — that is the
    // defect — nor read as an error, because describing every gift is a useful answer.
    chosen = undefined
    mockApi.getProgrammeOverview.mockResolvedValue({ ...ADMIN_PAYLOAD, programme: null })
    render(<ProgrammeOverviewPage />)
    await waitFor(() => expect(mockApi.getProgrammeOverview).toHaveBeenCalled())
    expect(mockApi.getProgrammeOverview.mock.calls[0][0]).toEqual(undefined)
    await waitFor(() => expect(heading()).toBe('admin.programmeOverview.title'))
  })
})
