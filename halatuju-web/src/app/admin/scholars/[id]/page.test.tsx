/**
 * @jest-environment jsdom
 *
 * One scholar's maintenance file (student maintenance Sprint 2). Pinned:
 *  * the header and the Results / Money / Contract cards read the server's payload;
 *  * the areas not built yet (Mentor, Letters, Surveys) say so — no sample data;
 *  * "No contract on file" when there is none (owner ruling 2026-10-29);
 *  * the status is READ-ONLY here (no sub-state control, no Close) — "View application" goes to the
 *    cockpit, which keeps those controls until Sprint 3;
 *  * a file the server will not show is the neutral RecordState, never "does not exist".
 */
import { fireEvent, render, screen } from '@testing-library/react'
import ScholarFilePage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin', owning_org_id: 11 } }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  useParams: () => ({ id: '104' }),
}))
jest.mock('@/components/ToastContext', () => ({ useToast: () => ({ showToast: jest.fn() }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const FILE: api.ScholarFile = {
  id: 104, name: 'NUR AISYAH', gift: { code: 'flag', name: 'Flagship' },
  course: 'Diploma in Accounting', institution: 'Politeknik Ungku Omar', status: 'awarded',
  maintenance_substate: 'on_hold', is_on_hold: true, in_maintenance: true, has_file: true,
  closure_reason: '', awarded_at: '2026-06-01T00:00:00Z', vircle_activated_at: '2026-07-01T00:00:00Z',
  closed_at: null, latest_result: null, standing: 'no_result_yet',
  money: { award_amount: '2000.00', paid_to_date: '1200.00', remaining: '800.00',
    last_payment: { amount: '200.00', at: '2026-10-01T00:00:00Z' } },
  contract: { exists: false, status: null }, mentor: null, letters: [], last_activity_at: null,
}

beforeEach(() => {
  jest.clearAllMocks()
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
  for (const key of ['mentor', 'letters', 'surveys']) {
    expect(screen.getByText(`admin.scholars.later.${key}`)).toBeTruthy()
  }
  const view = screen.getByRole('link', { name: 'admin.scholars.file.viewApplication' })
  expect(view.getAttribute('href')).toBe('/admin/scholarship/104')
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

it('a file the server will not show is the neutral not-found', async () => {
  mockApi.getScholarFile.mockRejectedValue(Object.assign(new Error('Not found'), { status: 404 }))
  render(<ScholarFilePage />)
  expect(await screen.findByTestId('record-not-found')).toBeTruthy()
})
