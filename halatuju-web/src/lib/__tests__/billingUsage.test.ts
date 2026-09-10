import {
  orderedServices, formatBytes, formatCount, formatMonth,
  SERVICE_ORDER, PAUSED_SERVICES, FREE_SERVICE_KEYS,
  orderedModels, jobsByModel, fixedJobs, secondProviderJobs,
} from '@/lib/billingUsage'
import type { AiJobRow, BillingOrgBlock } from '@/lib/admin-api'

function block(services: Array<Partial<BillingOrgBlock['services'][number]> & { service: string }>): BillingOrgBlock {
  return {
    organisation_id: 1, organisation: 'X', is_platform: false,
    services: services.map((s) => ({
      service: s.service, events: s.events ?? 0, quantity: s.quantity ?? 0,
      input_tokens: s.input_tokens ?? 0, output_tokens: s.output_tokens ?? 0,
      // Which AI versions did this service's work (2026-09-11). Empty = the service HAS no
      // model (email, WhatsApp, OCR), never "we do not know".
      models: s.models ?? [],
    })),
    totals: { events: 0, quantity: 0, input_tokens: 0, output_tokens: 0 },
    storage_bytes: 0,
  }
}

describe('orderedServices', () => {
  test('orders by SERVICE_ORDER, unknowns appended alphabetically', () => {
    const b = block([
      { service: 'whatsapp' }, { service: 'zzz_unknown' }, { service: 'gemini' },
      { service: 'email' }, { service: 'aaa_unknown' },
    ])
    expect(orderedServices(b).map((s) => s.service))
      .toEqual(['gemini', 'email', 'whatsapp', 'aaa_unknown', 'zzz_unknown'])
  })

  test('does not mutate the input array', () => {
    const b = block([{ service: 'whatsapp' }, { service: 'gemini' }])
    const before = b.services.map((s) => s.service)
    orderedServices(b)
    expect(b.services.map((s) => s.service)).toEqual(before)
  })

  test('empty services → empty array', () => {
    expect(orderedServices(block([]))).toEqual([])
  })
})

describe('formatBytes', () => {
  test.each([
    [0, '0 B'],
    [512, '512 B'],
    [1024, '1 KB'],
    [1536, '2 KB'],            // rounds at KB
    [1048576, '1 MB'],
    [1572864, '1.5 MB'],
    [1073741824, '1 GB'],
    [1099511627776, '1 TB'],
  ])('formats %d bytes', (n, expected) => {
    expect(formatBytes(n)).toBe(expected)
  })

  test('non-numeric → 0 B', () => {
    // @ts-expect-error deliberate bad input
    expect(formatBytes(undefined)).toBe('0 B')
  })
})

describe('formatCount', () => {
  test('groups thousands', () => {
    expect(formatCount(1234567)).toBe('1,234,567')
    expect(formatCount(0)).toBe('0')
  })
})

describe('formatMonth', () => {
  test('YYYY-MM → Month YYYY', () => {
    expect(formatMonth('2026-07')).toBe('July 2026')
    expect(formatMonth('2026-01')).toBe('January 2026')
    expect(formatMonth('2026-12')).toBe('December 2026')
  })
  test('malformed returns input unchanged', () => {
    expect(formatMonth('nope')).toBe('nope')
    expect(formatMonth('2026-13')).toBe('2026-13')
  })
})

describe('service constants', () => {
  test('metered order + paused + free are stable', () => {
    expect(SERVICE_ORDER).toEqual(['gemini', 'vision_ocr', 'openai', 'email', 'whatsapp'])
    expect(PAUSED_SERVICES).toEqual(['sms_verify'])
    expect(FREE_SERVICE_KEYS).toEqual(['turnstile'])
  })

  test('Google Workspace is NOT listed as free — we pay for it', () => {
    // 2026-09-11. It was in this list, and the owner's August invoice charges MYR 18.90 for it.
    // It now has its own PlatformCost source and its own line in the cost section. A paid
    // subscription named in a "these cost nothing" footnote tells the one person who reads this
    // page that a recurring bill does not exist.
    expect(FREE_SERVICE_KEYS).not.toContain('workspace')
  })
})

