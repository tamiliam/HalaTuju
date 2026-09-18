/**
 * The Overview layout's list arithmetic (node — no DOM, by design).
 *
 * ⚠ THE ORDERING IS TESTED HERE RATHER THAN THROUGH A DRAGGED CARD, because jsdom's drag-and-drop
 * is a stub: a `drop` event it never really fired would prove the handler ran, not that the list
 * came out in the order the pointer promised. What the component test next door proves is that the
 * switches and the Save bar reached the markup.
 *
 * ⚠ No jest-dom matchers exist in this project: `toBe` / `toEqual` / `toBeNull`.
 */
import {
  SECTION_KEYS, isDirty, moveItem, reorderByDrop, setOn, type LayoutRow,
} from '@/lib/overviewLayout'

const rows = (): LayoutRow[] => SECTION_KEYS.map((key) => ({ key, on: true }))
const keysOf = (list: readonly LayoutRow[]) => list.map((r) => r.key)

describe('SECTION_KEYS — the catalogue, and nothing outside it', () => {
  it('is the five customisable widgets in the platform default order', () => {
    expect(SECTION_KEYS.slice()).toEqual([
      'funnel', 'money', 'attention', 'applications_series', 'money_series',
    ])
  })

  /* ⚠ `mine` and `qc` are a reviewer's and a checker's WHOLE PAGE, not a widget on somebody
   * else's — outside the catalogue, so an org admin can never switch them off. */
  it('does not contain mine or qc', () => {
    expect(SECTION_KEYS.indexOf('mine' as never)).toBe(-1)
    expect(SECTION_KEYS.indexOf('qc' as never)).toBe(-1)
  })
})

describe('setOn', () => {
  it('flips exactly one row and leaves the order alone', () => {
    const next = setOn(rows(), 'money', false)
    expect(keysOf(next)).toEqual(keysOf(rows()))
    expect(next.filter((r) => !r.on).map((r) => r.key)).toEqual(['money'])
  })

  it('never mutates the list it was given', () => {
    const before = rows()
    setOn(before, 'funnel', false)
    expect(before.every((r) => r.on)).toBe(true)
  })

  it('is a no-op for a key that is not in the list', () => {
    expect(setOn(rows(), 'mine', false)).toEqual(rows())
  })
})

describe('isDirty', () => {
  it('is false for two identical lists', () => {
    expect(isDirty(rows(), rows())).toBe(false)
  })

  it('counts a flag change', () => {
    expect(isDirty(rows(), setOn(rows(), 'attention', false))).toBe(true)
  })

  /* ⚠ ORDER COUNTS. Sprint B moves cards without touching a switch, and a Save that slept
   * through a reorder would strand the one edit the person came to make. */
  it('counts a change of ORDER even when every flag is the same', () => {
    expect(isDirty(rows(), moveItem(rows(), 0, 1))).toBe(true)
  })

  it('counts a different length', () => {
    expect(isDirty(rows(), rows().slice(1))).toBe(true)
  })
})

describe('moveItem', () => {
  it('moves a middle row up', () => {
    expect(keysOf(moveItem(rows(), 2, -1)))
      .toEqual(['funnel', 'attention', 'money', 'applications_series', 'money_series'])
  })

  it('moves a middle row down', () => {
    expect(keysOf(moveItem(rows(), 1, 1)))
      .toEqual(['funnel', 'attention', 'money', 'applications_series', 'money_series'])
  })

  /* ⚠ THE ENDS ARE HARMLESS AS WELL AS DISABLED — a refused move returns the list unchanged
   * rather than throwing or silently dropping the row off the end. */
  it('leaves the list unchanged at either end, and for an index that is not there', () => {
    const before = rows()
    expect(moveItem(before, 0, -1)).toBe(before)
    expect(moveItem(before, before.length - 1, 1)).toBe(before)
    expect(moveItem(before, -1, 1)).toBe(before)
    expect(moveItem(before, 99, -1)).toBe(before)
  })

  it('never mutates the list it was given', () => {
    const before = rows()
    moveItem(before, 0, 1)
    expect(keysOf(before)).toEqual(keysOf(rows()))
  })
})

describe('reorderByDrop', () => {
  it('drops a row BEFORE a target that is above it', () => {
    // money_series (last) onto money (index 1) → it lands at index 1.
    expect(keysOf(reorderByDrop(rows(), 'money_series', 'money')))
      .toEqual(['funnel', 'money_series', 'money', 'attention', 'applications_series'])
  })

  it('drops a row AFTER a target that is below it', () => {
    // funnel (first) onto attention (index 2) → it lands where attention was.
    expect(keysOf(reorderByDrop(rows(), 'funnel', 'attention')))
      .toEqual(['money', 'attention', 'funnel', 'applications_series', 'money_series'])
  })

  /* ⚠⚠ THE SAME REFERENCE COMES BACK ON A NO-OP, and that is the assertion — a new array with
   * equal contents would wake Save on a gesture that changed nothing. */
  it('returns the SAME list when a row is dropped on itself', () => {
    const before = rows()
    expect(reorderByDrop(before, 'money', 'money')).toBe(before)
  })

  it('returns the SAME list when either key is unknown', () => {
    // HTML5 drag-and-drop hands over whatever `text/plain` is on the clipboard, including a
    // payload from another page, without apology.
    const before = rows()
    expect(reorderByDrop(before, 'nonsense', 'money')).toBe(before)
    expect(reorderByDrop(before, 'money', 'nonsense')).toBe(before)
  })

  it('never mutates the list it was given', () => {
    const before = rows()
    reorderByDrop(before, 'funnel', 'money_series')
    expect(keysOf(before)).toEqual(keysOf(rows()))
  })
})
