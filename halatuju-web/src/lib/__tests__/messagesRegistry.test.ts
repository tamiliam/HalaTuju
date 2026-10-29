/**
 * @jest-environment jsdom
 *
 * TD-360 Sprint 1 (2026-10-21): the SLICE REGISTRY in `lib/messages.ts`, driven slice by slice.
 *
 * Each language is now delivered as `core` (every namespace but `admin`) plus, once an admin layout
 * has loaded `lib/messagesAdmin.ts`, `admin`. The rules this file holds:
 *
 *  1. Before `admin` is required, a Malay / Tamil load asks for CORE ONLY — a student never
 *     downloads the console's words.
 *  2. Once it is required, `loadCatalogue` resolves only when core AND admin are both in, merged
 *     into ONE object; `catalogueIfLoaded` stays `undefined` until then.
 *  3. A load already in the air when `admin` becomes required (the returning Tamil officer: the
 *     warm start in `i18n.tsx` began fetching core before the admin layout evaluated) waits for
 *     the admin slice too — and requiring a slice fetches nothing by itself (only the language on
 *     screen is asked for, by the provider).
 *  4. English admin words are merged INTO `FALLBACK_CATALOGUE` — identity kept, so
 *     `contentLocale`'s `catalogue === FALLBACK_CATALOGUE` derivation is untouched.
 *  5. A failed slice rejects the load and clears its record, so a retry really fetches again.
 *  6. Arrivals and requirements are ANNOUNCED, so the provider can re-render.
 *
 * ⚠ The network edge (`lib/messageChunks.ts`) is mocked so the test owns the clock; the slices it
 * hands back are cut from the REAL files by the REAL loader script, so nothing passes on a shape.
 * Every test takes a FRESH copy of the registry (`jest.isolateModules`), because the registry is
 * module state that lives for the life of a tab.
 */
import en from '@/messages/en.json'
import ta from '@/messages/ta.json'

jest.mock('@/lib/messageChunks', () => {
  const { pickSlice } = jest.requireActual('../../../scripts/messages-slice-loader')
  const files: Record<string, Record<string, unknown>> = {
    ms: jest.requireActual('@/messages/ms.json'),
    ta: jest.requireActual('@/messages/ta.json'),
  }
  const state = {
    calls: [] as string[],
    waiting: [] as Array<{ id: string; settle: (ok: boolean) => void }>,
  }
  return {
    __state: state,
    fetchSlice: (locale: string, slice: string) => {
      const id = `${locale}:${slice}`
      state.calls.push(id)
      return new Promise((resolve, reject) => {
        state.waiting.push({
          id,
          settle: (ok) => (ok
            ? resolve({ default: pickSlice(files[locale], slice) })
            : reject(new Error(`chunk ${id} is gone`))),
        })
      })
    },
  }
})

type Registry = typeof import('@/lib/messages')
interface ChunkState { calls: string[]; waiting: Array<{ id: string; settle: (ok: boolean) => void }> }

function fresh(): { m: Registry; chunks: ChunkState } {
  let m: Registry | undefined
  let chunks: ChunkState | undefined
  jest.isolateModules(() => {
    m = require('@/lib/messages')
    chunks = (require('@/lib/messageChunks') as { __state: ChunkState }).__state
  })
  return { m: m as Registry, chunks: chunks as ChunkState }
}

async function flush(): Promise<void> {
  for (let i = 0; i < 10; i += 1) await Promise.resolve()
}

async function settle(chunks: ChunkState, id: string, ok = true): Promise<void> {
  const i = chunks.waiting.findIndex((w) => w.id === id)
  if (i < 0) throw new Error(`no request for ${id} is in the air. Asked for: [${chunks.calls.join(', ')}]`)
  const [w] = chunks.waiting.splice(i, 1)
  w.settle(ok)
  await flush()
}

const EN_ADMIN = { admin: (en as Record<string, unknown>).admin as Record<string, unknown> }
const TA = ta as Record<string, unknown>

describe('1. before the admin slice is required', () => {
  test('a Tamil load asks for core only, and the catalogue holds no admin words', async () => {
    const { m, chunks } = fresh()
    const loading = m.loadCatalogue('ta')
    expect(chunks.calls).toEqual(['ta:core'])
    await settle(chunks, 'ta:core')
    const cat = await loading
    expect(cat).toHaveProperty('common')
    expect(cat).not.toHaveProperty('admin')
    expect(m.catalogueIfLoaded('ta')).toBe(cat)
  })

  test('English core is static: no fetch, available from the first line', () => {
    // ⚠ Under jest the static `?slice=core` import is the WHOLE file (jest.config.js maps every
    // `?slice=` import to it — a superset), so English here does hold `admin`. That the BUILD's
    // English core holds no admin words is proved on the real files by `messagesSlice.test.ts`.
    const { m, chunks } = fresh()
    expect(m.catalogueIfLoaded('en')).toBe(m.FALLBACK_CATALOGUE)
    expect(m.FALLBACK_CATALOGUE).toHaveProperty('common')
    expect(chunks.calls).toEqual([])
  })
})

