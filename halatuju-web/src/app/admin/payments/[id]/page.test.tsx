/**
 * @jest-environment jsdom
 *
 * The payment run on a PHONE (owner, 2026-09-08).
 *
 * Seven columns do not fit a phone, so the same rows are drawn as cards below 768px. What is
 * pinned here is the part that would be quietly wrong rather than visibly broken:
 *
 *  · **the amount is NOT editable on a phone** — the owner's ruling ("desktop is the preferred
 *    option; phone is for quick checking"), and a money box a thumb can graze is exactly the
 *    thing that ruling is about. The card says WHERE to change it instead of showing an inert
 *    control;
 *  · **the include toggle IS live on a draft** — it is the reason to open a run on a phone;
 *  · **nothing a row can carry is lost**: the not-activated warning, the exclusion reason and
 *    the credit note all survive the move. A phone layout that silently drops a warning is
 *    worse than the table it replaced.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import PaymentRunPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'admin', is_super_admin: true, owning_org_id: 11 } }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  useParams: () => ({ id: '3' }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const ITEM = {
  id: 1, application_id: 91, name: 'THEEPICAA A/P SELVAVINAYAGAM',
  nric: '081119-05-0548', vircle_id: '8000400175153', activated: true,
  award_amount: '2000', paid_to_date: '400', amount: '200', credit_applied: '0',
  included: true, exclude_reason: '',
}

const run = (over: Partial<api.PaymentRunDetail> = {}): api.PaymentRunDetail => ({
  id: 3, reference: 'PR-2026-09-01-03', payment_date: '2026-09-01', month: '2026-09',
  status: 'draft', total_amount: '11600', student_count: 58,
  items: [
    ITEM,
    { ...ITEM, id: 2, application_id: 92, name: 'HARISH A/L SANGGAR', activated: false,
      nric: '080923-06-0355', vircle_id: '8000400175166' },
    { ...ITEM, id: 3, application_id: 93, name: 'YESWINDRAN A/L MURALY',
      included: false, amount: '0', exclude_reason: 'deferred to next month' },
    { ...ITEM, id: 4, application_id: 94, name: 'THERESA ARUL MARY', credit_applied: '150' },
  ],
  skipped: [], signatures: [],
  ...over,
} as unknown as api.PaymentRunDetail)

const cards = () => screen.getByTestId('payment-cards')
const cardFor = (name: string) =>
  within(cards()).getByText(new RegExp(name)).closest('div[class*="rounded-xl"]') as HTMLElement

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getPaymentRun.mockResolvedValue(run())
})

async function mount() {
  render(<PaymentRunPage />)
  await waitFor(() => expect(screen.getByTestId('payment-cards')).toBeTruthy())
}

describe('the phone card carries every row, and every state a row can be in', () => {
  it('draws one card per student, in the table’s order', async () => {
    await mount()
    for (const n of ['THEEPICAA', 'HARISH', 'YESWINDRAN', 'THERESA']) {
      expect(within(cards()).getByText(new RegExp(n))).toBeTruthy()
    }
  })

  it('keeps the not-activated warning welded to the e-wallet id', async () => {
    // The one fact on this row that stops a payment. Losing it in the move would be silent.
    await mount()
    expect(within(cardFor('HARISH')).getByText(/notActivated/)).toBeTruthy()
    expect(within(cardFor('THEEPICAA')).queryByText(/notActivated/)).toBeNull()
  })

  it('shows an excluded student’s REASON in full, not a truncated box', async () => {
    await mount()
    const card = cardFor('YESWINDRAN')
    expect(within(card).getByText(/leftOut/)).toBeTruthy()
    expect(within(card).getByText(/deferred to next month/)).toBeTruthy()
  })

  it('keeps the credit note', async () => {
    await mount()
    expect(within(cardFor('THERESA')).getByText(/creditApplied/)).toBeTruthy()
  })
})

describe('the amount is read-only on a phone — the owner’s ruling', () => {
  it('prints the figure and names where to change it, on a DRAFT run', async () => {
    await mount()
    const card = cardFor('THEEPICAA')
    // No money input anywhere in the card…
    expect(within(card).queryByRole('textbox')).toBeNull()
    expect(within(card).getByText('RM 200')).toBeTruthy()
    // …and it says so, rather than leaving a dead-looking control.
    expect(within(card).getByTestId('edit-on-desktop')).toBeTruthy()
  })

  it('says nothing about editing once the run is past draft', async () => {
    mockApi.getPaymentRun.mockResolvedValue(run({ status: 'completed' }))
    await mount()
    expect(screen.queryByTestId('edit-on-desktop')).toBeNull()
  })

  it('leaves the include toggle live on a draft and locked afterwards', async () => {
    // The toggle is why somebody opens a draft run on a phone at all.
    await mount()
    const on = within(cardFor('THEEPICAA')).getByRole('switch')
    expect(on.hasAttribute('disabled')).toBe(false)

    mockApi.getPaymentRun.mockResolvedValue(run({ status: 'completed' }))
    render(<PaymentRunPage />)
    await waitFor(() => expect(screen.getAllByTestId('payment-cards').length).toBeGreaterThan(1))
    const locked = within(screen.getAllByTestId('payment-cards')[1]).getAllByRole('switch')[0]
    expect(locked.hasAttribute('disabled')).toBe(true)
  })
})

describe('the desktop table is untouched', () => {
  it('still renders, and is hidden only below the md breakpoint', async () => {
    await mount()
    const frame = document.querySelector('[data-testid="table-scroller"]')?.closest('div.relative')
    expect(frame).toBeTruthy()
    expect(frame?.className).toContain('hidden')
    expect(frame?.className).toContain('md:block')
    expect(cards().className).toContain('md:hidden')
  })
})
