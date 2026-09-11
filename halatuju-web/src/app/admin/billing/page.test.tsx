/**
 * @jest-environment jsdom
 *
 * The cost + charge section on Billing & usage (2026-09-11).
 *
 * ⚠ THE TESTS THAT CARRY THIS FILE ARE WRITTEN FROM THE HARM:
 *
 *  * `a discounted month still shows what it would have cost` — the owner's July instruction was
 *    two sentences and both matter: *"we do not bill anything for July. 100% discount. But show
 *    the values."* A month suppressed to zero satisfies the first and destroys the second, and
 *    nothing would fail.
 *  * `a category we cannot price says so` — metered and infrastructure are REFUSED, not zeroed.
 *    A line the reader can see is missing gets fixed; a RM0.00 gets believed and invoiced.
 *  * `the health warnings reach the screen` — the cost module computes `entered_sources`,
 *    `is_complete` and `period_caveats` and they died in a docstring for six weeks. A total
 *    mixing measured and hand-typed figures without saying so is not an audit.
 *  * `a failing cost fetch never darkens the usage screen` — the costs endpoint 403s an
 *    org_admin, who is legitimately entitled to the usage half. Sharing one error state would
 *    blank a page they are allowed to read.
 *  * `changing the month re-reads BOTH` — two endpoints back one picker. Re-reading one would
 *    leave August's cost beside July's usage, with nothing failing.
 */
import { render, fireEvent, waitFor, within } from '@testing-library/react'
import BillingPage from './page'
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

const USAGE: api.BillingUsagePayload = {
  month: '2026-08', months: ['2026-08', '2026-07'], can_see_platform: true,
  organisations: [{
    organisation_id: 1, organisation: 'BrightPath', is_platform: false,
    services: [], totals: { events: 0, quantity: 0, input_tokens: 0, output_tokens: 0 },
    storage_bytes: 0,
  }],
}

const COSTS = (over: Partial<api.BillingCostsPayload> = {}): api.BillingCostsPayload => ({
  month: '2026-08',
  months: ['2026-08', '2026-07'],
  costs: {
    lines: 4, total_myr: '150.19', attributable_myr: '23.92', platform_myr: '126.27',
    development_myr: '0.00',
    tax_myr: '0.00',
    by_source: { gcp: '23.92', supabase: '105.00', workspace: '18.90', twilio: '2.37' },
    entered_sources: [],
    extracted_sources: ['supabase', 'twilio', 'workspace'],
    is_complete: true, unconverted: [], period_caveats: [],
    metered_events: 500, metered_org_null: 50, metered_org_null_pct: 10,
  },
  charges: [{
    organisation_id: 1, organisation: 'BrightPath',
    lines: [{
      category: 'development', hours: '27.5', rate_myr: '150.00', margin_pct: '20.00',
      cost_myr: '4125.00', share_pct: null, share_rule: '',
      amount_myr: '4950.00', detail: [],
    }],
    subtotal_myr: '4950.00', discount_pct: '0.00', discount_myr: '0.00',
    discount_reason: '', discount_set_by: '', charged_myr: '4950.00',
    blocked: [
      { category: 'metered', reason: 'No unit prices are set.' },
      { category: 'infrastructure', reason: 'No rule has been agreed for sharing it.' },
    ],
  }],
  unbilled_requests: [],
  ...over,
})

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getBillingUsage.mockResolvedValue(USAGE)
  mockApi.getBillingCosts.mockResolvedValue(COSTS())
  mockApi.setBillingAdjustment.mockResolvedValue({ id: 1 })
  mockApi.recordBuildHours.mockResolvedValue({ id: 1 })
})

