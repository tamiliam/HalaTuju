/**
 * @jest-environment jsdom
 *
 * "Apply gift clarity" D1 (2026-10-05) — the application page shows the application the apply form
 * sent the student here for.
 *
 * It used to show only a LIVE application (shortlisted and later), so a student whose only
 * application was `submitted` read "You haven't applied yet", pressed "Start your application", and
 * was bounced straight back here by the form. The neutral "received" card meant for her could not be
 * reached. Both pages now read `applicationScreen` / `mustLeaveApplyPage` (applicationScreen.ts).
 *
 * `t` echoes its key.
 */
import { render, screen } from '@testing-library/react'
import ScholarshipApplicationPage from './page'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ status: 'ready', token: 'tok', profile: null }),
}))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)
jest.mock('@/components/ScholarshipNextSteps', () => () => null)
jest.mock('@/components/ActionCentre', () => () => null)
jest.mock('@/components/scholarship/LazyInterviewBookingPanel', () => () => null)
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

type AppsReply = Awaited<ReturnType<typeof api.getMyScholarshipApplications>>
type AwardReply = Awaited<ReturnType<typeof api.getStudentAward>>

const ROUND = 'BrightPath Bursary Programme 2026'
const serve = (...apps: { id: number; status: string; cohort_name?: string }[]) =>
  mockApi.getMyScholarshipApplications.mockResolvedValue({ applications: apps } as unknown as AppsReply)

beforeEach(() => {
  jest.resetAllMocks()
  mockApi.getStudentAward.mockResolvedValue({ offer: null, is_minor: false } as AwardReply)
})

it('a lone SUBMITTED application shows the "received" card — not "you haven\'t applied"', async () => {
  serve({ id: 1, status: 'submitted', cohort_name: ROUND })
  render(<ScholarshipApplicationPage />)
  expect(await screen.findByText('scholarship.application.receivedTitle')).toBeTruthy()
  expect(screen.queryByText('scholarship.application.none')).toBeNull()
})

it('a lone EXPIRED application reads "you haven\'t applied" — the form will let her start again', async () => {
  serve({ id: 1, status: 'expired', cohort_name: ROUND })
  render(<ScholarshipApplicationPage />)
  expect(await screen.findByText('scholarship.application.none')).toBeTruthy()
  expect(screen.queryByTestId('application-gift-line')).toBeNull()
})

it('names the gift (round) the application is for, under the title', async () => {
  serve({ id: 1, status: 'submitted', cohort_name: ROUND })
  render(<ScholarshipApplicationPage />)
  const line = await screen.findByTestId('application-gift-line')
  expect(line.textContent).toContain('scholarship.application.giftLabel')
  expect(line.textContent).toContain(ROUND)
})

it.each(['rejected', 'withdrawn', 'closed'])(
  'a lone %s application shows the neutral "closed" card — not "received", not the raw status',
  async (status) => {
    serve({ id: 1, status, cohort_name: ROUND })
    render(<ScholarshipApplicationPage />)
    expect(await screen.findByText('scholarship.application.finishedTitle')).toBeTruthy()
    expect(screen.getByText('scholarship.application.finishedBody')).toBeTruthy()
    expect(screen.getByText('scholarship.application.homeCta')).toBeTruthy()      // onward links
    expect(screen.queryByText('scholarship.application.receivedTitle')).toBeNull()
    expect(screen.queryByText('scholarship.application.none')).toBeNull()
    expect(screen.queryByText(new RegExp(status))).toBeNull()
    expect(screen.getByTestId('application-gift-line').textContent).toContain(ROUND)
  },
)

it('several finished applications, none submitted → the "closed" card, naming no gift', async () => {
  serve({ id: 1, status: 'rejected', cohort_name: ROUND }, { id: 2, status: 'withdrawn', cohort_name: 'Other' })
  render(<ScholarshipApplicationPage />)
  expect(await screen.findByText('scholarship.application.finishedTitle')).toBeTruthy()
  expect(screen.queryByText('scholarship.application.multiple.title')).toBeNull()
  expect(screen.queryByTestId('application-gift-line')).toBeNull()   // no single gift to name
})

it('two submitted applications → the "more than one" message', async () => {
  serve({ id: 1, status: 'submitted' }, { id: 2, status: 'submitted' })
  render(<ScholarshipApplicationPage />)
  expect(await screen.findByText('scholarship.application.multiple.title')).toBeTruthy()
  expect(screen.queryByText('scholarship.application.none')).toBeNull()
})
