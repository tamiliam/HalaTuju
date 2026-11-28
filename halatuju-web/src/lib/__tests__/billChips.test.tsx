/**
 * @jest-environment jsdom
 */
/**
 * Chip Sprint 2 (owner 2026-11-28): the bill chips on the officer drawer.
 * - every REASON_WORDS key exists in en, ms and ta (a raw engine word is never shown);
 * - the drawer's chip line draws the field names, the amount as a plain value, and never a name or
 *   an address (those live in the opened document's Checks panel). All values are invented.
 */
import { render } from '@testing-library/react'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import type { AdminApplicantDocument } from '@/lib/admin-api'
import { ChipLine, REASON_WORDS, ReasonLines, drawerChips } from '../../app/admin/scholarship/[id]/view/docChipRow'

function lookup(messages: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>((o, k) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), messages)
}

const t = (key: string) => key

const bill = (o: Record<string, unknown> = {}, auth?: string) => ({
  id: 1, doc_type: 'water_bill',
  utility_check: { name: 'SAMPLE HOLDER', address: 'SAMPLE ADDRESS 1', monthly_bill: '84.20', unpaid_balance: '',
    address_status: 'found', current_status: 'current', bill_month: 'Oct 2026', reasonable_status: 'reasonable',
    reasonable_detail: '', outstanding_status: '', name_note: '', ...o },
  authenticity: auth ? { status: auth, reason: '' } : null,
}) as unknown as AdminApplicantDocument

describe('bill reason words', () => {
  test.each(Object.entries(REASON_WORDS))('%s has words in en, ms and ta', (_k, key) => {
    for (const m of [en, ms, ta]) {
      const v = lookup(m, key)
      expect(typeof v).toBe('string')
      expect((v as string).length).toBeGreaterThan(0)
    }
  })

  test('the officer words carry no B40', () => {
    for (const key of Object.values(REASON_WORDS)) expect(String(lookup(en, key))).not.toMatch(/B40/)
  })
})

describe('the bill chip line in the drawer', () => {
  test('Name, Address, Date, then the amount as a plain value', () => {
    const { container } = render(<ChipLine chips={drawerChips(bill())} t={t} />)
    const chips = [...container.querySelectorAll('[data-chip]')]
    expect(chips.map((c) => c.getAttribute('data-chip'))).toEqual(['green', 'green', 'green', 'plain'])
    expect(chips[3].textContent).toBe('RM 84.20')
  })

  test('no name or address ever renders in the drawer chip line or its reason lines', () => {
    for (const d of [bill(), bill({ name_note: 'unrelated', address_status: 'mismatch', current_status: 'stale' }),
      bill({}, 'not_water_bill'), bill({}, 'suspect')]) {
      const chips = drawerChips(d)
      const { container } = render(<><ChipLine chips={chips} t={t} /><ReasonLines chips={chips} t={t} /></>)
      expect(container.textContent).not.toContain('SAMPLE HOLDER')
      expect(container.textContent).not.toContain('SAMPLE ADDRESS')
    }
  })

  test('a wrong type caps the chips red and drops the amount', () => {
    const chips = drawerChips(bill({}, 'not_water_bill'))
    expect(chips.map((c) => [c.key, c.state])).toEqual([['type', 'red'], ['name', 'red'], ['address', 'red'], ['date', 'red']])
  })

  test('a served reason draws its fixed words', () => {
    const served = [{ key: 'date', status: 'not' as const, state: 'red' as const, student_action: 'none', reason: 'stale', kind: 'fact' as const }]
    const { container } = render(<ReasonLines chips={served} t={t} />)
    expect(container.textContent).toContain('admin.scholarship.docsDrawer.reason.billDateStale')
  })
})
