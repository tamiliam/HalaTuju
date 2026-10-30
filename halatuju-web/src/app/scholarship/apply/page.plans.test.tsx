/**
 * @jest-environment jsdom
 *
 * The apply form's "My Plans" step, mounted (Scholarship My Plans redesign, owner rulings 2026-10-30).
 * The picker's own behaviour is `components/PathwayPicker.test.tsx`; this file pins what the PAGE
 * adds around it:
 *   - "Eligible only" sits in the step card's header, beside "4. My Plans" (the approved mock-up),
 *     and only on the offer branch;
 *   - a named place reads back to her with the offer-letter note, and the pick lands in the form
 *     with the institution, so the submit payload carries it (`buildApplicationPayload`, unit-tested);
 *   - the waiting branch keeps its optional answers and the free-text note.
 *
 * `t` echoes its key, so assertions read against i18n keys.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileSpm } from '@/sandbox/fixtures/scholarship'

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
  getPathwayOfferings: jest.fn(() => Promise.resolve({
    pathway: 'poly',
    institutions: [{ id: 'PUO', institution_id: 'PUO', name: 'Politeknik Ungku Omar', state: 'Perak', course_ids: ['ELEK'] }],
    courses: [{ course_id: 'ELEK', course_name: 'Diploma Kejuruteraan Elektrik', field_key: 'elek', aliran: null }],
  })),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const SPM = { ...sandboxProfileSpm, results_exam_type: 'spm', results_held: 'spm' }

const openPlans = async () => {
  render(
    <AuthContext.Provider value={{ status: 'ready', profile: SPM, token: 'tkn', showAuthGate: () => {} } as never}>
      <ScholarshipApplyPage />
    </AuthContext.Provider>,
  )
  const tabs = await screen.findAllByText('scholarship.apply.section.plans')
  fireEvent.click(tabs[0].closest('button') as HTMLButtonElement)
  return screen.findByText(/^4\. scholarship\.apply\.section\.plans$/)
}
const press = async (key: string) =>
  fireEvent.click((await screen.findByText(key)).closest('button') as HTMLButtonElement)

it('draws "Eligible only" in the card header, beside the step title, on the offer branch only', async () => {
  const heading = await openPlans()
  await press('scholarship.apply.plan.uncertain')
  expect(screen.queryByRole('switch', { name: 'search.eligibleOnly' })).toBeNull()
  await press('scholarship.apply.plan.sure')
  const sw = await screen.findByRole('switch', { name: 'search.eligibleOnly' })
  expect(sw.getAttribute('aria-checked')).toBe('false')                    // default OFF
  expect(heading.parentElement?.contains(sw)).toBe(true)                   // the header row
})

it('a named place reads back with the offer-letter note', async () => {
  await openPlans()
  await press('scholarship.apply.plan.sure')
  fireEvent.change(screen.getByLabelText('scholarship.apply.plan.pathwayLabel'), { target: { value: 'poly' } })
  const state = await screen.findByLabelText('scholarship.apply.plan.stateLabel')
  fireEvent.change(state, { target: { value: 'Perak' } })
  fireEvent.change(screen.getByLabelText('scholarship.apply.plan.institutionLabel.poly'), { target: { value: 'PUO' } })
  fireEvent.focus(screen.getByPlaceholderText('scholarship.apply.plan.programmePlaceholder'))
  fireEvent.click(screen.getByText('Diploma Kejuruteraan Elektrik'))
  await waitFor(() => expect(screen.getByTestId('plan-named').textContent)
    .toBe('Diploma Kejuruteraan Elektrik · Politeknik Ungku Omar, Perak'))
  expect(screen.getByText('scholarship.apply.plan.offerNote')).toBeTruthy()
  expect(screen.getByText('scholarship.apply.plan.uncertainNoteLabel')).toBeTruthy()   // the note stays
})

it('the waiting branch keeps its optional answers and the note', async () => {
  await openPlans()
  await press('scholarship.apply.plan.uncertain')
  expect(screen.getByText('scholarship.apply.plan.uncertainIntro')).toBeTruthy()
  expect(screen.getByText('scholarship.apply.plan.leaningLabel')).toBeTruthy()
  expect(screen.getByText('scholarship.apply.plan.reasonLabel')).toBeTruthy()
  expect(screen.getByText('scholarship.apply.plan.uncertainNoteLabel')).toBeTruthy()
  expect(screen.queryByText('scholarship.apply.plan.offerNote')).toBeNull()
})
