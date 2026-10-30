/**
 * @jest-environment node
 *
 * ⚠ THE SCHOLARSHIP PICKER DOES NOT FILTER BY RESULTS UNLESS THE STUDENT ASKS (owner, 2026-10-30).
 *
 * The course guide (dashboard, search, course and pathway pages) shows what a student's results
 * qualify her for. The scholarship side asks her to NAME the course and institution she holds or
 * awaits an offer for, so its lists are the whole catalogue; "Eligible only" (default off) is the
 * one door to the eligibility endpoints, and it lives in `lib/planEligibility.ts`, reached only by
 * an `import()` that runs when she switches it on. Mirrors `lib/bumiputera.scope.test.ts` (Option A).
 *
 * A CLOSED SET on purpose: a web file outside the course guide that calls an eligibility endpoint
 * is the defect this guards against, so a new one must be added below beside its reason.
 */
import * as path from 'path'

import { floorCount, readWeb, walkFloor, WEB_ROOT } from '@/test/sourceGuard'

const ELIGIBILITY = /\b(checkEligibility|checkStpmEligibility|calculatePathways|searchStpmCourses)\b/

/** Every non-test web file that may name an eligibility endpoint, and why. */
const MAY_ASK: Record<string, string> = {
  'src/lib/api.ts': 'the barrel re-exports them',
  'src/lib/api/courses.ts': 'declares checkEligibility',
  'src/lib/api/stpm.ts': 'declares the STPM check and search',
  'src/lib/api/calculations.ts': 'declares calculatePathways',
  'src/app/dashboard/page.tsx': 'course guide: the results dashboard',
  'src/app/search/page.tsx': 'course guide: search and its own "eligible only"',
  'src/app/pathway/matric/page.tsx': 'course guide: the matriculation page',
  'src/app/pathway/stpm/page.tsx': 'course guide: the Form 6 page',
  'src/components/HigherRouteDegrees.tsx': "course guide: the third route's degree browse",
  'src/lib/planEligibility.ts': 'the scholarship picker\'s "Eligible only" — loaded only when switched on',
}

/** The scholarship picker's own modules: none may name an eligibility endpoint. */
const PICKER = [
  'src/app/scholarship/apply/page.tsx',
  'src/app/profile/page.tsx',
  'src/components/PathwayPicker.tsx',
  'src/components/scholarship/LazyPathwayPicker.tsx',
  'src/components/scholarship/InstitutionCoursePicker.tsx',
  'src/components/ProgrammePicker.tsx',
  'src/components/PathwaySelect.tsx',
  'src/lib/planPicker.ts',
]

/** A static or dynamic import of the module (a comment naming it is not one). */
const IMPORTS_IT = /from '@\/lib\/planEligibility'|import\('@\/lib\/planEligibility'\)/

const sources = () => walkFloor(path.join(WEB_ROOT, 'src'), 400, 'every web source file',
  { exts: ['.ts', '.tsx'] })
  .map((f) => path.relative(WEB_ROOT, f).split(path.sep).join('/'))
  .filter((f) => !/\.test\.tsx?$/.test(f) && !f.includes('/__tests__/'))

it('only the course guide and "Eligible only" name an eligibility endpoint', () => {
  const askers = sources().filter((f) => ELIGIBILITY.test(readWeb(f, 'scanned for eligibility calls'))).sort()
  expect(askers).toEqual(Object.keys(MAY_ASK).sort())
})

it('the picker modules exist and none of them names an eligibility endpoint', () => {
  for (const f of PICKER) expect(readWeb(f, 'a scholarship picker module (unfiltered by default)')).not.toMatch(ELIGIBILITY)
})

it('"Eligible only" really asks the eligibility endpoints (the positive half)', () => {
  const src = readWeb('src/lib/planEligibility.ts', 'the one results-based narrowing')
  for (const fn of ['checkEligibility', 'checkStpmEligibility', 'calculatePathways']) expect(src).toContain(fn)
})

it('the picker reaches "Eligible only" by import() alone, behind the switch', () => {
  const importers = floorCount(
    sources().filter((f) => IMPORTS_IT.test(readWeb(f, 'scanned for planEligibility imports'))),
    1, 'importers of lib/planEligibility', 'the picker must reach it')
  expect(importers).toEqual(['src/components/PathwayPicker.tsx'])
  const picker = readWeb('src/components/PathwayPicker.tsx', 'the shared Plans picker')
  // a type import (erased) and one dynamic import(), inside the effect that waits for the switch
  expect(picker).toMatch(/import type \{ PlanEligibility \} from '@\/lib\/planEligibility'/)
  expect(picker.match(/import\('@\/lib\/planEligibility'\)/g)?.length).toBe(1)
  expect(picker).not.toMatch(/^import \{[^}]*\} from '@\/lib\/planEligibility'/m)
  expect(picker).toMatch(/if \(!eligibleOnly \|\| elig/)
})
