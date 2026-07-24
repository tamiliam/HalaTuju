import {
  orderedServices, formatBytes, formatCount, formatMonth,
  SERVICE_ORDER, PAUSED_SERVICES, FREE_SERVICE_KEYS,
} from '@/lib/billingUsage'
import type { BillingOrgBlock } from '@/lib/admin-api'

function block(services: Array<Partial<BillingOrgBlock['services'][number]> & { service: string }>): BillingOrgBlock {
  return {
    organisation_id: 1, organisation: 'X', is_platform: false,
    services: services.map((s) => ({
      service: s.service, events: s.events ?? 0, quantity: s.quantity ?? 0,
      input_tokens: s.input_tokens ?? 0, output_tokens: s.output_tokens ?? 0,
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
    expect(FREE_SERVICE_KEYS).toEqual(['workspace', 'turnstile'])
  })
})
