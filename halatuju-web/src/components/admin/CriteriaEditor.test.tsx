/**
 * @jest-environment jsdom
 *
 * The criteria editor's layout and copy (editor fixes, owner 2026-11-27). Pinned:
 *  1. "Student must pass" and its buttons sit on the right of the row.
 *  2. The course-start box sits on the right of its label, in the same row (not under it).
 *  3. No "SPM grades" header above the grade rules.
 *  4. The grade-rule number box and grade drop-down are as wide as the other rows' boxes.
 *  5-7. The copy: SPM merit hint, the per-person label (no hint), "their highest result".
 *  8. The results join shows ONLY when both results groups are switched on.
 *  9. The joins run strict to loose.
 */
import { render, screen, within } from '@testing-library/react'

import CriteriaEditor, { INCOME_JOINS, RESULTS_JOINS } from './CriteriaEditor'
import { EMPTY_STATE, stateToTree, type EditorState } from '@/lib/criteriaTree'
import en from '@/messages/en.json'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k }),
}))

const draw = (over: Partial<EditorState> = {}) =>
  render(<CriteriaEditor state={{ ...EMPTY_STATE, ...over }} onChange={() => {}} idPrefix="ed" />)

const FULL: Partial<EditorState> = {
  postOn: true, pngkOn: true, pngk: '2', spmOn: true, spmMeritOn: true, spmMerit: '50',
  rows: [{ count: '3', grade: 'C' }], householdOn: true, household: '5000', perPersonOn: true,
  perPerson: '1000', startOn: true, startYears: '2026',
}

const crit = (en as unknown as { admin: { criteria: Record<string, Record<string, unknown>> } }).admin.criteria

describe('layout', () => {
  it('1. the join row is pushed to the right', () => {
    draw(FULL)
    expect(screen.getByTestId('ed-results-join').className).toContain('justify-end')
    expect(screen.getByTestId('ed-income-join').className).toContain('justify-end')
  })

  it('2. the course-start box is a sibling of its label in one row, not under it', () => {
    draw(FULL)
    const card = screen.getByTestId('ed-start')
    const box = screen.getByTestId('ed-start-years')
    expect(box.parentElement).toBe(card)
    expect(card.className).not.toContain('flex-wrap')
    expect(box.className).not.toContain('mt-2')
    expect(box.className).toContain('w-28')
  })

  it('3. no "SPM grades" header above the grade rules', () => {
    draw(FULL)
    const grades = screen.getByTestId('ed-grades')
    expect(within(grades).queryByText('admin.criteria.grades.title')).toBeNull()
    expect('title' in crit.grades).toBe(false)
  })

  it('4. the grade-rule boxes are as wide as the other rows\' boxes', () => {
    draw(FULL)
    const other = screen.getByTestId('ed-household-value').className
    expect(screen.getByTestId('grade-row-0-count').className).toBe(other)
    expect(screen.getByTestId('grade-row-0-grade').className).toBe(other)
  })
})

describe('copy (en)', () => {
  it('5. the SPM merit hint', () => {
    expect(crit.spm.meritHint).toBe('Out of 100, from the grades and Co-curricular marks.')
  })

  it('6. the per-person label, and its hint is gone', () => {
    expect(crit.income.perPerson).toBe('Income per person at most (RM per month)')
    expect('perPersonHint' in crit.income).toBe(false)
    draw(FULL)
    expect(screen.getByTestId('ed-per-person').textContent).toBe('admin.criteria.income.perPerson')
  })

  it('7. "own" reads "their highest result"', () => {
    expect(crit.join.own).toBe('their highest result')
  })
})

describe('8. the results join shows only when both results groups are on', () => {
  it.each([
    [false, false, false], [true, false, false], [false, true, false], [true, true, true],
  ])('post %s, SPM %s -> shown %s', (postOn, spmOn, shown) => {
    draw({ postOn, spmOn })
    expect(screen.queryByTestId('ed-results-join') !== null).toBe(shown)
  })

  it('never lets a void SPM door through: both groups on under "any" with no grade rule is refused', () => {
    // criteria.py VOID_SPM_DOOR: the join only shows with both groups on, and then the editor's own
    // check (stateToTree) blocks the save, so hiding the join opens no way round the server rule.
    const both = { ...EMPTY_STATE, postOn: true, pngkOn: true, pngk: '2', spmOn: true, rows: [] }
    expect(stateToTree({ ...both, resultsJoin: 'any' }).problems).toContain('voidSpmDoor')
    expect(stateToTree({ ...both, resultsJoin: 'any', rows: [{ count: '1', grade: 'C' }] }).problems)
      .not.toContain('voidSpmDoor')
    expect(stateToTree({ ...both, spmOn: false, resultsJoin: 'any' }).problems).not.toContain('voidSpmDoor')
  })
})

describe('9. strict to loose', () => {
  it('results: all | their highest result | any; income: all | any', () => {
    expect(RESULTS_JOINS).toEqual(['all', 'own', 'any'])
    expect(INCOME_JOINS).toEqual(['all', 'any'])
    draw(FULL)
    const order = (id: string) => within(screen.getByTestId(id)).getAllByRole('radio')
      .map((b) => b.getAttribute('data-testid'))
    expect(order('ed-results-join')).toEqual(['ed-results-join-all', 'ed-results-join-own', 'ed-results-join-any'])
    expect(order('ed-income-join')).toEqual(['ed-income-join-all', 'ed-income-join-any'])
  })
})
