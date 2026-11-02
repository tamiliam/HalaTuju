/**
 * @jest-environment jsdom
 *
 * Regression test (2026-07): after a sponsor funds a student, the funded student must drop off
 * the shared "available students" pool list WITHOUT a hard page refresh. The portal fetches its
 * data once on mount, so the fund handler has to ask the context to refresh (refreshPool +
 * refreshWallet). Before the fix the context exposed no refreshPool and the stale card lingered
 * until a full reload / next session ("overnight").
 */
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import StudentDetailPage from './page'
import { fundStudent, getSponsorPoolDetail, getSponsorWallet } from '@/lib/api'

let routeId = '5'
jest.mock('next/navigation', () => ({ useParams: () => ({ id: routeId }) }))
jest.mock('next/link', () => ({ __esModule: true, default: ({ children }: { children: React.ReactNode }) => children }))
jest.mock('react-markdown', () => ({ __esModule: true, default: ({ children }: { children: React.ReactNode }) => children }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }) }))
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
  routeId = '5'
  mockDetail.mockResolvedValue({
    ref: 'Student A9', state: 'Selangor', field: 'Engineering', academic: '5A 3B',
    institution: 'Politeknik Ungku Omar', school: 'SMK Test', reporting_date: '2026-09-01',
    funding_categories: ['Fees'], programme_months: 24, enrolment_verified: true,
    anon_profile: '', award_amount: '3000',
  })
  mockWallet.mockResolvedValue({ balance: '5000' })
  mockFund.mockResolvedValue({})
})

it('refreshes the pool + wallet after a successful fund', async () => {
  render(<StudentDetailPage />)

  // Fully fund → Confirm (the i18n mock returns the key as the visible label). Mobile M5: the phone's
  // sticky bar and the desktop sidebar both carry the button; both open the ONE confirm Sheet.
  fireEvent.click((await screen.findAllByText('sponsorPool.fullyFund', { selector: 'button' }))[0])
  fireEvent.click(await screen.findByText('sponsorPortal.students.confirmAward'))

  await waitFor(() => expect(mockFund).toHaveBeenCalledWith(5, { token: 'tok' }))
  // The fix: both shared surfaces are refreshed so the funded student leaves the available
  // list and shows under "My students" without a manual reload.
  await waitFor(() => expect(refreshPool).toHaveBeenCalled())
  expect(refreshWallet).toHaveBeenCalled()
})

it('shows the sidebar facts table + balance (owner spec)', async () => {
  render(<StudentDetailPage />)
  await screen.findAllByText('sponsorPool.fullyFund', { selector: 'button' })   // detail loaded
  // The facts table renders its labels (home state / institution / reporting date / covers).
  expect(screen.getByText('sponsorPool.homeState')).toBeTruthy()
  expect(screen.getByText('sponsorPool.secondarySchool')).toBeTruthy()
  expect(screen.getByText('sponsorPool.reportingDate')).toBeTruthy()
  expect(screen.getByText('sponsorPool.coversLabel')).toBeTruthy()
  // "SUPPORT NEEDED" eyebrow + the balance line.
  expect(screen.getByText('sponsorPool.supportNeeded')).toBeTruthy()
  // (Mobile M5: the phone's fund bar shows the balance too — so at least one paragraph, not exactly one.)
  await waitFor(() =>
    expect(screen.getAllByText((_c, node) =>
      node?.tagName === 'P' && (node.textContent || '').includes('sponsorPortal.students.balanceLabel'),
    ).length).toBeGreaterThan(0))
})

it('links the programme to its public course page, in a new tab', async () => {
  // owner 2026-07-25: the sponsor surface should hyperlink the programme, as the cockpit does.
  // `course_href` is server-computed (card_display.course_href) so the FE never re-derives it.
  mockDetail.mockResolvedValue({
    ref: 'Student A9', state: 'Selangor', field: 'Engineering', academic: '5A 3B',
    course: 'Diploma Teknologi Animasi', course_href: '/course/UB4213001',
    institution: 'Universiti Tun Hussein Onn Malaysia', school: 'SMK Test',
    reporting_date: '2026-09-01', funding_categories: ['Fees'], programme_months: 24,
    enrolment_verified: true, anon_profile: '', award_amount: '3000',
  })
  render(<StudentDetailPage />)
  const link = await screen.findByText('Diploma Teknologi Animasi')
  expect(link.tagName).toBe('A')
  // Plain DOM assertions — this project's jest setup does not load @testing-library/jest-dom.
  expect(link.getAttribute('href')).toBe('/course/UB4213001')
  expect(link.getAttribute('target')).toBe('_blank')
})

it('renders the programme as plain text when it has no course page', async () => {
  // A stale course_id in neither catalogue, or a pathway with no public page → '' from the
  // server. Never a dead link.
  mockDetail.mockResolvedValue({
    ref: 'Student A9', state: 'Selangor', field: 'Engineering', academic: '5A 3B',
    course: 'Diploma Teknologi Animasi', course_href: '',
    institution: 'Politeknik Ungku Omar', school: 'SMK Test', reporting_date: '2026-09-01',
    funding_categories: ['Fees'], programme_months: 24, enrolment_verified: true,
    anon_profile: '', award_amount: '3000',
  })
  render(<StudentDetailPage />)
  expect((await screen.findByText('Diploma Teknologi Animasi')).tagName).not.toBe('A')
})

// ── Mobile M5 (owner): the fund action on a phone — a sticky page bar, one confirm Sheet ─────────────

