// The criteria tree <-> editor boxes (criteria editor Sprint 4).
import {
  canShow, errorKey, nextGrade, sameTree, serverProblemKey, stateToTree,
  treeToState, EMPTY_STATE, GRADES, type CriteriaTree,
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
    expect([s.startOn, s.startYears]).toEqual([true, '2025, 2026'])
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
    expect(stateToTree({ ...base, startOn: true, startYears: '2025, 20x6' }).problems).toContain('years')
  })
  it('text that is not a number is out of range, never blank', () => {
    const pngk = stateToTree({ ...base, postOn: true, pngkOn: true, pngk: 'abc' }).problems
    expect(pngk).toContain('pngkRange')
    expect(pngk).not.toContain('pngkBlank')
    const merit = stateToTree({ ...base, spmOn: true, rows: [{ count: '3', grade: 'C' }], spmMeritOn: true, spmMerit: 'x' }).problems
    expect(merit).toContain('meritRange')
    expect(merit).not.toContain('meritBlank')
    const count = stateToTree({ ...base, spmOn: true, rows: [{ count: 'two', grade: 'C' }] }).problems
    expect(count).toContain('countRange')
    expect(count).not.toContain('countBlank')
    const income = stateToTree({ ...base, household: 'lots' }).problems
    expect(income).toContain('incomeRange')
    expect(income).not.toContain('incomeBlank')
  })
  it('two grade rows at the same grade', () => {
    const rows = [{ count: '2', grade: 'A-' as const }, { count: '3', grade: 'A-' as const }]
    expect(stateToTree({ ...base, spmOn: true, rows }).problems).toContain('gradeTwice')
    expect(stateToTree({ ...base, spmOn: true, rows: [rows[0], { count: '3', grade: 'C' }] }).problems).toEqual([])
  })
  it('a new grade row takes the lowest grade not used', () => {
    expect(nextGrade([])).toBe('C')
    expect(nextGrade([{ count: '1', grade: 'C' }])).toBe('C+')
    expect(nextGrade(GRADES.map((grade) => ({ count: '1', grade })))).toBe('C')
  })
  it('course start switched on needs a year; switched off it is not applied', () => {
    expect(stateToTree({ ...base, startOn: true, startYears: ' ' }).problems).toContain('yearsBlank')
    const off = stateToTree({ ...base, startOn: false, startYears: '2025' })
    expect(off.problems).toEqual([])
    expect(off.tree.flag).toBeUndefined()
  })
  it('a post-SPM group needs its floor; results must test something', () => {
    expect(stateToTree({ ...base, postOn: true }).problems).toContain('postNoFloor')
    expect(stateToTree({ ...base, spmOn: true }).problems).toContain('resultsNoTest')
    // The API rule (NO_RESULTS_RULE): a merit section is a test, so the results are not empty.
    expect(stateToTree({ ...base, spmOn: true, spmMeritOn: true, spmMerit: '80' }).problems).not.toContain('resultsNoTest')
  })
  it('the void SPM traps', () => {
    const both = { ...base, postOn: true, pngkOn: true, pngk: '3', spmOn: true, rows: [{ count: '0', grade: 'C' as const }] }
    expect(stateToTree({ ...both, resultsJoin: 'any' }).problems).toContain('voidSpmDoor')
    expect(stateToTree({ ...both, resultsJoin: 'own' }).problems).toContain('voidSpmGroup')
    expect(stateToTree({ ...both, resultsJoin: 'own', spmMeritOn: true, spmMerit: '80' }).problems).toEqual([])
    // Only when both groups are on: one group alone is never a void door, whatever the hidden join.
    expect(stateToTree({ ...both, postOn: false, resultsJoin: 'any', rows: [{ count: '1', grade: 'C' as const }] })
      .problems).toEqual([])
    expect(stateToTree({ ...both, spmOn: false, resultsJoin: 'any' }).problems).toEqual([])
  })
  it('one results group saves the standard join "own", whatever the hidden join row says', () => {
    const post = { ...base, postOn: true, pngkOn: true, pngk: '3' }
    const spm = { ...base, spmOn: true, rows: [{ count: '5', grade: 'C' as const }] }
    for (const s of [post, spm]) {
      for (const resultsJoin of ['own', 'all', 'any'] as const) {
        const results = stateToTree({ ...s, resultsJoin }).tree.all.find((x) => x.section === 'results')
        expect(Object.keys(results ?? {}).sort()).toEqual(['own', 'section'])
      }
    }
    const two = stateToTree({ ...post, spmOn: true, rows: [{ count: '5', grade: 'C' as const }], resultsJoin: 'all' })
    expect(two.tree.all.find((x) => x.section === 'results')).toHaveProperty('all')
  })
  it('one income test saves the standard join "any"; two keep the chosen join', () => {
    const household = { ...base, incomeJoin: 'all' as const }
    const perPerson = { ...EMPTY_STATE, perPersonOn: true, perPerson: '1584', incomeJoin: 'all' as const }
    for (const s of [household, perPerson]) {
      const income = stateToTree(s).tree.all.find((x) => x.section === 'income')
      expect(Object.keys(income ?? {}).sort()).toEqual(['any', 'section'])
    }
    const both = stateToTree({ ...household, perPersonOn: true, perPerson: '1584' })
    expect(both.tree.all.find((x) => x.section === 'income')).toHaveProperty('all')
  })
  it('an older tree saved with a non-standard join on one item still shows', () => {
    expect(canShow({ all: [{ section: 'income', all: [{ test: 'household_income_max', rm: 5860 }] }] })).toBe(true)
    expect(canShow({ all: [{ section: 'results', all: [{ route: 'spm', all: [
      { test: 'grade_count', at_least: 5, grade_or_better: 'C' }] }] }] })).toBe(true)
  })
  it('years are sorted and once each', () => {
    expect(stateToTree({ ...base, startOn: true, startYears: '2026, 2025 2026' }).tree.flag)
      .toEqual([{ test: 'course_start_year', allowed: [2025, 2026] }])
  })
  it('sameTree ignores text that means the same', () => {
    expect(sameTree({ ...base, startOn: true, startYears: '2025,2026' }, { ...base, startOn: true, startYears: '2025, 2026' })).toBe(true)
  })
})

