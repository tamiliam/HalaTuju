/**
 * @jest-environment jsdom
 *
 * Request #54 (owner 2026-11-06): the Household income field shows what the student DECLARED. A tick
 * only on a ±10% / RM300 document match (`household_check.income.matches`); when the documents
 * disagree, an amber note names what they show; when an earner's document is untrusted or unread,
 * the note gives the total read so far and names who. Per capita = declared income ÷ effective size.
 * Rendered through the real English messages, with synthetic figures only.
 */
import { render, screen } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'
import enMessages from '@/messages/en.json'
import { ApplicantCards, householdFigures } from './ApplicantCards'
import type { T } from './shared'

const t = ((key: string, params?: Record<string, string>) => {
  let v: unknown = enMessages
  for (const part of key.split('.')) v = (v as Record<string, unknown> | undefined)?.[part]
  let s = typeof v === 'string' ? v : key
  for (const [k, val] of Object.entries(params ?? {})) s = s.replace(`{${k}}`, String(val))
  return s
}) as unknown as T

type Income = NonNullable<AdminScholarshipDetail['household_check']>['income']
const SIZE = { described: 4, stated: 4, accounted: true, overcount: false, confirmed: false }

function renderCard(income: Partial<Income>, extra: Partial<AdminScholarshipDetail> = {}) {
  const app = buildApplicationDetail('submitted', {
    household_income: 4000, household_size: 4,
    household_check: {
      income: { documented_total: null, all_known: true, genuine: true, stated: 4000, matches: false,
        read_total: null, unchecked: [], has_documents: true, ...income },
      size: SIZE,
    },
    ...extra,
  })
  render(<ApplicantCards app={app} t={t} vtip={() => undefined} {...householdFigures(app, t)} />)
}

const incomeField = () => screen.getByText('Household income').closest('div') as HTMLElement
const TICK = 'Matches the income documents'

describe('ApplicantCards — household income (request #54)', () => {
  it('ticks the declared figure on a match, with no note', () => {
    renderCard({ documented_total: 4200, read_total: 4200, matches: true })
    const f = incomeField()
    expect(f.textContent).toContain('RM 4,000')
    expect(f.textContent).not.toContain('4,200')
    expect(f.querySelector(`[aria-label="${TICK}"]`)).not.toBeNull()
    expect(f.querySelector('p')).toBeNull()
  })

  it('keeps the declared figure, no tick, and an amber note when the documents disagree', () => {
    renderCard({ documented_total: 5100, read_total: 5100, matches: false })
    const f = incomeField()
    expect(f.querySelector('dd')!.textContent).toBe('RM 4,000')
    expect(f.querySelector(`[aria-label="${TICK}"]`)).toBeNull()
    const note = f.querySelector('p')!
    expect(note.textContent).toBe('Documents show RM 5,100')
    expect(note.className).toContain('text-caution-700')
  })

  it('gives the total read so far and names an unverified earner', () => {
    renderCard({ all_known: true, genuine: false, read_total: 5100,
      unchecked: [{ member: 'father', reason: 'unverified' }] })
    const f = incomeField()
    expect(f.querySelector('dd')!.textContent).toBe('RM 4,000')
    expect(f.querySelector(`[aria-label="${TICK}"]`)).toBeNull()
    expect(f.querySelector('p')!.textContent).toBe(
      "Documents read so far show RM 5,100. Father's income document is not fully checked.")
  })

  it('names an unread earner', () => {
    renderCard({ all_known: false, read_total: 2000, unchecked: [{ member: 'mother', reason: 'unread' }] })
    expect(incomeField().querySelector('p')!.textContent).toBe(
      "Documents read so far show RM 2,000. Mother's income has not been read yet.")
  })

  it('shows no note when there are no income documents at all', () => {
    renderCard({ all_known: false, read_total: 0, has_documents: false,
      unchecked: [{ member: 'father', reason: 'unread' }] })
    const f = incomeField()
    expect(f.querySelector('dd')!.textContent).toBe('RM 4,000')
    expect(f.querySelector('p')).toBeNull()
  })

  it('computes per capita from the declared income, never the documents\' total', () => {
    renderCard({ documented_total: 6000, read_total: 6000, matches: false })
    const pc = screen.getByText('Per capita income').closest('div') as HTMLElement
    expect(pc.textContent).toContain('RM 1,000')
  })

  it('divides by the confirmed roster count once the student confirms it', () => {
    const app = buildApplicationDetail('submitted', {
      household_income: 4000, household_size: 4,
      household_check: {
        income: { documented_total: null, all_known: false, stated: 4000, matches: false },
        size: { ...SIZE, described: 5, accounted: false, confirmed: true },
      },
    })
    expect(householdFigures(app, t).perCapita).toBe(800)
  })
})
