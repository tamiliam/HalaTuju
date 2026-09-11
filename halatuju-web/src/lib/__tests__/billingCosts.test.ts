import {
  formatMyr, formatPct, formatHours, orderedCostSources, costCaveats,
  hasDiscount, unbilledByOrg, rateGrid, rateMonthOptions, isCostWarning,
  COST_SOURCE_ORDER, RATE_SLOTS, RATE_MONTHS_BACK, blockedKey,
} from '@/lib/billingCosts'
import type {
  BillingCharge, BillingCostsPayload, BillingRateRow, PlatformCostBlock,
} from '@/lib/admin-api'

const costs = (over: Partial<PlatformCostBlock> = {}): PlatformCostBlock => ({
  lines: 3,
  total_myr: '128.92',
  attributable_myr: '23.92',
  platform_myr: '105.00',
  development_myr: '0.00',
  tax_myr: '0.00',
  by_source: { gcp: '23.92', supabase: '105.00' },
  entered_sources: [],
  extracted_sources: [],
  is_complete: true,
  unconverted: [],
  period_caveats: [],
  metered_events: 100,
  metered_org_null: 10,
  metered_org_null_pct: 10,
  ...over,
})

const rate = (over: Partial<BillingRateRow> & { category: string; kind: string }): BillingRateRow => ({
  id: 1, value: '15.00', effective_from: '2026-07-01', updated_by_email: '', note: '', ...over,
})

describe('money never becomes a number', () => {
  test('a ringgit figure formats with two decimals and thousands', () => {
    expect(formatMyr('1800')).toBe('RM1,800.00')
    expect(formatMyr('23.92')).toBe('RM23.92')
  })

  test('a missing amount is an em dash, NOT RM0.00', () => {
    // The property that matters. "We do not have this figure" and "this figure is zero" are
    // different claims, and only one of them is safe in front of somebody about to invoice.
    expect(formatMyr(null)).toBe('—')
    expect(formatMyr('')).toBe('—')
    expect(formatMyr(undefined)).toBe('—')
    expect(formatMyr('not-a-number')).toBe('—')
  })

  test('percentages and hours drop trailing zeros', () => {
    expect(formatPct('15.00')).toBe('15%')
    expect(formatPct('12.50')).toBe('12.5%')
    expect(formatPct(null)).toBe('—')
    expect(formatHours('27.5')).toBe('27.5h')
    expect(formatHours(null)).toBe('—')
  })
})

describe('cost sources', () => {
  test('render in the fixed order, unknown sources appended alphabetically', () => {
    const rows = orderedCostSources(costs({
      by_source: { other: '1.00', twilio: '7.60', gcp: '23.92', zzz: '2.00', workspace: '18.90' },
    }))
    expect(rows.map((r) => r.source)).toEqual(['gcp', 'workspace', 'twilio', 'other', 'zzz'])
  })

  test('Google Workspace has its own place in the order', () => {
    expect(COST_SOURCE_ORDER).toContain('workspace')
  })

  test('an empty ledger yields no rows rather than throwing', () => {
    expect(orderedCostSources(null)).toEqual([])
    expect(orderedCostSources(costs({ by_source: {} }))).toEqual([])
  })
})

describe('the health warnings on a total', () => {
  test('a clean measured month carries none', () => {
    expect(costCaveats(costs())).toEqual([])
  })

  test('an unconverted invoice says the total is a floor, and names it', () => {
    const out = costCaveats(costs({
      is_complete: false,
      unconverted: [{ source: 'twilio', invoice_ref: 'TW-9', currency: 'USD', amount_original: '1.77' }],
    }))
    expect(out[0].kind).toBe('incomplete')
    expect(out[0].detail).toContain('TW-9')
    expect(out[0].detail).toContain('USD')
  })

  test('hand-entered sources are named, because a mixed total is not an audit', () => {
    const out = costCaveats(costs({ entered_sources: ['supabase', 'workspace'] }))
    expect(out).toHaveLength(1)
    expect(out[0].kind).toBe('entered')
    expect(out[0].detail).toBe('supabase, workspace')
  })

  test('a provider billing outside the calendar month gets its own caveat', () => {
    const out = costCaveats(costs({ period_caveats: ['Supabase bills the 8th to the 7th'] }))
    expect(out[0].kind).toBe('caveat')
  })

  test('the floor warning comes first — a wrong number outranks a number needing context', () => {
    const out = costCaveats(costs({
      is_complete: false,
      unconverted: [{ source: 'twilio', invoice_ref: '', currency: 'USD', amount_original: '1.77' }],
      entered_sources: ['supabase'],
      period_caveats: ['Bills the 8th'],
    }))
    expect(out.map((c) => c.kind)).toEqual(['incomplete', 'entered', 'caveat'])
  })
})

