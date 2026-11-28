/**
 * TD-773: which results note Step 3 of /scholarship/apply shows. Display only; the server's
 * `results_routes` and the student's results decide, and nothing here changes a verdict.
 */
import { resultsRouteNote } from '@/lib/resultsRouteNote'

describe('resultsRouteNote: which note Step 3 shows', () => {
  const KINDS = ['spm', 'stpm', 'matric', 'asasi', 'diploma'] as const

  it('post_spm: the warning to an SPM-only holder, nothing to a post-SPM holder', () => {
    expect(resultsRouteNote('post_spm', 'spm', true)).toBe('needsPostSpm')
    for (const k of KINDS.filter((x) => x !== 'spm')) expect(resultsRouteNote('post_spm', k, true)).toBeNull()
  })

  it('both: the same PNGK hint for STPM, Matriculation, Asasi and Diploma, none for SPM', () => {
    for (const k of ['stpm', 'matric', 'asasi', 'diploma'] as const) expect(resultsRouteNote('both', k, true)).toBe('pngkOnly')
    expect(resultsRouteNote('both', 'spm', true)).toBeNull()
  })

  it("spm, either, no rule and an unread answer show nothing, whatever the results", () => {
    for (const routes of ['spm', 'either', null, undefined] as const) {
      for (const k of KINDS) expect(resultsRouteNote(routes, k, true)).toBeNull()
    }
  })

  it('no results yet: nothing (the card already asks for them)', () => {
    expect(resultsRouteNote('post_spm', 'spm', false)).toBeNull()
    expect(resultsRouteNote('both', 'stpm', false)).toBeNull()
    expect(resultsRouteNote('post_spm', 'spm', false)).toBeNull()
  })
})
