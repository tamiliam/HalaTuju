/**
 * M4b review nit (2026-10-30): the reviewer never sees a raw genuineness `doc_seen` code. Every code
 * the api's scorers store for a document the interview question names is a label in en / ms / ta;
 * the list is pinned to the api's own constants, so a new code turns this red.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { readApi } from '@/test/apiSource'
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

  it('the list matches the api (drift)', () => {
    const mp = readApi('apps/scholarship/genuineness/matric_poly_doc.py')
    const codes = mp.match(/^MATRIC_SLIP, POLY_SLIP, POLY_PORTAL, MATRIC_OFFER = \(\s*([^)]*)\)/m)
    const notFinal = mp.match(/^MATRIC_NOT_FINAL, POLY_NOT_FINAL = ([^\n]*)/m)
    expect(codes && notFinal).toBeTruthy()
    const mpCodes = `${codes![1]} ${notFinal![1]}`.match(/'([a-z_]+)'/g)!.map((q) => q.slice(1, -1))
    expect(mpCodes).toHaveLength(6)
    for (const fam of ['matric_transcript', 'poly_transcript']) expect(mp).toContain(`'${fam}')`)
    const stpm = readApi('apps/scholarship/genuineness/stpm_doc.py')
    const online = stpm.match(/^ONLINE_PAGE = '([a-z_]+)'/m)
    const stpmLists = stpm.match(/^STPM_LISTS = \{([^}]*)\}/m)
    expect(online && stpmLists).toBeTruthy()
    const rd = readApi('apps/scholarship/genuineness/results_doc.py')
    const results = rd.match(/^_RESULTS_LISTS = \{'results_slip': SLIP_SIGNATURES, 'certificate': CERT_SIGNATURES,/m)
    const str = rd.match(/^_STR_LISTS = \{([^}]*)\}/m)
    expect(results && str).toBeTruthy()
    const keys = (s: string) => s.match(/'([a-z_]+)':/g)!.map((q) => q.slice(1, -2))
    const api = new Set([...mpCodes, 'matric_transcript', 'poly_transcript', online![1], ...keys(stpmLists![1]),
      'results_slip', 'certificate', 'birth_certificate', 'epf', ...keys(str![1])])
    expect([...api].sort()).toEqual([...DOC_SEEN_CODES].sort())
  })
})
