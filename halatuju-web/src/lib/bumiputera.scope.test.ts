/**
 * @jest-environment node
 *
 * ⚠ WHO MAY READ THE BUMIPUTERA ANSWER IN THE BROWSER — a CLOSED set (Bumi coverage Sprint B).
 *
 * The answer is COURSE-GUIDE ONLY (owner ruling 2026-10-28). The scholarship side — the apply form,
 * /profile's "Your Plans" (PathwayPicker), sponsor and admin screens — never reads it: by Option A
 * its programme pickers offer every course to every student, and (owner, 2026-10-30) never narrow
 * by the student's results either unless she switches "Eligible only" on — that half is guarded by
 * `lib/planPicker.scope.test.ts`. The set is closed on purpose: one
 * extra reader IS the defect, so a new file reading `.bumiputera` must be added here beside the
 * reason it is course-guide, or the guard goes red.
 */
import * as path from 'path'

import { readWeb, walkFloor, WEB_ROOT } from '@/test/sourceGuard'

/** Each course-guide file that reads the answer, and why it may. */
const COURSE_GUIDE_READERS: Record<string, string> = {
  'src/lib/bumiputera.ts': 'the one rule (Malaysian + yes)',
  'src/app/onboarding/profile/page.tsx': 'asks the question and saves the answer',
  'src/app/dashboard/page.tsx': 'the course-guide results: STPM check + degree browse',
  'src/app/profile/page.tsx': "the student's own /profile: shows and edits her answer",
  'src/components/profile/BumiputeraField.tsx': "/profile's Yes/No pair and read-only row (its i18n keys, onboarding.bumiputera, match too)",
  'src/components/AuthGateModal.tsx': 'sign-in sync: sends the answer given before sign-in',
  'src/lib/auth-context.tsx': 'hydrates this browser from the server profile',
  'src/lib/api/courses.ts': 'course search request parameter',
  'src/lib/api/stpm.ts': 'STPM search request parameter',
}

const READS = /\.bumiputera\b|\[['"]bumiputera['"]\]/

it('only the course-guide files read the Bumiputera answer', () => {
  const files = walkFloor(path.join(WEB_ROOT, 'src'), 400, 'every web source file',
                          { exts: ['.ts', '.tsx'] })
    .map((f) => path.relative(WEB_ROOT, f).split(path.sep).join('/'))
    .filter((f) => !/\.test\.tsx?$/.test(f))
  const readers = files.filter((f) => READS.test(readWeb(f, 'scanned for reads of the answer'))).sort()
  expect(readers).toEqual(Object.keys(COURSE_GUIDE_READERS).sort())
})

// `lib/degreeChoices.ts` (the degree loader this read until 2026-10-30) left with the unfiltered
// picker: the lists now come from the catalogue (`getPathwayOfferings`), and the only results-based
// narrowing is "Eligible only" in `lib/planEligibility.ts` — which must still include Bumi-only courses.
it('"Eligible only" sends bumiputera: true and never reads the answer (Option A)', () => {
  const src = readWeb('src/lib/planEligibility.ts', 'the one results-based narrowing of the scholarship picker')
  expect(src).not.toMatch(READS)
  expect(src).not.toMatch(/isBumiputera/)
  expect(src).toMatch(/checkEligibility\(\{ \.\.\.profile, bumiputera: true \}/)   // the SPM check
  expect(src).toMatch(/^\s+bumiputera: true,/m)                                   // the STPM check
})