describe('what the platform cost', () => {
  it('shows the total and the split between what tenants drove and what we did', async () => {
    const { container } = render(<BillingPage />)
    const section = await waitFor(() => within(container).getByTestId('cost-section'))
    expect(within(section).getByText('RM150.19')).not.toBeNull()
    // RM23.92 appears twice on purpose — as the tenant-driven tile and as the Google Cloud row.
    expect(within(section).getAllByText('RM23.92').length).toBeGreaterThan(0)
    expect(within(section).getByText('RM126.27')).not.toBeNull()
  })

  it('lists Google Workspace as its own provider, not lumped into other', async () => {
    const { container } = render(<BillingPage />)
    const section = await waitFor(() => within(container).getByTestId('cost-section'))
    expect(within(section).getByText('admin.billing.cost.source.workspace')).not.toBeNull()
    expect(within(section).getByText('RM18.90')).not.toBeNull()
  })

  it('says which figures were read from the provider\'s own invoice', async () => {
    const { container } = render(<BillingPage />)
    const caveats = await waitFor(() => within(container).getByTestId('cost-caveats'))
    const note = within(caveats).getByText(/admin\.billing\.cost\.caveat\.extracted/)
    expect(note.textContent).toContain('supabase')
    // ⚠ NOT styled as a caution. An extracted figure is a parse of the provider's own PDF that
    // refuses unless it reconciles to the printed total. Dressing it as a warning would train
    // the reader to ignore `entered`, which is the one that IS a warning.
    expect(note.className).not.toContain('caution')
  })

  it('names the sources somebody typed by hand, and marks those as a warning', async () => {
    // The owner's standing instruction (2026-09-11) is that nothing is typed by hand, so this
    // should be empty on a healthy month — which is exactly why it has to be loud when it is not.
    mockApi.getBillingCosts.mockResolvedValue(COSTS({
      costs: { ...COSTS().costs, entered_sources: ['supabase'], extracted_sources: [] },
    }))
    const { container } = render(<BillingPage />)
    const caveats = await waitFor(() => within(container).getByTestId('cost-caveats'))
    const warn = within(caveats).getByText(/admin\.billing\.cost\.caveat\.entered/)
    expect(warn.className).toContain('caution')
  })

  it('marks each provider row with where its figure came from', async () => {
    const { container } = render(<BillingPage />)
    const section = await waitFor(() => within(container).getByTestId('cost-section'))
    expect(within(section).getAllByText('admin.billing.cost.fromInvoice').length).toBe(3)
    expect(within(section).queryByText('admin.billing.cost.byHand')).toBeNull()
  })

  it('says the total is a FLOOR when an invoice is not yet in ringgit', async () => {
    mockApi.getBillingCosts.mockResolvedValue(COSTS({
      costs: {
        ...COSTS().costs, is_complete: false,
        unconverted: [{ source: 'twilio', invoice_ref: 'TW-9', currency: 'USD', amount_original: '1.77' }],
      },
    }))
    const { container } = render(<BillingPage />)
    const caveats = await waitFor(() => within(container).getByTestId('cost-caveats'))
    expect(within(caveats).getByText(/admin\.billing\.cost\.caveat\.incomplete.*TW-9/)).not.toBeNull()
  })

  it('a clean measured month carries no warnings at all', async () => {
    mockApi.getBillingCosts.mockResolvedValue(COSTS({
      costs: { ...COSTS().costs, entered_sources: [], extracted_sources: [] },
    }))
    const { container } = render(<BillingPage />)
    await waitFor(() => within(container).getByTestId('cost-section'))
    expect(within(container).queryByTestId('cost-caveats')).toBeNull()
  })
})

