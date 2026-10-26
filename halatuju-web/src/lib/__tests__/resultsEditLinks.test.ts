/**
 * S2b adversarial review (HIGH) — an edit-results link must open the form for the results the
 * student HOLDS. `/profile`'s results row and the Action Centre's "grades" ticket both sent STPM and
 * third-route holders to the SPM form, and finishing it recorded an SPM completion over theirs.
 *
 * A source guard, on purpose: the claim is STRUCTURAL — "this surface routes through
 * `resultsEditPath`, and names no results form by hand" — and both surfaces are too large to
 * mount for one link (the rule itself is unit-tested in `qualificationDrift.test.ts`). Each file is
 * asserted BOTH ways, so the guard cannot go green by the code leaving the file.
 *
 * The two SPM-slip grade fixes, as a dated sequence: S2b (round 2, finding C, superseding round 1's
 * re-route) pinned BOTH `DocumentHelpCoach`'s "adjust grades" link and the Action Centre "grades"
 * ticket (`ScholarshipNextSteps`) to the SPM form, because the comparison read `profile.grades`,
 * which only the SPM form writes. S3b moved the comparison onto `spm_grades_for` (the STPM /
 * third-route pages' SPM block counts for a tertiary holder), and S4 (2026-10-27) then routed the
 * TICKET by the results HELD, as its brief asked. `DocumentHelpCoach`'s link stays on the SPM form by
 * that same brief: it speaks only about an SPM slip, and since S4 a higher result in the SPM card is
 * never coached at all.
 */
import { readWeb } from '@/test/sourceGuard'

describe.each([
  ['src/app/profile/page.tsx', 'the /profile results row (merit / overall CGPA)'],
  ['src/app/onboarding/profile/page.tsx', 'the last onboarding step\'s Back link'],
  ['src/components/ScholarshipNextSteps.tsx', 'the Action Centre "grades" ticket (S4)'],
])('%s', (file, what) => {
  const src = readWeb(file, `${what} must route by the results held`)
  it('routes through resultsEditPath', () => {
    expect(src).toMatch(/resultsEditPath\(/)
  })
  it('names no results form by hand', () => {
    expect(src).not.toMatch(/['"]\/onboarding\/(grades|stpm-grades|higher-grades)['"]\)?\s*(\}|$|;)/m)
    expect(src).not.toMatch(/router\.push\(['"]\/onboarding\/grades['"]\)/)
    expect(src).not.toMatch(/href="\/onboarding\/grades"/)
  })
})

describe('the Action Centre "grades" ticket (S4)', () => {
  const src = readWeb('src/components/ScholarshipNextSteps.tsx', 'the grades ticket must open the results HELD')
  it('routes by the SERVER\'s results held, never the declaration', () => {
    expect(src).toMatch(/router\.push\(resultsEditPath\(profile\?\.results_held\)\)/)
  })
})

describe.each([
  ['src/components/DocumentHelpCoach.tsx', /href="\/onboarding\/grades"/],
])('%s keeps the SPM form (S4 brief)', (file, link) => {
  const src = readWeb(file, 'the SPM-slip grade fix must open the form that writes profile.grades')
  it('links the SPM form', () => { expect(src).toMatch(link) })
  it('and does not route by results held', () => { expect(src).not.toMatch(/resultsEditPath\(/) })
})