describe('the discount is a visible line', () => {
  const charge = (pct: string): BillingCharge => ({
    organisation_id: 1, organisation: 'BrightPath', lines: [],
    subtotal_myr: '1800.00', discount_pct: pct, discount_myr: '1800.00',
    discount_reason: 'Pre-launch goodwill period', discount_set_by: 'super@x.com',
    charged_myr: '0.00', blocked: [],
  })

  test('a discounted month is flagged as discounted', () => {
    expect(hasDiscount(charge('100.00'))).toBe(true)
  })

  test('an undiscounted month is not', () => {
    expect(hasDiscount(charge('0.00'))).toBe(false)
    expect(hasDiscount(null)).toBe(false)
  })
})

describe('unbilled request work', () => {
  const payload = (rows: BillingCostsPayload['unbilled_requests']): BillingCostsPayload => ({
    month: '2026-08', months: ['2026-08'], costs: costs(), charges: [], unbilled_requests: rows,
  })

  test('groups by organisation, ordered by name', () => {
    const out = unbilledByOrg(payload([
      { request_id: 2, organisation_id: 9, organisation: 'Zenith', title: 'B', hours: '3.0', module: '[REQ-2] B', worked_on: '2026-08-01', worked_month: '2026-08', worked_basis: 'scheduled' },
      { request_id: 1, organisation_id: 1, organisation: 'BrightPath', title: 'A', hours: '7.5', module: '[REQ-1] A', worked_on: '2026-07-01', worked_month: '2026-07', worked_basis: 'scheduled' },
      { request_id: 3, organisation_id: 1, organisation: 'BrightPath', title: 'C', hours: '2.0', module: '[REQ-3] C', worked_on: '2026-09-01', worked_month: '2026-09', worked_basis: 'scheduled' },
    ]))
    expect(out.map((g) => g.organisation)).toEqual(['BrightPath', 'Zenith'])
    expect(out[0].rows).toHaveLength(2)
  })

  test('nothing outstanding is an empty list, not a crash', () => {
    expect(unbilledByOrg(null)).toEqual([])
    expect(unbilledByOrg(payload([]))).toEqual([])
  })
})

