/**
 * @jest-environment jsdom
 *
 * The scholar file's maintenance controls (student maintenance S3 — moved from the cockpit). Pinned:
 *  * the server's `controls` offer decides what is drawn — hold buttons only for payments rights
 *    (with the reason said otherwise), Close only with reasons;
 *  * an awarded case still holding the sponsor's offer SAYS why it cannot close (S1 review L4);
 *  * a refusal reads as a sentence, never a bare code (TD-419's `hold_needs_payments`);
 *  * Close asks twice, then calls the close door and re-reads.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarControls from './ScholarControls'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const BASE = {
  id: 9, name: 'X', gift: null, course: '', institution: '', status: 'active',
  maintenance_substate: 'on_track', is_on_hold: false, in_maintenance: true, has_file: true,
  closure_reason: '', awarded_at: null, vircle_activated_at: null, closed_at: null,
  latest_result: null, standing: 'no_result_yet',
  money: { award_amount: null, paid_to_date: '0.00', remaining: '0.00', last_payment: null },
  contract: { exists: false, status: null }, mentor: null, letters: [], last_activity_at: null,
} as unknown as api.ScholarFile
const file = (controls: Partial<api.ScholarControls>, over: Partial<api.ScholarFile> = {}) => ({
  ...BASE, ...over,
  controls: { can_set_substate: true, can_hold: true, close_reasons: [], close_refusal: '', ...controls },
}) as api.ScholarFile

beforeEach(() => jest.clearAllMocks())

it('a payments-rights holder may hold', () => {
  render(<ScholarControls file={file({})} token="tok" onChanged={jest.fn()} />)
  expect(screen.getByRole('button', { name: 'admin.maintenance.action.on_hold' })).toBeTruthy()
  expect(screen.queryByTestId('hold-needs-payments')).toBeNull()
})

it('without payments rights the hold is not offered, and the reason is said', () => {
  render(<ScholarControls file={file({ can_hold: false })} token="tok" onChanged={jest.fn()} />)
  expect(screen.queryByRole('button', { name: 'admin.maintenance.action.on_hold' })).toBeNull()
  expect(screen.getByRole('button', { name: 'admin.maintenance.action.probation' })).toBeTruthy()
  expect(screen.getByTestId('hold-needs-payments')).toBeTruthy()
})

it('a held student cannot be resumed by somebody without payments rights', () => {
  render(<ScholarControls file={file({ can_hold: false }, { maintenance_substate: 'on_hold' })}
    token="tok" onChanged={jest.fn()} />)
  expect(screen.queryByRole('button', { name: /admin\.maintenance\.action\./ })).toBeNull()
})

it('an awarded case still holding the offer says why it cannot close', () => {
  render(<ScholarControls file={file({ close_refusal: 'sponsorship_open' }, { status: 'awarded' })}
    token="tok" onChanged={jest.fn()} />)
  expect(screen.getByTestId('close-refusal').textContent)
    .toBe('admin.scholars.control.refusal.sponsorship_open')
  expect(screen.queryByRole('button', { name: 'admin.scholars.control.closeFile' })).toBeNull()
})

it('a refusal is a sentence, never a bare code', async () => {
  mockApi.setMaintenanceSubstate.mockRejectedValue(Object.assign(new Error('x'), { code: 'hold_needs_payments' }))
  render(<ScholarControls file={file({})} token="tok" onChanged={jest.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'admin.maintenance.action.on_hold' }))
  expect((await screen.findByRole('alert')).textContent).toBe('admin.scholars.control.error.hold_needs_payments')
})

it('a change re-reads the file', async () => {
  mockApi.setMaintenanceSubstate.mockResolvedValue({} as never)
  const onChanged = jest.fn()
  render(<ScholarControls file={file({})} token="tok" onChanged={onChanged} />)
  fireEvent.click(screen.getByRole('button', { name: 'admin.maintenance.action.probation' }))
  await waitFor(() => expect(mockApi.setMaintenanceSubstate).toHaveBeenCalledWith(9, 'probation', { token: 'tok' }))
  await waitFor(() => expect(onChanged).toHaveBeenCalled())
})

it('Close asks twice, then closes with the chosen reason', async () => {
  mockApi.closeApplication.mockResolvedValue({} as never)
  const onChanged = jest.fn()
  render(<ScholarControls file={file({ close_reasons: ['graduated', 'withdrawn'] })} token="tok"
    onChanged={onChanged} />)
  // The funded-close note and the offboarding checklist come BEFORE the confirm (S3 review M2).
  expect(screen.getByText('admin.closure.note')).toBeTruthy()
  expect(screen.getByTestId('close-checklist').textContent).toContain('admin.closure.checklist.finalDisbursement')
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'graduated' } })
  fireEvent.click(screen.getByRole('button', { name: 'admin.scholars.control.closeFile' }))
  expect(screen.getByTestId('close-confirm')).toBeTruthy()
  fireEvent.click(screen.getAllByRole('button', { name: 'admin.scholars.control.closeFile' })[0])
  await waitFor(() => expect(mockApi.closeApplication).toHaveBeenCalledWith(9, 'graduated', { token: 'tok' }))
  await waitFor(() => expect(onChanged).toHaveBeenCalled())
})

it('a closed file draws no controls', () => {
  const { container } = render(<ScholarControls file={file({}, { status: 'closed' })} token="tok"
    onChanged={jest.fn()} />)
  expect(container.innerHTML).toBe('')
})
