/**
 * @jest-environment jsdom
 *
 * Owner, 2026-11-03 (Mobile M6b follow-up, TD-480 item 4): the maintenance status buttons — On track, Probation,
 * On hold, Ready to close — are READ-ONLY ON A PHONE, the same as the payment rule: hidden below md ONLY, with a
 * "use a computer" note, and the desktop unchanged. On hold stops a student's money. Both places that draw them are
 * pinned: the scholar file (`ScholarControls`) and the cockpit's no-file control (`PostAwardPanels`).
 * jsdom applies no media query, so this reads the classes that do the hiding and presses the desktop controls.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarControls from './ScholarControls'
import { PostAwardPanels } from '@/app/admin/scholarship/[id]/view/PostAwardPanels'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const STATUS = /^admin\.maintenance\.action\./
/** Is `el` inside something hidden below md (and only below md)? */
const hiddenOnPhone = (el: Element) => !!el.closest('.max-md\\:hidden')

const FILE = {
  id: 9, name: 'X', gift: null, course: '', institution: '', status: 'active',
  maintenance_substate: 'on_track', is_on_hold: false, in_maintenance: true, has_file: true,
  closure_reason: '', awarded_at: null, vircle_activated_at: null, closed_at: null,
  latest_result: null, standing: 'no_result_yet',
  money: { award_amount: null, paid_to_date: '0.00', remaining: '0.00', last_payment: null },
  contract: { exists: false, status: null }, mentor: null, letters: [], last_activity_at: null,
  controls: { can_set_substate: true, can_hold: true, close_reasons: [], close_refusal: '' },
} as unknown as api.ScholarFile

const t = (k: string) => k
const cockpit = (controls: { can_set_substate: boolean; can_hold: boolean }) => ({
  app: { id: 5, status: 'awarded', maintenance_substate: 'on_track', disbursements: [], has_file: false,
    maintenance_controls: controls, closure_reason: '', closed_at: null } as unknown as api.AdminScholarshipDetail,
  t: t as never, busy: '', isSuper: false, canWrite: true, orgSuper: true,
  bursary: null, bursaryMsg: '', doCountersignBursary: jest.fn(), doWitnessBursary: jest.fn(),
  disbAmount: '', setDisbAmount: jest.fn(), disbLabel: '', setDisbLabel: jest.fn(), disbMsg: '',
  doScheduleTranche: jest.fn(), doDisbursementAction: jest.fn(), doSetSubstate: jest.fn(),
  closeReason: '' as const, setCloseReason: jest.fn(), closeMsg: '', doClose: jest.fn(),
})

beforeEach(() => jest.clearAllMocks())

describe('the scholar file: the status is read-only on a phone', () => {
  it('every status button sits inside a below-md-hidden container, and the phone gets the note', () => {
    render(<ScholarControls file={FILE} token="tok" onChanged={jest.fn()} />)
    const buttons = screen.getAllByRole('button', { name: STATUS })
    expect(buttons).toHaveLength(3)
    for (const b of buttons) expect(hiddenOnPhone(b)).toBe(true)
    const note = screen.getByText('admin.maintenance.useComputer')
    expect(note.className.split(' ')).toContain('md:hidden')
    expect(hiddenOnPhone(note)).toBe(false)
  })

  it('from md the buttons are the ones they were, wired the same way', async () => {
    mockApi.setMaintenanceSubstate.mockResolvedValue({} as never)
    render(<ScholarControls file={FILE} token="tok" onChanged={jest.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'admin.maintenance.action.on_hold' }))
    await waitFor(() => expect(mockApi.setMaintenanceSubstate).toHaveBeenCalledWith(9, 'on_hold', { token: 'tok' }))
  })

  it('a person who may not set the status sees neither the buttons nor the note', () => {
    render(<ScholarControls file={{ ...FILE, controls: { ...FILE.controls!, can_set_substate: false } } as api.ScholarFile}
      token="tok" onChanged={jest.fn()} />)
    expect(screen.queryAllByRole('button', { name: STATUS })).toHaveLength(0)
    expect(screen.queryByText('admin.maintenance.useComputer')).toBeNull()
  })
})

describe('the cockpit (a payable student with no file): the status is read-only on a phone', () => {
  it('every status button sits inside a below-md-hidden container, and the phone gets the note', () => {
    render(<PostAwardPanels {...cockpit({ can_set_substate: true, can_hold: true })} />)
    const buttons = screen.getAllByRole('button', { name: STATUS })
    expect(buttons).toHaveLength(3)
    for (const b of buttons) expect(hiddenOnPhone(b)).toBe(true)
    const note = screen.getByText('admin.maintenance.useComputer')
    expect(note.className.split(' ')).toContain('md:hidden')
    expect(hiddenOnPhone(note)).toBe(false)
  })

  it('from md the buttons are the ones they were, wired the same way', () => {
    const p = cockpit({ can_set_substate: true, can_hold: true })
    render(<PostAwardPanels {...p} />)
    fireEvent.click(screen.getByRole('button', { name: 'admin.maintenance.action.probation' }))
    expect(p.doSetSubstate).toHaveBeenCalledWith('probation')
  })

  it('the "needs payments rights" reason goes with the buttons (desktop only)', () => {
    render(<PostAwardPanels {...cockpit({ can_set_substate: true, can_hold: false })} />)
    expect(hiddenOnPhone(screen.getByText('admin.scholars.control.holdNeedsPayments'))).toBe(true)
  })
})