describe('what we charge', () => {
  it('a category we cannot price says so rather than showing RM0.00', async () => {
    const { container } = render(<BillingPage />)
    const blocked = await waitFor(() => within(container).getByTestId('blocked-1'))
    expect(within(blocked).getByText(/No unit prices are set/)).not.toBeNull()
    expect(within(blocked).getByText(/No rule has been agreed/)).not.toBeNull()
  })

  it('a cost line shows what WE paid and the margin on top, not just the charge', async () => {
    // ⚠ A single marked-up figure hides the markup, and the markup is the thing the reader is
    // here to check. Owner, 2026-09-11: apply the margin as determined by the rate that is set.
    mockApi.getBillingCosts.mockResolvedValue(COSTS({
      charges: [{
        ...COSTS().charges[0],
        lines: [{
          category: 'infrastructure', hours: null, rate_myr: null, margin_pct: '15.00',
          cost_myr: '126.27', share_pct: '100.00',
          share_rule: 'infrastructure split equally', amount_myr: '145.21', detail: [],
        }],
        subtotal_myr: '145.21', charged_myr: '145.21', blocked: [],
      }],
    }))
    const { container } = render(<BillingPage />)
    const card = await waitFor(() => within(container).getByTestId('charge-1'))
    expect(within(card).getByText(/admin\.billing\.charge\.costPlus.*RM126\.27.*15%/)).not.toBeNull()
    // And the tenant's share of a platform-wide cost, with the rule behind it. With one tenant
    // this reads 100% — which is exactly when it is worth writing down.
    expect(within(card).getByText(/admin\.billing\.charge\.share.*100%/)).not.toBeNull()
    expect(within(card).getByText(/split equally/)).not.toBeNull()
  })

  it('an undiscounted month shows no discount line', async () => {
    const { container } = render(<BillingPage />)
    await waitFor(() => within(container).getByTestId('charge-1'))
    expect(within(container).queryByTestId('discount-line')).toBeNull()
  })

  it('a discounted month still shows what it would have cost', async () => {
    // The owner's July rule, both halves. Shown in full — and charged nothing.
    mockApi.getBillingCosts.mockResolvedValue(COSTS({
      charges: [{
        ...COSTS().charges[0],
        discount_pct: '100.00', discount_myr: '4950.00', charged_myr: '0.00',
        discount_reason: 'Pre-launch goodwill period',
      }],
    }))
    const { container } = render(<BillingPage />)
    const card = await waitFor(() => within(container).getByTestId('charge-1'))
    expect(within(card).getByTestId('discount-line')).not.toBeNull()
    // The subtotal SURVIVES a 100% discount — that is the half of the instruction a suppressed
    // month would destroy. It appears on the development line, the subtotal and the discount.
    expect(within(card).getAllByText(/RM4,950\.00/).length).toBeGreaterThan(1)
    expect(within(card).getByText('Pre-launch goodwill period')).not.toBeNull()
    expect(within(card).getAllByText('RM0.00').length).toBeGreaterThan(0)
  })

  it('a discount cannot be applied without a reason', async () => {
    const { container } = render(<BillingPage />)
    const card = await waitFor(() => within(container).getByTestId('charge-1'))
    fireEvent.click(within(card).getByText(/admin\.billing\.charge\.setDiscount/))
    const apply = within(card).getByText('admin.billing.charge.apply') as HTMLButtonElement
    expect(apply.disabled).toBe(true)

    fireEvent.change(within(card).getByLabelText('admin.billing.charge.reason'), {
      target: { value: 'Pre-launch goodwill period' },
    })
    expect((within(card).getByText('admin.billing.charge.apply') as HTMLButtonElement).disabled)
      .toBe(false)
  })

  it('applying a discount re-reads the costs rather than patching the card', async () => {
    const { container } = render(<BillingPage />)
    const card = await waitFor(() => within(container).getByTestId('charge-1'))
    expect(mockApi.getBillingCosts).toHaveBeenCalledTimes(1)

    fireEvent.click(within(card).getByText(/admin\.billing\.charge\.setDiscount/))
    fireEvent.change(within(card).getByLabelText('admin.billing.charge.reason'), {
      target: { value: 'Pre-launch goodwill period' },
    })
    fireEvent.click(within(card).getByText('admin.billing.charge.apply'))

    await waitFor(() => expect(mockApi.setBillingAdjustment).toHaveBeenCalled())
    const [body] = mockApi.setBillingAdjustment.mock.calls[0]
    expect(body.period_month).toBe('2026-08')
    expect(body.reason).toBe('Pre-launch goodwill period')
    await waitFor(() => expect(mockApi.getBillingCosts).toHaveBeenCalledTimes(2))
  })
})

describe('finished work not yet billed', () => {
  const withUnbilled = () => COSTS({
    unbilled_requests: [{
      request_id: 12, organisation_id: 1, organisation: 'BrightPath',
      title: 'Add a spending report', hours: '7.5', module: '[REQ-12] Add a spending report',
    }],
  })

  it('lists a finished quoted request', async () => {
    mockApi.getBillingCosts.mockResolvedValue(withUnbilled())
    const { container } = render(<BillingPage />)
    const section = await waitFor(() => within(container).getByTestId('unbilled-requests'))
    expect(within(section).getByText(/Add a spending report/)).not.toBeNull()
    expect(within(section).getByText('7.5h')).not.toBeNull()
  })

  it('recording sends the tagged module and a basis naming the request', async () => {
    mockApi.getBillingCosts.mockResolvedValue(withUnbilled())
    const { container } = render(<BillingPage />)
    const section = await waitFor(() => within(container).getByTestId('unbilled-requests'))
    fireEvent.click(within(section).getByText('admin.billing.unbilled.record'))

    await waitFor(() => expect(mockApi.recordBuildHours).toHaveBeenCalled())
    const [orgId, body] = mockApi.recordBuildHours.mock.calls[0]
    expect(orgId).toBe(1)
    expect(body.period_month).toBe('2026-08')
    // ⚠ The tag is what stops the same work being offered for billing again next month.
    expect(body.module).toContain('[REQ-12]')
    // ⚠ `basis` is required by the model and is the point of it: an hours figure with no stated
    // reconstruction is not auditable. Written by the code, so it always names its source.
    expect(body.basis).toContain('#12')
  })

  it('nothing outstanding means no section at all', async () => {
    const { container } = render(<BillingPage />)
    await waitFor(() => within(container).getByTestId('cost-section'))
    expect(within(container).queryByTestId('unbilled-requests')).toBeNull()
  })
})

