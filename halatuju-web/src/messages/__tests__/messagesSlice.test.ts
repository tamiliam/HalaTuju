/**
 * TD-360 Sprint 1 (2026-10-21): the build-time cut of a message file into slices, proved on the
 * REAL files.
 *
 * `scripts/messages-slice-loader.js` answers `import x from '@/messages/en.json?slice=admin'`. jest
 * never runs it (its `moduleNameMapper` hands a `?slice=` import the whole file), so this is the
 * one place the cut itself is checked. If a slice dropped a namespace, a route would render raw
 * dotted keys in production and every jest render test would still pass on the whole file.
 *
 * Claims, for en, ms and ta:
 *  - `core ∪ admin ∪ documents ∪ scholarship` is the WHOLE file — no namespace lost, every value
 *    identical — when merged as the runtime merges them (`mergeSlice`, children of a split namespace);
 *  - no two slices share a namespace, and the one SPLIT namespace (`scholarship`, TD-416) shares no
 *    CHILD — nothing shipped twice;
 *  - `sponsor` is exactly the four `sponsor*` namespaces (TD-416);
 *  - `admin` is exactly the `admin` namespace, `documents` exactly `documentsTab` (third results
 *    route S3, the student Documents tab's words), `scholarship` every `scholarship.*` child except
 *    `CORE_KEEPS` (the menu and banner words most routes read), and `core` is every other namespace
 *    plus those kept children (so a new namespace defaults to core and can never go missing);
 *  - the runtime's `SPLIT_NAMESPACES` names exactly the loader's `CORE_KEEPS` namespaces;
 *  - an unknown slice name THROWS rather than shipping an empty catalogue;
 *  - the loader turns a query into JSON text that parses to the slice.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

import { SPLIT_NAMESPACES, mergeSlice } from '@/lib/messages'
import loader, {
  CORE_KEEPS as KEEPS, pickSlice as pick, sliceOfQuery as ofQuery,
} from '../../../scripts/messages-slice-loader'

const pickSlice = pick as (json: Record<string, unknown>, name: string) => Record<string, unknown>
const sliceOfQuery = ofQuery as (q: string) => string
const CORE_KEEPS = KEEPS as Record<string, string[]>
type Cat = Record<string, Record<string, unknown>>

const FILES = [['en', en], ['ms', ms], ['ta', ta]] as Array<[string, Record<string, unknown>]>

describe.each(FILES)('the %s file, cut into slices', (_name, file) => {
  const core = pickSlice(file, 'core')
  const admin = pickSlice(file, 'admin')
  const documents = pickSlice(file, 'documents')
  const scholarship = pickSlice(file, 'scholarship') as Cat
  const sponsor = pickSlice(file, 'sponsor')
  const whole = file.scholarship as Record<string, unknown>
  const SPONSOR_NS = ['sponsorPortal', 'sponsorAuth', 'sponsorPool', 'sponsorLanding']

  test('core ∪ admin ∪ documents ∪ scholarship ∪ sponsor is the whole file, value for value', () => {
    // Merged the way the runtime merges them, in BOTH orders (Malay core and Malay scholarship
    // arrive in parallel, either first) — a plain spread would drop the split namespace's half.
    for (const order of [[core, admin, documents, scholarship, sponsor], [sponsor, scholarship, documents, admin, core]]) {
      const merged = order.reduce((acc, s) => mergeSlice(acc, s), {} as Record<string, unknown>)
      expect(merged).toEqual(file)
    }
  })

  test('no two slices share a namespace, and the split namespace shares no child', () => {
    expect(Object.keys(core).filter((ns) => ns in admin || ns in documents || ns in sponsor)).toEqual([])
    expect(Object.keys(admin).filter((ns) => ns in documents || ns in scholarship || ns in sponsor)).toEqual([])
    expect(Object.keys(sponsor).filter((ns) => ns in documents || ns in scholarship)).toEqual([])
    expect(Object.keys(scholarship)).toEqual(['scholarship'])
    const coreChildren = Object.keys((core as Cat).scholarship)
    expect(coreChildren.filter((c) => c in scholarship.scholarship)).toEqual([])
  })

  test('TD-416: scholarship holds every scholarship.* child but the kept ones; core holds those only', () => {
    expect(Object.keys((core as Cat).scholarship).sort()).toEqual([...CORE_KEEPS.scholarship].sort())
    for (const k of CORE_KEEPS.scholarship) expect((core as Cat).scholarship[k]).toBe(whole[k])
    expect(Object.keys(scholarship.scholarship))
      .toEqual(Object.keys(whole).filter((k) => !CORE_KEEPS.scholarship.includes(k)))
    for (const k of Object.keys(scholarship.scholarship)) expect(scholarship.scholarship[k]).toBe(whole[k])
    // A floor: the slice is the bulk of the namespace, not a sliver (13 children on 2026-10-29).
    expect(Object.keys(scholarship.scholarship).length).toBeGreaterThanOrEqual(10)
  })

  test('TD-416: sponsor is exactly the four sponsor* namespaces, whole', () => {
    expect(Object.keys(sponsor).sort()).toEqual([...SPONSOR_NS].sort())
    for (const ns of SPONSOR_NS) expect(sponsor[ns]).toBe(file[ns])
  })

  test('admin, documents and sponsor are their namespaces alone; core is every other namespace', () => {
    expect(Object.keys(admin)).toEqual(['admin'])
    expect(admin.admin).toBe(file.admin)
    expect(Object.keys(documents)).toEqual(['documentsTab'])
    expect(documents.documentsTab).toBe(file.documentsTab)
    expect(Object.keys(core)).toEqual(Object.keys(file)
      .filter((ns) => ns !== 'admin' && ns !== 'documentsTab' && !SPONSOR_NS.includes(ns)))
    // A floor, so a file that lost its namespaces cannot pass the identity checks above on {}.
    expect(Object.keys(core).length).toBeGreaterThanOrEqual(30)
  })
})

describe('the split namespaces (TD-416)', () => {
  test('the runtime (SPLIT_NAMESPACES) and the loader (CORE_KEEPS) name the same ones', () => {
    expect([...SPLIT_NAMESPACES].sort()).toEqual(Object.keys(CORE_KEEPS).sort())
  })

  test('every kept child is real in all three files', () => {
    for (const [ns, kept] of Object.entries(CORE_KEEPS)) {
      for (const file of [en, ms, ta] as Array<Record<string, Record<string, unknown>>>) {
        for (const k of kept) expect(file[ns]).toHaveProperty([k])
      }
    }
  })
})

describe('the loader', () => {
  test('an unknown slice name throws — never an empty catalogue', () => {
    expect(() => pickSlice(en as Record<string, unknown>, 'sponsors')).toThrow(/unknown slice "sponsors"/)
    expect(() => pickSlice(en as Record<string, unknown>, '')).toThrow(/unknown slice/)
  })

  test('the slice comes from the resource query', () => {
    expect(sliceOfQuery('?slice=admin')).toBe('admin')
    expect(sliceOfQuery('?slice=core')).toBe('core')
    expect(() => sliceOfQuery('')).toThrow(/no slice named/)
  })

  test('run as webpack runs it, it returns JSON text of the slice', () => {
    const source = JSON.stringify(en)
    const out = (loader as (this: { resourceQuery: string }, s: string) => string)
      .call({ resourceQuery: '?slice=admin' }, source)
    expect(JSON.parse(out)).toEqual({ admin: (en as Record<string, unknown>).admin })
  })

  test('a namespace added tomorrow lands in core by default', () => {
    const tomorrow = { ...(en as Record<string, unknown>), brandNewNamespace: { hello: 'Hello' } }
    expect(pickSlice(tomorrow, 'core')).toHaveProperty('brandNewNamespace')
    expect(pickSlice(tomorrow, 'admin')).not.toHaveProperty('brandNewNamespace')
    expect(pickSlice(tomorrow, 'documents')).not.toHaveProperty('brandNewNamespace')
    expect(pickSlice(tomorrow, 'scholarship')).not.toHaveProperty('brandNewNamespace')
    expect(pickSlice(tomorrow, 'sponsor')).not.toHaveProperty('brandNewNamespace')
  })
})
