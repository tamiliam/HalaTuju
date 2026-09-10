/**
 * @jest-environment jsdom
 *
 * The sponsor's portfolio detail page — the spending panel's PRESENCE (S5).
 *
 * ⚠ FOUND BY A SILENT BITE-CHECK, 2026-09-10. Making the panel render unconditionally failed
 * nothing: `SpendingCard.test.tsx` proves the card once it HAS data, and nothing proved the page's
 * decision not to show it. The harm is specific: a student we have received no report for would
 * show four zeroes and an empty donut, which reads as *"they have spent nothing"* — a claim we
 * cannot make, when the likelier truth is that no report has reached us yet.
 */
import { render, screen, waitFor } from '@testing-library/react'
import MyStudentDetailPage from './page'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/sponsor-auth-context', () => ({ useSponsorAuth: () => ({ token: 'tok' }) }))
jest.mock('next/navigation', () => ({ useParams: () => ({ id: '7' }) }))
jest.mock('react-markdown', () => ({
  __esModule: true, default: ({ children }: { children: string }) => <div>{children}</div>,
}))
jest.mock('@/lib/api')

const mockApi = api as jest.Mocked<typeof api>

const SPENDING: api.SponsorSpending = {
  promised: '2000.00', released: '1400.00', spent: '1120.00', left: '280.00',
  as_at: '2026-09-10',
  categories: [{ code: 'food', label: 'Food & drink', total: '1120.00' }],
}

const detail = (spending: api.SponsorSpending | null) => ({
  id: 1,
  status: 'active',
  amount: '2000.00',
  offered_at: null,
  accept_deadline: null,
  decided_at: null,
  onboarded: true,
  semesters: 1,
  anon_profile: 'A reviewed profile.',
  spending,
  student: {
    id: 7, reference: 'B40-0119', portfolio_status: 'on_track', progress_state: 'studying',
  },
}) as unknown as api.SponsorMyStudentDetail

beforeEach(() => jest.clearAllMocks())

it('shows the spending panel when there is something to show', async () => {
  mockApi.getMyStudentDetail.mockResolvedValue(detail(SPENDING))
  render(<MyStudentDetailPage />)
  await waitFor(() => expect(screen.queryByTestId('spending-card')).not.toBeNull())
})

it('shows NO panel — not four zeroes — when nothing has been imported', async () => {
  // ⚠ THE HARM. An empty card is a claim; an absent card is the truth.
  mockApi.getMyStudentDetail.mockResolvedValue(detail(null))
  render(<MyStudentDetailPage />)
  await waitFor(() => expect(screen.queryByText('sponsorPortal.myStudents.detail.spend.none'))
    .not.toBeNull())
  expect(screen.queryByTestId('spending-card')).toBeNull()
})

it('never claims the feature is "coming soon" once it has shipped', async () => {
  // ⚠ Copy asserting a capability's ABSENCE goes stale the day it ships. Both keys were retired
  // from all three locales; this proves the page stopped asking for them.
  mockApi.getMyStudentDetail.mockResolvedValue(detail(null))
  render(<MyStudentDetailPage />)
  await waitFor(() => expect(screen.queryByText('sponsorPortal.myStudents.detail.spend.none'))
    .not.toBeNull())
  // ⚠ Written as PARTIAL key paths on purpose. `sponsor-i18n.test.ts` scans this file for literal
  // `sponsorPortal.…` keys and demands each resolve in en.json — and these two no longer exist,
  // which is the whole point. Spelling them in full here would make the scanner fail on a test
  // asserting their absence. (It caught exactly that, and it was right to.)
  expect(document.body.textContent).not.toContain('.detail.soon')
  expect(document.body.textContent).not.toContain('.detail.spendingSoon')
})
