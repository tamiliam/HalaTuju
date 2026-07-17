/**
 * @jest-environment jsdom
 *
 * Regression test (2026-07): after a sponsor funds a student, the funded student must drop off
 * the shared "available students" pool list WITHOUT a hard page refresh. The portal fetches its
 * data once on mount, so the fund handler has to ask the context to refresh (refreshPool +
 * refreshWallet). Before the fix the context exposed no refreshPool and the stale card lingered
 * until a full reload / next session ("overnight").
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import StudentDetailPage from './page'
import { fundStudent, getSponsorPoolDetail, getSponsorWallet } from '@/lib/api'

jest.mock('next/navigation', () => ({ useParams: () => ({ id: '5' }) }))
jest.mock('next/link', () => ({ __esModule: true, default: ({ children }: { children: React.ReactNode }) => children }))
jest.mock('react-markdown', () => ({ __esModule: true, default: ({ children }: { children: React.ReactNode }) => children }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/sponsor-auth-context', () => ({ useSponsorAuth: () => ({ token: 'tok' }) }))

const refreshPool = jest.fn()
const refreshWallet = jest.fn()
jest.mock('@/lib/sponsor-portal-context', () => ({
  useSponsorPortal: () => ({ refreshPool, refreshWallet }),
}))

jest.mock('@/lib/api', () => ({
  fundStudent: jest.fn(),
  getSponsorPoolDetail: jest.fn(),
  getSponsorWallet: jest.fn(),
}))

const mockFund = fundStudent as jest.Mock
const mockDetail = getSponsorPoolDetail as jest.Mock
const mockWallet = getSponsorWallet as jest.Mock

beforeEach(() => {
  jest.clearAllMocks()
  mockDetail.mockResolvedValue({
    ref: 'Student A9', state: 'Selangor', field: 'Engineering', academic: '5A 3B',
    funding_categories: ['Fees'], programme_months: 24, enrolment_verified: true,
    anon_profile: '', award_amount: '3000',
  })
  mockWallet.mockResolvedValue({ balance: '5000' })
  mockFund.mockResolvedValue({})
})

it('refreshes the pool + wallet after a successful fund', async () => {
  render(<StudentDetailPage />)

  // Support → Confirm (the i18n mock returns the key as the visible label).
  fireEvent.click(await screen.findByText('sponsorPortal.students.support'))
  fireEvent.click(await screen.findByText('sponsorPortal.students.confirmAward'))

  await waitFor(() => expect(mockFund).toHaveBeenCalledWith(5, { token: 'tok' }))
  // The fix: both shared surfaces are refreshed so the funded student leaves the available
  // list and shows under "My students" without a manual reload.
  await waitFor(() => expect(refreshPool).toHaveBeenCalled())
  expect(refreshWallet).toHaveBeenCalled()
})

it('shows the balance line and renders no facts table (redesign IA)', async () => {
  render(<StudentDetailPage />)
  await screen.findByText('sponsorPortal.students.support')   // detail loaded
  // Sidebar balance line is present (mock wallet resolves to RM 5000).
  await waitFor(() =>
    expect(screen.getByText((_c, node) =>
      node?.tagName === 'P' && (node.textContent || '').includes('sponsorPortal.students.balanceLabel'),
    )).toBeTruthy())
  // The old <dl> facts table is gone — none of its labels render.
  expect(screen.queryByText('sponsorPool.fieldLabel')).toBeNull()
  expect(screen.queryByText('sponsorPool.academicLabel')).toBeNull()
  expect(screen.queryByText('sponsorPool.durationLabel')).toBeNull()
  // The verification strip (our differentiator) is present (emoji-prefixed → substring).
  expect(screen.getByText('sponsorPool.verifiedByBrightPath', { exact: false })).toBeTruthy()
})
