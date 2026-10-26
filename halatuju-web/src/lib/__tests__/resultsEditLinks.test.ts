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
 * Deliberately the SPM form, for every route: `DocumentHelpCoach`'s "adjust grades" link and the
 * Action Centre "grades" ticket (`ScholarshipNextSteps`, round 2 finding C, superseding round 1's
 * re-route). Both fix the SPM grades the slip is compared with, which the comparison reads from
 * `profile.grades` and only the SPM form writes; the server refuses to let that form demote a
 * tertiary holder (`ProfileUpdateSerializer._never_demote_held_results`). Pinned below so a
 * "tidy-up" cannot re-route them before S3b moves the comparison onto `spm_grades_for`.
 */
import { readWeb } from '@/test/sourceGuard'

describe.each([
  ['src/app/profile/page.tsx', 'the /profile results row (merit / overall CGPA)'],
  ['src/app/onboarding/profile/page.tsx', 'the last onboarding step\'s Back link'],
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

describe.each([
  ['src/components/ScholarshipNextSteps.tsx', /router\.push\('\/onboarding\/grades'\)/],
  ['src/components/DocumentHelpCoach.tsx', /href="\/onboarding\/grades"/],
])('%s keeps the SPM form (until S3b)', (file, link) => {
  const src = readWeb(file, 'the SPM-slip grade fix must open the form that writes profile.grades')
  it('links the SPM form', () => { expect(src).toMatch(link) })
  it('and does not route by results held', () => { expect(src).not.toMatch(/resultsEditPath\(/) })
})

