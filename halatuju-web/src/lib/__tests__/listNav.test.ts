/**
 * @jest-environment jsdom
 *
 * `lib/listNav` — the record a list leaves for its detail pages' Previous / Next (Requests list
 * R1). Storage is injected, so these run against a Map-backed fake; the browser store is only
 * reached through `sessionStore()`, which must never throw.
 */
import {
  arrowKeysIgnored, positionIn, readListNav, sessionStore, writeListNav, type StorageLike,
} from '@/lib/listNav'

function fakeStore(): StorageLike & { map: Map<string, string> } {
  const map = new Map<string, string>()
  return { map, getItem: (k) => map.get(k) ?? null, setItem: (k, v) => { map.set(k, v) } }
}

/** One element on the page, with the given attributes. */
function place(tag: string, attrs: Record<string, string> = {}): HTMLElement {
  const el = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v)
  if (tag === 'select') el.appendChild(document.createElement('option'))
  document.body.appendChild(el)
  return el
}

const record = { ids: [11, 7, 3], backHref: '/admin/requests?tab=closed', labelKey: 'tab.closed' }

describe('the record round-trips', () => {
  it('reads back exactly what was written, under its own key', () => {
    const store = fakeStore()
    writeListNav('requests', record, store)
    expect(readListNav('requests', store)).toEqual(record)
    expect(readListNav('applications', store)).toBeNull()
  })

  it('treats a record of the wrong shape as no record', () => {
    const store = fakeStore()
    writeListNav('requests', record, store)
    const [key] = Array.from(store.map.keys())
    for (const bad of ['not json', '{"ids":"1,2"}', '{"ids":[1],"backHref":3,"labelKey":"x"}']) {
      store.map.set(key, bad)
      expect(readListNav('requests', store)).toBeNull()
    }
  })

  it('a store that throws is no store — nothing escapes', () => {
    const angry: StorageLike = {
      getItem: () => { throw new Error('denied') },
      setItem: () => { throw new Error('full') },
    }
    expect(() => writeListNav('requests', record, angry)).not.toThrow()
    expect(readListNav('requests', angry)).toBeNull()
    expect(readListNav('requests', null)).toBeNull()
  })

  it('reaches the browser store when there is one', () => {
    expect(sessionStore()).toBe(window.sessionStorage)
  })
})

describe('positionIn', () => {
  it('names the neighbours and the place, greyed (null) at each end', () => {
    expect(positionIn(record, 11)).toEqual(
      { index: 0, total: 3, prevId: null, nextId: 7, backHref: record.backHref, labelKey: 'tab.closed' })
    expect(positionIn(record, 7)).toMatchObject({ index: 1, prevId: 11, nextId: 3 })
    expect(positionIn(record, 3)).toMatchObject({ index: 2, prevId: 7, nextId: null })
  })

  it('an id the list does not hold (a direct link, a stale list) has no position', () => {
    expect(positionIn(record, 99)).toBeNull()
    expect(positionIn(null, 7)).toBeNull()
  })
})

describe('arrowKeysIgnored', () => {
  const key = (init: KeyboardEventInit = {}) =>
    new KeyboardEvent('keydown', { key: 'ArrowRight', ...init })

  afterEach(() => { document.body.replaceChildren() })

  it('lets a plain arrow through on the page', () => {
    expect(arrowKeysIgnored(key())).toBe(false)
  })

  it('leaves the key alone while typing or picking', () => {
    for (const [tag, attrs] of [['input', {}], ['textarea', {}], ['select', {}],
      ['div', { contenteditable: 'true', tabindex: '0' }]] as const) {
      document.body.replaceChildren()
      place(tag, attrs).focus()
      expect(arrowKeysIgnored(key())).toBe(true)
    }
  })

  it('leaves the key alone with a modifier held or already handled', () => {
    for (const mod of ['altKey', 'ctrlKey', 'metaKey', 'shiftKey'] as const) {
      expect(arrowKeysIgnored(key({ [mod]: true }))).toBe(true)
    }
    const handled = key({ cancelable: true })
    handled.preventDefault()
    expect(arrowKeysIgnored(handled)).toBe(true)
  })

  it('leaves the key alone while a dialog is open', () => {
    place('div', { role: 'dialog' })
    expect(arrowKeysIgnored(key())).toBe(true)
  })
})
