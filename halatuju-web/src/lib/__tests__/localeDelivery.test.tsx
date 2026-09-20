/**
 * @jest-environment jsdom
 *
 * ONE LOCALE PER VISITOR — rendered. (Code health H17, 2026-09-20.)
 *
 * `i18n.tsx` used to import all three message catalogues statically, so every visitor downloaded
 * 1.53 MB of raw JSON to read one language of it. Malay and Tamil now arrive as their own chunks.
 * That is a change to DELIVERY, and the price of getting it wrong is a visitor reading the wrong
 * words, or worse, a raw dotted key. So the four things that must survive are asserted HERE, on a
 * rendered tree, rather than argued for in a docstring:
 *
 *  1. **The switcher still switches** — and lands on the language it was asked for, not English.
 *  2. **The catalogue is really that locale's** — the expected words are read out of the JSON
 *     file itself, so a loader that quietly serves English fails rather than passing on a shape.
 *  3. **The fallback still falls back** — `t` returns the KEY for a key it cannot resolve, which
 *     is the contract `tOr` is built on, and `tOr` returns its fallback.
 *  4. **No raw key ever reaches the screen**, including in the window before a chunk has landed.
 *     A reader arriving already set to Tamil sees English words first (exactly as they always
 *     have — the server cannot read `localStorage`, so the HTML it sends is English), never
 *     `common.save`.
 *
 * ⚠ These read their expectations OUT OF `en/ms/ta.json`, never out of a hardcoded string. This
 * sprint is forbidden from changing one word of any language, and a test that repeated the words
 * would have to be edited by anyone who legitimately changed one.
 *
 * ⚠ Plain DOM assertions — this project's jest setup does not load `@testing-library/jest-dom`.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import LanguageSelector from '@/components/LanguageSelector'
import { I18nProvider, useT, tOr } from '@/lib/i18n'
import { KEY_LOCALE } from '@/lib/storage'

/** A key that exists in all three, is one plain word, and has a different value in each. */
const PROBE_KEY = 'common.save'
const EXPECTED = {
  en: (en as { common: { save: string } }).common.save,
  ms: (ms as { common: { save: string } }).common.save,
  ta: (ta as { common: { save: string } }).common.save,
}

/** A key no catalogue holds, for the fallback arm. */
const ABSENT_KEY = 'code.health.h17.no.such.key'

function Probe() {
  const { locale, t } = useT()
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="word">{t(PROBE_KEY)}</span>
      <span data-testid="absent">{t(ABSENT_KEY)}</span>
      <span data-testid="absent-or">{tOr(t, ABSENT_KEY, 'a written fallback')}</span>
    </div>
  )
}

function mount() {
  return render(<I18nProvider><LanguageSelector /><Probe /></I18nProvider>)
}

const word = () => screen.getByTestId('word').textContent
const shownLocale = () => screen.getByTestId('locale').textContent
const switcher = () => screen.getByLabelText('Language') as HTMLSelectElement

beforeEach(() => {
  localStorage.clear()
})

describe('the three catalogues are distinct, so these tests can tell them apart', () => {
  test('en, ms and ta disagree on the probe key', () => {
    // If this ever became true, every assertion below would pass on English and prove nothing.
    expect(new Set([EXPECTED.en, EXPECTED.ms, EXPECTED.ta]).size).toBe(3)
    expect(EXPECTED.en.length).toBeGreaterThan(0)
  })

  test('the absent key really is absent from all three', () => {
    for (const cat of [en, ms, ta] as Array<Record<string, unknown>>) {
      expect(Object.prototype.hasOwnProperty.call(cat, 'code')).toBe(false)
    }
  })
})

