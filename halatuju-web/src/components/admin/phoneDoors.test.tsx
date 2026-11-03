/**
 * @jest-environment jsdom
 *
 * Owner, Mobile M7 (moved into M7a by the M7a review): the decided doors are READ-ONLY ON A PHONE — hidden below
 * md BY WIDTH with a "use a computer" note, the desktop unchanged and wired the same way. This file renders the two
 * component doors (Close file on the scholar file; logging billable hours on a request) and the restacked table's
 * ARIA roles; the page doors (payment run, New payment run, Delete student, a sponsor's gift membership) are pinned
 * by `mobileStandard.test.ts` ("every decided door is read-only on a phone").
 * jsdom applies no media query, so this reads the classes that do the hiding and presses the desktop controls.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarControls from './ScholarControls'
import { RequestHoursForm } from './RequestHoursForm'
import TableFrame from './TableFrame'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const hiddenOnPhone = (el: Element) => !!el.closest('.max-md\\:hidden')
const phoneNote = (el: Element) => el.className.split(' ').includes('md:hidden') && !hiddenOnPhone(el)

const FILE = {
  id: 9, name: 'X', gift: null, course: '', institution: '', status: 'active',
  maintenance_substate: 'on_track', is_on_hold: false, in_maintenance: true, has_file: true,
  closure_reason: '', awarded_at: null, vircle_activated_at: null, closed_at: null,
  latest_result: null, standing: 'no_result_yet',
  money: { award_amount: null, paid_to_date: '0.00', remaining: '0.00', last_payment: null },
  contract: { exists: false, status: null }, mentor: null, letters: [], last_activity_at: null,
  controls: { can_set_substate: false, can_hold: false, close_reasons: ['graduated'], close_refusal: '' },
} as unknown as api.ScholarFile

beforeEach(() => jest.clearAllMocks())

describe('Close file is read-only on a phone', () => {
  it('the reason, the checklist and Close sit in a below-md-hidden box; the phone gets the note', () => {
    render(<ScholarControls file={FILE} token="tok" onChanged={jest.fn()} />)
    expect(hiddenOnPhone(screen.getByRole('combobox'))).toBe(true)
    expect(hiddenOnPhone(screen.getByRole('button', { name: 'admin.scholars.control.closeFile' }))).toBe(true)
    expect(hiddenOnPhone(screen.getByTestId('close-checklist'))).toBe(true)
    expect(phoneNote(screen.getByText('admin.useComputer.close'))).toBe(true)
  })

  it('from md it closes exactly as before: a reason, asked twice, then the close door', async () => {
    mockApi.closeApplication.mockResolvedValue({} as never)
    render(<ScholarControls file={FILE} token="tok" onChanged={jest.fn()} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'graduated' } })
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholars.control.closeFile' }))
    const both = screen.getAllByRole('button', { name: 'admin.scholars.control.closeFile' })
    fireEvent.click(both[both.length - 1])
    await waitFor(() => expect(mockApi.closeApplication).toHaveBeenCalledWith(9, 'graduated', { token: 'tok' }))
  })

  it('a file with nothing to close shows no note', () => {
    render(<ScholarControls file={{ ...FILE, controls: { ...FILE.controls!, close_reasons: [] } } as api.ScholarFile}
      token="tok" onChanged={jest.fn()} />)
    expect(screen.queryByText('admin.useComputer.close')).toBeNull()
  })
})

describe('logging billable hours is read-only on a phone', () => {
  const analysis = {
    id: 5, body: '', estimated_hours: '7.0', actual_hours: null, charged_hours: null, charge_note: '',
    cited_files: [], authored_by: '', repo_sha: '', proposed_kind: '', proposed_lane: '',
    created_at: '', approved_at: null, approved_by_name: '', superseded_at: null, is_current: true,
  } as unknown as api.OrgRequestAnalysis
  const t = (k: string) => k

  it('the only way into the form is below-md-hidden; the phone gets the note; what is recorded stays visible', () => {
    render(<RequestHoursForm analysis={analysis} t={t as never} busy={false} onSave={jest.fn()} />)
    expect(hiddenOnPhone(screen.getByRole('button', { name: 'admin.requests.owner.hoursRecord' }))).toBe(true)
    expect(phoneNote(screen.getByText('admin.useComputer.hours'))).toBe(true)
    expect(hiddenOnPhone(screen.getByText('admin.requests.owner.hoursMissing'))).toBe(false)
  })

  it('from md the button opens the same form', () => {
    render(<RequestHoursForm analysis={analysis} t={t as never} busy={false} onSave={jest.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'admin.requests.owner.hoursRecord' }))
    expect(screen.getByTestId('hours-form-5')).toBeTruthy()
  })
})

describe('a table drawn as rows keeps its table semantics (M7a review: VoiceOver and display:block)', () => {
  const Table = ({ rows }: { rows: string[] }) => (
    <table><thead><tr><th>Name</th><th>When</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r}><td>{r}</td><td data-label="When">today</td></tr>)}</tbody></table>
  )

  it('phoneRows stamps table, rowgroup, row, columnheader and cell — and again when rows arrive', async () => {
    const { rerender } = render(<TableFrame phoneRows label="L"><Table rows={['a']} /></TableFrame>)
    await waitFor(() => expect(screen.getByRole('table')).toBeTruthy())
    expect(screen.getAllByRole('rowgroup')).toHaveLength(2)
    expect(screen.getAllByRole('columnheader')).toHaveLength(2)
    rerender(<TableFrame phoneRows label="L"><Table rows={['a', 'b']} /></TableFrame>)
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(3))
    for (const cell of screen.getAllByRole('cell')) expect(cell.getAttribute('role')).toBe('cell')
  })

  it('without phoneRows the markup is left as it was (no role attributes added)', () => {
    const { container } = render(<TableFrame label="L"><Table rows={['a']} /></TableFrame>)
    expect(container.querySelectorAll('[role="table"], [role="row"], [role="cell"]')).toHaveLength(0)
  })
})
