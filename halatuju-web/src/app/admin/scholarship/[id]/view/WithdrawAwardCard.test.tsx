/**
 * @jest-environment jsdom
 *
 * A1.13b (TD-198): the award-withdrawal card, MAKER and CHECKER. It draws only from the served
 * `withdrawal_request` and its `your_step` (the server's one predicate): 'request' shows the ask form,
 * 'cancel' the maker's waiting view, 'decide' the checker's approve/refuse view, and null (or a
 * finished request) a read-only outcome. Each action calls its own route with the right body and hands
 * the refreshed case back; each refusal code reads as words. Dummy data only.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import {
  KNOWN_ERRORS, TEXT_MAX, WithdrawAwardCard, hasPaidTranche, paidSoFarCents, rmFromCents, toCents,
} from './WithdrawAwardCard'
import { activityText } from '@/lib/scholarActivity'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const K = 'admin.scholarship.withdrawAward'
const t = ((k: string, p?: Record<string, unknown>) => (p ? `${k}|${JSON.stringify(p)}` : k)) as never
const tranche = (status: string, amount = '500.00') => ({ id: 1, sequence: 1, amount, status })
const PENDING = {
  id: 31, status: 'pending', requested_by_name: 'Dummy Maker', requested_at: '2026-11-08T03:00:00Z',
  expires_at: '2026-11-22T03:00:00Z', explanation: 'Dummy explanation', sponsorship_count: 1,
  amount_freed: '2500.00', tranches_to_withhold: 3, decided_by_name: '', decided_at: null, decision_note: '',
}
const caseOf = (wr: Record<string, unknown> | null, over: Record<string, unknown> = {}) =>
  ({ id: 7, status: 'awarded', award_amount: '3000.00', disbursements: [], withdrawal_request: wr, ...over }) as unknown as api.AdminScholarshipDetail

const draw = (app: api.AdminScholarshipDetail) => {
  const onChanged = jest.fn()
  render(<WithdrawAwardCard app={app} t={t} token="tok" onChanged={onChanged} />)
  return onChanged
}
const ACTION = `${K}.action`
const CONFIRM = `${K}.confirm`
const PLACEHOLDER = `${K}.placeholder`
const APPROVE_CONFIRM = `${K}.approveConfirm`
const NOTE = `${K}.approvePlaceholder`
const refusal = (code: string) => Object.assign(new Error('x'), { code, status: 409 })

beforeEach(() => jest.clearAllMocks())

describe('nothing to show', () => {
  it.each([
    ['no payload (not an awarded or recommended case)', null],
    ['no row and no step', { id: null, status: null, your_step: null }],
  ])('%s', (_label, wr) => {
    draw(caseOf(wr))
    expect(screen.queryByTestId('withdraw-award')).toBeNull()
  })
})

describe('state 1: request (your_step=request)', () => {
  const ask = () => caseOf({ id: null, status: null, your_step: 'request' })

  it('shows the hint and the action; nothing changes until a checker approves', () => {
    draw(ask())
    expect(screen.getByTestId('withdrawal-request')).toBeTruthy()
    expect(screen.getByText(`${K}.hint`)).toBeTruthy()
    expect(screen.getByRole('button', { name: ACTION })).toBeTruthy()
  })

  it('Confirm rests until the explanation has text', () => {
    draw(ask())
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    const confirm = screen.getByRole('button', { name: CONFIRM }) as HTMLButtonElement
    expect(confirm.disabled).toBe(true)
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: '   ' } })
    expect(confirm.disabled).toBe(true)
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: 'Dummy' } })
    expect(confirm.disabled).toBe(false)
  })

  it('sends the trimmed explanation to the request route and hands the case back', async () => {
    const next = caseOf({ ...PENDING, your_step: 'cancel' })
    mockApi.requestAwardWithdrawal.mockResolvedValue(next)
    const onChanged = draw(ask())
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: '  Dummy explanation  ' } })
    fireEvent.click(screen.getByRole('button', { name: CONFIRM }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(next))
    expect(mockApi.requestAwardWithdrawal).toHaveBeenCalledWith(7, 'Dummy explanation', { token: 'tok' })
  })

  it('an explanation over the limit is refused here, never cut, and never sent', () => {
    draw(ask())
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: 'x'.repeat(TEXT_MAX + 1) } })
    fireEvent.click(screen.getByRole('button', { name: CONFIRM }))
    expect(screen.getByRole('alert').textContent).toBe(`${K}.error.explanation_too_long`)
    expect(mockApi.requestAwardWithdrawal).not.toHaveBeenCalled()
  })

  it('Cancel closes the box without calling the API', () => {
    draw(ask())
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    fireEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(screen.queryByPlaceholderText(PLACEHOLDER)).toBeNull()
    expect(mockApi.requestAwardWithdrawal).not.toHaveBeenCalled()
  })

  it.each(['released', 'returned'])('a %s tranche swaps the button for the paid note', (status) => {
    draw(caseOf({ id: null, status: null, your_step: 'request' }, { disbursements: [tranche('scheduled'), tranche(status)] }))
    expect(screen.queryByRole('button', { name: ACTION })).toBeNull()
    expect(screen.getByText(`${K}.paidNote`)).toBeTruthy()
  })

  it('an earlier refused request shows read-only above a fresh ask', () => {
    draw(caseOf({ ...PENDING, status: 'refused', your_step: 'request', decided_by_name: 'Dummy Checker',
      decided_at: '2026-11-09T03:00:00Z', decision_note: 'Dummy refusal' }))
    expect(screen.getByTestId('withdrawal-outcome')).toBeTruthy()
    expect(screen.getByTestId('withdrawal-pill').textContent).toBe(`${K}.pill.refused`)
    expect(screen.getByText('Dummy refusal')).toBeTruthy()
    expect(screen.getByRole('button', { name: ACTION })).toBeTruthy()
  })
})

describe('state 2: the maker waits (your_step=cancel)', () => {
  const mine = () => caseOf({ ...PENDING, your_step: 'cancel' })

  it('shows the indigo pill, the explanation and the 14-day note', () => {
    draw(mine())
    expect(screen.getByTestId('withdrawal-maker')).toBeTruthy()
    expect(screen.getByTestId('withdrawal-pill').textContent).toBe(`${K}.pill.pending`)
    expect(screen.getByText(`${K}.yourExplanation`)).toBeTruthy()
    expect(screen.getByText('Dummy explanation')).toBeTruthy()
    expect(screen.getByText(`${K}.checkersEmailed`)).toBeTruthy()
    expect(screen.queryByTestId('withdrawal-approve')).toBeNull()
  })

  it('Cancel request calls the cancel route with the request id', async () => {
    const next = caseOf({ ...PENDING, status: 'cancelled', your_step: 'request' })
    mockApi.cancelAwardWithdrawal.mockResolvedValue(next)
    const onChanged = draw(mine())
    fireEvent.click(screen.getByTestId('withdrawal-cancel'))
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(next))
    expect(mockApi.cancelAwardWithdrawal).toHaveBeenCalledWith(31, { token: 'tok' })
  })
})

describe('state 3: a checker decides (your_step=decide)', () => {
  const theirs = (over: Record<string, unknown> = {}) => caseOf({ ...PENDING, your_step: 'decide' }, over)

  it('shows the amber pill, who asked, their explanation and the payload figures', () => {
    draw(theirs({ disbursements: [tranche('scheduled', '250.00')] }))
    expect(screen.getByTestId('withdrawal-pill').textContent).toBe(`${K}.pill.yourApproval`)
    expect(screen.getByText(/Dummy Maker/)).toBeTruthy()
    expect(screen.getByText(`${K}.theirExplanation`)).toBeTruthy()
    const facts = screen.getByTestId('withdrawal-facts').textContent
    expect(facts).toBe(
      `${K}.fact.awardRM 3,000.00${K}.fact.paidRM 0.00${K}.fact.freedRM 2,500.00${K}.fact.stopped3`)
    expect(screen.getByText(`${K}.approveNote`)).toBeTruthy()
    expect(screen.getByText(`${K}.selfNote`)).toBeTruthy()
  })

  it('a missing award amount is left out, never invented', () => {
    draw(theirs({ award_amount: null }))
    expect(screen.getByTestId('withdrawal-facts').textContent).not.toContain(`${K}.fact.award`)
  })

  it('Approve opens a confirm first: one click withdraws nothing', () => {
    draw(theirs())
    fireEvent.click(screen.getByTestId('withdrawal-approve'))
    expect(mockApi.approveAwardWithdrawal).not.toHaveBeenCalled()
    const box = screen.getByTestId('withdrawal-approve-box')
    expect(box.textContent).toContain(`${K}.approveDialogTitle`)
    expect(box.textContent).toContain(`${K}.approveDialogHint`)
    // the note is optional: Confirm is ready with an empty box
    expect((screen.getByRole('button', { name: APPROVE_CONFIRM }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('Approve with an empty note sends an empty note', async () => {
    const next = caseOf(null, { status: 'recommended' })
    mockApi.approveAwardWithdrawal.mockResolvedValue(next)
    const onChanged = draw(theirs())
    fireEvent.click(screen.getByTestId('withdrawal-approve'))
    fireEvent.click(screen.getByRole('button', { name: APPROVE_CONFIRM }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(next))
    expect(mockApi.approveAwardWithdrawal).toHaveBeenCalledWith(31, '', { token: 'tok' })
  })

  it('Approve sends the trimmed note for the record', async () => {
    const next = caseOf(null, { status: 'recommended' })
    mockApi.approveAwardWithdrawal.mockResolvedValue(next)
    const onChanged = draw(theirs())
    fireEvent.click(screen.getByTestId('withdrawal-approve'))
    fireEvent.change(screen.getByPlaceholderText(NOTE), { target: { value: '  Dummy note  ' } })
    fireEvent.click(screen.getByRole('button', { name: APPROVE_CONFIRM }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(next))
    expect(mockApi.approveAwardWithdrawal).toHaveBeenCalledWith(31, 'Dummy note', { token: 'tok' })
  })

  it('a note over the limit is refused here and never sent', () => {
    draw(theirs())
    fireEvent.click(screen.getByTestId('withdrawal-approve'))
    fireEvent.change(screen.getByPlaceholderText(NOTE), { target: { value: 'x'.repeat(TEXT_MAX + 1) } })
    fireEvent.click(screen.getByRole('button', { name: APPROVE_CONFIRM }))
    expect(screen.getByRole('alert').textContent).toBe(`${K}.error.note_too_long`)
    expect(mockApi.approveAwardWithdrawal).not.toHaveBeenCalled()
  })

  it('a typed refusal reason survives opening and cancelling the approve confirm', () => {
    draw(theirs())
    fireEvent.change(screen.getByTestId('withdrawal-reason'), { target: { value: 'Dummy reason' } })
    fireEvent.click(screen.getByTestId('withdrawal-approve'))
    expect(screen.queryByTestId('withdrawal-reason')).toBeNull()       // the refuse box is for Refuse only
    fireEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(screen.queryByTestId('withdrawal-approve-box')).toBeNull()
    expect((screen.getByTestId('withdrawal-reason') as HTMLTextAreaElement).value).toBe('Dummy reason')
    expect(mockApi.approveAwardWithdrawal).not.toHaveBeenCalled()
  })

  it('Refuse needs a reason: blank is refused here and never sent', () => {
    draw(theirs())
    fireEvent.click(screen.getByTestId('withdrawal-refuse'))
    expect(screen.getByRole('alert').textContent).toBe(`${K}.error.reason_required`)
    expect(mockApi.refuseAwardWithdrawal).not.toHaveBeenCalled()
  })

  it('Refuse sends the trimmed reason to the refuse route', async () => {
    const next = caseOf({ ...PENDING, status: 'refused', your_step: null })
    mockApi.refuseAwardWithdrawal.mockResolvedValue(next)
    const onChanged = draw(theirs())
    fireEvent.change(screen.getByTestId('withdrawal-reason'), { target: { value: '  Dummy reason  ' } })
    fireEvent.click(screen.getByTestId('withdrawal-refuse'))
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(next))
    expect(mockApi.refuseAwardWithdrawal).toHaveBeenCalledWith(31, 'Dummy reason', { token: 'tok' })
  })

  it('a reason over the limit is refused here and never sent', () => {
    draw(theirs())
    fireEvent.change(screen.getByTestId('withdrawal-reason'), { target: { value: 'x'.repeat(TEXT_MAX + 1) } })
    fireEvent.click(screen.getByTestId('withdrawal-refuse'))
    expect(screen.getByRole('alert').textContent).toBe(`${K}.error.reason_too_long`)
    expect(mockApi.refuseAwardWithdrawal).not.toHaveBeenCalled()
  })

  it('a paid tranche shows the paid note; the server still has the last word', () => {
    draw(theirs({ disbursements: [tranche('released')] }))
    expect(screen.getByText(`${K}.paidNote`)).toBeTruthy()
    expect(screen.getByTestId('withdrawal-facts').textContent).toContain('RM 500.00')
  })
})

describe('state 4: read only', () => {
  it('a pending request with no step (a super, or a bystander) reads only', () => {
    draw(caseOf({ ...PENDING, your_step: null }))
    expect(screen.getByTestId('withdrawal-outcome')).toBeTruthy()
    expect(screen.getByTestId('withdrawal-pill').textContent).toBe(`${K}.pill.pending`)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it.each(['approved', 'refused', 'cancelled', 'expired'])('a %s request reads only, with its pill', (status) => {
    draw(caseOf({ ...PENDING, status, your_step: null, decided_by_name: 'Dummy Checker',
      decided_at: '2026-11-09T03:00:00Z', decision_note: 'Dummy note' }))
    expect(screen.getByTestId('withdrawal-pill').textContent).toBe(`${K}.pill.${status}`)
    expect(screen.getByText(new RegExp(`${K}.decided.${status}`))).toBeTruthy()
    expect(screen.getByText('Dummy note')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('a stale cancel/decide step on a finished request still reads only', () => {
    draw(caseOf({ ...PENDING, status: 'approved', your_step: 'decide' }))
    expect(screen.queryByTestId('withdrawal-approve')).toBeNull()
    expect(screen.getByTestId('withdrawal-outcome')).toBeTruthy()
  })
})

describe('refusals read as words', () => {
  it('names all thirteen API codes, plus not_found', () => {
    expect([...KNOWN_ERRORS].sort()).toEqual([
      'already_pending', 'explanation_required', 'explanation_too_long', 'has_payments', 'no_checker',
      'not_awarded', 'not_found', 'not_pending', 'note_too_long', 'reason_required', 'reason_too_long',
      'same_person', 'stale', 'wrong_role',
    ])
  })

  it.each([...KNOWN_ERRORS])('%s', async (code) => {
    mockApi.approveAwardWithdrawal.mockRejectedValue(refusal(code))
    const onChanged = draw(caseOf({ ...PENDING, your_step: 'decide' }))
    fireEvent.click(screen.getByTestId('withdrawal-approve'))
    fireEvent.click(screen.getByRole('button', { name: APPROVE_CONFIRM }))
    expect((await screen.findByRole('alert')).textContent).toBe(`${K}.error.${code}`)
    expect(onChanged).not.toHaveBeenCalled()
  })

  it('an unknown failure gets the generic message', async () => {
    mockApi.requestAwardWithdrawal.mockRejectedValue(new Error('network'))
    draw(caseOf({ id: null, status: null, your_step: 'request' }))
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: 'Dummy' } })
    fireEvent.click(screen.getByRole('button', { name: CONFIRM }))
    expect((await screen.findByRole('alert')).textContent).toBe(`${K}.error.generic`)
  })
})

describe('the money helpers are exact', () => {
  it('reads decimal strings as whole cents, never floats', () => {
    expect(toCents('2500.00')).toBe(250000)
    expect(toCents('0.1')).toBe(10)
    expect(toCents('12')).toBe(1200)
    expect(toCents(null)).toBeNull()
    expect(toCents('abc')).toBeNull()
    expect(rmFromCents(123456789)).toBe('RM 1,234,567.89')
    expect(rmFromCents(5)).toBe('RM 0.05')
  })

  it('paid so far adds only released tranches, exactly', () => {
    const app = caseOf(null, { disbursements: [tranche('released', '0.10'), tranche('released', '0.20'),
      tranche('returned', '100.00'), tranche('scheduled', '50.00')] })
    expect(paidSoFarCents(app)).toBe(30)
  })

  it('scheduled, due and withheld tranches are not paid', () => {
    expect(hasPaidTranche(caseOf(null, { disbursements: ['scheduled', 'due', 'withheld'].map((s) => tranche(s)) }))).toBe(false)
    expect(hasPaidTranche(caseOf(null, { disbursements: undefined }))).toBe(false)
  })
})

it("the scholar timeline reads the withdrawal with its staff-only reason", () => {
  const tp = (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k)
  const row = (body: string) => ({ id: 1, kind: 'system', event: 'award_withdrawn', body, meta: {},
    actor_email: 'super@example.org', internal: true, created_at: '2026-11-08T00:00:00Z' }) as api.ScholarActivity
  expect(activityText(row('Dummy reason'), tp)).toBe('admin.scholars.event.award_withdrawn|{"reason":"Dummy reason"}')
  expect(activityText(row(''), tp)).toBe('admin.scholars.event.award_withdrawn|{"reason":"—"}')
})
