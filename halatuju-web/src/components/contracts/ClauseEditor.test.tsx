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
    expect(saveBtn().title).toBe('admin.contracts.nothingToSave')
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