// ── Which AI version did the work, and which is each job set to (2026-09-11) ───────────────

const job = (over: Partial<AiJobRow> & { key: string; model: string }): AiJobRow => ({
  label: over.key, module: `apps/x/${over.key}.py`, seam: 'own client', provider: 'gemini',
  source: 'setting', source_name: 'SOME_MODEL', fixed: false, fallbacks: [],
  fallback_provider: '', fallback_model: '', ...over,
})

describe('orderedModels', () => {
  it('puts the busiest version first', () => {
    const row = block([{ service: 'gemini', models: [
      { model: 'b', events: 1, input_tokens: 0, output_tokens: 0, first_seen: null, last_seen: null },
      { model: 'a', events: 9, input_tokens: 0, output_tokens: 0, first_seen: null, last_seen: null },
    ] }]).services[0]
    expect(orderedModels(row).map((m) => m.model)).toEqual(['a', 'b'])
  })

  it('breaks a tie by name, so the order never wobbles between loads', () => {
    const row = block([{ service: 'gemini', models: [
      { model: 'z', events: 3, input_tokens: 0, output_tokens: 0, first_seen: null, last_seen: null },
      { model: 'a', events: 3, input_tokens: 0, output_tokens: 0, first_seen: null, last_seen: null },
    ] }]).services[0]
    expect(orderedModels(row).map((m) => m.model)).toEqual(['a', 'z'])
  })

  it('⚠ gives back nothing for a service that HAS no model', () => {
    // Email, WhatsApp and Cloud Vision OCR are working exactly as designed. A row saying
    // "unknown" would invent a mystery out of three services that have no model to report.
    expect(orderedModels(block([{ service: 'email' }]).services[0])).toEqual([])
  })

  it('never mutates the row it was given', () => {
    const row = block([{ service: 'gemini', models: [
      { model: 'b', events: 1, input_tokens: 0, output_tokens: 0, first_seen: null, last_seen: null },
      { model: 'a', events: 9, input_tokens: 0, output_tokens: 0, first_seen: null, last_seen: null },
    ] }]).services[0]
    orderedModels(row)
    expect(row.models.map((m) => m.model)).toEqual(['b', 'a'])
  })
})

describe('jobsByModel', () => {
  it('⚠ answers the question an upgrade actually asks', () => {
    // Not "what does this job use" (nineteen answers) but "if this model is replaced, what do I
    // have to touch" (one group).
    const groups = jobsByModel([
      job({ key: 'a', model: 'flash' }), job({ key: 'b', model: 'pro' }),
      job({ key: 'c', model: 'flash' }), job({ key: 'd', model: 'flash' }),
    ])
    expect(groups.map((g) => g.model)).toEqual(['flash', 'pro'])
    expect(groups[0].jobs.map((j) => j.key)).toEqual(['a', 'c', 'd'])
  })

  it('is empty for no jobs, rather than throwing', () => {
    expect(jobsByModel([])).toEqual([])
  })
})

describe('the two lists an upgrade must not walk past', () => {
  it('names the jobs whose model needs a DEPLOY to change', () => {
    const jobs = [job({ key: 'batch', model: 'x', fixed: true }), job({ key: 'normal', model: 'x' })]
    expect(fixedJobs(jobs).map((j) => j.key)).toEqual(['batch'])
  })

  it('names the job that falls through to a SECOND PROVIDER', () => {
    // A different key and a different bill. It has never fired, which is exactly why it would
    // otherwise be missed.
    const jobs = [
      job({ key: 'report', model: 'x', fallback_provider: 'openai', fallback_model: 'gpt-4o-mini' }),
      job({ key: 'other', model: 'x' }),
    ]
    expect(secondProviderJobs(jobs).map((j) => j.key)).toEqual(['report'])
  })

  it('⚠ and both are empty when nothing qualifies', () => {
    // Drive over the bump: a filter that let everything through would pass both tests above.
    const jobs = [job({ key: 'plain', model: 'x' })]
    expect(fixedJobs(jobs)).toEqual([])
    expect(secondProviderJobs(jobs)).toEqual([])
  })
})
