/**
 * @jest-environment jsdom
 *
 * One scholar's maintenance file (student maintenance Sprint 2). Pinned:
 *  * the header and the Results / Money / Contract cards read the server's payload;
 *  * S9: the Surveys card and the Surveys tab (its own chunk) for super / org_admin / admin only;
 *  * S10: the Growth tab (its own chunk) for the same three only;
 *  * S7b: the mentor card and the Mentoring tab (its own chunk) for super / org_admin / admin only;
 *  * "No contract on file" when there is none (owner ruling 2026-10-29);
 *  * the status is READ-ONLY here (no sub-state control, no Close) — "View application" goes to the
 *    cockpit, which keeps those controls until Sprint 3;
 *  * a file the server will not show is the neutral RecordState, never "does not exist".
 */
import { fireEvent, render, screen } from '@testing-library/react'
import ScholarFilePage from './page'
import * as api from '@/lib/admin-api'
import * as dev from '@/lib/admin-api/development'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
let mockRole: Record<string, unknown> = { role: 'org_admin', owning_org_id: 11 }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: mockRole }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  useParams: () => ({ id: '104' }),
}))
jest.mock('@/components/ToastContext', () => ({ useToast: () => ({ showToast: jest.fn() }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>
jest.mock('@/lib/admin-api/development')
const mockDev = dev as jest.Mocked<typeof dev>

const FILE: api.ScholarFile = {
  id: 104, name: 'NUR AISYAH', gift: { code: 'flag', name: 'Flagship' },
  course: 'Diploma in Accounting', institution: 'Politeknik Ungku Omar', status: 'awarded',
  maintenance_substate: 'on_hold', is_on_hold: true, in_maintenance: true, has_file: true,
  closure_reason: '', awarded_at: '2026-06-01T00:00:00Z', vircle_activated_at: '2026-07-01T00:00:00Z',
  closed_at: null, latest_result: null, standing: 'no_result_yet',
  money: { award_amount: '2000.00', paid_to_date: '1200.00', remaining: '800.00',
    last_payment: { amount: '200.00', at: '2026-10-01T00:00:00Z' } },
  contract: { exists: false, status: null }, mentor: null, last_activity_at: null,
  letters: { count: 0, awaiting: 0, overdue: 0, latest: [] },
}

beforeEach(() => {
  jest.clearAllMocks()
  mockRole = { role: 'org_admin', owning_org_id: 11 }
  mockApi.getScholarFile.mockResolvedValue(FILE)
  mockApi.getScholarActivity.mockResolvedValue({ count: 0, page: 1, page_size: 50, results: [] })
})

it('draws the header and the cards from the payload', async () => {
  render(<ScholarFilePage />)
  expect(await screen.findByRole('heading', { name: 'NUR AISYAH' })).toBeTruthy()
  expect(screen.getByTestId('file-substate').textContent).toBe('admin.maintenance.substate.on_hold')
  expect(screen.getByText('RM2,000.00')).toBeTruthy()
  expect(screen.getByText('RM800.00')).toBeTruthy()
  expect(screen.getByText('admin.scholars.file.noResult')).toBeTruthy()
  expect(screen.getByText('admin.scholars.contract.none')).toBeTruthy()
  expect(screen.getByTestId('card-surveys').textContent).toContain('admin.scholars.surveys.card')
  expect(screen.getByTestId('card-mentor').textContent).toContain('admin.scholars.mentoring.none.title')
  // S6b: Letters is no longer a "later" card — it reads the file's own letters summary.
  expect(screen.queryByText('admin.scholars.later.letters')).toBeNull()
  expect(screen.getByTestId('card-letters').textContent).toContain('admin.scholars.letters.empty')
  const view = screen.getByRole('link', { name: 'admin.scholars.file.viewApplication' })
  expect(view.getAttribute('href')).toBe('/admin/scholarship/104')
})

it('names when her next result is due (S4b), and nothing when no term is open', async () => {
  mockApi.getScholarFile.mockResolvedValue({ ...FILE, next_due: '2026-12-15' })
  const { unmount } = render(<ScholarFilePage />)
  expect((await screen.findByTestId('file-next-due')).textContent).toContain('admin.scholars.file.nextDue')
  unmount()
  mockApi.getScholarFile.mockResolvedValue({ ...FILE, next_due: null })
  render(<ScholarFilePage />)
  await screen.findByRole('heading', { name: 'NUR AISYAH' })
  expect(screen.queryByTestId('file-next-due')).toBeNull()
})

it('keeps the sub-state and Close controls in the cockpit (read-only here)', async () => {
  render(<ScholarFilePage />)
  await screen.findByRole('heading', { name: 'NUR AISYAH' })
  expect(screen.queryByRole('combobox')).toBeNull()
  expect(screen.queryByText(/admin\.closure\.close/)).toBeNull()
})

it('shows the contract status when there is one, and switches tabs', async () => {
  mockApi.getScholarFile.mockResolvedValue({ ...FILE, contract: { exists: true, status: 'executed' } })
  render(<ScholarFilePage />)
  await screen.findByText('admin.scholars.contract.executed')
  fireEvent.click(screen.getByRole('tab', { name: 'admin.scholars.tab.activity' }))
  expect(await screen.findByTestId('activity-empty')).toBeTruthy()
  expect(screen.queryByTestId('card-money')).toBeNull()
})

it('the money links open on THIS gift, and only for a viewer who may open them', async () => {
  render(<ScholarFilePage />)
  const pay = await screen.findByRole('link', { name: 'admin.scholars.money.openPayments' })
  expect(pay.getAttribute('href')).toBe('/admin/payments?programme=flag')
  expect(screen.getByRole('link', { name: 'admin.scholars.money.openSpending' })
    .getAttribute('href')).toBe('/admin/spending?programme=flag')
})

it('the Money and Contract tabs read their own endpoints (S5a)', async () => {
  mockApi.getScholarMoney.mockResolvedValue({ award_amount: '2000.00', paid_to_date: '1200.00', remaining: '800.00', releases: [] })
  mockApi.getScholarContract.mockResolvedValue({ exists: false })
  render(<ScholarFilePage />)
  await screen.findByRole('heading', { name: 'NUR AISYAH' })
  fireEvent.click(screen.getByRole('tab', { name: 'admin.scholars.tab.money' }))
  expect((await screen.findByTestId('money-remaining')).textContent).toBe('RM800.00')
  expect(mockApi.getScholarMoney).toHaveBeenCalledWith(104, { token: 'tok' })
  fireEvent.click(screen.getByRole('tab', { name: 'admin.scholars.tab.contract' }))
  expect(await screen.findByTestId('contract-none')).toBeTruthy()
  expect(mockApi.getScholarContract).toHaveBeenCalledWith(104, { token: 'tok' })
})

it('a reviewer gets no money links (Payments and Spending are not theirs)', async () => {
  mockRole = { role: 'reviewer', owning_org_id: 11 }
  render(<ScholarFilePage />)
  await screen.findByRole('heading', { name: 'NUR AISYAH' })
  expect(screen.queryByRole('link', { name: 'admin.scholars.money.openPayments' })).toBeNull()
  expect(screen.queryByRole('link', { name: 'admin.scholars.money.openSpending' })).toBeNull()
})

it('a closed file has no composer (closed is read-only)', async () => {
  mockApi.getScholarFile.mockResolvedValue({ ...FILE, status: 'closed', in_maintenance: false })
  render(<ScholarFilePage />)
  expect(await screen.findByTestId('activity-read-only')).toBeTruthy()
  expect(screen.queryByPlaceholderText('admin.scholars.activity.placeholder')).toBeNull()
})

it('a file the server will not show is the neutral not-found', async () => {
  mockApi.getScholarFile.mockRejectedValue(Object.assign(new Error('Not found'), { status: 404 }))
  render(<ScholarFilePage />)
  expect(await screen.findByTestId('record-not-found')).toBeTruthy()
})

it('S6b review 1: an API that still sends letters: [] (web deployed first) reads as no letters', async () => {
  const before = { ...FILE, letters: [] } as unknown as api.ScholarFile
  mockApi.getScholarFile.mockResolvedValue(before)
  const { unmount } = render(<ScholarFilePage />)
  expect((await screen.findByTestId('card-letters')).textContent).toContain('admin.scholars.letters.empty')
  unmount()
  mockApi.getScholarFile.mockResolvedValue({ ...FILE, letters: undefined } as unknown as api.ScholarFile)
  render(<ScholarFilePage />)
  expect((await screen.findByTestId('card-letters')).textContent).toContain('admin.scholars.letters.empty')
})

it('S7b: the mentor card, the Asked-for-help chip and the lazy Mentoring tab', async () => {
  mockApi.getScholarFile.mockResolvedValue({ ...FILE, mentor: { name: 'Kavitha Raman', since: '2026-09-02T00:00:00Z',
    meetings: 3 }, asked_for_help: { university: true, scholarship: false, flagged: false } })
  mockApi.getScholarMentoring.mockResolvedValue({ current: null, history: [], meetings: [],
    asked_for_help: { university: true, scholarship: false, flagged: false }, assignable: [], can_act: true,
    file_closed: false, email_switch_on: true })
  render(<ScholarFilePage />)
  expect((await screen.findByTestId('card-mentor')).textContent).toContain('Kavitha Raman')
  expect(screen.getByTestId('file-asked-for-help').textContent).toContain('admin.scholars.mentoring.help.chip')
  fireEvent.click(screen.getByRole('tab', { name: 'admin.scholars.tab.mentoring' }))
  expect(await screen.findByTestId('scholar-mentoring')).toBeTruthy()
  expect(mockApi.getScholarMentoring).toHaveBeenCalledWith(104, { token: 'tok' })
})

it('S7b: a reviewer or QC sees no Mentoring tab and no mentor card', async () => {
  for (const r of ['reviewer', 'qc']) {
    mockRole = { role: r, owning_org_id: 11 }
    const { unmount } = render(<ScholarFilePage />)
    await screen.findByRole('heading', { name: 'NUR AISYAH' })
    expect(screen.queryByRole('tab', { name: 'admin.scholars.tab.mentoring' })).toBeNull()
    expect(screen.queryByTestId('card-mentor')).toBeNull()
    unmount()
  }
  expect(mockApi.getScholarMentoring).not.toHaveBeenCalled()
})

it('S9: the Surveys tab reads the answers of this scholar, for super / org_admin / admin only', async () => {
  mockApi.getScholarSurveys.mockResolvedValue({ waiting: [], answered: [{ id: 7, title: 'Check-in', status: 'open',
    submitted_at: '2026-11-02T00:00:00Z', updated_at: '2026-11-02T00:00:00Z',
    answers: [{ question_id: 1, text: 'In a hostel?', kind: 'yes_no', value: true }] }] })
  render(<ScholarFilePage />)
  await screen.findByRole('heading', { name: 'NUR AISYAH' })
  fireEvent.click(screen.getByRole('tab', { name: 'admin.scholars.tab.surveys' }))
  expect((await screen.findByTestId('scholar-survey-7')).textContent).toContain('admin.surveys.yes')
  expect(mockApi.getScholarSurveys).toHaveBeenCalledWith(104, { token: 'tok' })
})

it('S9: a reviewer or QC sees no Surveys tab and no Surveys card', async () => {
  for (const r of ['reviewer', 'qc']) {
    mockRole = { role: r, owning_org_id: 11 }
    const { unmount } = render(<ScholarFilePage />)
    await screen.findByRole('heading', { name: 'NUR AISYAH' })
    expect(screen.queryByRole('tab', { name: 'admin.scholars.tab.surveys' })).toBeNull()
    expect(screen.queryByTestId('card-surveys')).toBeNull()
    unmount()
  }
  expect(mockApi.getScholarSurveys).not.toHaveBeenCalled()
})

it('S10: the Growth tab reads the modules of this scholar, for super / org_admin / admin only', async () => {
  mockDev.getScholarGrowth.mockResolvedValue({ modules: [{ id: 3, title: 'Managing your money', status: 'published',
    due_on: '2026-11-30', task_kind: 'reflection', lessons: 3, read: 1, done: false, late: true, task_sent_at: null,
    task_text: '', task_file: null, reviewed_at: null, review_comment: '' }] })
  render(<ScholarFilePage />)
  await screen.findByRole('heading', { name: 'NUR AISYAH' })
  fireEvent.click(screen.getByRole('tab', { name: 'admin.scholars.tab.growth' }))
  expect((await screen.findByTestId('growth-row-3')).textContent).toContain('Managing your money')
  expect(screen.getByTestId('growth-late-3')).toBeTruthy()
  expect(mockDev.getScholarGrowth).toHaveBeenCalledWith(104, { token: 'tok' })
})

it('S10: a reviewer or QC sees no Growth tab', async () => {
  for (const r of ['reviewer', 'qc']) {
    mockRole = { role: r, owning_org_id: 11 }
    const { unmount } = render(<ScholarFilePage />)
    await screen.findByRole('heading', { name: 'NUR AISYAH' })
    expect(screen.queryByRole('tab', { name: 'admin.scholars.tab.growth' })).toBeNull()
    unmount()
  }
  expect(mockDev.getScholarGrowth).not.toHaveBeenCalled()
})
