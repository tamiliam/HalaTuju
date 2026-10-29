/**
 * @jest-environment jsdom
 *
 * The scholar file's Results tab (student maintenance S4a). Pinned from the harm:
 *  * every result shows its REVIEW state — only an accepted one counts, so "awaiting review" must
 *    be visible, never read as accepted;
 *  * the slip opens in the shared DocViewer (a result with no slip says so instead of a dead button);
 *  * Accept sends `accepted`; Query cannot be sent without a note (she must be told what to fix);
 *  * no slip, no Accept (owner ruling 2026-10-29) — the officer queries her to upload it;
 *  * with no review rights (`canReview` false) there are no buttons at all — the server refuses too;
 *  * a refusal code renders its own sentence, anything else the generic one.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarResults from './ScholarResults'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
const mockToast = jest.fn()
jest.mock('@/components/ToastContext', () => ({ useToast: () => ({ showToast: mockToast }) }))
const mockViewer = jest.fn()
jest.mock('@/components/DocViewer', () => ({
  __esModule: true,
  default: (props: { doc: unknown }) => { mockViewer(props.doc); return null },
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const PENDING: api.ScholarResultRow = {
  id: 1, semester: 'Sem 3', cgpa: '2.40', graduated: false, note: 'Retaking one paper.',
  created_at: '2026-10-20T00:00:00Z', review_status: 'pending', review_note: '', reviewed_by: '',
  reviewed_at: null, slip: { url: 'https://signed.example/slip.pdf', filename: 'slip.pdf', content_type: 'application/pdf' },
}
const ACCEPTED: api.ScholarResultRow = {
  ...PENDING, id: 2, semester: 'Sem 2', cgpa: '3.10', note: '', review_status: 'accepted',
  reviewed_by: 'officer@example.test', reviewed_at: '2026-07-01T00:00:00Z', slip: null,
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getScholarResults.mockResolvedValue({ results: [PENDING, ACCEPTED] })
  mockApi.reviewScholarResult.mockResolvedValue({ ...PENDING, review_status: 'accepted' })
})

it('shows each result with its review state, her note and the slip', async () => {
  render(<ScholarResults id={7} token="tok" canReview onChanged={jest.fn()} />)
  const rows = await screen.findAllByTestId('admin-result-row')
  expect(rows).toHaveLength(2)
  expect(rows[0].textContent).toContain('admin.scholars.results.status.pending')
  expect(rows[0].textContent).toContain('Retaking one paper.')
  expect(rows[1].textContent).toContain('admin.scholars.results.status.accepted')
  expect(rows[1].textContent).toContain('admin.scholars.results.noSlip')
  fireEvent.click(screen.getByText('admin.scholars.results.viewSlip'))
  expect(mockViewer).toHaveBeenLastCalledWith(expect.objectContaining({
    url: 'https://signed.example/slip.pdf', kind: 'pdf' }))
})

it('Accept sends accepted, then re-reads the tab and the file', async () => {
  const onChanged = jest.fn()
  render(<ScholarResults id={7} token="tok" canReview onChanged={onChanged} />)
  await screen.findAllByTestId('admin-result-row')
  // The accepted row offers no second Accept.
  expect(screen.getAllByText('admin.scholars.results.accept')).toHaveLength(1)
  fireEvent.click(screen.getByText('admin.scholars.results.accept'))
  await waitFor(() => expect(mockApi.reviewScholarResult).toHaveBeenCalledWith(
    7, 1, { decision: 'accepted', note: '' }, { token: 'tok' }))
  await waitFor(() => expect(onChanged).toHaveBeenCalled())
  expect(mockApi.getScholarResults).toHaveBeenCalledTimes(2)
})

it('Query needs a note before it can be sent, and sends it', async () => {
  render(<ScholarResults id={7} token="tok" canReview onChanged={jest.fn()} />)
  await screen.findAllByTestId('admin-result-row')
  fireEvent.click(screen.getAllByText('admin.scholars.results.query')[0])
  const send = screen.getByText('admin.scholars.results.sendQuery').closest('button')!
  expect(send.disabled).toBe(true)
  fireEvent.change(screen.getByPlaceholderText('admin.scholars.results.queryPlaceholder'),
    { target: { value: 'Please send the stamped slip.' } })
  expect(send.disabled).toBe(false)
  fireEvent.click(send)
  await waitFor(() => expect(mockApi.reviewScholarResult).toHaveBeenCalledWith(
    7, 1, { decision: 'queried', note: 'Please send the stamped slip.' }, { token: 'tok' }))
})

it('renders a refusal code as its own sentence', async () => {
  mockApi.reviewScholarResult.mockRejectedValue(Object.assign(new Error('x'), { code: 'file_closed' }))
  render(<ScholarResults id={7} token="tok" canReview onChanged={jest.fn()} />)
  await screen.findAllByTestId('admin-result-row')
  fireEvent.click(screen.getByText('admin.scholars.results.accept'))
  await waitFor(() => expect(mockToast).toHaveBeenCalledWith('admin.scholars.results.error.file_closed', 'error'))
})

it('a result with no slip offers Query, never Accept (owner ruling 2026-10-29)', async () => {
  mockApi.getScholarResults.mockResolvedValue({ results: [{ ...PENDING, slip: null }] })
  render(<ScholarResults id={7} token="tok" canReview onChanged={jest.fn()} />)
  const row = await screen.findByTestId('admin-result-row')
  expect(row.textContent).toContain('admin.scholars.results.noSlip')
  expect(screen.queryByText('admin.scholars.results.accept')).toBeNull()
  expect(screen.getByText('admin.scholars.results.query')).toBeTruthy()
})

it('the server refusing slip_required reads as its own sentence', async () => {
  mockApi.reviewScholarResult.mockRejectedValue(Object.assign(new Error('x'), { code: 'slip_required' }))
  render(<ScholarResults id={7} token="tok" canReview onChanged={jest.fn()} />)
  await screen.findAllByTestId('admin-result-row')
  fireEvent.click(screen.getByText('admin.scholars.results.accept'))
  await waitFor(() => expect(mockToast).toHaveBeenCalledWith('admin.scholars.results.error.slip_required', 'error'))
})

it('without review rights there are no buttons', async () => {
  render(<ScholarResults id={7} token="tok" canReview={false} onChanged={jest.fn()} />)
  await screen.findAllByTestId('admin-result-row')
  expect(screen.queryByText('admin.scholars.results.accept')).toBeNull()
  expect(screen.queryByText('admin.scholars.results.query')).toBeNull()
  expect(screen.getByText('admin.scholars.results.viewSlip')).toBeTruthy()
})
