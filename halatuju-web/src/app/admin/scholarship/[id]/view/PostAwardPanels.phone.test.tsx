/**
 * @jest-environment jsdom
 *
 * Mobile M6b (owner, 2026-11-03): scheduling a tranche and the payment actions are READ-ONLY ON A PHONE, with a
 * "use a computer" note — hidden below md ONLY, so the desktop keeps exactly the controls it had, wired as before.
 * jsdom applies no media query, so this reads the classes that do the hiding and presses the desktop controls.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { PostAwardPanels } from './PostAwardPanels'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

const t = (k: string) => k
const ROWS = [
  { id: 1, sequence: 1, amount: '1200.00', status: 'scheduled', label: 'Semester 1', scheduled_for: null,
    released_at: null, actioned_by: '', reference: '', note: '', sponsorship_id: null, created_at: '' },
]
const props = (over: Record<string, unknown> = {}) => ({
  app: { id: 5, status: 'maintenance', maintenance_substate: 'on_track', disbursements: ROWS, has_file: true,
    closure_reason: '', closed_at: null } as unknown as AdminScholarshipDetail,
  t: t as never, busy: '', isSuper: false, canWrite: true, orgSuper: true, mayOpenFile: true,
  bursary: null, bursaryMsg: '', doCountersignBursary: jest.fn(), doWitnessBursary: jest.fn(),
  disbAmount: '500', setDisbAmount: jest.fn(), disbLabel: '', setDisbLabel: jest.fn(), disbMsg: '',
  doScheduleTranche: jest.fn(), doDisbursementAction: jest.fn(), doSetSubstate: jest.fn(),
  closeReason: '' as const, setCloseReason: jest.fn(), closeMsg: '', doClose: jest.fn(),
  ...over,
})
/** Is `el` inside something hidden below md (and only below md)? */
const hiddenOnPhone = (el: Element) => !!el.closest('.max-md\\:hidden')

describe('payments are read-only on a phone (Mobile M6b)', () => {
  it('every tranche action and the Schedule form sit inside a below-md-hidden container', () => {
    render(<PostAwardPanels {...props()} />)
    const actions = screen.getAllByRole('button', { name: /admin\.disbursement\.action\./ })
    expect(actions.length).toBeGreaterThan(0)
    for (const b of actions) expect(hiddenOnPhone(b)).toBe(true)
    expect(hiddenOnPhone(screen.getByRole('button', { name: 'admin.disbursement.schedule' }))).toBe(true)
    expect(hiddenOnPhone(screen.getByPlaceholderText('500'))).toBe(true)
  })

  it('the phone gets the "use a computer" note, and the desktop does not', () => {
    render(<PostAwardPanels {...props()} />)
    const note = screen.getByText('admin.disbursement.useComputer')
    expect(note.className.split(' ')).toContain('md:hidden')
    expect(hiddenOnPhone(note)).toBe(false)
  })

  it('from md the controls are the ones they were, wired the same way', () => {
    const p = props()
    render(<PostAwardPanels {...p} />)
    fireEvent.click(screen.getByRole('button', { name: 'admin.disbursement.action.release' }))
    expect(p.doDisbursementAction).toHaveBeenCalledWith(1, 'release')
    fireEvent.click(screen.getByRole('button', { name: 'admin.disbursement.schedule' }))
    expect(p.doScheduleTranche).toHaveBeenCalledTimes(1)
  })

  it('a person who cannot write sees neither the controls nor the note (nothing changed for them)', () => {
    render(<PostAwardPanels {...props({ canWrite: false })} />)
    expect(screen.queryByText('admin.disbursement.useComputer')).toBeNull()
    expect(screen.queryByRole('button', { name: 'admin.disbursement.schedule' })).toBeNull()
  })
})
