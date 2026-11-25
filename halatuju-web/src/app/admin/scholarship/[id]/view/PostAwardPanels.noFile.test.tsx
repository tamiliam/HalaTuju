/**
 * @jest-environment jsdom
 *
 * S3 review M1: a PAYABLE student with NO scholar file (awarded, an eWallet id, Vircle has not
 * reported it live) is paid by the runs, so somebody must be able to hold her — from the cockpit,
 * because there is no file. With a file, the control is NOT here (it moved to the file).
 */
import { fireEvent, render as rtlRender, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { PostAwardPanels } from './PostAwardPanels'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { AdminAuthContext, type AdminAuthContextValue } from '@/lib/adminAuthCore'

// The signed-in reader (`/admin/role/`): an organisation admin unless a test says otherwise.
let viewer: Record<string, unknown> = { role: 'org_admin', permissions: ['see_all', 'scholars'] }
const render = (ui: ReactElement) => rtlRender(
  <AdminAuthContext.Provider value={{ role: viewer } as unknown as AdminAuthContextValue}>{ui}</AdminAuthContext.Provider>)
beforeEach(() => { viewer = { role: 'org_admin', permissions: ['see_all', 'scholars'] } })

const t = (k: string) => k
const props = (app: Partial<AdminScholarshipDetail>, over: Record<string, unknown> = {}) => ({
  app: { id: 5, status: 'awarded', maintenance_substate: 'on_track', disbursements: [],
    closure_reason: '', closed_at: null, ...app } as unknown as AdminScholarshipDetail,
  t: t as never, busy: '', isSuper: false, canWrite: true, canTranche: true, canClosePreAward: true, mayOpenFile: true,
  bursary: null, bursaryMsg: '', doCountersignBursary: jest.fn(), doWitnessBursary: jest.fn(),
  disbAmount: '', setDisbAmount: jest.fn(), disbLabel: '', setDisbLabel: jest.fn(), disbMsg: '',
  doScheduleTranche: jest.fn(), doDisbursementAction: jest.fn(), doSetSubstate: jest.fn(),
  closeReason: '' as const, setCloseReason: jest.fn(), closeMsg: '', doClose: jest.fn(),
  ...over,
})

it('a payable student with no file is held from here, by a payments-rights holder', () => {
  const p = props({ has_file: false, maintenance_controls: { can_set_substate: true, can_hold: true } })
  render(<PostAwardPanels {...p} />)
  expect(screen.getByTestId('no-file-substate')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'admin.maintenance.action.on_hold' }))
  expect(p.doSetSubstate).toHaveBeenCalledWith('on_hold')
})

it('without payments rights the hold is not offered here either', () => {
  render(<PostAwardPanels {...props({ has_file: false,
    maintenance_controls: { can_set_substate: true, can_hold: false } })} />)
  expect(screen.queryByRole('button', { name: 'admin.maintenance.action.on_hold' })).toBeNull()
  expect(screen.getByRole('button', { name: 'admin.maintenance.action.probation' })).toBeTruthy()
})

it('a student WITH a file is changed on the file, not here', () => {
  render(<PostAwardPanels {...props({ has_file: true,
    maintenance_controls: { can_set_substate: true, can_hold: true } })} />)
  expect(screen.queryByTestId('no-file-substate')).toBeNull()
  expect(screen.getByTestId('open-scholar-file')).toBeTruthy()
})

it('nothing for a case that takes no sub-state, or a reader who cannot write', () => {
  const { unmount } = render(<PostAwardPanels {...props({ has_file: false,
    maintenance_controls: { can_set_substate: false, can_hold: true } })} />)
  expect(screen.queryByTestId('no-file-substate')).toBeNull()
  unmount()
  render(<PostAwardPanels {...props({ has_file: false,
    maintenance_controls: { can_set_substate: true, can_hold: false } }, { canWrite: false })} />)
  expect(screen.queryByTestId('no-file-substate')).toBeNull()
})

describe('S4a review round 2: each move offered by the scholar file\'s rule on the served flags', () => {
  // `canWrite` = served `can_write` (Manage scholar files past the award); `can_hold` = the hold door.
  const offered = (current: string, canWrite: boolean, canHold: boolean | null) => {
    const { unmount } = render(<PostAwardPanels {...props({ has_file: false, maintenance_substate: current as never,
      maintenance_controls: { can_set_substate: true, can_hold: canHold } }, { canWrite })} />)
    const names = screen.queryAllByRole('button').map((b) => b.textContent)
      .filter((n): n is string => !!n && n.startsWith('admin.maintenance.action.'))
      .map((n) => n.replace('admin.maintenance.action.', ''))
    const drawn = !!screen.queryByTestId('no-file-substate')
    unmount()
    return { drawn, names }
  }

  it('Manage only: every move but placing or lifting a hold', () => {
    expect(offered('on_track', true, false)).toEqual({ drawn: true, names: ['probation', 'ready_to_close'] })
    expect(offered('on_hold', true, false)).toEqual({ drawn: true, names: [] })
  })

  it('View scholars and Payments: Prepare only (Manage off): the hold and its lift, nothing else', () => {
    expect(offered('on_track', false, true)).toEqual({ drawn: true, names: ['on_hold'] })
    expect(offered('probation', false, true)).toEqual({ drawn: true, names: ['on_hold'] })
    expect(offered('on_hold', false, true)).toEqual({ drawn: true, names: ['on_track'] })
  })

  it('neither: no control', () => {
    expect(offered('on_track', false, false).drawn).toBe(false)
    expect(offered('on_hold', false, false).drawn).toBe(false)
  })

  it('both: every move, a hold\'s too', () => {
    expect(offered('on_track', true, true)).toEqual({ drawn: true,
      names: ['probation', 'on_hold', 'ready_to_close'] })
    expect(offered('on_hold', true, true)).toEqual({ drawn: true,
      names: ['on_track', 'probation', 'ready_to_close'] })
  })

  it('an older payload with no viewer answer (`can_hold` null) behaves as before: Manage moves only', () => {
    expect(offered('on_track', true, null)).toEqual({ drawn: true, names: ['probation', 'ready_to_close'] })
    expect(offered('on_track', false, null).drawn).toBe(false)
  })
})

it('sprint S1: no "Open scholar file" for a reader the Scholars page refuses (no `scholars` key)', () => {
  render(<PostAwardPanels {...props({ has_file: true,
    maintenance_controls: { can_set_substate: true, can_hold: true } }, { mayOpenFile: false })} />)
  expect(screen.queryByTestId('open-scholar-file')).toBeNull()
})

it('sprint S1: no "Open scholar file" for staff who mentor but lack `scholars` (the student may not be theirs)', () => {
  viewer = { role: 'reviewer', permissions: ['review'], mentoring: true }
  render(<PostAwardPanels {...props({ has_file: true,
    maintenance_controls: { can_set_substate: true, can_hold: true } })} />)
  expect(screen.queryByTestId('open-scholar-file')).toBeNull()
})