describe('2. once the admin slice is required', () => {
  test('a Tamil load waits for core AND admin, and merges them into one object', async () => {
    const { m, chunks } = fresh()
    m.requireSlice('admin', EN_ADMIN)
    const loading = m.loadCatalogue('ta')
    expect(chunks.calls.sort()).toEqual(['ta:admin', 'ta:core'])

    let done = false
    loading.then(() => { done = true })
    await settle(chunks, 'ta:core')
    // ⚠ Half a catalogue is not handed out: the switch on an admin page must not commit yet.
    expect(done).toBe(false)
    expect(m.catalogueIfLoaded('ta')).toBeUndefined()

    await settle(chunks, 'ta:admin')
    const cat = await loading
    expect(done).toBe(true)
    expect(cat.admin).toEqual(TA.admin)
    expect(cat.common).toEqual(TA.common)
    expect(m.catalogueIfLoaded('ta')).toBe(cat)
  })

  test('English admin words are merged INTO the fallback — identity kept', () => {
    const { m } = fresh()
    const before = m.FALLBACK_CATALOGUE
    m.requireSlice('admin', EN_ADMIN)
    expect(m.FALLBACK_CATALOGUE).toBe(before)
    expect(m.FALLBACK_CATALOGUE.admin).toBe(EN_ADMIN.admin)
    expect(m.catalogueIfLoaded('en')).toBe(before)
  })

  test('an admin chunk that fails rejects the load; a retry fetches it again and only it', async () => {
    const { m, chunks } = fresh()
    m.requireSlice('admin', EN_ADMIN)
    const first = m.loadCatalogue('ta')
    await settle(chunks, 'ta:core')
    await settle(chunks, 'ta:admin', false)
    await expect(first).rejects.toThrow(/ta:admin is gone/)
    expect(m.catalogueIfLoaded('ta')).toBeUndefined()

    const second = m.loadCatalogue('ta')
    // Core is in memory; only the slice that failed is asked for again.
    expect(chunks.calls.filter((c) => c === 'ta:core')).toHaveLength(1)
    expect(chunks.calls.filter((c) => c === 'ta:admin')).toHaveLength(2)
    await settle(chunks, 'ta:admin')
    expect((await second).admin).toEqual(TA.admin)
  })
})

describe('3. a load already in the air when the admin layout evaluates', () => {
  test('the earlier load goes round again and waits for the admin slice too', async () => {
    const { m, chunks } = fresh()
    const warm = m.loadCatalogue('ta')          // i18n.tsx's warm start for a stored Tamil reader
    expect(chunks.calls).toEqual(['ta:core'])
    m.requireSlice('admin', EN_ADMIN)           // then lib/messagesAdmin.ts evaluates

    let done = false
    warm.then(() => { done = true })
    await settle(chunks, 'ta:core')
    // Core is in, but admin is now required: the load asks for it rather than resolving half.
    expect(done).toBe(false)
    expect(chunks.calls).toEqual(['ta:core', 'ta:admin'])
    await settle(chunks, 'ta:admin')
    expect(done).toBe(true)
    expect((await warm).admin).toEqual(TA.admin)
  })

  test('a language already IN MEMORY gets its admin slice merged into the same object, when asked', async () => {
    const { m, chunks } = fresh()
    const loading = m.loadCatalogue('ta')
    await settle(chunks, 'ta:core')
    const cat = await loading

    m.requireSlice('admin', EN_ADMIN)
    // Until it lands the Tamil catalogue is incomplete for the new requirement.
    expect(m.catalogueIfLoaded('ta')).toBeUndefined()
    const again = m.loadCatalogue('ta')         // what the provider's effect does on the announcement
    expect(chunks.calls).toEqual(['ta:core', 'ta:admin'])
    await settle(chunks, 'ta:admin')
    expect(await again).toBe(cat)               // the SAME object, now holding admin too
    expect(cat.admin).toEqual(TA.admin)
  })

  test('requiring admin FETCHES NOTHING — not even for languages already in memory', async () => {
    // The 2026-10-21 smoke: a tab that had visited Malay then Tamil downloaded BOTH admin slices on
    // opening the console. Only the language on screen is asked for, by the provider.
    const { m, chunks } = fresh()
    const ms = m.loadCatalogue('ms')
    await settle(chunks, 'ms:core')
    await ms
    m.requireSlice('admin', EN_ADMIN)
    expect(chunks.calls).toEqual(['ms:core'])
  })
})

