/**
 * @jest-environment jsdom
 *
 * Request #75 re-check 5: "Reject before interview" sits in ONE slot of the Reviewer card, whether or
 * not the assign controls show above it. A reject's reply is held by the panel itself, and a panel
 * that remounts drops it (its mounted guard), so if a reload flips the assign card while a reject is
 * pending, the officer must still read the success or the refusal. Dummy data only.
 */
import { useState } from 'react'
import { act, fireEvent, render, screen } from '@testing-library/react'

import * as api from '@/lib/admin-api'

import { AssignAndWitness } from './AssignAndWitness'
import { PreInterviewOption } from './PreInterviewReject'

jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const P = 'admin.scholarship.preInterview'
const t = ((k: string) => k) as never
const noop = () => undefined
const OFFER = { hold_hours: 24, reasons: ['not_b40'], note_max: 2000 }
const app = { id: 7, name: 'Dummy Student', status: 'profile_complete', assigned_to_id: null, programme_id: null,
  query_sla: { ready_for_assignment: true }, pre_interview: OFFER } as unknown as api.AdminScholarshipDetail

/** The page: holds the refusal, as `view.tsx` does, and draws the card with or without the assign door. */
function Page({ canAssign, onDone }: { canAssign: boolean; onDone: jest.Mock }) {
  const [err, setErr] = useState('')
  return (
    <AssignAndWitness
      app={app} t={t} busy="" isSuper={false} canAssign={canAssign} decisionLocked={false}
      admins={[{ id: 5, name: 'Reviewer Five', role: 'reviewer' }]} doAssign={noop}
      witnessCardVisible={false} activeSources={[]} witnessSel="" setWitnessSel={noop}
      witnessBusy={false} witnessMsg="" setWitnessMsg={noop} witnessEditing={false}
      setWitnessEditing={noop} doAssignWitness={noop}
      // ⚠ No `key` here, on purpose. The page keys the panel by case, and today that key alone lets React
      // match it across two different card layouts. This test pins the slot itself (without the key and
      // without the fix, all four tests fail).
      preInterview={<PreInterviewOption app={app} t={t} token="tok" busy="" canAssign={canAssign}
        err={err} setErr={setErr} onDone={onDone} onStale={noop} />}
    />
  )
}

/** Press "Yes, reject" with the reply held, then flip the assign card. */
const rejectThenFlip = (from: boolean) => {
  const onDone = jest.fn()
  const reply: { settle: (ok: boolean, v: unknown) => void } = { settle: () => {} }
  mockApi.rejectBeforeInterview.mockReturnValue(new Promise((res, rej) => {
    reply.settle = (ok, v) => (ok ? res(v as never) : rej(v))
  }))
  const view = render(<Page canAssign={from} onDone={onDone} />)
  expect(!!screen.queryByText('admin.scholarship.assignTitle')).toBe(from)
  fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
  fireEvent.change(screen.getByLabelText(`${P}.reasonLabel`), { target: { value: 'not_b40' } })
  fireEvent.change(screen.getByLabelText(`${P}.whyLabel`), { target: { value: 'Dummy note' } })
  fireEvent.click(screen.getByRole('button', { name: `${P}.submit` }))
  fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` }))
  expect(screen.getByRole('button', { name: `${P}.running` })).toBeTruthy()
  view.rerender(<Page canAssign={!from} onDone={onDone} />)
  expect(!!screen.queryByText('admin.scholarship.assignTitle')).toBe(!from)
  // Still the same panel, still waiting: nothing was remounted.
  expect(screen.getByRole('button', { name: `${P}.running` })).toBeTruthy()
  return { onDone, reply }
}
const land = (fn: () => void) => act(async () => { fn(); await new Promise((r) => setTimeout(r, 0)) })

beforeEach(() => jest.clearAllMocks())

describe.each([
  ['the assign card goes away', true],
  ['the assign card comes back', false],
])('a reject pending while %s', (_, from) => {
  it('its refusal still shows', async () => {
    const { reply } = rejectThenFlip(from)
    await land(() => reply.settle(false, Object.assign(new Error('x'), { code: 'comments_required' })))
    expect(screen.getByRole('alert').textContent).toBe(`${P}.error.comments_required`)
    expect(screen.getByLabelText(`${P}.whyLabel`)).toBeTruthy()   // back on the form, as without the flip
  })

  it('its success still reaches the page', async () => {
    const { onDone, reply } = rejectThenFlip(from)
    const next = { ...app, status: 'rejected', pre_interview: undefined }
    await land(() => reply.settle(true, next))
    expect(onDone).toHaveBeenCalledWith(next)
    expect(screen.getByRole('button', { name: `${P}.start` })).toBeTruthy()   // the panel rests
  })
})
