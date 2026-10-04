/**
 * THE DRIFT TEST for the WEB-TO-WEB mirrors — pairs where both copies live in `halatuju-web`, so
 * there is no backend source to read and H9's pattern does not apply (code health H10).
 *
 * The standard does not care which side of the wire a copied rule lives on: "a comment asking two
 * files to stay in step is a request; only a test is a rule." These four pairs are each named by a
 * `drift-test:` marker pointing here.
 *
 * Characterised first (the H8 rule). Three AGREE. One DISAGREES — the two `ResolutionItem`
 * interfaces, which are fed by ONE backend serializer and have fallen out of step. Pinned below
 * as **TD-266**, reported and not fixed: narrowing or widening a type the cockpit reads is a
 * change to what that screen can render, and H10 moves no visible answer.
 *
 * These read source TEXT because a TypeScript interface has no runtime, and because the other
 * copy is a private `const` inside a page component. That is the honest instrument for the
 * question; where a pair has a public seam, the test goes through it instead.
 */
import * as fs from 'fs'
import * as path from 'path'

import { MALAYSIAN_STATES } from '@/lib/scholarship'
import { isPreSubmissionStage, showsPostSubmissionCards } from '@/lib/officerCockpit'
import { readApi } from '@/test/apiSource'

const SRC = path.join(__dirname, '..', '..')

function read(...rel: string[]): string {
  const full = path.join(SRC, ...rel)
  if (!fs.existsSync(full)) {
    throw new Error(
      `drift test: src/${rel.join('/')} is missing. The other half of a keep-in-sync pair has `
      + 'MOVED — follow it, never delete the assertion.')
  }
  return fs.readFileSync(full, 'utf8').replace(/\r\n/g, '\n')
}

/** The string members of a `const NAME = [ … ] as const` array literal. */
function stringArray(text: string, name: string, where: string): string[] {
  const m = text.match(new RegExp(`const ${name}\\s*=\\s*\\[([\\s\\S]*?)\\]`))
  if (!m) throw new Error(`drift test: no \`const ${name} = [ … ]\` in ${where}`)
  return [...m[1].matchAll(/'([^']*)'/g)].map((x) => x[1])
}

/** The declared keys of an `export interface NAME { … }` block, with their declared types. */
function interfaceFields(text: string, name: string, where: string): Record<string, string> {
  const m = text.match(new RegExp(`export interface ${name}[^{]*\\{([\\s\\S]*?)\\n\\}`))
  if (!m) throw new Error(`drift test: no \`export interface ${name} { … }\` in ${where}`)
  const out: Record<string, string> = {}
  for (const f of m[1].matchAll(/^ {2}([a-z_]+)(\??):\s*([^\n]+?)$/gm)) out[f[1]] = f[3].trim()
  return out
}

// ── 1. The Malaysian state list ───────────────────────────────────────────────────────────────
describe('MALAYSIAN_STATES vs the onboarding profile page\'s own list', () => {
  const pageStates = stringArray(
    read('app', 'onboarding', 'profile', 'page.tsx'), 'MALAYSIAN_STATES',
    'app/onboarding/profile/page.tsx')

  test('parse sanity: sixteen states and federal territories', () => {
    expect(pageStates.length).toBe(16)
    expect(pageStates).toContain('Johor')
  })

  test('the same list, in the same order', () => {
    // Order is the dropdown's order on both screens; a student who edits their profile must not
    // meet a differently sorted list from the one they filled in at onboarding.
    expect([...MALAYSIAN_STATES]).toEqual(pageStates)
  })

  test('every federal territory keeps its "W.P." prefix on both sides', () => {
    const wp = pageStates.filter((s) => s.startsWith('W.P. '))
    expect(wp.length).toBe(3)
    expect(MALAYSIAN_STATES.filter((s) => s.startsWith('W.P. '))).toEqual(wp)
  })
})

// ── 2. The served booking grid ────────────────────────────────────────────────────────────────
describe('the booking-grid fields are declared identically on both sides of the wire', () => {
  // The values are SERVED (Org Config Sprint D) — the good pattern. What is mirrored is only the
  // SHAPE, and the student panel's comment says so: "the field list must match the payload it
  // actually receives". The admin picker reads the same payload.
  const GRID = [
    'slot_window_start_min', 'slot_window_end_min', 'slot_step_min',
    'slot_min_lead_hours', 'interview_duration_min',
  ]
  // ⚠ Both sides MOVED at code health H13: `api.ts` and `admin-api.ts` are now barrels and the
  // interfaces live in the module that owns their domain. The paths followed the code — never
  // delete the assertion. `read()` throws loudly if either moves again.
  const student = interfaceFields(
    read('lib', 'api', 'interview.ts'), 'InterviewSchedule', 'lib/api/interview.ts')
  const admin = interfaceFields(
    read('lib', 'admin-api', 'interviews.ts'), 'InterviewSchedule', 'lib/admin-api/interviews.ts')

  test('parse sanity: both interfaces parsed and carry the grid', () => {
    expect(Object.keys(student).length).toBeGreaterThan(5)
    expect(Object.keys(admin).length).toBeGreaterThan(5)
    expect(GRID.filter((f) => !(f in student))).toEqual([])
  })

  test('every grid field is declared on both, with the same type', () => {
    for (const field of GRID) {
      expect(`${field}: ${admin[field]}`).toBe(`${field}: ${student[field]}`)
    }
  })
})

