// The four live intakes' stored criteria trees, as `build_criteria_trees --apply` stores them
// (`from_legacy` of the API fixtures COHORT_1/3/4/5 in halatuju_api apps/scholarship/tests/
// test_criteria.py). Used by the criteria editor tests (Sprint 4).
import type { CriteriaTree } from '@/lib/criteriaTree'

const income = (ceiling: number, perPerson: number) => ({
  section: 'income',
  any: [{ test: 'household_income_max', rm: ceiling }, { test: 'income_per_person_under', rm: perPerson }],
})

export const PENINSULA = ['johor', 'kedah', 'kelantan', 'melaka', 'negeri_sembilan', 'pahang', 'perak',
  'perlis', 'pulau_pinang', 'selangor', 'terengganu', 'wp_kuala_lumpur', 'wp_putrajaya']

/** Intake 1: SPM only - at least 4 at A- or better, at least 5 at B+ or better (a TOTAL). */
export const TREE_1: CriteriaTree = {
  all: [
    { section: 'results', own: [{ route: 'spm', all: [
      { test: 'grade_count', at_least: 4, grade_or_better: 'A-' },
      { test: 'grade_count', at_least: 5, grade_or_better: 'B+' },
    ] }] },
    income(5860, 1584),
  ],
}

/** Intake 3: counts of 0 are REAL rules (ON with value 0), a UPU merit of 0, born in Sabah/Labuan. */
export const TREE_3: CriteriaTree = {
  all: [
    { section: 'results', own: [
      { route: 'post_spm', all: [{ test: 'min_pngk', value: 2.0 }] },
      { route: 'spm', all: [
        { test: 'grade_count', at_least: 0, grade_or_better: 'A-' },
        { test: 'grade_count', at_least: 0, grade_or_better: 'B+' },
        { test: 'grade_count', at_least: 3, grade_or_better: 'C' },
      ] },
    ] },
    { section: 'merit', all: [{ test: 'min_upu_merit', value: 0 }] },
    income(5860, 1180),
    { section: 'born_in', any: ['sabah', 'wp_labuan'] },
  ],
}

/** Intake 4: PNGK 2.0 or at least 3 at C or better. */
export const TREE_4: CriteriaTree = {
  all: [
    { section: 'results', own: [
      { route: 'post_spm', all: [{ test: 'min_pngk', value: 2.0 }] },
      { route: 'spm', all: [{ test: 'grade_count', at_least: 3, grade_or_better: 'C' }] },
    ] },
    income(5860, 1000),
  ],
}

/** Intake 5: the CGPA trap switched off - post-SPM only, the SPM group OFF; course start flagged. */
export const TREE_5: CriteriaTree = {
  all: [
    { section: 'results', own: [{ route: 'post_spm', all: [{ test: 'min_pngk', value: 3.0 }] }] },
    income(5860, 900),
    { section: 'born_in', any: PENINSULA },
  ],
  flag: [{ test: 'course_start_year', allowed: [2025, 2026] }],
}

export const LIVE_TREES = { '1': TREE_1, '3': TREE_3, '4': TREE_4, '5': TREE_5 }
