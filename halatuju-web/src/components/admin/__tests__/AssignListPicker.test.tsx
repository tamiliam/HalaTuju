/**
 * @jest-environment jsdom
 *
 * T1-e (owner D7, 2026-11-09): THE CASE LIST'S ASSIGN DROPDOWN OFFERS ONLY WHO MAY TAKE THIS CASE.
 *
 * The server serves `assignable` per person (the Reviewers table, fenced to an org admin's own
 * organisation) and each list row serves its gifts (`gift_ids`). The list hides anyone not
 * assignable and anyone of another gift, keeps the current holder whatever they are, treats a
 * reviewer with no gifts as covering every gift, and says what ✓ and ⚠ mean.
 *
 * Synthetic names only.
 */
import { render, screen } from '@testing-library/react'

import { AssigneeOptions, AssignLangNote } from '../AssignListPicker'
import { listAssignees, type Reviewer } from '@/lib/assignOptions'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const GIFT_A = 11
const GIFT_B = 22
const rv = (id: number, over: Partial<Reviewer> = {}): Reviewer =>
  ({ id, name: `Reviewer ${id}`, role: 'reviewer', languages: ['ms'], assignable: true, gifts: [], ...over })

const roster: Reviewer[] = [
  rv(1, { gifts: [{ id: GIFT_A }] }),                        // covers this case
  rv(2, { gifts: [{ id: GIFT_B }] }),                        // another gift
  rv(3),                                                     // every gift
  rv(4, { role: 'admin', assignable: false }),               // not in Reviewers
  rv(5, { role: 'admin', assignable: false, gifts: [{ id: GIFT_B }] }),  // neither
]
const row = (over = {}) =>
  ({ assigned_to_id: null, assigned_to_name: null, call_language: 'ms', gift_ids: [GIFT_A], ...over })
const ids = (rows: Reviewer[]) => rows.map((r) => r.id)

describe('who the list offers for one case', () => {
  it('hides a person who is not assignable', () => {
    expect(ids(listAssignees(roster, row(), true))).not.toContain(4)
  })

  it('hides a reviewer of another gift', () => {
    expect(ids(listAssignees(roster, row(), true))).not.toContain(2)
  })

  it('offers the gift\'s own reviewer and an every-gift reviewer', () => {
    expect(ids(listAssignees(roster, row(), true))).toEqual([1, 3])
  })

  it('shows an every-gift reviewer for a case of any gift', () => {
    expect(ids(listAssignees(roster, row({ gift_ids: [GIFT_B] }), false))).toEqual([2, 3])
    expect(ids(listAssignees([rv(3)], row({ gift_ids: [99] }), false))).toEqual([3])
  })

  it('keeps the current holder even when they are neither assignable nor of this gift', () => {
    expect(ids(listAssignees(roster, row({ assigned_to_id: 5 }), true))).toEqual([1, 3, 5])
  })

  it('narrows nothing by gift when the case\'s gifts are unknown', () => {
    expect(ids(listAssignees(roster, row({ gift_ids: [] }), true))).toEqual([1, 2, 3])
    expect(ids(listAssignees(roster, row({ gift_ids: undefined }), true))).toEqual([1, 2, 3])
  })

  it('renders the holder as an option and hides the others', () => {
    render(<select aria-label="assign"><AssigneeOptions reviewers={roster} row={row({ assigned_to_id: 5 })} isSuper /></select>)
    const names = screen.getAllByRole('option').map((o) => o.textContent)
    expect(names).toEqual(['admin.scholarship.unassigned', '✓ Reviewer 1', '✓ Reviewer 3', '✓ Reviewer 5'])
  })

  it('still names a holder the served list does not carry', () => {
    render(<select aria-label="assign"><AssigneeOptions reviewers={roster} row={row({ assigned_to_id: 77, assigned_to_name: 'Former Holder' })} isSuper /></select>)
    expect(screen.getByRole('option', { name: 'Former Holder' })).toBeTruthy()
  })
})

describe('the ✓ / ⚠ legend', () => {
  it('renders under the preferred language', () => {
    const { container } = render(<AssignLangNote lang="ta" className="x" />)
    expect(container.querySelector('[data-assign-legend]')?.textContent).toBe('admin.scholarship.assignLangLegend')
  })

  it('is not shown when the student named no single language', () => {
    const { container } = render(<AssignLangNote lang="mixed" className="x" />)
    expect(container.textContent).toBe('')
  })

  it('is written in all three languages and keeps both marks', () => {
    for (const m of [en, ms, ta]) {
      const text = (m as { admin: { scholarship: { assignLangLegend: string } } }).admin.scholarship.assignLangLegend
      expect(text).toContain('✓')
      expect(text).toContain('⚠')
    }
  })
})
