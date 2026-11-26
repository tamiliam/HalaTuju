// The criteria editor's model (criteria editor Sprint 4): the stored criteria TREE <-> the boxes
// on the screen. Pure, no React, so every live shape is pinned by a unit test.
//
// THE TREE (halatuju_api apps/scholarship/criteria.py, the gate reads it):
//   { all: [results?, merit?, income?, born_in?], flag?: [course_start_year] }
// * results: { section, own|all|any: [ {route:'post_spm', all:[min_pngk?]}, {route:'spm', all:[grade_count...]} ] }
//   'own' (owner ruling B, 26 Nov) = each student is judged on the group for the results they hold.
// * merit: { section, all: [min_upu_merit? (SPM holders), min_merit? (post-SPM holders)] } - the
//   screen shows each merit inside its group, as v9 does.
// * income: { section, any|all: [household_income_max?, income_per_person_under?] }
// * born_in: { section, any: [state keys] }
// * flag: course_start_year - flags a student for the reviewer, never declines.
//
// ⚠ A SAVE MUST NEVER CHANGE MEANING SILENTLY. `canShow` proves the screen can say a stored tree
// exactly (tree -> boxes -> tree gives the same tree, order aside); when it cannot, the editor says
// so and will not save, rather than rebuilding a different tree from the boxes.
//
// ⚠ A 0 IS A RULE, NOT A BLANK. Intake 3 stores grade counts of 0 ("SPM grades must be given"),
// so a row with count 0 is ON with value 0. Only an empty box is "not filled in".

import { toggleBirthState } from './birthStates'

export const GRADES = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C'] as const
export type Grade = typeof GRADES[number]
export type ResultsJoin = 'own' | 'all' | 'any'
export type IncomeJoin = 'all' | 'any'

/** Typo guards the server enforces on a save (criteria_write.py). */
export const PNGK_MAX = 4
export const MERIT_MAX = 100
export const COUNT_MAX = 20
export const RM_MAX = 100000
export const YEAR_MIN = 2000
export const YEAR_MAX = 2100

export interface GradeRow { count: string; grade: Grade }

export interface EditorState {
  resultsJoin: ResultsJoin
  postOn: boolean
  pngkOn: boolean
  pngk: string
  postMeritOn: boolean
  postMerit: string
  spmOn: boolean
  rows: GradeRow[]
  spmMeritOn: boolean
  spmMerit: string
  incomeJoin: IncomeJoin
  householdOn: boolean
  household: string
  perPersonOn: boolean
  perPerson: string
  bornIn: string[]
  startYears: string
}

// The stored tree, loosely typed: it comes from the server and `canShow` checks it.
type Json = Record<string, unknown>
export type CriteriaTree = { all: Json[]; flag?: Json[] }

export const EMPTY_STATE: EditorState = {
  resultsJoin: 'own', postOn: false, pngkOn: false, pngk: '', postMeritOn: false, postMerit: '',
  spmOn: false, rows: [], spmMeritOn: false, spmMerit: '',
  incomeJoin: 'any', householdOn: false, household: '', perPersonOn: false, perPerson: '',
  bornIn: [], startYears: '',
}

const str = (v: unknown) => (typeof v === 'number' ? String(v) : '')
const asList = (v: unknown): Json[] => (Array.isArray(v) ? v as Json[] : [])

function modeOf(sec: Json): [string, Json[]] {
  for (const k of ['own', 'all', 'any']) if (k in sec) return [k, asList(sec[k])]
  return ['', []]
}

function find(tests: Json[], test: string): Json | undefined {
  return tests.find((t) => t.test === test)
}

/** The stored tree -> the boxes. Anything the boxes cannot hold is dropped here and caught by
 *  `canShow`, so the editor never saves a tree built from a partial reading. */
