/**
 * @jest-environment node
 *
 * ⚠ WHO MAY READ THE BUMIPUTERA ANSWER IN THE BROWSER — a CLOSED set (Bumi coverage Sprint B).
 *
 * The answer is COURSE-GUIDE ONLY (owner ruling 2026-10-28). The scholarship side — the apply form,
 * /profile's "Your Plans" (PathwayPicker), sponsor and admin screens — never reads it: by Option A
 * its programme pickers offer every course to every student. The set is closed on purpose: one
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

it('the scholarship degree loader takes its scope from the caller, never the profile', () => {
  const src = readWeb('src/lib/degreeChoices.ts', 'the apply / Your Plans programme list (Option A)')
  expect(src).not.toMatch(READS)
  expect(src).not.toMatch(/isBumiputera/)
})