// ── 3. The pre-submission card group ──────────────────────────────────────────────────────────
describe('isPreSubmissionStage vs the Assignment card\'s own guard in view.tsx', () => {
  // ⚠ THE WHOLE COCKPIT, NOT JUST `view.tsx` (code health H14). The screen's panels moved to
  // `[id]/view/`, and the Assignment card — the very card this pair is about — moved with them.
  // Reading only `view.tsx` would have made the two `not.toMatch` assertions below pass because
  // the code is somewhere else, which is the most dangerous way for a guard to be green. It is a
  // WALK, so a panel added or split tomorrow is read the day it lands.
  const COCKPIT_DIR = path.join(SRC, 'app', 'admin', 'scholarship', '[id]', 'view')
  const cockpit = [
    read('app', 'admin', 'scholarship', '[id]', 'view.tsx'),
    ...fs.readdirSync(COCKPIT_DIR)
      .filter((f) => /\.tsx?$/.test(f))
      .map((f) => read('app', 'admin', 'scholarship', '[id]', 'view', f)),
  ].join('\n')


  test('the cockpit no longer carries a second `status !== shortlisted` test of its own', () => {
    // The comment says this function "Mirrors the Assignment card's long-standing
    // `status !== 'shortlisted'` guard". The end state a mirror wants is one home: the card now
    // calls the pure helper, so there is nothing left to drift. This asserts that it stays so.
    // The floor that stops this reading one file again: the screen plus fourteen panel modules.
    expect(fs.readdirSync(COCKPIT_DIR).filter((f) => /\.tsx?$/.test(f)).length)
      .toBeGreaterThanOrEqual(14)
    expect(cockpit).toMatch(/isPreSubmissionStage|showsPostSubmissionCards/)
    expect(cockpit).not.toMatch(/status\s*!==\s*'shortlisted'/)
    expect(cockpit).not.toMatch(/status\s*===\s*'shortlisted'/)
  })

  test('the helper answers only at shortlisted, and the two halves are complements', () => {
    expect(isPreSubmissionStage('shortlisted')).toBe(true)
    for (const status of ['submitted', 'interviewing', 'awarded', '', null, undefined]) {
      expect(isPreSubmissionStage(status)).toBe(false)
      expect(showsPostSubmissionCards(status)).toBe(true)
    }
    expect(showsPostSubmissionCards('shortlisted')).toBe(false)
  })
})

// ── 4. The two ResolutionItem interfaces ──────────────────────────────────────────────────────
/**
 * TD-266 (closed 2026-10-04). `AdminResolutionItem` and `ResolutionItem` are read from ONE backend
 * serializer (`ResolutionItemSerializer`), and the admin payload returns system + officer +
 * **check2** items. Until this date the admin copy was stale — two `kind` values, one `source`
 * value and the `vircle_expected` field short. It now declares what the serializer sends, and these
 * rows hold BOTH halves to that: identical to each other, field for field, and keyed exactly as the
 * serializer's `Meta.fields`. (The cockpit reads `caveats` with no switch over `kind`, so widening
 * the type changed nothing on screen.)
 */
describe("the two ResolutionItem interfaces are one shape, and it is the serializer's (TD-266)", () => {
  // ⚠ Both sides MOVED at code health H13 — see the note on the booking grid above.
  const student = interfaceFields(
    read('lib', 'api', 'resolution.ts'), 'ResolutionItem', 'lib/api/resolution.ts')
  const admin = interfaceFields(
    read('lib', 'admin-api', 'resolution.ts'), 'AdminResolutionItem', 'lib/admin-api/resolution.ts')
  const serializerSrc = readApi('apps/scholarship/serializers.py')
  const block = serializerSrc.match(
    /class ResolutionItemSerializer\(([\s\S]*?)\n\S/)?.[0].match(/fields = \[([\s\S]*?)\]/)
  const served = block ? [...block[1].matchAll(/'([a-z_]+)'/g)].map((x) => x[1]) : []

  test("parse sanity: both interfaces and the serializer's field list parsed", () => {
    expect(Object.keys(student).length).toBeGreaterThan(10)
    expect(Object.keys(admin).length).toBeGreaterThan(10)
    expect(served.length).toBeGreaterThan(10)
  })

  test('the two interfaces declare the same fields with the same types', () => {
    expect(Object.keys(admin).sort()).toEqual(Object.keys(student).sort())
    for (const key of Object.keys(student)) expect(`${key}: ${admin[key]}`).toBe(`${key}: ${student[key]}`)
  })

  test('their keys are exactly what ResolutionItemSerializer sends', () => {
    expect(Object.keys(admin).sort()).toEqual([...served].sort())
  })

  test('the Check 2 values the admin payload carries are declared', () => {
    expect(admin.kind).toBe("'doc' | 'confirm' | 'explanation' | 'clarify' | 'human'")
    expect(admin.source).toBe("'system' | 'officer' | 'check2'")
  })
})
