/**
 * @jest-environment jsdom
 *
 * Owner ruling 2026-10-28 (Bumi coverage, Option A): the apply form's programme picker offers EVERY
 * course — Bumiputera-only ones included — to EVERY student, and never reads the Bumiputera answer.
 * That answer is course-guide only (the s44(6) stance: the bursary does not collect ethnicity); a
 * wrong pick is corrected by the offer letter.
 *
 * Since 2026-10-30 the picker lists the CATALOGUE (`getPathwayOfferings`), which serves every course
 * with no student in the request at all; "Eligible only" (opt-in) still sends `bumiputera: true`.
 * Until then this file asserted the eligibility check's `bumiputera: true` on mount.
 *
 * Mounted: the claims are about the request the page makes and the list the student can pick from.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileSpm, sandboxProfileStpm } from '@/sandbox/fixtures/scholarship'
import { checkEligibility, checkStpmEligibility, getPathwayOfferings } from '@/lib/api'

const mockRouter = { push: jest.fn(), replace: jest.fn() }
jest.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
  usePathname: () => '/scholarship/apply',
  useSearchParams: () => new URLSearchParams(),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  tOr: (t: (k: string) => string, k: string, fallback: string) => (t(k) === k ? fallback : t(k)),
}))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getScholarshipIntake: jest.fn(() => Promise.resolve({ open: true, choices: [] })),
  getMyScholarshipApplications: jest.fn(() => Promise.resolve({ applications: [] })),
  getApplyGate: jest.fn(() => Promise.resolve({ allowed: true, reason: '', application_id: null })),
  checkEligibility: jest.fn(() => Promise.resolve({ pathway_stats: {}, eligible_courses: [] })),
  calculatePathways: jest.fn(() => Promise.resolve({ pathways: [] })),
  // What the server answers to bumiputera=true: the Bumi-only UiTM course is in the list.
  checkStpmEligibility: jest.fn(() => Promise.resolve({ eligible_courses: [{ course_id: 'UITM-BUMI' }], total_eligible: 1 })),
  // The catalogue: the Bumi-only UiTM degree is served like any other.
  getPathwayOfferings: jest.fn(() => Promise.resolve({
    pathway: 'degree',
    institutions: [{ id: 'UITM', institution_id: 'UITM', name: 'Universiti Teknologi MARA', state: 'Selangor', course_ids: ['UITM-BUMI'] }],
    courses: [{ course_id: 'UITM-BUMI', course_name: 'Ijazah Sarjana Muda Seni Bina (UiTM)', field_key: 'senibina', aliran: null }],
  })),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const STPM = { ...sandboxProfileStpm, results_exam_type: 'stpm', results_held: 'stpm', nationality: 'malaysian' }

const mount = (profile: Record<string, unknown>) => render(
  <AuthContext.Provider value={{ status: 'ready', profile, token: 'tkn', showAuthGate: () => {} } as never}>
    <ScholarshipApplyPage />
  </AuthContext.Provider>,
)
const openOffer = async () => {
  const tabs = await screen.findAllByText('scholarship.apply.section.plans')
  fireEvent.click(tabs[0].closest('button') as HTMLButtonElement)
  fireEvent.click((await screen.findByText('scholarship.apply.plan.sure')).closest('button') as HTMLButtonElement)
}

beforeEach(() => { jest.clearAllMocks() })

it.each([
  ['answered No', { bumiputera: false }],
  ['never answered', { bumiputera: null }],
  ['an older profile without the field', {}],
])('a student who %s is offered the Bumi-only course in the programme picker', async (_label, answer) => {
  mount({ ...STPM, ...answer })
  await openOffer()
  const uni = await screen.findByLabelText('scholarship.apply.plan.institutionLabel.university')
  fireEvent.change(uni, { target: { value: 'UITM' } })
  fireEvent.focus(screen.getByPlaceholderText('scholarship.apply.plan.programmePlaceholder'))
  expect(await screen.findByText(/Seni Bina \(UiTM\)/)).toBeTruthy()
  expect(getPathwayOfferings).toHaveBeenCalledWith('degree')       // the catalogue: no student in it
  expect(checkStpmEligibility).not.toHaveBeenCalled()
})

it('"Eligible only" still includes Bumi-only courses: the STPM check is sent bumiputera: true', async () => {
  mount({ ...STPM, bumiputera: false })
  await openOffer()
  fireEvent.click(screen.getByRole('switch', { name: 'search.eligibleOnly' }))
  await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
  expect((checkStpmEligibility as jest.Mock).mock.calls[0][0].bumiputera).toBe(true)
})

// Bumi Sprint D1: the SPM course list has Bumi-only (UiTM) rows too. "Eligible only" sends the SPM
// check `bumiputera: true` whatever the stored answer — every course, as above.
it.each([false, null, undefined])('an SPM student (stored answer %s) is sent the whole SPM list', async (answer) => {
  mount({ ...sandboxProfileSpm, results_exam_type: 'spm', results_held: 'spm', bumiputera: answer })
  await openOffer()
  expect(checkEligibility).not.toHaveBeenCalled()                   // nothing asked until she switches it on
  fireEvent.click(screen.getByRole('switch', { name: 'search.eligibleOnly' }))
  await waitFor(() => expect(checkEligibility).toHaveBeenCalled())
  expect((checkEligibility as jest.Mock).mock.calls[0][0].bumiputera).toBe(true)
})

it('never reads the stored Bumiputera answer', async () => {
  const reads: string[] = []
  const profile = new Proxy({ ...STPM, bumiputera: false }, {
    get(target, key, recv) {
      if (key === 'bumiputera') reads.push(new Error().stack ?? '')
      return Reflect.get(target, key, recv)
    },
  })
  mount(profile)
  await openOffer()
  fireEvent.click(screen.getByRole('switch', { name: 'search.eligibleOnly' }))
  await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
  expect(reads).toEqual([])
})