describe('the rate grid', () => {
  test('every rate that EXISTS gets a row, even ones nobody has set', () => {
    const grid = rateGrid([])
    expect(grid).toHaveLength(RATE_SLOTS.length)
    expect(grid.every((r) => r.current === null)).toBe(true)
  })

  test('⚠ it offers only the FOUR rates the charge actually reads', () => {
    // The first version drew every category crossed with every kind, so it offered
    // "Infrastructure - rate per hour" and "Metered usage - rate per hour". You do not bill
    // infrastructure by the hour, and `charge_for` never read either: the two cost lines take a
    // MARGIN only, and the hourly rate belongs to development alone. Two boxes that could never
    // do anything, beside four that decide what every tenant pays.
    expect(rateGrid([]).map((r) => `${r.category}.${r.kind}`)).toEqual([
      'infrastructure.margin_pct',
      'metered.margin_pct',
      'development.margin_pct',
      'development.hourly_rate',
    ])
  })

  test('no category is billed by the hour except development', () => {
    const hourly = RATE_SLOTS.filter((s) => s.kind === 'hourly_rate')
    expect(hourly.map((s) => s.category)).toEqual(['development'])
  })

  test('each box gets its OWN unset message, keyed by category AND kind', () => {
    // Keyed by category alone, the two hourly-rate cards showed the margin's sentence and said
    // something untrue about themselves.
    const keys = rateGrid([]).map((r) => blockedKey(r.category, r.kind))
    expect(new Set(keys).size).toBe(keys.length)
    expect(keys).toContain('admin.billingRates.blocked.development_hourly_rate')
  })

  test('an unset hourly rate is present and null, NOT skipped', () => {
    // The single most important thing this screen can say: until an hourly rate exists, no
    // development work can be billed at all. A row that is not drawn says nothing; a row that
    // says "not set" gets acted on.
    const grid = rateGrid([rate({ category: 'infrastructure', kind: 'margin_pct' })])
    const hourly = grid.find((r) => r.category === 'development' && r.kind === 'hourly_rate')
    expect(hourly).toBeDefined()
    expect(hourly!.current).toBeNull()
  })

  test('the newest effective date is current and the rest become history', () => {
    const grid = rateGrid([
      rate({ id: 1, category: 'development', kind: 'hourly_rate', value: '150.00', effective_from: '2026-06-01' }),
      rate({ id: 2, category: 'development', kind: 'hourly_rate', value: '200.00', effective_from: '2026-08-01' }),
      rate({ id: 3, category: 'development', kind: 'hourly_rate', value: '120.00', effective_from: '2026-01-01' }),
    ])
    const row = grid.find((r) => r.category === 'development' && r.kind === 'hourly_rate')!
    expect(row.current!.value).toBe('200.00')
    expect(row.history.map((h) => h.value)).toEqual(['150.00', '120.00'])
  })

  test('history is kept, because a rate change must never erase what a closed month was billed at', () => {
    const grid = rateGrid([
      rate({ id: 1, category: 'infrastructure', kind: 'margin_pct', value: '15.00', effective_from: '2026-07-01' }),
      rate({ id: 2, category: 'infrastructure', kind: 'margin_pct', value: '20.00', effective_from: '2026-09-01' }),
    ])
    const row = grid.find((r) => r.category === 'infrastructure' && r.kind === 'margin_pct')!
    expect(row.history).toHaveLength(1)
    expect(row.history[0].effective_from).toBe('2026-07-01')
  })
})

describe('the effective-from month list', () => {
  it('offers months either side of today, in order, as YYYY-MM', () => {
    const out = rateMonthOptions(new Date(2026, 8, 11))   // September 2026
    expect(out).toHaveLength(13)
    expect(out[0]).toBe('2026-03')
    expect(out[RATE_MONTHS_BACK]).toBe('2026-09')         // today's month sits at the index the page uses
    expect(out[12]).toBe('2027-03')
  })

  it('crosses a year boundary without producing a month 13', () => {
    const out = rateMonthOptions(new Date(2026, 11, 1))   // December 2026
    expect(out).toContain('2027-01')
    expect(out.every((m) => /^\d{4}-(0[1-9]|1[0-2])$/.test(m))).toBe(true)
  })
})

describe('where a figure came from', () => {
  test('an extracted source is reported, and is NOT a warning', () => {
    // ⚠ The distinction the provenance column exists for. An extracted figure is a parse of the
    // provider's own PDF, refused unless it reconciles to the printed total — reproducible by
    // anyone holding the file. Styling that as a caution would train the reader to ignore the
    // one entry here that IS a caution.
    const out = costCaveats(costs({ extracted_sources: ['supabase', 'twilio', 'workspace'] }))
    expect(out).toHaveLength(1)
    expect(out[0].kind).toBe('extracted')
    expect(isCostWarning('extracted')).toBe(false)
  })

  test('a hand-typed source IS a warning, and outranks the extracted note', () => {
    const out = costCaveats(costs({
      entered_sources: ['supabase'],
      extracted_sources: ['twilio'],
    }))
    expect(out.map((c) => c.kind)).toEqual(['entered', 'extracted'])
    expect(isCostWarning('entered')).toBe(true)
    expect(isCostWarning('incomplete')).toBe(true)
    expect(isCostWarning('caveat')).toBe(false)
  })

  test('a month with no extracted rows says nothing about extraction', () => {
    expect(costCaveats(costs({ extracted_sources: [] }))).toEqual([])
    // A payload from before the field existed must not crash the page.
    expect(costCaveats(costs({ extracted_sources: undefined as unknown as string[] }))).toEqual([])
  })
})