it('draws the fund action as a sticky page bar that gives way to nothing and swaps the tabs out', async () => {
  render(<StudentDetailPage />)
  const bar = await screen.findByTestId('fund-bar')
  expect(bar.hasAttribute('data-page-bar')).toBe(true)
  expect(bar.className).toMatch(/\bsticky\b/)
  expect(bar.className).toMatch(/\bmd:hidden\b/)
  // The balance the bar shows is the wallet's string, formatted as everywhere else — never computed.
  await waitFor(() => expect(bar.textContent).toContain('RM5,000'))
})

it('confirms in a Sheet that names the server amount, cannot be dismissed, and sends ONE request per tap burst', async () => {
  let release: (v: unknown) => void = () => {}
  mockFund.mockImplementation(() => new Promise((r) => { release = r }))
  render(<StudentDetailPage />)
  fireEvent.click(within(await screen.findByTestId('fund-bar')).getByRole('button'))
  const sheet = await screen.findByTestId('fund-confirm')
  // The amount is the server's award_amount (3000), through the same rmWhole as before.
  expect(sheet.textContent).toContain('sponsorPortal.students.confirmBody {"amount":"3,000"}')
  // dismissible={false}: no close button, and Escape does nothing.
  expect(within(sheet).queryByRole('button', { name: /close/i })).toBeNull()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByTestId('fund-confirm')).not.toBeNull()
  // A burst of taps before React re-renders (all inside ONE act, so the disabled state has not landed):
  // exactly one award request — the ref lock, not the button's disabled attribute, is what holds.
  const confirm = screen.getByTestId('fund-confirm-award')
  act(() => { confirm.click(); confirm.click(); confirm.click() })
  expect(mockFund).toHaveBeenCalledTimes(1)
  // While it is in the air, Cancel cannot close it (busy).
  const cancel = within(screen.getByTestId('fund-confirm')).getByText('common.cancel')
  expect((cancel as HTMLButtonElement).disabled).toBe(true)
  release({})
  await waitFor(() => expect(screen.queryByTestId('fund-confirm')).toBeNull())
  // Funded: the bar is gone and the sidebar says so.
  expect(screen.queryByTestId('fund-bar')).toBeNull()
  expect(mockFund).toHaveBeenCalledTimes(1)
})

it('keeps the Sheet open with the reason when the award is refused, and allows another try', async () => {
  mockFund.mockRejectedValueOnce(Object.assign(new Error('x'), { code: 'insufficient_balance' }))
  render(<StudentDetailPage />)
  fireEvent.click(within(await screen.findByTestId('fund-bar')).getByRole('button'))
  fireEvent.click(await screen.findByTestId('fund-confirm-award'))
  await screen.findByText('sponsorPortal.students.errInsufficient')
  expect(screen.getByTestId('fund-confirm')).toBeTruthy()
  fireEvent.click(screen.getByTestId('fund-confirm-award'))
  await waitFor(() => expect(mockFund).toHaveBeenCalledTimes(2))
})

it('offers no fund action for a student already funded in the grace window', async () => {
  mockDetail.mockResolvedValue({
    ref: 'Student A9', state: 'Selangor', field: 'Engineering', academic: '5A 3B', institution: 'X', school: 'Y',
    reporting_date: null, funding_categories: [], programme_months: 24, enrolment_verified: true,
    anon_profile: '', award_amount: '3000', funded: true,
  })
  render(<StudentDetailPage />)
  await screen.findByText('sponsorPool.fundedBody', { exact: false })
  expect(screen.queryByTestId('fund-bar')).toBeNull()
  expect(screen.queryByText('sponsorPool.fullyFund', { selector: 'button' })).toBeNull()
})

// ── M5 review: a different student in place must never show the previous one's figures ─────────────
it('forgets the previous student at once when the address names another one', async () => {
  const { rerender } = render(<StudentDetailPage />)
  fireEvent.click(within(await screen.findByTestId('fund-bar')).getByRole('button'))
  expect((await screen.findByTestId('fund-confirm')).textContent).toContain('{"amount":"3,000"}')
  // Student 6 is slow to arrive; until it does, neither its page nor the confirm may show student 5's RM 3,000.
  let arrive: (v: unknown) => void = () => {}
  mockDetail.mockImplementation(() => new Promise((r) => { arrive = r }))
  routeId = '6'
  rerender(<StudentDetailPage />)
  await waitFor(() => expect(screen.queryByTestId('fund-confirm')).toBeNull())
  expect(screen.getByText('common.loading')).toBeTruthy()
  expect(document.body.textContent).not.toContain('3,000')
  await act(async () => { arrive({ ref: 'Student B2', state: 'Kedah', field: 'Health', academic: '5A', institution: 'X', school: 'Y',
    reporting_date: null, funding_categories: [], programme_months: 12, enrolment_verified: false, anon_profile: '', award_amount: '2000' }) })
  expect(mockDetail).toHaveBeenLastCalledWith(6, { token: 'tok' })
  expect(document.body.textContent).toContain('RM2,000')
})

it('paints the confirm in the sponsor portal face (the Sheet is portalled out of the shell)', async () => {
  render(<StudentDetailPage />)
  fireEvent.click(within(await screen.findByTestId('fund-bar')).getByRole('button'))
  // (`testId` marks the Sheet's outer layer; `className` dresses its panel, inside it.)
  const sheet = await screen.findByTestId('fund-confirm')
  expect(sheet.querySelector('.font-sponsor')).not.toBeNull()
})
