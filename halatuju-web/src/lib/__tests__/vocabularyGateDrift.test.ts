/**
 * A4.7 / CO-12 - vocabularies that were not yet a gate.
 *
 * The mirror ledger (`code-standards.json`, `unguarded_mirrors`) is already at zero, so every vocabulary
 * that SAYS it copies the api has a drift test. These two copy it without saying so, and had nothing:
 *   1. the payment-run status pill: the api owns `PaymentRun.STATUS_CHOICES`, the web paints one tone each;
 *   2. the call-language options: `preferred_call_language` is a free CharField on the api, so the only
 *      closed list is the web's, and the api branches on two of its values (`emails/sending.py`).
 * Every parse is sanity-checked, so a refactor that stops matching turns this RED, not into a no-op.
 */
import { statusPill } from '@/lib/paymentStatus'
import { CALL_LANGUAGE_OPTIONS } from '@/lib/scholarship'
import { pyChoiceValues, readApi } from '@/test/apiSource'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

describe('payment-run status pill vs PaymentRun.STATUS_CHOICES', () => {
  const py = pyChoiceValues(readApi('apps/scholarship/models/funding.py'), 'STATUS_CHOICES')
  // The tone each status must wear: in flight is amber, done is green, cancelled is grey, draft is blue.
  const TONE: Record<string, string> = {
    draft: 'info', admin_signed: 'caution', finance_checked: 'caution',
    completed: 'positive', cancelled: 'ground',
  }
  it('parses (sanity)', () => expect(py.length).toBeGreaterThanOrEqual(5))
  it('the api has no status the web does not paint, and the web names none the api lacks', () => {
    expect([...py].sort()).toEqual(Object.keys(TONE).sort())
  })
  it.each(Object.entries(TONE))('%s wears the %s tone', (status, tone) => {
    expect(statusPill(status)).toContain(`bg-${tone}-100`)
  })
})

describe('call-language options vs what the api branches on', () => {
  const sending = readApi('apps/scholarship/emails/sending.py')
  const branch = sending.match(/call_lang in \(([^)]*)\)/)
  it('finds the api branch (sanity)', () => expect(branch).not.toBeNull())
  it('every language the api branches on is an option the student can pick', () => {
    const apiValues = [...(branch?.[1] ?? '').matchAll(/'([^']+)'/g)].map((m) => m[1])
    expect(apiValues.length).toBeGreaterThanOrEqual(2)
    for (const v of apiValues) expect(CALL_LANGUAGE_OPTIONS).toContain(v)
  })
  it('every option has a label in all three languages', () => {
    for (const [name, bundle] of Object.entries({ en, ms, ta })) {
      const labels = (bundle as any).scholarship.apply.callLang
      for (const code of CALL_LANGUAGE_OPTIONS) {
        expect([name, code, typeof labels[code]]).toEqual([name, code, 'string'])
      }
    }
  })
})
