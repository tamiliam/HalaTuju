/**
 * @jest-environment jsdom
 *
 * OCR-13: the API's offer IC status 'not_printed' (UUM and UPSI leave the IC off their letters by
 * design). Owner chip rule, 2026-11-26: the student sees a GREY chip with the field name only, never
 * the words "Not printed" and never a missing-key label. `t` reads the real copy in each language.
 */
import { render } from '@testing-library/react'
import type { ApplicantDocument, PathwayCheck } from '@/lib/api'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

import { OfferLetterChecklist } from './checklistsPathway'

const tFor = (file: unknown) => (key: string): string =>
  String(key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], file) ?? key)

const CHECK: PathwayCheck = {
  name: 'match', ic: 'not_printed', candidate_name: 'Anbu A/L Raj', candidate_nric: '', programme: 'Ijazah Sarjana Muda',
  institution: 'Universiti Contoh', issuer: '', offer_date: '', intake: '2024', address: '',
}

const offer = { id: 1, doc_type: 'offer_letter', pathway_check: CHECK } as unknown as ApplicantDocument

describe('the offer IC chip when the issuer prints no IC', () => {
  it.each([['en', en], ['ms', ms], ['ta', ta]])('shows the field name in grey (%s)', (_lang, file) => {
    const t = tFor(file)
    const { container } = render(<OfferLetterChecklist doc={offer} t={t} />)
    const chips = Array.from(container.querySelectorAll('span.rounded-full'))
    const icChip = chips[1]
    expect(icChip.textContent).toBe(t('scholarship.docs.pathwayCheck.ic'))
    expect(icChip.className).toContain('bg-ground-50')
    expect(icChip.className).not.toMatch(/caution|critical|positive/)
    expect(container.textContent).not.toContain('scholarship.docs.pathwayCheck')
    expect(container.textContent?.toLowerCase()).not.toContain('not printed')
  })
})
