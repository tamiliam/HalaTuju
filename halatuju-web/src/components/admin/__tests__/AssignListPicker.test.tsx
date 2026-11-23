/**
 * @jest-environment jsdom
 *
 * T1-e (owner D7, 2026-11-09): THE ASSIGN DROPDOWN (now the case page's) OFFERS ONLY WHO MAY TAKE THIS CASE.
 * F1 / I-13: the case list holds no picker; its "Assigned" cell is plain text from `AssignedCell`.
 *
 * The server serves `assignable` per person (the Reviewers table, fenced to an org admin's own
 * organisation) and each list row serves its gifts (`gift_ids`). The list hides anyone not
 * assignable and anyone of another gift, keeps the current holder whatever they are, treats a
 * reviewer with no gifts as covering every gift.
 *
 * Synthetic names only.
 */
import { render, screen } from '@testing-library/react'

import { AssignedCell, AssignLangNote } from '../AssignListPicker'
import { listAssignees, type Reviewer } from '@/lib/assignOptions'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { formatDate } from '@/lib/formatDate'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${Object.values(p).join(',')}` : k) }) }))

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

  it('hides a paused reviewer, but keeps a paused holder', () => {
    const paused = [rv(1, { paused: true }), rv(3)]
    expect(ids(listAssignees(paused, row(), true))).toEqual([3])
    expect(ids(listAssignees(paused, row({ assigned_to_id: 1 }), true))).toEqual([1, 3])
  })

  it('hides a paused reviewer even when the case\'s gift is unknown', () => {
    expect(ids(listAssignees([rv(1, { paused: true }), rv(3)], row({ gift_ids: [] }), true))).toEqual([3])
  })
})

const cell = (over = {}) => ({
  status: 'profile_complete', assigned_to_id: null, assigned_to_name: null, call_language: 'ta',
  ready_for_assignment: true, ready_on: null, ...over,
})
const renderCell = (over = {}) =>
  render(<AssignedCell row={cell(over)} className="main" noteClassName="note" />).container

describe('the list Assigned cell (F1 / I-13)', () => {
  it('names the reviewer at any stage, and never renders a select', () => {
    for (const status of ['profile_complete', 'interviewing', 'rejected', 'accepted']) {
      const c = renderCell({ status, assigned_to_id: 4, assigned_to_name: 'Rohini' })
      expect(c.textContent).toBe('Rohini')
      expect(c.querySelector('select')).toBeNull()
    }
  })

  it('says Waiting for a reviewer with the language note when ready and nobody holds it', () => {
    const c = renderCell()
    expect(c.textContent).toContain('admin.programmeOverview.attention.unassigned')
    expect(c.querySelector('.note')?.textContent).toContain('admin.scholarship.prefersLang')
    expect(c.querySelector('select')).toBeNull()
  })

  it('leaves out the language note when the student named no single language', () => {
    expect(renderCell({ call_language: 'mixed' }).querySelector('.note')).toBeNull()
  })

  it('says Not ready yet with Ready on <date> inside the 5-day window', () => {
    const c = renderCell({ ready_for_assignment: false, ready_on: '2026-12-01T09:00:00+08:00' })
    expect(c.textContent).toContain('admin.scholarship.assignedCell.notReady')
    expect(c.querySelector('.note')?.textContent).toBe(`admin.scholarship.assignedCell.readyOn|${formatDate('2026-12-01T09:00:00+08:00')}`)
  })

  it('says Not ready yet without a date note when none is served', () => {
    expect(renderCell({ ready_for_assignment: false }).textContent).toBe('admin.scholarship.assignedCell.notReady')
  })

  it('shows a dash for any other stage with nobody', () => {
    for (const status of ['submitted', 'shortlisted', 'interviewing', 'rejected']) {
      expect(renderCell({ status }).textContent).toBe('—')
    }
  })

  it('has its new strings in all three languages', () => {
    for (const m of [en, ms, ta]) {
      const c = (m as { admin: { scholarship: { assignedCell: { notReady: string; readyOn: string } } } }).admin.scholarship.assignedCell
      expect(c.notReady.length).toBeGreaterThan(0)
      expect(c.readyOn).toContain('{date}')
    }
  })
})

describe('the Prefers note', () => {
  it('shows the preferred language and nothing for a mixed one', () => {
    expect(render(<AssignLangNote lang="ta" className="x" />).container.textContent).not.toBe('')
    expect(render(<AssignLangNote lang="mixed" className="x" />).container.textContent).toBe('')
  })
})
