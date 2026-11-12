/**
 * M4b review nit (2026-10-30): the reviewer never sees a raw genuineness `doc_seen` code. Every code
 * the api's scorers store for a document the interview question names is a label in en / ms / ta;
 * the list is pinned to the api's own constants, so a new code turns this red.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { DOC_SEEN_CODES, anomalyParams, docSeenLabel } from '../docSeen'

const t = (key: string) => `T(${key})`

function lookup(messages: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>((o, k) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), messages)
}

describe('doc_seen labels', () => {
  it('every listed code has plain words in en, ms and ta, and so does "other"', () => {
    for (const messages of [en, ms, ta]) {
      for (const code of [...DOC_SEEN_CODES, 'other']) {
        const label = lookup(messages, `admin.scholarship.docSeen.${code}`)
        expect(typeof label === 'string' && label.length > 3).toBe(true)
        expect(label).not.toMatch(/_/)
      }
    }
  })

  it('a known code reads its label, an unknown code the generic words, free words as they are', () => {
    expect(docSeenLabel(t, 'matric_offer_letter')).toBe('T(admin.scholarship.docSeen.matric_offer_letter)')
    expect(docSeenLabel(t, 'some_new_family')).toBe('T(admin.scholarship.docSeen.other)')
    expect(docSeenLabel(t, '')).toBe('T(admin.scholarship.docSeen.other)')
    expect(docSeenLabel(t, 'A typed letter')).toBe('A typed letter')
  })

  it("an anomaly's seen param is put into words, the rest kept as strings", () => {
    expect(anomalyParams(t, { doc: 'Matriculation results', status: 'not_higher_results', seen: 'poly_portal_page' }))
      .toEqual({ doc: 'Matriculation results', status: 'not_higher_results', seen: 'T(admin.scholarship.docSeen.poly_portal_page)' })
    expect(anomalyParams(t, { doc: 'STR', n: 2 })).toEqual({ doc: 'STR', n: '2' })
  })
})
