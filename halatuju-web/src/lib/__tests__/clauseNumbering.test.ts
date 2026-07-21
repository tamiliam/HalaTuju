/**
 * Clause numbering — pinned to the SAME spec as the Django `contracts.clause_numbers` /
 * `normalise_levels` (verified against those functions). If this drifts from the backend, the
 * preview/PDF and the editor would show different numbers — keep the two in lockstep.
 */
import { clauseNumbers, normaliseLevels, canIndent, canOutdent } from '@/lib/clauseNumbering'

describe('clauseNumbers', () => {
  test('three levels: 1. / 1.1. / I. (Word style)', () => {
    expect(clauseNumbers([0, 1, 1, 2, 2, 0, 1, 2]))
      .toEqual(['1.', '1.1.', '1.2.', 'I.', 'II.', '2.', '2.1.', 'I.'])
  })
  test('roman resets under each new parent', () => {
    expect(clauseNumbers([0, 2, 2, 0, 2])).toEqual(['1.', 'I.', 'II.', '2.', 'I.'])
    // NB: [0,2] is only valid post-normalise as [0,1]; clauseNumbers assumes valid input.
  })
  test('roman numerals I..V (uppercase)', () => {
    expect(clauseNumbers([0, 2, 2, 2, 2, 2])).toEqual(['1.', 'I.', 'II.', 'III.', 'IV.', 'V.'])
  })
})

describe('normaliseLevels', () => {
  test('no skipping a level; first forced to 0', () => {
    expect(normaliseLevels([0, 2, 1, 3, 0, 2])).toEqual([0, 1, 1, 2, 0, 1])
    expect(normaliseLevels([2, 1])).toEqual([0, 1])
  })
})

describe('indent/outdent guards', () => {
  test('canIndent requires a shallower-or-equal predecessor and below max', () => {
    const levels = [0, 0, 1, 2]
    expect(canIndent(levels, 0)).toBe(false)   // first row can't indent
    expect(canIndent(levels, 1)).toBe(true)    // 0 under 0 -> can become 1
    expect(canIndent(levels, 3)).toBe(false)   // already at max depth
  })
  test('canOutdent only when deeper than 0', () => {
    expect(canOutdent([0, 1], 0)).toBe(false)
    expect(canOutdent([0, 1], 1)).toBe(true)
  })
})
