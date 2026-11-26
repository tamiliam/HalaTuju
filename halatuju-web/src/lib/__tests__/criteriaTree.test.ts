// The criteria tree <-> editor boxes (criteria editor Sprint 4).
import {
  canShow, errorKey, sameTree, stateToTree, treeToState, EMPTY_STATE, GRADES, type CriteriaTree,
} from '../criteriaTree'
import { LIVE_TREES, PENINSULA, TREE_3, TREE_5 } from '@/test/criteriaShapes'

describe('the live intakes', () => {
  it.each(Object.entries(LIVE_TREES))('intake %s round-trips exactly and can be shown', (_n, tree) => {
    expect(canShow(tree)).toBe(true)
    const { tree: back, problems } = stateToTree(treeToState(tree))
    expect(problems).toEqual([])
    expect(back).toEqual(tree)
  })

  it('intake 3 keeps its 0 counts and 0 merit as rules that are ON', () => {
    const s = treeToState(TREE_3)
    expect(s.rows).toEqual([{ count: '0', grade: 'A-' }, { count: '0', grade: 'B+' }, { count: '3', grade: 'C' }])
    expect([s.spmMeritOn, s.spmMerit]).toEqual([true, '0'])
    expect([s.postOn, s.pngkOn, s.pngk]).toEqual([true, true, '2'])
    expect(s.bornIn).toEqual(['sabah', 'wp_labuan'])
  })

  it('intake 5 has its SPM group off and the course-start years', () => {
    const s = treeToState(TREE_5)
    expect([s.spmOn, s.postOn, s.pngk]).toEqual([false, true, '3'])
    expect(s.startYears).toBe('2025, 2026')
    expect(s.bornIn).toEqual(PENINSULA)
    expect([s.householdOn, s.household, s.perPersonOn, s.perPerson, s.incomeJoin])
      .toEqual([true, '5860', true, '900', 'any'])
  })
})

describe('every grade in the list is shown (the old form showed A, B and C+ blank)', () => {
  it.each(['A', 'B', 'C+'])('a count at %s', (grade) => {
    const tree: CriteriaTree = { all: [{ section: 'results', own: [{ route: 'spm', all: [
      { test: 'grade_count', at_least: 2, grade_or_better: grade }] }] }] }
    expect(treeToState(tree).rows).toEqual([{ count: '2', grade }])
    expect(canShow(tree)).toBe(true)
  })
  it('offers all seven grades', () => {
    expect(GRADES).toEqual(['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C'])
  })
})

describe('what cannot be shown is never saved over', () => {
  it('a post-SPM merit with no post-SPM group', () => {
    expect(canShow({ all: [{ section: 'merit', all: [{ test: 'min_merit', value: 80 }] }] })).toBe(false)
  })
  it('an unknown grade, a null tree', () => {
    expect(canShow({ all: [{ section: 'results', own: [{ route: 'spm', all: [
      { test: 'grade_count', at_least: 2, grade_or_better: 'D' }] }] }] })).toBe(false)
    expect(canShow(null)).toBe(false)
  })
  it('order alone is not a difference', () => {
    const shuffled: CriteriaTree = { all: [TREE_3.all[2], TREE_3.all[0], TREE_3.all[1], TREE_3.all[3]] }
    expect(canShow(shuffled)).toBe(true)
  })
})

describe('the boxes the server would refuse', () => {
  const base = { ...EMPTY_STATE, householdOn: true, household: '5860' }
  it('nothing on is an empty tree', () => {
    expect(stateToTree(EMPTY_STATE).problems).toContain('empty')
  })
  it('blank and out-of-range values', () => {
    expect(stateToTree({ ...base, postOn: true, pngkOn: true, pngk: '' }).problems).toContain('pngkBlank')
    expect(stateToTree({ ...base, postOn: true, pngkOn: true, pngk: '30' }).problems).toContain('pngkRange')
    expect(stateToTree({ ...base, household: '5860.5' }).problems).toContain('incomeRange')
    expect(stateToTree({ ...base, spmOn: true, rows: [{ count: '', grade: 'C' }] }).problems).toContain('countBlank')
    expect(stateToTree({ ...base, spmOn: true, rows: [{ count: '21', grade: 'C' }] }).problems).toContain('countRange')
    expect(stateToTree({ ...base, startYears: '2025, 20x6' }).problems).toContain('years')
  })
  it('a post-SPM group needs its floor; results must test something', () => {
    expect(stateToTree({ ...base, postOn: true }).problems).toContain('postNoFloor')
    expect(stateToTree({ ...base, spmOn: true }).problems).toContain('resultsNoTest')
  })
  it('the void SPM traps', () => {
    const both = { ...base, postOn: true, pngkOn: true, pngk: '3', spmOn: true, rows: [{ count: '0', grade: 'C' as const }] }
    expect(stateToTree({ ...both, resultsJoin: 'any' }).problems).toContain('voidSpmDoor')
    expect(stateToTree({ ...both, resultsJoin: 'own' }).problems).toContain('voidSpmGroup')
    expect(stateToTree({ ...both, resultsJoin: 'own', spmMeritOn: true, spmMerit: '80' }).problems).toEqual([])
  })
  it('years are sorted and once each', () => {
    expect(stateToTree({ ...base, startYears: '2026, 2025 2026' }).tree.flag)
      .toEqual([{ test: 'course_start_year', allowed: [2025, 2026] }])
  })
  it('sameTree ignores text that means the same', () => {
    expect(sameTree({ ...base, startYears: '2025,2026' }, { ...base, startYears: '2025, 2026' })).toBe(true)
  })
})

describe('error codes', () => {
  it.each([
    ['bad_criteria', 'badCriteria'], ['rules_error', 'rulesError'], ['criteria_not_built', 'notBuilt'],
    ['rule_year_changed', 'ruleYearChanged'], ['criteria_changed', 'criteriaChanged'],
    ['rules_beyond_columns', 'beyondColumns'], ['not_found', 'notFound'], ['no_intake_year', 'notFound'],
    ['network_failure', 'network'], ['criteria_required', 'generic'], ['unknown_field', 'generic'],
    ['intake_id_required', 'generic'], ['something_new', 'generic'],
  ])('%s -> %s', (code, key) => {
    expect(errorKey(code)).toBe(`admin.criteria.error.${key}`)
  })
  it('a 403 without a known code', () => {
    expect(errorKey(undefined, 403)).toBe('admin.criteria.error.forbidden')
  })
})