describe('the language switcher still switches', () => {
  test('choosing Tamil renders the TAMIL word, not the English one', async () => {
    mount()
    expect(word()).toBe(EXPECTED.en)

    fireEvent.change(switcher(), { target: { value: 'ta' } })

    // ⚠ The whole of bite (a). A loader that always served English would leave this on `Save`.
    await waitFor(() => expect(word()).toBe(EXPECTED.ta))
    expect(shownLocale()).toBe('ta')
    expect(localStorage.getItem(KEY_LOCALE)).toBe('ta')
  })

  test('choosing Malay renders the MALAY word', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ms' } })
    await waitFor(() => expect(word()).toBe(EXPECTED.ms))
    expect(shownLocale()).toBe('ms')
  })

  test('switching back to English is instant and correct', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ta' } })
    await waitFor(() => expect(word()).toBe(EXPECTED.ta))

    fireEvent.change(switcher(), { target: { value: 'en' } })
    await waitFor(() => expect(word()).toBe(EXPECTED.en))
  })

  test('the locale and the words it names change TOGETHER', async () => {
    // The flash this sprint could have introduced: `locale` says Tamil while the catalogue on
    // screen is still English. One piece of state in `I18nProvider` is what rules it out, and
    // this is the assertion that keeps it one piece.
    mount()
    fireEvent.change(switcher(), { target: { value: 'ta' } })
    await waitFor(() => expect(shownLocale()).toBe('ta'))
    expect(word()).toBe(EXPECTED.ta)
  })
})

describe('a reader who arrives already set to another language', () => {
  test('sees that language once the catalogue lands, and never a raw key on the way', async () => {
    localStorage.setItem(KEY_LOCALE, 'ta')
    mount()

    // Whatever the first paint holds, it is WORDS. `common.save` on screen is the TD-259 defect.
    expect(word()).not.toBe(PROBE_KEY)
    expect([EXPECTED.en, EXPECTED.ta]).toContain(word())

    await waitFor(() => expect(word()).toBe(EXPECTED.ta))
    expect(shownLocale()).toBe('ta')
  })

  test('a stored Malay preference selects Malay in the switcher', async () => {
    localStorage.setItem(KEY_LOCALE, 'ms')
    mount()
    await waitFor(() => expect(word()).toBe(EXPECTED.ms))
    expect(switcher().value).toBe('ms')
  })

  test('an unreadable stored value is English, as before', () => {
    localStorage.setItem(KEY_LOCALE, 'fr')
    mount()
    expect(shownLocale()).toBe('en')
    expect(word()).toBe(EXPECTED.en)
  })
})

describe('the fallback still falls back', () => {
  test('t returns the KEY for a key no catalogue holds — the contract tOr is built on', () => {
    mount()
    // ⚠ Bite (c) lives here. `getNestedValue` returning '' or undefined instead of the path would
    // make `tOr`'s `value === key` test never fire, and `t(key) || 'fallback'` start "working" —
    // which is the idiom `tOr` exists to kill (TD-259).
    expect(screen.getByTestId('absent').textContent).toBe(ABSENT_KEY)
    expect(screen.getByTestId('absent-or').textContent).toBe('a written fallback')
  })

  test('the fallback holds in a non-English catalogue too', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ta' } })
    await waitFor(() => expect(word()).toBe(EXPECTED.ta))

    expect(screen.getByTestId('absent').textContent).toBe(ABSENT_KEY)
    expect(screen.getByTestId('absent-or').textContent).toBe('a written fallback')
  })
})

describe('the loader itself', () => {
  test('hands back the catalogue that was ASKED for', async () => {
    const { loadCatalogue, catalogueIfLoaded } = await import('@/lib/messages')

    const tamil = await loadCatalogue('ta') as { common: { save: string } }
    expect(tamil.common.save).toBe(EXPECTED.ta)

    const malay = await loadCatalogue('ms') as { common: { save: string } }
    expect(malay.common.save).toBe(EXPECTED.ms)

    // English needs no chunk — it is the static import, available from the first line.
    const english = catalogueIfLoaded('en') as { common: { save: string } } | undefined
    expect(english?.common.save).toBe(EXPECTED.en)
  })

  test('asking twice returns the same object, so a switch back costs no fetch', async () => {
    const { loadCatalogue } = await import('@/lib/messages')
    const first = await loadCatalogue('ms')
    const second = await loadCatalogue('ms')
    expect(second).toBe(first)
  })
})
