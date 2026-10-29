/**
 * @jest-environment jsdom
 *
 * The officer's Scholars list (student maintenance Sprint 2). Pinned from the harm:
 *  * the list asks the SERVER for each filter, search, sort and page — a client-side filter over a
 *    page of 25 would quietly miss the rest of the list;
 *  * the filters for what is NOT built yet (Results overdue, Wants a mentor) are shown DISABLED,
 *    never faked and never hidden (PanelTabs' rule); Underperforming is live since S4a and asks the
 *    SERVER (`standing=below_minimum`) — the browser never compares a CGPA;
 *  * the row's standing is the server's word (`standing.py`), drawn as given;
 *  * finance cannot open the page (the server refuses too) — names beside case data.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarsPage from './page'
import * as api from '@/lib/admin-api'

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
  standing: 'underperforming', mentor: null, last_activity_at: '2026-10-27T00:00:00Z',
}
const LIST: api.ScholarList = {
  summary: { in_programme: 65, on_hold: 1, probation: 5, ready_to_close: 0, closed: 2, below_minimum: 3 },
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

it('shows the not-yet-built filters disabled', async () => {
  render(<ScholarsPage />)
  await screen.findAllByText('NUR AISYAH')
  for (const key of ['overdue', 'wantsMentor']) {
    const tab = screen.getByText(`admin.scholars.filter.${key}`).closest('button')!
    expect([tab.getAttribute('role'), tab.hasAttribute('disabled')]).toEqual(['tab', true])
  }
})

it('Underperforming is live: it carries its count and asks the server, never the browser', async () => {
  render(<ScholarsPage />)
  await screen.findAllByText('NUR AISYAH')
  const tab = screen.getByRole('tab', { name: /admin\.scholars\.filter\.underperforming/ })
  expect(tab.hasAttribute('disabled')).toBe(false)
  expect(tab.textContent).toContain('3')
  fireEvent.click(tab)
  await waitFor(() => expect(mockApi.getScholars).toHaveBeenLastCalledWith(
    expect.objectContaining({ standing: 'below_minimum', closed: false, substate: '' }), { token: 'tok' }))
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
