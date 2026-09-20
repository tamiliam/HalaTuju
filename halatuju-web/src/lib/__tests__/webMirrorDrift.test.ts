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
  const cockpit = read('app', 'admin', 'scholarship', '[id]', 'view.tsx')

  test('the cockpit no longer carries a second `status !== shortlisted` test of its own', () => {
    // The comment says this function "Mirrors the Assignment card's long-standing
    // `status !== 'shortlisted'` guard". The end state a mirror wants is one home: the card now
    // calls the pure helper, so there is nothing left to drift. This asserts that it stays so.
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
 * ⚠ PINNED DISAGREEMENT (TD-266) — reported, not fixed, and no winner picked here.
 *
 * `AdminResolutionItem` says it "Mirrors the student-facing ResolutionItem … but kept separate".
 * Both are read from ONE backend serializer (`ResolutionItemSerializer`), and the admin payload's
 * own docstring says it returns "system + officer + **check2**" items — so the admin copy is not a
 * narrower view by design, it is a stale copy: it is missing two `kind` values, one `source`
 * value, and the `vircle_expected` field the serializer always sends.
 *
 * The end state lesson 290 asks for is to DELETE one side. That is a type change under the
 * cockpit, so it is the next sprint's, not this one's. These rows pin the gap so it cannot widen.
 */
describe('PINNED: the two ResolutionItem interfaces have fallen out of step (TD-266)', () => {
  // ⚠ Both sides MOVED at code health H13 — see the note on the booking grid above.
  const student = interfaceFields(
    read('lib', 'api', 'resolution.ts'), 'ResolutionItem', 'lib/api/resolution.ts')
  const admin = interfaceFields(
    read('lib', 'admin-api', 'resolution.ts'), 'AdminResolutionItem', 'lib/admin-api/resolution.ts')

  test('parse sanity: both interfaces parsed', () => {
    expect(Object.keys(student).length).toBeGreaterThan(10)
    expect(Object.keys(admin).length).toBeGreaterThan(10)
  })

  test('the shared fields are declared identically — the half that did NOT drift', () => {
    const shared = Object.keys(admin).filter((k) => k in student && !['kind', 'source'].includes(k))
    expect(shared.length).toBeGreaterThanOrEqual(8)
    for (const key of shared) expect(`${key}: ${admin[key]}`).toBe(`${key}: ${student[key]}`)
  })

  test('the admin copy declares no field the student copy does not', () => {
    expect(Object.keys(admin).filter((k) => !(k in student))).toEqual([])
  })

  test('the gap is exactly the three things named in TD-266', () => {
    expect(Object.keys(student).filter((k) => !(k in admin))).toEqual(['vircle_expected'])
    expect(student.kind).toBe("'doc' | 'confirm' | 'explanation' | 'clarify' | 'human'")
    expect(admin.kind).toBe("'doc' | 'confirm' | 'explanation'")
    expect(student.source).toBe("'system' | 'officer' | 'check2'")
    expect(admin.source).toBe("'system' | 'officer'")
  })
})