describe('the two halves of this page are fenced apart', () => {
  it('a failing cost fetch never darkens the usage screen', async () => {
    // An org_admin gets a 403 from the costs endpoint and is entitled to the usage half.
    // Sharing one error state would blank a page they are allowed to read.
    mockApi.getBillingCosts.mockRejectedValue(new Error('403 forbidden'))
    const { container } = render(<BillingPage />)
    await waitFor(() => within(container).getByText('BrightPath'))
    expect(within(container).queryByTestId('cost-section')).toBeNull()
    expect(within(container).getByTestId('cost-error')).not.toBeNull()
  })

  it('changing the month re-reads BOTH endpoints', async () => {
    const { container } = render(<BillingPage />)
    await waitFor(() => within(container).getByTestId('cost-section'))
    expect(mockApi.getBillingUsage).toHaveBeenCalledTimes(1)
    expect(mockApi.getBillingCosts).toHaveBeenCalledTimes(1)

    fireEvent.change(container.querySelector('select')!, { target: { value: '2026-07' } })
    await waitFor(() => expect(mockApi.getBillingCosts).toHaveBeenCalledTimes(2))
    expect(mockApi.getBillingUsage).toHaveBeenCalledTimes(2)
    expect(mockApi.getBillingCosts.mock.calls[1][0]!.month).toBe('2026-07')
    expect(mockApi.getBillingUsage.mock.calls[1][0]!.month).toBe('2026-07')
  })
})

describe('Claude is shown as a cost of delivering hours, and charged only once', () => {
  // ⚠ Owner, 2026-09-11: "My biggest cost is Claude, which needs to be included via the request
  // hours." Leaving it in the platform bucket would mark it up as infrastructure AND leave the
  // hourly rate recovering it — the same ringgit taken twice, on an invoice, quietly.

  it('gets its own tile, separate from what we spend running the platform', async () => {
    mockApi.getBillingCosts.mockResolvedValue(COSTS({
      costs: { ...COSTS().costs, development_myr: '400.00' },
    }))
    const { container } = render(<BillingPage />)
    const section = await waitFor(() => within(container).getByTestId('cost-section'))
    expect(within(section).getByText('admin.billing.cost.development')).not.toBeNull()
    expect(within(section).getByText('RM400.00')).not.toBeNull()
  })

  it('no tile at all in a month where no tools were bought', async () => {
    const { container } = render(<BillingPage />)
    const section = await waitFor(() => within(container).getByTestId('cost-section'))
    expect(within(section).queryByText('admin.billing.cost.development')).toBeNull()
  })

  it('the development line says what the tools cost, beside what the hours are charged', async () => {
    // Shown, never added — the rate already recovers it. It exists so "is RM50/hour enough?" is
    // a figure on a screen rather than a feeling.
    mockApi.getBillingCosts.mockResolvedValue(COSTS({
      charges: [{
        ...COSTS().charges[0],
        lines: [{ ...COSTS().charges[0].lines[0], tool_cost_myr: '400.00' }],
      }],
    }))
    const { container } = render(<BillingPage />)
    const card = await waitFor(() => within(container).getByTestId('charge-1'))
    expect(within(card).getByText(/admin\.billing\.charge\.toolCost.*RM400\.00/)).not.toBeNull()
    // And it is NOT added into the charge.
    expect(within(card).getAllByText('RM4,950.00').length).toBeGreaterThan(0)
  })
})
