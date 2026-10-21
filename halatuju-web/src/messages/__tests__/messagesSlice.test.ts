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
 *  - `core ∪ admin` is the WHOLE file — no namespace lost, every value identical;
 *  - `core ∩ admin` is empty — no namespace shipped twice;
 *  - `admin` is exactly the `admin` namespace, and `core` is every other one (so a new namespace
 *    defaults to core and can never go missing from a route);
 *  - an unknown slice name THROWS rather than shipping an empty catalogue;
 *  - the loader turns a query into JSON text that parses to the slice.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

import loader, { pickSlice as pick, sliceOfQuery as ofQuery } from '../../../scripts/messages-slice-loader'

const pickSlice = pick as (json: Record<string, unknown>, name: string) => Record<string, unknown>
const sliceOfQuery = ofQuery as (q: string) => string

const FILES = [['en', en], ['ms', ms], ['ta', ta]] as Array<[string, Record<string, unknown>]>

describe.each(FILES)('the %s file, cut into slices', (_name, file) => {
  const core = pickSlice(file, 'core')
  const admin = pickSlice(file, 'admin')

  test('core ∪ admin is the whole file, value for value', () => {
    expect({ ...core, ...admin }).toEqual(file)
    expect(Object.keys(core).length + Object.keys(admin).length).toBe(Object.keys(file).length)
  })

  test('core ∩ admin is empty', () => {
    expect(Object.keys(core).filter((ns) => ns in admin)).toEqual([])
  })

  test('admin is the admin namespace alone; core is every other namespace', () => {
    expect(Object.keys(admin)).toEqual(['admin'])
    expect(admin.admin).toBe(file.admin)
    expect(Object.keys(core)).toEqual(Object.keys(file).filter((ns) => ns !== 'admin'))
    // A floor, so a file that lost its namespaces cannot pass the identity checks above on {}.
    expect(Object.keys(core).length).toBeGreaterThanOrEqual(30)
  })
})

describe('the loader', () => {
  test('an unknown slice name throws — never an empty catalogue', () => {
    expect(() => pickSlice(en as Record<string, unknown>, 'scholarship')).toThrow(/unknown slice "scholarship"/)
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
  })
})
