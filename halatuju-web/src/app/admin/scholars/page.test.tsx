/**
 * @jest-environment jsdom
 *
 * The officer's Scholars list (student maintenance Sprint 2). Pinned from the harm:
 *  * the list asks the SERVER for each filter, search, sort and page — a client-side filter over a
 *    page of 25 would quietly miss the rest of the list;
 *  * Underperforming (S4a) and Results overdue (S4b) are live and ask the SERVER
 *    (`standing=below_minimum` / `results_overdue`) — the browser never judges a date or a CGPA;
 *  * S7b: the Mentor column, "No mentor" / "Asked for help" (with the server's counts, asking the
 *    server `mentoring=`) and the row's "Asked for help" chip — for super / org_admin / admin only;
 *  * the row's standing is the server's word (`standing.py`), drawn as given;
 *  * finance cannot open the page (the server refuses too) — names beside case data.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarsPage from './page'
import * as api from '@/lib/admin-api'
import { ProgrammeScopeProvider } from '@/lib/programmeScope'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
let mockRole: Record<string, unknown> = { role: 'org_admin', owning_org_id: 11 }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: mockRole }),
}))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const ROW: api.ScholarRow = {
  id: 104, name: 'NUR AISYAH', gift: { code: 'flag', name: 'Flagship' },
  course: 'Diploma in Accounting', institution: 'Politeknik Ungku Omar', status: 'awarded',
  maintenance_substate: 'probation', is_on_hold: false,
  latest_result: { cgpa: '2.85', semester: 'Sem 2', at: '2026-07-12T00:00:00Z' },
  standing: 'underperforming', next_due: '2026-12-15', mentor: 'Kavitha Raman', asked_for_help: true,
  last_activity_at: '2026-10-27T00:00:00Z',
}
const LIST: api.ScholarList = {
  summary: { in_programme: 65, on_hold: 1, probation: 5, ready_to_close: 0, closed: 2, below_minimum: 3, results_overdue: 4,
    no_mentor: 58, asked_for_help: 22 },
  count: 1, page: 1, page_size: 25, results: [ROW],
}

beforeEach(() => {
  jest.clearAllMocks()
  mockRole = { role: 'org_admin', owning_org_id: 11 }
  mockApi.getScholars.mockResolvedValue(LIST)
})

it('draws the tiles, the row and its link to the file', async () => {
  render(<ScholarsPage />)
  // ⚠ Every row is drawn twice — a phone card and a desktop row — because jsdom applies no
  // breakpoints; `getAll*` is the honest query.
  const links = await screen.findAllByRole('link', { name: /NUR AISYAH/ })
  expect(links.map((l) => l.getAttribute('href'))).toEqual(['/admin/scholars/104', '/admin/scholars/104'])
  expect(screen.getAllByText('65').length).toBeGreaterThan(0)      // a tile and the All tab's count
  expect(screen.getByText('Diploma in Accounting')).toBeTruthy()
  expect(screen.getByText('2.85')).toBeTruthy()
  expect(screen.getByText('admin.maintenance.substate.probation', { selector: 'td span' })).toBeTruthy()
  expect(screen.getAllByText('admin.scholars.standing.underperforming')).toHaveLength(2)
})

it('S7b: the Mentor column, the two Mentoring pills with their counts, and the Asked-for-help chip', async () => {
  render(<ScholarsPage />)
  await screen.findAllByText(/NUR AISYAH/)
  expect(screen.getByTestId('mentor-cell').textContent).toBe('Kavitha Raman')
  expect(screen.getAllByTestId('asked-for-help')).toHaveLength(2)          // phone card + desktop row
  expect(screen.getByText('admin.scholars.askedForHelpNote')).toBeTruthy()
  const none = screen.getByRole('tab', { name: /admin\.scholars\.filter\.noMentor/ })
  expect(none.textContent).toContain('58')
  fireEvent.click(none)
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ mentoring: 'no_mentor', standing: '' }), { token: 'tok' }))
  const asked = screen.getByRole('tab', { name: /admin\.scholars\.filter\.askedForHelp/ })
  expect(asked.textContent).toContain('22')
  fireEvent.click(asked)
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ mentoring: 'asked_for_help' }), { token: 'tok' }))
})

it('S7b: a role that does not see mentors gets no Mentor column and no Mentoring pills', async () => {
  mockRole = { role: 'qc', owning_org_id: 11, permissions: ['qc', 'scholars'] }   // S1: Scholars asks its own key
  const { mentor: _m, asked_for_help: _a, ...bare } = ROW
  mockApi.getScholars.mockResolvedValue({ ...LIST, results: [bare] })
  render(<ScholarsPage />)
  await screen.findAllByText('NUR AISYAH')
  expect(screen.queryByTestId('mentor-cell')).toBeNull()
  expect(screen.queryByText('admin.scholars.col.mentor')).toBeNull()
  expect(screen.queryByRole('tab', { name: /noMentor/ })).toBeNull()
  expect(screen.queryByRole('tab', { name: /askedForHelp/ })).toBeNull()
  expect(screen.queryByTestId('asked-for-help')).toBeNull()
})

it('Underperforming is live: it carries its count and asks the server, never the browser', async () => {
  render(<ScholarsPage />)
  await screen.findAllByText(/NUR AISYAH/)
  const tab = screen.getByRole('tab', { name: /admin\.scholars\.filter\.underperforming/ })
  expect(tab.hasAttribute('disabled')).toBe(false)
  expect(tab.textContent).toContain('3')
  fireEvent.click(tab)
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ standing: 'below_minimum', closed: false, substate: '' }), { token: 'tok' }))
})

it('Results overdue is live: its count, its tile, the next-due column, and it asks the server', async () => {
  render(<ScholarsPage />)
  await screen.findAllByText('NUR AISYAH')
  expect(screen.getByText('admin.scholars.tile.resultsOverdue')).toBeTruthy()
  expect(screen.getByTestId('next-due').textContent).not.toBe('—')
  const tab = screen.getByRole('tab', { name: /admin\.scholars\.filter\.overdue/ })
  expect(tab.hasAttribute('disabled')).toBe(false)
  expect(tab.textContent).toContain('4')
  fireEvent.click(tab)
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ standing: 'results_overdue', closed: false, substate: '' }), { token: 'tok' }))
  fireEvent.click(screen.getByRole('button', { name: /admin\.scholars\.col\.nextDue/ }))
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ sort: 'due' }), { token: 'tok' }))
})

it('asks the server for the filter, the search and the sort', async () => {
  render(<ScholarsPage />)
  await screen.findAllByText('NUR AISYAH')
  fireEvent.click(screen.getByRole('tab', { name: /admin\.scholars\.filter\.closed/ }))
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ closed: true, substate: '', page: 1 }), { token: 'tok' }))
  fireEvent.click(screen.getByRole('tab', { name: /admin\.maintenance\.substate\.on_hold/ }))
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ closed: false, substate: 'on_hold' }), { token: 'tok' }))
  fireEvent.click(screen.getByRole('button', { name: /admin\.scholars\.col\.cgpa/ }))
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ sort: '-cgpa' }), { token: 'tok' }))
  fireEvent.change(screen.getByPlaceholderText('admin.scholars.searchPlaceholder'),
    { target: { value: 'aisyah' } })
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ search: 'aisyah' }), { token: 'tok' }))
})

it('says so when nothing matches', async () => {
  mockApi.getScholars.mockResolvedValue({ ...LIST, count: 0, results: [] })
  render(<ScholarsPage />)
  expect(await screen.findByTestId('scholars-empty')).toBeTruthy()
})

it('finance cannot open the page', () => {
  mockRole = { role: 'finance', owning_org_id: 11 }
  render(<ScholarsPage />)
  expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
  expect(mockApi.getScholars).not.toHaveBeenCalled()
})

it('S7c: "Mentor concerned" — the row chip, and the pill with the server\'s count asking `mentoring=mentor_concerned`', async () => {
  mockApi.getScholars.mockResolvedValue({
    ...LIST, summary: { ...LIST.summary, mentor_concerned: 1 }, results: [{ ...ROW, mentor_concerned: true }],
  })
  render(<ScholarsPage />)
  await screen.findAllByText(/NUR AISYAH/)
  expect(screen.getAllByTestId('mentor-concerned')).toHaveLength(2)          // phone card + desktop row
  const pill = screen.getByRole('tab', { name: /admin\.scholars\.filter\.mentorConcerned/ })
  expect(pill.textContent).toContain('1')
  fireEvent.click(pill)
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ mentoring: 'mentor_concerned' }), { token: 'tok' }))
})

it('S7c: a role that does not see mentors gets no Mentor concerned pill', async () => {
  mockRole = { role: 'qc', owning_org_id: 11, permissions: ['see_all', 'scholars'] }   // S1: Scholars asks its own key
  render(<ScholarsPage />)
  await screen.findAllByText(/NUR AISYAH/)
  expect(screen.queryByRole('tab', { name: /admin\.scholars\.filter\.mentorConcerned/ })).toBeNull()
})

it('sprint S1 (S1-h): a mentor login and staff who mentor open the list (the server lists their students)', async () => {
  for (const who of [{ role: 'mentor', permissions: [] }, { role: 'reviewer', permissions: ['review'], mentoring: true }]) {
    mockRole = { ...who, owning_org_id: 11 }
    const { unmount } = render(<ScholarsPage />)
    expect(await screen.findAllByRole('link', { name: /NUR AISYAH/ })).toHaveLength(2)
    expect(screen.queryByText('apiErrors.superAdminRequired')).toBeNull()
    unmount()
  }
  mockApi.getScholars.mockClear()
  mockRole = { role: 'reviewer', owning_org_id: 11, permissions: ['review'], mentoring: false }
  render(<ScholarsPage />)
  expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
  expect(mockApi.getScholars).not.toHaveBeenCalled()
})

it('sprint S1 (S1-h): anyone viewing as a mentor never waits on the gift gate; a `scholars` reader does', async () => {
  const asMentor = [
    { role: 'mentor', permissions: [] },                                    // a mentor login
    { role: 'reviewer', permissions: ['review'], mentoring: true },          // staff who mentor
    { role: 'admin', permissions: ['see_all'], mentoring: true },            // an admin without Scholars
  ]
  const readers = [
    { role: 'org_admin', permissions: [] },
    { role: 'admin', permissions: ['see_all', 'scholars'], mentoring: true },  // the key wins over mentoring
  ]
  for (const who of [...asMentor, ...readers]) {
    mockRole = { ...who, owning_org_id: 11 }
    const { unmount } = render(
      <ProgrammeScopeProvider choices={[]} settled={false}><ScholarsPage /></ProgrammeScopeProvider>)
    if (asMentor.includes(who)) expect(await screen.findAllByRole('link', { name: /NUR AISYAH/ })).toHaveLength(2)
    else expect(screen.getByTestId('gift-wait')).toBeTruthy()      // staff still wait for the scopes
    unmount()
  }
})