describe('error codes', () => {
  it.each([
    ['bad_criteria', 'badCriteria'], ['rules_error', 'rulesError'], ['criteria_not_built', 'notBuilt'],
    ['rule_year_changed', 'ruleYearChanged'], ['criteria_changed', 'criteriaChanged'],
    ['rules_beyond_columns', 'beyondColumns'], ['not_found', 'notFound'], ['no_intake_year', 'notFound'],
    ['network_failure', 'network'], ['criteria_required', 'generic'], ['unknown_field', 'generic'],
    ['intake_id_required', 'generic'], ['something_new', 'generic'], ['digest_required', 'digestRequired'],
  ])('%s -> %s', (code, key) => {
    expect(errorKey(code)).toBe(`admin.criteria.error.${key}`)
  })
  it('a 403 without a known code', () => {
    expect(errorKey(undefined, 403)).toBe('admin.criteria.error.forbidden')
  })
  it('a 404 without a code (criteria_tree.py: a missing intake)', () => {
    expect(errorKey(undefined, 404)).toBe('admin.criteria.error.notFound')
  })
})

describe('the server refusal reasons, in the admin language', () => {
  // The strings criteria.py and criteria_write.py send in a bad_criteria problems list.
  it.each([
    ['the tree checks nothing, so every student would pass: add at least one section', 'empty'],
    ['results: no group holds a rule, so every student passes it - add a rule, or a merit section', 'resultsNoTest'],
    ['results: a post-SPM group needs a min_pngk floor', 'postNoFloor'],
    ['merit: min_merit (the post-SPM merit) needs a post-SPM group with a min_pngk floor', 'meritNeedsFloor'],
    ['results: an SPM group with no rule that can fail, beside a post-SPM group under "any", lets every SPM holder in', 'voidSpmDoor'],
    ['results: an SPM group with no rule that can fail, beside a post-SPM group, lets every SPM holder in', 'voidSpmGroup'],
    ['spm: grade_count repeated', 'gradeTwice'],
    ['spm: grade_count at_least must be 20 or fewer', 'countRange'],
    ['income: household_income_max needs a whole number rm from 0 to 100000', 'incomeRange'],
    ['income: income_per_person_under needs a whole number rm from 0 to 100000', 'incomeRange'],
    ['post_spm: min_pngk needs a number value from 0 to 4', 'pngkRange'],
    ['merit: min_upu_merit needs a number value from 0 to 100', 'meritRange'],
    ['merit: min_merit needs a number value from 0 to 100', 'meritRange'],
    ['course_start_year needs allowed: [...]', 'years'],
  ])('%s', (p, key) => {
    expect(serverProblemKey(p)).toBe(key)
  })
  it('an unknown string has no key (shown under technical detail)', () => {
    expect(serverProblemKey('results: something brand new')).toBeNull()
  })
})
