/**
 * TD-421 (A1.9b): a people-search term travels in the X-Search-Term header, NEVER in the URL.
 *
 * An officer searching by IC types a student's full NRIC; Cloud Run logs the request line (path
 * and query string), not custom headers. The header is percent-encoded so a Tamil or Malay name
 * survives HTTP's ASCII-only header rule; the API URI-decodes it
 * (`apps.courses.search.people_search_term`, pinned by `test_search_term_header.py`).
 *
 * Tested through the public functions, not `adminFetch` (private to `lib/admin-api/`).
 */
import { getPartnerStudents, getScholars, getScholarshipApplications } from '@/lib/admin-api'

const realFetch = global.fetch
let calls: Array<{ url: string; headers: Record<string, string> }>

beforeEach(() => {
  calls = []
  global.fetch = jest.fn(async (url: string, init?: { headers?: Record<string, string> }) => {
    calls.push({ url, headers: init?.headers ?? {} })
    return { ok: true, status: 200, json: async () => ({}) }
  }) as unknown as typeof global.fetch
})

afterEach(() => {
  global.fetch = realFetch
})

const IC = '080918-08-1813'
const TAMIL = 'தமிழ்செல்வி'
const MALAY = 'Nur Aisyah binti Abdullah'

const last = () => calls[calls.length - 1]
const isAscii = (s: string) => /^[\x20-\x7e]*$/.test(s)

describe.each([
  ['Applications', (term?: string) => getScholarshipApplications({ q: term, status: 'submitted' }, { token: 't' })],
  ['Scholars', (term?: string) => getScholars({ search: term, programme: 'b40' }, { token: 't' })],
  ['Students', (term?: string) => getPartnerStudents({ q: term, exam: 'spm' }, { token: 't' })],
])('%s list', (_name, fetchList) => {
  it('sends an IC in the header and never in the URL', async () => {
    await fetchList(IC)
    expect(last().url).not.toContain('080918')
    expect(last().url).not.toMatch(/[?&](q|search)=/)
    expect(last().headers['X-Search-Term']).toBe(IC)
    // The other filters still travel in the query string.
    expect(last().url).toMatch(/[?&](status|programme|exam)=/)
  })

  it('percent-encodes a Tamil name so the header stays ASCII, and it decodes back exactly', async () => {
    await fetchList(TAMIL)
    const sent = last().headers['X-Search-Term']
    expect(isAscii(sent)).toBe(true)
    expect(decodeURIComponent(sent)).toBe(TAMIL)
    expect(decodeURI(last().url)).not.toContain(TAMIL)
  })

  it('carries a Malay name with spaces intact', async () => {
    await fetchList(MALAY)
    expect(decodeURIComponent(last().headers['X-Search-Term'])).toBe(MALAY)
  })

  it('sends no header for a blank or missing term', async () => {
    await fetchList('   ')
    expect(last().headers).not.toHaveProperty('X-Search-Term')
    await fetchList(undefined)
    expect(last().headers).not.toHaveProperty('X-Search-Term')
  })
})