describe('4. announcements', () => {
  test('requiring a slice and a slice arriving each move the version and call subscribers', async () => {
    const { m, chunks } = fresh()
    const heard = jest.fn()
    const unsubscribe = m.subscribeCatalogues(heard)
    const v0 = m.catalogueVersion()

    m.requireSlice('admin', EN_ADMIN)
    expect(m.catalogueVersion()).toBe(v0 + 1)
    m.requireSlice('admin', EN_ADMIN)            // idempotent: nothing new, nothing announced
    expect(m.catalogueVersion()).toBe(v0 + 1)

    const loading = m.loadCatalogue('ms')
    await settle(chunks, 'ms:core')
    await settle(chunks, 'ms:admin')
    await loading
    expect(m.catalogueVersion()).toBe(v0 + 3)
    expect(heard).toHaveBeenCalledTimes(3)

    unsubscribe()
    m.requireSlice('admin', EN_ADMIN)
    expect(heard).toHaveBeenCalledTimes(3)
  })
})

/**
 * TD-416 (2026-10-29): `scholarship` is the first namespace SPLIT across slices — its `nav`,
 * `subnav` and `banner` children stay in core (most routes read them), the rest is its own slice.
 * The mocked network cuts both halves from the REAL Tamil file with the REAL loader, so a merge
 * that replaced the namespace instead of merging its children would lose one half here.
 */
describe('5. the split scholarship namespace', () => {
  const TA_SCHOLARSHIP = TA.scholarship as Record<string, unknown>

  test.each([
    ['core first', ['ta:core', 'ta:scholarship']],
    ['scholarship first', ['ta:scholarship', 'ta:core']],
  ])('a Tamil load merges both halves of scholarship.* whichever arrives first (%s)', async (_n, order) => {
    const { m, chunks } = fresh()
    m.requireSlice('scholarship', {})
    const loading = m.loadCatalogue('ta')
    expect([...chunks.calls].sort()).toEqual(['ta:core', 'ta:scholarship'])
    for (const id of order) await settle(chunks, id)
    const cat = await loading
    expect(cat.scholarship).toEqual(TA_SCHOLARSHIP)
    expect(cat.common).toEqual(TA.common)
  })

  test('sliceAbsent: a split child that has not arrived is absent; a missing KEY is not', async () => {
    const { m, chunks } = fresh()
    const loading = m.loadCatalogue('ta')
    await settle(chunks, 'ta:core')
    const coreOnly = await loading
    // Core holds the menu half of the namespace…
    expect(m.sliceAbsent(coreOnly, 'scholarship.nav.scholarship')).toBe(false)
    // …so the rest of it is ABSENT (the slice is not in), and t() answers it in English.
    expect(m.sliceAbsent(coreOnly, 'scholarship.apply.title')).toBe(true)
    // A namespace not split is judged as TD-360 judged it: present means present.
    expect(m.sliceAbsent(coreOnly, 'common.noSuchKeyAnywhere')).toBe(false)
    expect(m.sliceAbsent(coreOnly, 'admin.anything')).toBe(true)
    // Once the slice is in, a key missing from a PRESENT child still echoes (never a fallback).
    m.requireSlice('scholarship', {})
    const again = m.loadCatalogue('ta')
    await settle(chunks, 'ta:scholarship')
    const whole = await again
    expect(m.sliceAbsent(whole, 'scholarship.apply.title')).toBe(false)
    expect(m.sliceAbsent(whole, 'scholarship.apply.noSuchKey')).toBe(false)
  })

  test('mergeSlice merges a split namespace\'s children into a FRESH object, others by assignment', () => {
    const { m } = fresh()
    const core = { scholarship: { nav: { a: 'A' } }, common: { x: 'X' } }
    const slice = { scholarship: { apply: { b: 'B' } } }
    const target: Record<string, unknown> = {}
    m.mergeSlice(target, core)
    m.mergeSlice(target, slice)
    expect(target).toEqual({ scholarship: { nav: { a: 'A' }, apply: { b: 'B' } }, common: { x: 'X' } })
    expect(core.scholarship).toEqual({ nav: { a: 'A' } })        // the inputs are never mutated
    expect(target.common).toBe(core.common)
  })
})
