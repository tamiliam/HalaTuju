/**
 * @jest-environment jsdom
 *
 * The scholar file's activity log (student maintenance Sprint 2). Pinned:
 *  * a system entry reads as a translated sentence built from its event code — never raw meta;
 *  * an officer's entry shows its kind, author and the staff-only badge;
 *  * the composer sends the chosen kind, the text and the staff-only flag (the site Toggle — a
 *    `role="switch"`, never a checkbox), then re-reads the log.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarActivity from './ScholarActivity'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
const mockToast = jest.fn()
jest.mock('@/components/ToastContext', () => ({ useToast: () => ({ showToast: mockToast }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const SYSTEM: api.ScholarActivity = {
  id: 1, kind: 'system', event: 'substate_changed', body: '',
  meta: { old: 'on_track', new: 'on_hold', excluded_from_runs: [] },
  actor_email: 'officer@example.test', internal: true, created_at: '2026-10-02T00:00:00Z',
}
const NOTE: api.ScholarActivity = {
  id: 2, kind: 'call', event: '', body: 'Talked through a study plan.', meta: {},
  actor_email: 'admin@example.test', internal: true, created_at: '2026-10-27T00:00:00Z',
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getScholarActivity.mockResolvedValue({ count: 2, page: 1, page_size: 50, results: [NOTE, SYSTEM] })
  mockApi.addScholarActivity.mockResolvedValue(NOTE)
})

it('reads a system row as a sentence and an officer row as its own words', async () => {
  render(<ScholarActivity id={7} token="tok" />)
  expect(await screen.findByText('Talked through a study plan.')).toBeTruthy()
  expect(screen.getByText(
    'admin.scholars.event.substate_changed|{"from":"admin.maintenance.substate.on_track","to":"admin.maintenance.substate.on_hold"}',
  )).toBeTruthy()
  expect(screen.queryByText(/excluded_from_runs/)).toBeNull()
  expect(screen.getAllByTestId('activity-row')).toHaveLength(2)
})

it('words the three letter events with the subject of each letter (S6b)', async () => {
  const letterRow = (id: number, event: string): api.ScholarActivity => ({ ...SYSTEM, id, event, meta: { subject: 'Warning (clause 5)' } })
  mockApi.getScholarActivity.mockResolvedValue({ count: 3, page: 1, page_size: 50, results: [
    letterRow(11, 'letter_issued'), letterRow(12, 'letter_withdrawn'), letterRow(13, 'letter_acknowledged')] })
  render(<ScholarActivity id={7} token="tok" />)
  for (const event of ['letter_issued', 'letter_withdrawn', 'letter_acknowledged']) {
    expect(await screen.findByText(`admin.scholars.event.${event}|{"subject":"Warning (clause 5)"}`)).toBeTruthy()
  }
})

it('sends the kind, the text and the staff-only flag, then re-reads', async () => {
  render(<ScholarActivity id={7} token="tok" />)
  await screen.findByText('Talked through a study plan.')
  fireEvent.click(screen.getByRole('button', { name: 'admin.scholars.activity.kind.meeting' }))
  fireEvent.change(screen.getByPlaceholderText('admin.scholars.activity.placeholder'),
    { target: { value: 'Met at the campus.' } })
  const toggle = screen.getByRole('switch', { name: 'admin.scholars.activity.staffOnly' })
  fireEvent.click(toggle)
  fireEvent.click(screen.getByRole('button', { name: 'admin.scholars.activity.save' }))
  await waitFor(() => expect(mockApi.addScholarActivity).toHaveBeenCalledWith(
    7, { kind: 'meeting', body: 'Met at the campus.', internal: true }, { token: 'tok' }))
  await waitFor(() => expect(mockApi.getScholarActivity).toHaveBeenCalledTimes(2))
  expect(mockToast).toHaveBeenCalledWith('admin.scholars.activity.saved', 'success')
})

it('cannot save an empty entry', async () => {
  render(<ScholarActivity id={7} token="tok" />)
  await screen.findByText('Talked through a study plan.')
  const save = screen.getByRole('button', { name: 'admin.scholars.activity.save' }) as HTMLButtonElement
  expect(save.disabled).toBe(true)
})

it('an overdue line names the due date as a date, never the raw ISO string (S4b review L10)', async () => {
  const overdue: api.ScholarActivity = {
    id: 3, kind: 'system', event: 'results_overdue', body: '', meta: { due_on: '2026-12-15', term_index: 2 },
    actor_email: '', internal: true, created_at: '2027-01-20T00:00:00Z',
  }
  mockApi.getScholarActivity.mockResolvedValue({ count: 1, page: 1, page_size: 50, results: [overdue] })
  render(<ScholarActivity id={7} token="tok" />)
  const row = await screen.findByTestId('activity-row')
  expect(row.textContent).toContain('admin.scholars.event.results_overdue')
  expect(row.textContent).not.toContain('2026-12-15')
})
