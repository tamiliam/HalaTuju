/**
 * THE DRIFT TEST for the "Born in" tick boxes — `BIRTH_STATES` (`lib/birthStates.ts`, named by
 * its `drift-test:` marker) against the server's `STATE_CHOICES`
 * (`halatuju_api/apps/scholarship/birth_state.py`). Request #31, 2026-10-08.
 *
 * ⚠ THE HARM RUNS BOTH WAYS. A key the web offers and the server does not know is refused on
 * save (`bad_requirement`), so an admin could never set that state. A key the server knows and the
 * web lacks can never be ticked. And a key spelled differently on the two sides is both at once.
 *
 * Also pinned: the display names are the platform's own state list (`MALAYSIAN_STATES`, what the
 * profile stores), in its order — one spelling of "W.P. Kuala Lumpur" across the product.
 */
import { BIRTH_STATES, toggleBirthState } from '@/lib/birthStates'
import { MALAYSIAN_STATES } from '@/lib/scholarship'
import { pyChoiceValues, pySeq, readApi } from '@/test/apiSource'

const src = readApi('apps/scholarship/birth_state.py')
const apiKeys = pyChoiceValues(src, 'STATE_CHOICES', false)
/** `STATE_CHOICES` as (key, name) pairs: its string literals, read two at a time. */
const apiPairs = (() => {
  const flat = pySeq(src, 'STATE_CHOICES')
  const out: [string, string][] = []
  for (let i = 0; i < flat.length; i += 2) out.push([flat[i], flat[i + 1]])
  return out
})()

describe('parse sanity — the server list was really found', () => {
  test('sixteen states and federal territories, Sabah among them', () => {
    expect(apiKeys).toHaveLength(16)
    expect(apiKeys).toEqual(expect.arrayContaining(['sabah', 'negeri_sembilan', 'wp_labuan']))
    expect(apiPairs).toHaveLength(16)
  })
})

describe('the web offers exactly the server keys, names and order', () => {
  test('same keys, same order', () => {
    expect(BIRTH_STATES.map((s) => s.key)).toEqual(apiKeys)
  })

  test('same names', () => {
    expect(BIRTH_STATES.map((s) => [s.key, s.name])).toEqual(apiPairs)
  })

  test("the names are the platform's own state list, in its order", () => {
    expect(BIRTH_STATES.map((s) => s.name)).toEqual([...MALAYSIAN_STATES])
  })
})

describe('toggleBirthState', () => {
  test('ticks into the server order whatever order they were ticked in', () => {
    let list: string[] = []
    list = toggleBirthState(list, 'wp_labuan', true)
    list = toggleBirthState(list, 'sabah', true)
    list = toggleBirthState(list, 'sarawak', true)
    expect(list).toEqual(['sabah', 'sarawak', 'wp_labuan'])
  })

  test('unticking removes only that state, and the last one leaves an empty list (rule off)', () => {
    expect(toggleBirthState(['sabah', 'sarawak'], 'sabah', false)).toEqual(['sarawak'])
    expect(toggleBirthState(['sabah'], 'sabah', false)).toEqual([])
  })

  test('ticking twice keeps one', () => {
    expect(toggleBirthState(['sabah'], 'sabah', true)).toEqual(['sabah'])
  })

  test('never mutates the list it was given', () => {
    const before = ['sabah']
    toggleBirthState(before, 'sarawak', true)
    expect(before).toEqual(['sabah'])
  })

  // Only a hand edit can store a key the screen does not know. Dropping it on the next save would
  // change the rule without anybody choosing to; it is kept, and the server refuses it instead.
  test('a key it does not know is KEPT, at the end', () => {
    expect(toggleBirthState(['atlantis', 'sarawak'], 'sabah', true))
      .toEqual(['sabah', 'sarawak', 'atlantis'])
  })
})
