/**
 * THE DRIFT TEST for `FundingSummaryRow` in `admin-api.ts` — named by its `drift-test:` marker
 * (code health H10).
 *
 * This interface describes **the only student data a `finance` admin ever sees.** The api side is
 * an allowlist by construction — a plain `Serializer` with every field explicit and no model
 * passthrough — precisely so a new column on `ScholarshipApplication` can never reach a finance
 * screen by accident. The web copy is the reader of that allowlist, and the pair is worth guarding
 * in BOTH directions:
 *   • a key the api grew and the interface has not → a column nobody can render (today's case);
 *   • a key the interface claims and the api does not send → `undefined` painted as a figure.
 *
 * Characterised first (the H8 rule): the api's declared fields listed against the interface's
 * declared keys. They DISAGREE by one — `programme` — pinned below as **TD-265**, not fixed.
 */
import * as fs from 'fs'
import * as path from 'path'

import { readApi } from '@/test/apiSource'

const SERIALIZERS = 'apps/scholarship/serializers_admin.py'
const src = readApi(SERIALIZERS)

/** The serializer's declared fields, in declaration order. */
const apiFields = (() => {
  const body = src.split('\nclass FundingSummaryRowSerializer(')[1]
  if (!body) {
    throw new Error(
      `drift test: FundingSummaryRowSerializer is no longer in ${SERIALIZERS}. The finance `
      + 'allowlist has moved — follow it, never delete the assertion.')
  }
  const cls = body.split('\nclass ')[0]
  return [...cls.matchAll(/^ {4}([a-z_]+) = serializers\./gm)].map((m) => m[1])
})()

/**
 * The interface's declared keys, read from the source itself (an interface has no runtime).
 *
 * ⚠ MOVED at code health H13: `admin-api.ts` is a barrel and `FundingSummaryRow` now lives in
 * `admin-api/payments.ts`, beside the payment run it reconciles. The path followed the code —
 * never delete the assertion.
 */
const webKeys = (() => {
  const text = fs.readFileSync(
    path.join(__dirname, '..', 'admin-api', 'payments.ts'), 'utf8')
  const block = text.match(/export interface FundingSummaryRow \{([\s\S]*?)\n\}/)
  if (!block) throw new Error('drift test: `export interface FundingSummaryRow { … }` not found')
  return [...block[1].matchAll(/^\s{2}([a-z_]+)\??:/gm)].map((m) => m[1])
})()

describe('parse sanity — both sides were really read', () => {
  test('the api allowlist parsed as an explicit field list', () => {
    expect(apiFields.length).toBeGreaterThanOrEqual(10)
    expect(apiFields).toContain('award_amount')
    expect(apiFields[0]).toBe('application_id')
  })

  test('the interface parsed as a key list', () => {
    expect(webKeys.length).toBeGreaterThanOrEqual(10)
    expect(webKeys).toContain('vircle_id')
  })
})

describe('the finance allowlist — nothing beyond what reconciles a payment', () => {
  test('the interface claims no key the api does not send', () => {
    // This is the direction that paints `undefined` into a money column.
    expect(webKeys.filter((k) => !apiFields.includes(k))).toEqual([])
  })

  /**
   * ⚠ THE BOUNDARY, RESTATED AS A TEST. The serializer's docstring lists what is deliberately
   * excluded and says it must not be added without a role-matrix change. A guard that only
   * compared the two lists would happily bless the day somebody adds `nric` to both.
   */
  // Matched on whole `_`-separated SEGMENTS, not substrings: `ic` inside `application_id` is not
  // an IC number, and a guard that cried wolf on it would be deleted within a week.
  const segments = (field: string) => field.split('_')
  test.each(['nric', 'ic', 'email', 'phone', 'address', 'income', 'verdict', 'documents', 'narrative'])(
    'neither side carries `%s` — finance has no B40 scope to see it through', (forbidden) => {
      expect(apiFields.filter((f) => segments(f).includes(forbidden))).toEqual([])
      expect(webKeys.filter((k) => segments(k).includes(forbidden))).toEqual([])
    })

  test('the api side is still an allowlist, not a model dump', () => {
    const cls = src.split('\nclass FundingSummaryRowSerializer(')[1].split('\nclass ')[0]
    expect(cls).toMatch(/serializers\.Serializer/)      // not ModelSerializer
    expect(cls).not.toMatch(/fields\s*=\s*'__all__'/)
  })
})

/**
 * ⚠ PINNED DISAGREEMENT (TD-265) — reported, not fixed.
 *
 * The api grew `programme` (P2b: *which gift funds this student*, added as a COLUMN for finance to
 * reconcile per programme). The TypeScript interface never gained it and the payments table never
 * drew it, so the field is sent on every row and read by nothing.
 *
 * It is not a leak — `programme` is inside the finance boundary by design — it is a column the
 * server pays to compute and no officer can see. It is NOT fixed here because adding a column to a
 * live finance table is a visible change, and H10's rule is that no visible answer moves.
 *
 * These assertions pin today's shape on both sides, so the gap cannot widen and closing it turns
 * this test red on purpose — at which point the expectation below is edited, deliberately.
 */
describe('PINNED: the api sends one field the web never declared (TD-265)', () => {
  test('the gap is exactly `programme`, and nothing else', () => {
    expect(apiFields.filter((f) => !webKeys.includes(f))).toEqual(['programme'])
  })

  test('the api really does compute it, so this is a drift and not a stale comment', () => {
    const cls = src.split('\nclass FundingSummaryRowSerializer(')[1].split('\nclass ')[0]
    expect(cls).toMatch(/^ {4}def get_programme\(/m)
  })
})
