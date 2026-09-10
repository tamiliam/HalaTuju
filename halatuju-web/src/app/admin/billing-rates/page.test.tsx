/**
 * @jest-environment jsdom
 *
 * The Billing rates screen (2026-09-11).
 *
 * ⚠ THE TESTS THAT CARRY THIS FILE ARE WRITTEN FROM THE HARM:
 *
 *  * `an unset rate is drawn, not hidden` — the hourly rate being blank is the single most
 *    important thing this screen can say: until it exists, no development work can be billed at
 *    all and `development_charge` refuses. A row that is not drawn says nothing; a row that says
 *    "not set" gets acted on. This asserts the card EXISTS, not merely that it lacks a number.
 *  * `saving adds a rate, it does not edit one` — the POST carries an `effective_from`, which is
 *    the whole mechanism that stops a rate typed in September re-pricing an August invoice. If
 *    the date is ever dropped the page silently becomes a "current value" editor and nothing else
 *    would fail.
 *  * `a save re-reads` — a save ADDS a row, so the "in force" figure AND the history both change.
 *    Patching one in place would leave the card disagreeing with itself with nothing failing.
 *  * `the effective-from control is a native select` — a native date box follows the BROWSER's
 *    locale, the same trap that made a time field untypeable and left Save asleep with no error
 *    (feedback, native pickers). A rate only ever applies from the first of a month, so a plain
 *    month `<select>` has no locale and no silent empty state.
 */
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import BillingRatesPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, vars?: Record<string, string>) =>
      vars ? `${k}:${Object.values(vars).join('|')}` : k,
    locale: 'en',
  }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'super', owning_org_id: null } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const rate = (over: Partial<api.BillingRateRow> & { id: number; category: string; kind: string }):
  api.BillingRateRow => ({
  value: '15.00', effective_from: '2026-07-01', updated_by_email: 'super@x.com', note: '', ...over,
})

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getBillingRates.mockResolvedValue({ rates: [] })
  mockApi.setBillingRate.mockResolvedValue(rate({ id: 9, category: 'development', kind: 'hourly_rate' }))
})

describe('what the screen says about a rate nobody has set', () => {
  it('an unset rate is drawn, not hidden', async () => {
    mockApi.getBillingRates.mockResolvedValue({
      rates: [rate({ id: 1, category: 'infrastructure', kind: 'margin_pct' })],
    })
    const { container } = render(<BillingRatesPage />)

    const card = await waitFor(() =>
      within(container).getByTestId('rate-development-hourly_rate'))
    // The card exists AND says so in words — the two halves of the property.
    expect(within(card).getByTestId('rate-not-set')).not.toBeNull()
    expect(within(card).getByText('admin.billingRates.blocked.development')).not.toBeNull()
  })

  it('every category and kind gets a card even on a completely empty rate table', async () => {
    const { container } = render(<BillingRatesPage />)
    await waitFor(() => within(container).getByTestId('rate-infrastructure-margin_pct'))
    for (const c of ['infrastructure', 'metered', 'development']) {
      for (const k of ['margin_pct', 'hourly_rate']) {
        expect(within(container).getByTestId(`rate-${c}-${k}`)).not.toBeNull()
      }
    }
  })

  it('a set rate shows its value and who set it', async () => {
    mockApi.getBillingRates.mockResolvedValue({
      rates: [rate({ id: 1, category: 'infrastructure', kind: 'margin_pct', value: '15.00' })],
    })
    const { container } = render(<BillingRatesPage />)
    const card = await waitFor(() =>
      within(container).getByTestId('rate-infrastructure-margin_pct'))
    expect(within(card).getByText('15%')).not.toBeNull()
    expect(within(card).queryByTestId('rate-not-set')).toBeNull()
  })
})

describe('saving', () => {
  it('adds a rate from a chosen month — it does not edit the current one', async () => {
    const { container } = render(<BillingRatesPage />)
    const card = await waitFor(() =>
      within(container).getByTestId('rate-development-hourly_rate'))

    fireEvent.change(within(card).getByLabelText(/billingRates.category.development/), {
      target: { value: '180' },
    })
    fireEvent.change(within(card).getByLabelText('admin.billingRates.from'), {
      target: { value: '2026-09' },
    })
    fireEvent.click(within(card).getByText('admin.billingRates.save'))

    await waitFor(() => expect(mockApi.setBillingRate).toHaveBeenCalled())
    const [body] = mockApi.setBillingRate.mock.calls[0]
    expect(body.category).toBe('development')
    expect(body.kind).toBe('hourly_rate')
    expect(body.value).toBe('180')
    // ⚠ The date is the mechanism. A rate always takes effect on the FIRST of the month, which
    // is the only day `rate_in_force` is ever asked about.
    expect(body.effective_from).toBe('2026-09-01')
  })

  it('a save re-reads the whole table rather than patching the card', async () => {
    const { container } = render(<BillingRatesPage />)
    const card = await waitFor(() =>
      within(container).getByTestId('rate-development-hourly_rate'))
    expect(mockApi.getBillingRates).toHaveBeenCalledTimes(1)

    fireEvent.change(within(card).getByLabelText(/billingRates.category.development/), {
      target: { value: '180' },
    })
    fireEvent.click(within(card).getByText('admin.billingRates.save'))
    await waitFor(() => expect(mockApi.getBillingRates).toHaveBeenCalledTimes(2))
  })

  it('an empty value cannot be saved', async () => {
    const { container } = render(<BillingRatesPage />)
    const card = await waitFor(() =>
      within(container).getByTestId('rate-metered-margin_pct'))
    expect((within(card).getByText('admin.billingRates.save') as HTMLButtonElement).disabled).toBe(true)
  })

  it('the effective-from control is a native select, never a date input', async () => {
    const { container } = render(<BillingRatesPage />)
    const card = await waitFor(() =>
      within(container).getByTestId('rate-development-hourly_rate'))
    const control = within(card).getByLabelText('admin.billingRates.from')
    expect(control.tagName).toBe('SELECT')
    expect(card.querySelector('input[type="date"]')).toBeNull()
  })
})

describe('history', () => {
  it('earlier values are kept and can be read', async () => {
    mockApi.getBillingRates.mockResolvedValue({
      rates: [
        rate({ id: 1, category: 'development', kind: 'hourly_rate', value: '150.00', effective_from: '2026-06-01' }),
        rate({ id: 2, category: 'development', kind: 'hourly_rate', value: '200.00', effective_from: '2026-08-01' }),
      ],
    })
    const { container } = render(<BillingRatesPage />)
    const card = await waitFor(() =>
      within(container).getByTestId('rate-development-hourly_rate'))

    // The newest is in force; the older one is history, not gone. A closed month was billed at
    // it, so erasing it would erase the reason that invoice says what it says.
    expect(within(card).getByText('RM200.00')).not.toBeNull()
    fireEvent.click(within(card).getByText('admin.billingRates.history:1'))
    expect(within(within(card).getByTestId('history-development-hourly_rate'))
      .getByText('RM150.00')).not.toBeNull()
  })
})
