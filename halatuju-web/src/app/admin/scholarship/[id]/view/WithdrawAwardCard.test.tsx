/**
 * @jest-environment jsdom
 *
 * A1.13 (TD-198 / CO-09): the super-only "Withdraw award" card. It shows only to a super admin on an
 * awarded case, asks for a reason in the decision reopen's box (Confirm rests until there is text),
 * sends the TRIMMED reason, hands the refreshed case back, and turns each refusal code into words.
 * A case with a paid tranche gets the note, never the button. Dummy data only.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { WithdrawAwardCard, hasPaidTranche } from './WithdrawAwardCard'
import { activityText } from '@/lib/scholarActivity'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const t = ((k: string) => k) as never
const tranche = (status: string) => ({ id: 1, sequence: 1, amount: '500.00', status })
const caseOf = (over: Record<string, unknown> = {}) =>
  ({ id: 7, status: 'awarded', disbursements: [], ...over }) as unknown as api.AdminScholarshipDetail

const draw = (over: Partial<Parameters<typeof WithdrawAwardCard>[0]> = {}) => {
  const onWithdrawn = jest.fn()
  render(<WithdrawAwardCard app={caseOf()} t={t} isSuper token="tok" onWithdrawn={onWithdrawn} {...over} />)
  return onWithdrawn
}
const ACTION = 'admin.scholarship.withdrawAward.action'
const CONFIRM = 'admin.scholarship.withdrawAward.confirm'
const PLACEHOLDER = 'admin.scholarship.withdrawAward.placeholder'

beforeEach(() => jest.clearAllMocks())

describe('who and when', () => {
  it('a super on an awarded case sees the action', () => {
    draw()
    expect(screen.getByRole('button', { name: ACTION })).toBeTruthy()
  })

  it('anyone who is not super sees nothing', () => {
    draw({ isSuper: false })
    expect(screen.queryByTestId('withdraw-award')).toBeNull()
  })

  it.each(['recommended', 'interviewed', 'awaiting_qc', 'active', 'closed'])('a %s case shows nothing', (status) => {
    draw({ app: caseOf({ status }) })
    expect(screen.queryByTestId('withdraw-award')).toBeNull()
  })

  it.each(['released', 'returned'])('a %s tranche swaps the button for the paid note', (status) => {
    draw({ app: caseOf({ disbursements: [tranche('scheduled'), tranche(status)] }) })
    expect(screen.queryByRole('button', { name: ACTION })).toBeNull()
    expect(screen.getByText('admin.scholarship.withdrawAward.paidNote')).toBeTruthy()
  })

  it('scheduled, due and withheld tranches are not paid', () => {
    expect(hasPaidTranche(caseOf({ disbursements: ['scheduled', 'due', 'withheld'].map(tranche) }))).toBe(false)
    expect(hasPaidTranche(caseOf({ disbursements: undefined }))).toBe(false)
  })
})

describe('the reason box', () => {
  it('Confirm rests until the reason has text, and blank space is not text', () => {
    draw()
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    const confirm = screen.getByRole('button', { name: CONFIRM }) as HTMLButtonElement
    expect(confirm.disabled).toBe(true)
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: '   ' } })
    expect(confirm.disabled).toBe(true)
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: 'Dummy reason' } })
    expect(confirm.disabled).toBe(false)
  })

  it('sends the trimmed reason and hands the refreshed case back', async () => {
    const next = caseOf({ status: 'recommended' })
    mockApi.withdrawAward.mockResolvedValue(next)
    const onWithdrawn = draw()
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: '  Dummy reason  ' } })
    fireEvent.click(screen.getByRole('button', { name: CONFIRM }))
    await waitFor(() => expect(onWithdrawn).toHaveBeenCalledWith(next))
    expect(mockApi.withdrawAward).toHaveBeenCalledWith(7, 'Dummy reason', { token: 'tok' })
  })

  it('Cancel closes the box without calling the API', () => {
    draw()
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    fireEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(screen.queryByPlaceholderText(PLACEHOLDER)).toBeNull()
    expect(mockApi.withdrawAward).not.toHaveBeenCalled()
  })
})

describe('refusals read as words', () => {
  it.each(['reason_required', 'reason_too_long', 'not_awarded', 'has_payments'])('%s', async (code) => {
    mockApi.withdrawAward.mockRejectedValue(Object.assign(new Error('x'), { code, status: 409 }))
    const onWithdrawn = draw()
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: 'Dummy reason' } })
    fireEvent.click(screen.getByRole('button', { name: CONFIRM }))
    expect((await screen.findByRole('alert')).textContent).toBe(`admin.scholarship.withdrawAward.error.${code}`)
    expect(onWithdrawn).not.toHaveBeenCalled()
  })

  it('an unknown failure gets the generic message', async () => {
    mockApi.withdrawAward.mockRejectedValue(new Error('network'))
    draw()
    fireEvent.click(screen.getByRole('button', { name: ACTION }))
    fireEvent.change(screen.getByPlaceholderText(PLACEHOLDER), { target: { value: 'Dummy reason' } })
    fireEvent.click(screen.getByRole('button', { name: CONFIRM }))
    expect((await screen.findByRole('alert')).textContent).toBe('admin.scholarship.withdrawAward.error.generic')
  })
})

it("the scholar timeline reads the withdrawal with its staff-only reason", () => {
  const tp = (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k)
  const row = (body: string) => ({ id: 1, kind: 'system', event: 'award_withdrawn', body, meta: {},
    actor_email: 'super@example.org', internal: true, created_at: '2026-11-08T00:00:00Z' }) as api.ScholarActivity
  expect(activityText(row('Dummy reason'), tp)).toBe('admin.scholars.event.award_withdrawn|{"reason":"Dummy reason"}')
  expect(activityText(row(''), tp)).toBe('admin.scholars.event.award_withdrawn|{"reason":"—"}')
})
