/**
 * DRIFT: the `doc_seen` code list is pinned to the api's own constants, so a new code turns this red.
 * The labels themselves are tested in `docSeen.test.ts`.
 */
import { readApi } from '@/test/apiSource'
import { DOC_SEEN_CODES } from '../docSeen'

describe('doc_seen codes', () => {
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