export function treeToState(tree: CriteriaTree | null | undefined): EditorState {
  const s: EditorState = { ...EMPTY_STATE, rows: [], bornIn: [] }
  for (const sec of asList(tree?.all)) {
    const [mode, items] = modeOf(sec)
    if (sec.section === 'results') {
      if (mode === 'own' || mode === 'all' || mode === 'any') s.resultsJoin = mode
      for (const g of items) {
        const tests = asList(g.all)
        if (g.route === 'post_spm') {
          s.postOn = true
          const p = find(tests, 'min_pngk')
          if (p) { s.pngkOn = true; s.pngk = str(p.value) }
        } else if (g.route === 'spm') {
          s.spmOn = true
          s.rows = tests.filter((t) => t.test === 'grade_count').map((t) => ({
            count: str(t.at_least),
            grade: (GRADES as readonly string[]).includes(t.grade_or_better as string)
              ? t.grade_or_better as Grade : 'C',
          }))
        }
      }
    } else if (sec.section === 'merit') {
      const upu = find(items, 'min_upu_merit')
      if (upu) { s.spmMeritOn = true; s.spmMerit = str(upu.value) }
      const pm = find(items, 'min_merit')
      if (pm) { s.postMeritOn = true; s.postMerit = str(pm.value) }
    } else if (sec.section === 'income') {
      if (mode === 'all' || mode === 'any') s.incomeJoin = mode
      const h = find(items, 'household_income_max')
      if (h) { s.householdOn = true; s.household = str(h.rm) }
      const pp = find(items, 'income_per_person_under')
      if (pp) { s.perPersonOn = true; s.perPerson = str(pp.rm) }
    } else if (sec.section === 'born_in') {
      s.bornIn = (Array.isArray(sec.any) ? sec.any as unknown[] : [])
        .filter((k): k is string => typeof k === 'string')
    }
  }
  const flag = asList(tree?.flag).find((f) => f.test === 'course_start_year')
  if (flag) s.startYears = asList(flag.allowed).map(String).join(', ')
  return s
}

/** One reason the boxes cannot be saved: an i18n key under `admin.criteria.problem`. */
export type Problem =
  | 'pngkBlank' | 'pngkRange' | 'meritBlank' | 'meritRange' | 'countBlank' | 'countRange'
  | 'incomeBlank' | 'incomeRange' | 'years' | 'empty' | 'voidSpmDoor' | 'voidSpmGroup'
  | 'postNoFloor' | 'resultsNoTest'

const num = (s: string) => (s.trim() === '' ? NaN : Number(s.trim()))
const isWhole = (n: number) => Number.isInteger(n) && n >= 0

/** The boxes -> the tree to save, with every reason it may not be saved (`[]` = it may). The tree
 *  is canonical: sections, groups and tests in the order `from_legacy` writes them. */
export function stateToTree(s: EditorState): { tree: CriteriaTree; problems: Problem[] } {
  const problems = new Set<Problem>()
  const sections: Json[] = []

  const groups: Json[] = []
  const merit: Json[] = []
  if (s.postOn) {
    const tests: Json[] = []
    if (s.pngkOn) {
      const v = num(s.pngk)
      if (Number.isNaN(v)) problems.add('pngkBlank')
      else if (v < 0 || v > PNGK_MAX) problems.add('pngkRange')
      tests.push({ test: 'min_pngk', value: v })
    }
    groups.push({ route: 'post_spm', all: tests })
  }
  if (s.spmOn) {
    const tests = s.rows.map((r) => {
      const n = num(r.count)
      if (Number.isNaN(n)) problems.add('countBlank')
      else if (!isWhole(n) || n > COUNT_MAX) problems.add('countRange')
      return { test: 'grade_count', at_least: n, grade_or_better: r.grade }
    })
    groups.push({ route: 'spm', all: tests })
  }
  const meritTest = (on: boolean, value: string, test: string) => {
    if (!on) return
    const v = num(value)
    if (Number.isNaN(v)) problems.add('meritBlank')
    else if (v < 0 || v > MERIT_MAX) problems.add('meritRange')
    merit.push({ test, value: v })
  }
  meritTest(s.spmOn && s.spmMeritOn, s.spmMerit, 'min_upu_merit')
  meritTest(s.postOn && s.postMeritOn, s.postMerit, 'min_merit')

  if (groups.length) sections.push({ section: 'results', [s.resultsJoin]: groups })
  if (merit.length) sections.push({ section: 'merit', all: merit })

  const income: Json[] = []
  const rm = (on: boolean, value: string, test: string) => {
    if (!on) return
    const v = num(value)
    if (Number.isNaN(v)) problems.add('incomeBlank')
    else if (!isWhole(v) || v > RM_MAX) problems.add('incomeRange')
    income.push({ test, rm: v })
  }
  rm(s.householdOn, s.household, 'household_income_max')
  rm(s.perPersonOn, s.perPerson, 'income_per_person_under')
  if (income.length) sections.push({ section: 'income', [s.incomeJoin]: income })

  // toggleBirthState returns the keys in the screen's fixed order; removing '' changes nothing else.
  const states = toggleBirthState(s.bornIn, '', false)
  if (states.length) sections.push({ section: 'born_in', any: states })

  const tree: CriteriaTree = { all: sections }
  const tokens = s.startYears.split(/[\s,]+/).filter(Boolean)
  if (tokens.length) {
    const years = tokens.map(Number)
    if (years.some((y) => !Number.isInteger(y) || y < YEAR_MIN || y > YEAR_MAX)) problems.add('years')
    tree.flag = [{ test: 'course_start_year', allowed: [...new Set(years)].sort((a, b) => a - b) }]
  }

  if (!sections.length) problems.add('empty')

  // The server's write rules (Sprint 3 review R1): a post-SPM group needs its minimum CGPA (a
  // post-SPM merit is read from it), and a results section must test something unless a merit
  // section binds its students.
  if (s.postOn && !s.pngkOn) problems.add('postNoFloor')
  if (groups.length && groups.every((g) => asList(g.all).length === 0) && !merit.length) {
    problems.add('resultsNoTest')
  }

  // The void SPM trap (criteria.py VOID_SPM_DOOR / VOID_SPM_GROUP): an SPM group that cannot fail
  // beside a post-SPM group lets every SPM holder through.
  if (s.postOn && s.spmOn && s.resultsJoin !== 'all') {
    const gradeCanFail = s.rows.some((r) => num(r.count) > 0)
    const meritCanFail = s.spmMeritOn && num(s.spmMerit) > 0
    if (s.resultsJoin === 'any' && !gradeCanFail) problems.add('voidSpmDoor')
    if (s.resultsJoin === 'own' && !gradeCanFail && !meritCanFail) problems.add('voidSpmGroup')
  }
  return { tree, problems: [...problems] }
}

