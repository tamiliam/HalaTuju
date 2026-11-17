/**
 * @jest-environment jsdom
 *
 * H3a, owner ruling "1A" (2026-11-15): the student's offer card shows a short reason when the
 * course started outside the gift's years ("This gift is for students whose course started in
 * 2025 or 2026."). It is not a block: the line says a reviewer still decides. Nothing is shown
 * for an unknown year or a gift with no setting (the server sends no `start_year_note`).
 * `t` reads the real English copy, so the sentence the student sees is what is asserted.
 */
import { render, screen } from '@testing-library/react'
import type { ApplicantDocument, PathwayCheck } from '@/lib/api'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

import { OfferLetterChecklist, startYearLine } from './checklistsPathway'

const t = (key: string): string =>
  String(key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], en) ?? key)

const CHECK: PathwayCheck = {
  name: 'match', ic: 'match', candidate_name: 'Anbu A/L Raj', candidate_nric: '', programme: 'Ijazah Sarjana Muda',
  institution: 'Universiti Contoh', issuer: '', offer_date: '', intake: '2024', address: '',
}

const offer = (extra: Partial<PathwayCheck>): ApplicantDocument =>
  ({ id: 1, doc_type: 'offer_letter', pathway_check: { ...CHECK, ...extra } }) as unknown as ApplicantDocument

describe('the start-year line on the student offer card', () => {
  it('names the gift years, joined with "or", and says a reviewer still decides', () => {
    render(<OfferLetterChecklist doc={offer({ start_year_note: { years: [2025, 2026] } })} t={t} />)
    expect(screen.getByTestId('offer-start-year-note').textContent).toBe(
      'This gift is for students whose course started in 2025 or 2026. '
        + 'A reviewer will still look at your application and decide.',
    )
  })

  it('reads one year on its own and three with commas', () => {
    const one = render(<>{startYearLine([2026], t)}</>)
    expect(one.container.textContent).toBe(
      'This gift is for students whose course started in 2026. A reviewer will still look at your application and decide.',
    )
    one.unmount()
    const three = render(<>{startYearLine([2024, 2025, 2026], t)}</>)
    expect(three.container.textContent).toContain('started in 2024, 2025 or 2026.')
  })

  it('shows nothing when the server sends no note (unknown year, no setting, inside the years)', () => {
    for (const note of [undefined, null, { years: [] }]) {
      const { unmount } = render(<OfferLetterChecklist doc={offer({ start_year_note: note })} t={t} />)
      expect(screen.queryByTestId('offer-start-year-note')).toBeNull()
      unmount()
    }
  })

  it('has the copy in every language file, with the same placeholders', () => {
    for (const file of [en, ms, ta]) {
      const msgs = file.documentsTab.pathwayCheck
      expect(msgs.startYearOne).toContain('{year}')
      expect(msgs.startYearMany).toContain('{years}')
      expect(msgs.startYearMany).toContain('{last}')
    }
  })
})
