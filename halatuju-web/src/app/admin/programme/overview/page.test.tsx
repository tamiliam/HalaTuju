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
import { render, screen, waitFor } from '@testing-library/react'

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
  // not place it", and it is at zero here on purpose: a slice at zero must still be listed.
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
    { week: '2026-05-04', students: 44, spent: '853.60', average: '19.40',
      purchases: 106, purchases_per_student: '2.4' },
  ],
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
  it('lists the not-yet-sorted slice even at zero', async () => {
    render(<ProgrammeOverviewPage />)
    const legend = await screen.findByTestId('chart-by-category-figures')
    expect(legend.textContent).toContain('admin.programmeOverview.category.none')
    expect(legend.textContent).toContain('RM0.00')
    // All eleven, every time — an absent slice cannot be told from a slice nobody drew.
    expect(legend.querySelectorAll('li').length).toBe(11)
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
