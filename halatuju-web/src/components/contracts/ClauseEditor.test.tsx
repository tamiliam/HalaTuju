/**
 * @jest-environment jsdom
 *
 * Request #6 — the Save button must be dead when there is nothing to save.
 *
 * ⚠ These are RENDERED tests, not tests of `clauseFingerprint` alone. A unit test on the helper
 * would pass just as happily with the helper wired to nothing, and this repo has already been
 * bitten by exactly that (see the parentage-marker lesson). What is worth protecting is that the
 * BUTTON goes dead — so every assertion here goes through the component.
 *
 * Why the fault mattered: `contracts.replace_clauses` DELETES every clause row and recreates it,
 * so a save that changes nothing still churns the rows and moves the "last changed" time of a
 * document people sign — with no field anywhere recording who did it.
 */
import { fireEvent, render, screen } from '@testing-library/react'

import ClauseEditor from './ClauseEditor'
import type { ContractTemplateDetail } from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const putContractClauses = jest.fn()
jest.mock('@/lib/admin-api', () => ({
  putContractClauses: (...a: unknown[]) => putContractClauses(...a),
  importContractDocx: jest.fn(),
  updateContractConfig: jest.fn(),
  putContractSchedule: jest.fn(),
  // The schedule editor offers a "copy from another template" control; a refusal just hides it.
  getContractTemplates: jest.fn(() => Promise.resolve({ templates: [] })),
}))

const clause = (over: Record<string, unknown> = {}) => ({
  order: 1, level: 0,
  heading_en: 'Duties', heading_ms: 'Tugas', heading_ta: 'கடமைகள்',
  body_en: 'The student shall study.', body_ms: '', body_ta: '',
  is_quiz_candidate: false, quiz_en: {}, quiz_ms: {}, quiz_ta: {},
  ...over,
})

const template = (over: Partial<ContractTemplateDetail> = {}) => ({
  id: 1, status: 'draft', clauses: [clause()], ...over,
}) as unknown as ContractTemplateDetail

const saveBtn = () =>
  screen.getByText('admin.contracts.saveClauses').closest('button') as HTMLButtonElement

const show = (over: Partial<ContractTemplateDetail> = {}) =>
  render(<ClauseEditor template={template(over)} token="t" onChange={jest.fn()} />)

describe('the Save button reflects whether anything changed', () => {
  it('starts DISABLED on an untouched template', () => {
    show()
    expect(saveBtn().disabled).toBe(true)
  })

  it('says why it is disabled rather than looking broken', () => {
    show()
    expect(saveBtn().title).toBe('common.nothingToSave')
  })

  it('wakes up when a clause body is edited', () => {
    show()
    fireEvent.change(screen.getByPlaceholderText('admin.contracts.body'),
      { target: { value: 'The student shall study diligently.' } })
    expect(saveBtn().disabled).toBe(false)
    expect(saveBtn().title).toBe('')   // the DOM reports an absent title as ''
  })

  it('wakes up when a clause is ADDED, not only when text is typed', () => {
    // Structure counts: add, delete, move and indent all change what would be written.
    show()
    fireEvent.click(screen.getByText('admin.contracts.addClause'))
    expect(saveBtn().disabled).toBe(false)
  })

  it('does NOT wake up merely because a different language tab is opened', () => {
    // Switching tabs re-renders and re-reads the drafts; it changes nothing that would be saved.
    show()
    fireEvent.click(screen.getByText('ms'))
    expect(saveBtn().disabled).toBe(true)
  })

  it('goes back to sleep when an edit is typed and then undone', () => {
    // The comparison is by VALUE against what was loaded, not a one-way "touched" latch — so
    // restoring the original text must disarm the button again.
    show()
    const body = screen.getByPlaceholderText('admin.contracts.body')
    fireEvent.change(body, { target: { value: 'changed' } })
    expect(saveBtn().disabled).toBe(false)
    fireEvent.change(body, { target: { value: 'The student shall study.' } })
    expect(saveBtn().disabled).toBe(true)
  })

  it('cannot be pressed while it is disabled', () => {
    // The one that actually protects the rows: no request, so nothing is deleted and recreated.
    show()
    fireEvent.click(saveBtn())
    expect(putContractClauses).not.toHaveBeenCalled()
  })
})

/**
 * The other three Saves in this module. The original report said "in the contracts module, and
 * PERHAPS ELSEWHERE AS WELL" — I fixed two of four and called it done, and the owner found the
 * config Save still live on the next screen along. Enumerating the module's save controls takes a
 * minute; being told twice costs more.
 */
import ConfigForm from './ConfigForm'
import ScheduleEditor from './ScheduleEditor'

const cfgTemplate = (over: Record<string, unknown> = {}) => ({
  id: 1, status: 'draft', clauses: [], schedule: [],
  title_en: 'Bursary agreement', title_ms: '', title_ta: '',
  preamble_en: '', preamble_ms: '', preamble_ta: '',
  progress_standard_en: '', progress_standard_ms: '', progress_standard_ta: '',
  counterparty_name: 'Tamil Foundation', counterparty_title: '', counterparty_nric: '',
  counterparty_address: '', counterparty_notify_emails: ['a@b.test'],
  parent_role: 'guardian', witness_policy: 'required',
  ...over,
}) as unknown as ContractTemplateDetail

describe('the config Save obeys the same rule', () => {
  const btn = () => screen.getByText('admin.contracts.save').closest('button') as HTMLButtonElement

  it('starts disabled and wakes on a real edit', () => {
    render(<ConfigForm template={cfgTemplate()} token="t" onChange={jest.fn()} />)
    expect(btn().disabled).toBe(true)
    fireEvent.change(screen.getByDisplayValue('Bursary agreement'),
      { target: { value: 'Bursary agreement v2' } })
    expect(btn().disabled).toBe(false)
  })

  it('counts a field that is NOT the title — the check must cover the whole patch', () => {
    // The failure this guards is silent and one-directional: a field that is editable but absent
    // from the comparison leaves Save dead on a genuine edit.
    render(<ConfigForm template={cfgTemplate()} token="t" onChange={jest.fn()} />)
    fireEvent.change(screen.getByDisplayValue('a@b.test'),
      { target: { value: 'a@b.test, c@d.test' } })
    expect(btn().disabled).toBe(false)
  })
})

describe('the payment-schedule Save obeys the same rule', () => {
  it('starts disabled on an untouched schedule', () => {
    render(<ScheduleEditor template={cfgTemplate({
      schedule: [{ order: 1, pathway: 'stpm', variant: 'standard', monthly_amount: '250',
                   paid_offsets: [0, 1, 2], label_en: 'Semester 1' }],
    })} token="t" onChange={jest.fn()} />)
    const btn = screen.getByText('admin.contracts.save').closest('button') as HTMLButtonElement
    expect(btn.disabled).toBe(true)
  })
})
