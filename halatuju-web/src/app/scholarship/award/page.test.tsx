/**
 * @jest-environment jsdom
 *
 * TD-229 (2026-10-03): a student signs THEIR GIFT's agreement and nobody else's.
 *
 * When the bursary flag is on and the student's gift has no active agreement template, the
 * server previews nothing and says `bursary_unavailable: 'no_active_template'`. Before this the
 * page fell through to the PLAIN accept flow (no preview means "flag off" to it), and pressing
 * Accept could only fail. Pinned: the page says the agreement is not ready, and offers no Accept.
 */
import { render, screen } from '@testing-library/react'
import ScholarshipAwardPage from './page'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({ useAuth: () => ({ status: 'authenticated', token: 'tok' }) }))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const OFFER = { amount: '3000', accept_deadline: null } as unknown as api.StudentAward

it('a gift with no agreement says so and offers no Accept', async () => {
  mockApi.getStudentAward.mockResolvedValue({
    offer: OFFER, finalising: false, is_minor: false, acceptance_enabled: true,
    bursary_unavailable: 'no_active_template',
  } as unknown as Awaited<ReturnType<typeof api.getStudentAward>>)
  render(<ScholarshipAwardPage />)
  expect((await screen.findByTestId('award-agreement-unavailable')).textContent)
    .toBe('scholarship.award.error.no_active_template')
  expect(screen.queryByText('scholarship.award.confirmed.accept')).toBeNull()
})

it('without the signal the plain offer is unchanged (no notice)', async () => {
  mockApi.getStudentAward.mockResolvedValue({
    offer: OFFER, finalising: false, is_minor: false, acceptance_enabled: true,
  } as unknown as Awaited<ReturnType<typeof api.getStudentAward>>)
  render(<ScholarshipAwardPage />)
  // The positive half of the pair above: the plain Accept IS there when nothing is withheld.
  expect(await screen.findByText('scholarship.award.confirmed.accept')).toBeTruthy()
  expect(screen.queryByTestId('award-agreement-unavailable')).toBeNull()
})
