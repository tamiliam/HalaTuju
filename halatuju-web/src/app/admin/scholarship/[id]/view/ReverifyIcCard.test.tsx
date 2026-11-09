/**
 * @jest-environment jsdom
 *
 * Audit sprint A2.8a (TD-378): an AWAITING-QC case on a ruled intake whose IC lock was released shows a
 * "Re-verify IC" card to a QC holder, and its one button calls the existing verify-accept.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { ReverifyIcCard, needsIcReverify } from './ReverifyIcCard'
import * as adminApi from '@/lib/admin-api'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

jest.mock('@/lib/admin-api', () => ({ verifyAcceptApplication: jest.fn() }))
const mockVerify = adminApi.verifyAcceptApplication as jest.Mock
const t = ((k: string) => k) as never

const APP = { id: 7, status: 'interviewed', nric_verified: false, birth_state: { meets_rule: true } } as
  unknown as AdminScholarshipDetail
const as = (over: Partial<Record<string, unknown>>) => ({ ...APP, ...over }) as unknown as AdminScholarshipDetail

beforeEach(() => jest.clearAllMocks())

it('shows only at awaiting QC, to a QC holder, on a ruled intake with an unlocked IC', () => {
  expect(needsIcReverify(APP, true)).toBe(true)
  expect(needsIcReverify(as({ birth_state: { meets_rule: false } }), true)).toBe(true)
  expect(needsIcReverify(APP, false)).toBe(false)
  expect(needsIcReverify(as({ nric_verified: true }), true)).toBe(false)
  expect(needsIcReverify(as({ birth_state: { meets_rule: null } }), true)).toBe(false)
  expect(needsIcReverify(as({ status: 'interviewing' }), true)).toBe(false)
})

it('the button calls verify-accept and hands back the new case', async () => {
  const done = { ...APP, nric_verified: true }
  mockVerify.mockResolvedValueOnce(done)
  const onDone = jest.fn()
  render(<ReverifyIcCard app={APP} t={t} token="tok" busy="" canQc onDone={onDone} />)
  await act(async () => { fireEvent.click(screen.getByText('admin.scholarship.qcDecision.reverifyButton')) })
  expect(mockVerify).toHaveBeenCalledWith(7, {}, { token: 'tok' })
  expect(onDone).toHaveBeenCalledWith(done)
})

it('a refusal (for example another account holds the IC verified) is shown, not swallowed', async () => {
  mockVerify.mockRejectedValueOnce(new Error('This NRIC is already verified on another account.'))
  render(<ReverifyIcCard app={APP} t={t} token="tok" busy="" canQc onDone={jest.fn()} />)
  await act(async () => { fireEvent.click(screen.getByText('admin.scholarship.qcDecision.reverifyButton')) })
  expect(screen.getByRole('alert').textContent).toContain('already verified')
})

it('renders nothing when the case does not need it', () => {
  const { container } = render(
    <ReverifyIcCard app={as({ nric_verified: true })} t={t} token="tok" busy="" canQc onDone={jest.fn()} />)
  expect(container.innerHTML).toBe('')
})