const SECTION_ORDER = ['results', 'merit', 'income', 'born_in']
const TEST_ORDER = ['min_upu_merit', 'min_merit', 'household_income_max', 'income_per_person_under']

/** The tree in canonical order, so two trees that mean the same compare equal. Grade rows keep
 *  their order (the admin's own order). */
function canonical(tree: CriteriaTree): string {
  const all = asList(tree?.all).map((sec) => {
    const [mode, items] = modeOf(sec)
    let list = items
    if (sec.section === 'results') {
      list = [...items].sort((a, b) => (a.route === 'post_spm' ? -1 : 0) - (b.route === 'post_spm' ? -1 : 0))
    } else if (sec.section === 'merit' || sec.section === 'income') {
      list = [...items].sort((a, b) => TEST_ORDER.indexOf(a.test as string) - TEST_ORDER.indexOf(b.test as string))
    }
    return { ...sec, [mode]: list }
  }).sort((a, b) => SECTION_ORDER.indexOf(a.section as string) - SECTION_ORDER.indexOf(b.section as string))
  const out: CriteriaTree = { all }
  if (asList(tree?.flag).length) out.flag = tree.flag
  return JSON.stringify(out, (_k, v) => (v && typeof v === 'object' && !Array.isArray(v)
    ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, v[k]])) : v))
}

/** True when the screen can say ``tree`` exactly. False = show the "cannot show" notice and do
 *  not save (a save would rebuild a different tree from the boxes). */
export function canShow(tree: CriteriaTree | null | undefined): boolean {
  if (!tree) return false
  return canonical(stateToTree(treeToState(tree)).tree) === canonical(tree)
}

/** Whether two sets of boxes say the same tree (the Save button's "is there a change"). */
export function sameTree(a: EditorState, b: EditorState): boolean {
  return canonical(stateToTree(a).tree) === canonical(stateToTree(b).tree)
}

/** An API error code -> its i18n key under `admin.criteria.error`. Unknown codes are generic. */
export const ERROR_KEYS: Record<string, string> = {
  criteria_required: 'generic',
  unknown_field: 'generic',
  intake_id_required: 'generic',
  bad_criteria: 'badCriteria',
  rules_error: 'rulesError',
  criteria_not_built: 'notBuilt',
  rule_year_changed: 'ruleYearChanged',
  criteria_changed: 'criteriaChanged',
  rules_beyond_columns: 'beyondColumns',
  not_found: 'notFound',
  no_intake_year: 'notFound',
  forbidden: 'forbidden',
  network_failure: 'network',
}

export function errorKey(code: string | undefined, status?: number): string {
  if (code && ERROR_KEYS[code]) return `admin.criteria.error.${ERROR_KEYS[code]}`
  if (status === 403) return 'admin.criteria.error.forbidden'
  return 'admin.criteria.error.generic'
}
