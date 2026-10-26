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

  it.each(['matric', 'asasi', 'diploma'])(
    'a %s holder gets the UNFILTERED degree list (D2) — never an eligibility check fed nothing',
    async (kind) => {
      (searchStpmCourses as jest.Mock).mockClear()
      mount({ ...sandboxProfileStpm, results_held: kind, higher_cgpa: 3.4 })
      await waitFor(() => expect(searchStpmCourses).toHaveBeenCalledWith({}, { token: 'tkn' }))
      expect(checkStpmEligibility).not.toHaveBeenCalled()
      expect(checkEligibility).not.toHaveBeenCalled()
    })
})
