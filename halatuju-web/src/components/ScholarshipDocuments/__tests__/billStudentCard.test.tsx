/**
 * @jest-environment jsdom
 */
/**
 * Chip Sprint 2 review round 1: the student's bill card shows no holder name and no bill month (the
 * approved mock has neither), a screen reader hears each chip's state, and the monthly charge is trimmed.
 * All values are invented.
 */
import { render } from '@testing-library/react'
import type { ApplicantDocument } from '@/lib/api'
import { UtilityChecklist } from '../checklists'
import en from '@/messages/en.json'

const t = (key: string) => {
  const v = key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], en)
  return typeof v === 'string' ? v : key
}
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t, locale: 'en' }) }))

const doc = (o: Record<string, unknown> = {}) => ({
  id: 7, doc_type: 'water_bill',
  utility_check: { name: 'SAMPLE HOLDER', address: '1 JALAN CONTOH', bill_month: 'Aug 2026', monthly_bill: '  84.20 ',
    address_status: 'found', current_status: 'ageing', name_note: 'unrelated', ...o },
}) as unknown as ApplicantDocument

describe('the student bill card', () => {
  it('shows no holder name and no bill month', () => {
    const { container } = render(<UtilityChecklist doc={doc()} t={t} />)
    const text = container.textContent || ''
    expect(text).not.toContain('SAMPLE HOLDER')
    expect(text).not.toContain('Aug 2026')
  })

  it('keeps the address the student saw before, and trims the monthly charge', () => {
    const { container } = render(<UtilityChecklist doc={doc()} t={t} />)
    expect(container.textContent).toContain('1 JALAN CONTOH')
    expect(container.textContent).toContain('84.20')
    expect(container.textContent).not.toContain(' 84.20 ')
  })

  it('speaks each chip state to a screen reader', () => {
    const { container } = render(<UtilityChecklist doc={doc()} t={t} />)
    const chips = Array.from(container.querySelectorAll('[data-chip]'))
    expect(chips.length).toBeGreaterThan(0)
    for (const c of chips) {
      const word = c.querySelector('[data-chip-state]')
      expect(word?.textContent).toBeTruthy()
    }
  })
})
