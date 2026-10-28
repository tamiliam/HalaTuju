/**
 * @jest-environment jsdom
 *
 * TD-325 (2026-10-04): the /profile pathway picker chooses the SPM pathway dropdown or the STPM
 * degree picker by the results we HOLD (the served `results_held`, through
 * `profileAcademicSummary`), never the declared exam — the same rule as /apply's Plans step.
 * Which eligibility check it asks for is what decides the branch, so that is what is asserted.
 */
import { render, waitFor } from '@testing-library/react'

import PathwayPicker, { type PathwayForm } from './PathwayPicker'
import { checkEligibility, checkStpmEligibility, searchStpmCourses } from '@/lib/api'
import { sandboxProfileFormSix, sandboxProfileStpm } from '@/sandbox/fixtures/scholarship'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  tOr: (t: (k: string) => string, k: string, fallback: string) => (t(k) === k ? fallback : t(k)),
}))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  checkEligibility: jest.fn(() => Promise.resolve({ pathway_stats: {}, eligible_courses: [] })),
  calculatePathways: jest.fn(() => Promise.resolve({ pathways: [] })),
  checkStpmEligibility: jest.fn(() => Promise.resolve({ eligible_courses: [] })),
  searchStpmCourses: jest.fn(() => Promise.resolve({ courses: [], total_count: 0, filters: {} })),
}))

const FORM: PathwayForm = {
  pathwayCertainty: '', chosenPathway: '', chosenProgramme: null, preUTrack: '',
  preUInstitution: '', pathwaysConsidered: [], uncertaintyReasons: [], uncertaintyNote: '',
}

const mount = (profile: Record<string, unknown>) => render(
  <PathwayPicker value={FORM} onChange={() => {}} profile={profile as never} token="tkn" />,
)

describe('PathwayPicker reads the results held, not the declared exam (TD-325)', () => {
  beforeEach(() => {
    (checkEligibility as jest.Mock).mockClear();
    (checkStpmEligibility as jest.Mock).mockClear()
  })

  it('asks the SPM check for the Form Six explorer the server says holds SPM', async () => {
    mount({ ...sandboxProfileFormSix, results_held: 'spm' })
    await waitFor(() => expect(checkEligibility).toHaveBeenCalled())
    expect(checkStpmEligibility).not.toHaveBeenCalled()
  })

  it('asks the STPM degree check for a student who holds STPM results', async () => {
    mount({ ...sandboxProfileStpm, results_held: 'stpm' })
    await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
    expect(checkEligibility).not.toHaveBeenCalled()
  })

  // Owner ruling 2026-10-28 (Bumi coverage, Option A): "Your Plans" offers EVERY course, Bumi-only
  // included, to EVERY student, and never reads the Bumiputera answer (course-guide only).
  it.each([false, null, undefined, true])(
    'the STPM degree check includes Bumi-only courses whatever the stored answer (%s)', async (answer) => {
      mount({ ...sandboxProfileStpm, results_held: 'stpm', nationality: 'malaysian', bumiputera: answer })
      await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
      expect((checkStpmEligibility as jest.Mock).mock.calls[0][0].bumiputera).toBe(true)
    })

  it('does not read the stored answer at all', async () => {
    const reads: string[] = []
    const profile = new Proxy({ ...sandboxProfileStpm, results_held: 'stpm', bumiputera: false }, {
      get(target, key, recv) { if (key === 'bumiputera') reads.push('read'); return Reflect.get(target, key, recv) },
    })
    mount(profile)
    await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
    expect(reads).toEqual([])
  })

  it.each(['matric', 'asasi', 'diploma'])(
    'a %s holder gets the UNFILTERED degree list (D2) — never an eligibility check fed nothing',
    async (kind) => {
      (searchStpmCourses as jest.Mock).mockClear()
      mount({ ...sandboxProfileStpm, results_held: kind, higher_cgpa: 3.4, bumiputera: false })
      // Every degree, Bumi-only included (Option A), though this student answered No.
      await waitFor(() => expect(searchStpmCourses).toHaveBeenCalledWith({ bumiputera: true }, { token: 'tkn' }))
      expect(checkStpmEligibility).not.toHaveBeenCalled()
      expect(checkEligibility).not.toHaveBeenCalled()
    })
})
