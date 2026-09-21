/**
 * @jest-environment jsdom
 *
 * SWITCHING LANGUAGE WHEN THE NETWORK IS NOT INSTANT — the four defects the 2026-09-21 audit
 * found in the H17 delivery split, each asserted on a rendered tree with a CONTROLLED promise.
 *
 * H17 moved Malay and Tamil behind `import()`. Everything it asserted is still true
 * (`localeDelivery.test.tsx`), because every one of those tests lets the chunk land before it
 * looks. That is the gap this file fills: **the window while the chunk is in the air**, and the
 * case where it never arrives at all. On a dev box that window is a millisecond; on a phone on a
 * bad line it is seconds, and on a tab held open across a deploy the chunk is simply gone.
 *
 *  A. **Two quick switches must not leave the reader in the language they abandoned.** Tamil then
 *     Malay, with Tamil's chunk resolving LAST, used to end with `localStorage` saying `ms`, the
 *     switcher saying `ta`, `html lang="ta"` and a Tamil heading — four surfaces, three answers.
 *  B. **The control must show the choice the moment it is made.** It is `<select value={locale}>`
 *     and `locale` only moved on arrival, so choosing Tamil snapped visibly back to English for
 *     the whole download. It reads as broken, and it invites the second click that causes A.
 *  D. **A chunk that fails must fail OUT LOUD, once.** Two fetches went out per switch and both
 *     failed silently: the switcher said Tamil, the words stayed English, no message, no retry.
 *  E. **`html lang` must follow the WORDS, not the request.** A screen reader was being told
 *     Tamil while reading English.
 *
 * ⚠ **THE LOADER IS MOCKED SO THE TEST OWNS THE CLOCK — no timers, no sleeps, no flake.** Each
 * request for a catalogue parks in `state.waiting` until this file lands it or fails it, so
 * "resolved out of order" is an ordinary two-line statement rather than a race to provoke.
 *
 * ⚠ The mock deliberately does NOT de-duplicate in-flight requests, which the real
 * `loadCatalogue` does. That is what lets `state.calls` COUNT what the provider asked for: the
 * real module's cache would hide a second ask behind a shared promise, and "one fetch per switch"
 * is exactly the claim D makes. The words are the REAL `en/ms/ta.json`, so nothing here can pass
 * on a shape.
 *
 * ⚠ Plain DOM assertions — this project's jest setup does not load `@testing-library/jest-dom`.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'

import { ToastProvider } from '@/components/Toast'
import { HtmlLang } from '@/components/HtmlLang'
import LanguageSelector from '@/components/LanguageSelector'
import * as messages from '@/lib/messages'
import { I18nProvider, useT } from '@/lib/i18n'
import { KEY_LOCALE } from '@/lib/storage'

jest.mock('@/lib/messages', () => {
  const real: Record<string, Record<string, unknown>> = {
    en: jest.requireActual('@/messages/en.json'),
    ms: jest.requireActual('@/messages/ms.json'),
    ta: jest.requireActual('@/messages/ta.json'),
  }
  const state = {
    loaded: { en: real.en } as Record<string, Record<string, unknown> | undefined>,
    waiting: [] as Array<{ locale: string; settle: (ok: boolean) => void }>,
    calls: [] as string[],
    reset(): void {
      state.loaded = { en: real.en }
      state.waiting = []
      state.calls = []
    },
  }
  return {
    __state: state,
    FALLBACK_CATALOGUE: real.en,
    catalogueIfLoaded: (l: string) => state.loaded[l],
    isCatalogueLoaded: (l: string) => state.loaded[l] !== undefined,
    loadCatalogue: (l: string) => {
      state.calls.push(l)
      const already = state.loaded[l]
      if (already) return Promise.resolve(already)
      return new Promise((resolve, reject) => {
        state.waiting.push({
          locale: l,
          settle: (ok: boolean) => {
            if (ok) {
              state.loaded[l] = real[l]
              resolve(real[l])
            } else {
              reject(new Error(`chunk for ${l} is gone (a deploy replaced it)`))
            }
          },
        })
      })
    },
  }
})

interface MockState {
  loaded: Record<string, Record<string, unknown> | undefined>
  waiting: Array<{ locale: string; settle: (ok: boolean) => void }>
  calls: string[]
  reset: () => void
}
const state = (messages as unknown as { __state: MockState }).__state

/** The real words, read out of the catalogues rather than repeated here. */
const EXPECTED = {
  en: (jest.requireActual('@/messages/en.json') as { common: { save: string } }).common.save,
  ms: (jest.requireActual('@/messages/ms.json') as { common: { save: string } }).common.save,
  ta: (jest.requireActual('@/messages/ta.json') as { common: { save: string } }).common.save,
}
/** The one string this fix ADDS, read from `en.json` so a reworded message needs no edit here. */
const EN_JSON = jest.requireActual('@/messages/en.json') as { common: { languageLoadFailed: string } }
const LOAD_FAILED = EN_JSON.common.languageLoadFailed

function Probe() {
  const { locale, t } = useT()
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="word">{t('common.save')}</span>
    </div>
  )
}

function mount() {
  return render(
    <I18nProvider>
      <ToastProvider>
        <LanguageSelector />
        <HtmlLang />
        <Probe />
      </ToastProvider>
    </I18nProvider>,
  )
}

const word = () => screen.getByTestId('word').textContent
const committedLocale = () => screen.getByTestId('locale').textContent
const switcher = () => screen.getByLabelText('Language') as HTMLSelectElement
const htmlLang = () => document.documentElement.lang
const asksFor = (locale: string) => state.calls.filter((c) => c === locale).length

/** Land the chunk a given locale is waiting on. Throws rather than hanging if none is in the air. */
async function land(locale: string): Promise<void> {
  await settle(locale, true)
}

/** Fail the chunk a given locale is waiting on — a tab held open across a deploy. */
async function lose(locale: string): Promise<void> {
  await settle(locale, false)
}

async function settle(locale: string, ok: boolean): Promise<void> {
  const i = state.waiting.findIndex((w) => w.locale === locale)
  if (i < 0) {
    throw new Error(`no request for "${locale}" is in the air. Asked for: [${state.calls.join(', ')}]`)
  }
  const [waiting] = state.waiting.splice(i, 1)
  await act(async () => {
    waiting.settle(ok)
    // One extra microtask turn so the provider's `.then` and the control's own `.then` both run
    // inside this `act`, rather than warning after it.
    await Promise.resolve()
  })
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.lang = ''
  state.reset()
})

// ── A ────────────────────────────────────────────────────────────────────────────────────────
describe('two quick switches leave the reader in the language they CHOSE', () => {
  test('the older, slower chunk may not overwrite the newer one', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ta' } })
    fireEvent.change(switcher(), { target: { value: 'ms' } })

    // Out of order on purpose: the NEWER request lands first, then the one the reader abandoned.
    await land('ms')
    await land('ta')

    // ⚠ All four surfaces, because the defect was that they disagreed. A guard on only one of
    // them would have gone green through the whole of the reported bug.
    expect(committedLocale()).toBe('ms')
    expect(word()).toBe(EXPECTED.ms)
    expect(switcher().value).toBe('ms')
    expect(localStorage.getItem(KEY_LOCALE)).toBe('ms')
    expect(htmlLang()).toBe('ms-MY')
  })

  test('and the same holds the other way round, so nothing here depends on ta vs ms', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ms' } })
    fireEvent.change(switcher(), { target: { value: 'ta' } })

    await land('ta')
    await land('ms')

    expect(committedLocale()).toBe('ta')
    expect(word()).toBe(EXPECTED.ta)
    expect(switcher().value).toBe('ta')
    expect(localStorage.getItem(KEY_LOCALE)).toBe('ta')
    expect(htmlLang()).toBe('ta')
  })
})

// ── B ────────────────────────────────────────────────────────────────────────────────────────
describe('the control shows the choice at once, and says it is working', () => {
  test('the pending choice is in the box before the words arrive', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ta' } })

    // ⚠ The whole of B. This read `en` for the entire download, so the reader watched their own
    // choice undo itself and clicked again — which is how A was reached in the browser.
    expect(switcher().value).toBe('ta')
    expect(switcher().getAttribute('aria-busy')).toBe('true')
    // The WORDS are allowed to lag; the committed state is still English until the chunk lands.
    expect(word()).toBe(EXPECTED.en)
    expect(committedLocale()).toBe('en')

    await land('ta')

    expect(switcher().value).toBe('ta')
    expect(switcher().getAttribute('aria-busy')).toBe('false')
    expect(word()).toBe(EXPECTED.ta)
  })

  test('switching to a language already in memory is instant and never reads as busy', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ta' } })
    await land('ta')
    fireEvent.change(switcher(), { target: { value: 'en' } })

    expect(switcher().getAttribute('aria-busy')).toBe('false')
    expect(word()).toBe(EXPECTED.en)
  })
})

// ── D ────────────────────────────────────────────────────────────────────────────────────────
describe('a catalogue chunk that never arrives', () => {
  test('costs ONE fetch, reverts the control, persists nothing, and says so on screen', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ta' } })
    await lose('ta')

    // ⚠ One fetch. The provider used to fire a second from its effect after committing the
    // failure, so a tab held open across a deploy asked twice for a chunk that was gone.
    expect(asksFor('ta')).toBe(1)
    // The control returns to the language actually on screen.
    expect(switcher().value).toBe('en')
    expect(committedLocale()).toBe('en')
    expect(word()).toBe(EXPECTED.en)
    expect(htmlLang()).toBe('en')
    // Nothing is stored, so a reload does not retry a choice that could not be honoured.
    expect(localStorage.getItem(KEY_LOCALE)).toBeNull()
    // And the reader is TOLD, in the language on screen. Silence was the defect.
    expect(screen.getByText(LOAD_FAILED)).toBeTruthy()
    expect(switcher().getAttribute('aria-busy')).toBe('false')
  })

  test('a successful switch costs one fetch too', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ms' } })
    await land('ms')
    expect(asksFor('ms')).toBe(1)
  })

  test('the reader may try again, and a second attempt that works clears the message', async () => {
    mount()
    fireEvent.change(switcher(), { target: { value: 'ta' } })
    await lose('ta')
    expect(screen.getByText(LOAD_FAILED)).toBeTruthy()

    fireEvent.change(switcher(), { target: { value: 'ta' } })
    await land('ta')

    expect(word()).toBe(EXPECTED.ta)
    expect(localStorage.getItem(KEY_LOCALE)).toBe('ta')
    expect(asksFor('ta')).toBe(2)   // one per attempt, never two per attempt
  })
})

// ── E ────────────────────────────────────────────────────────────────────────────────────────
describe('html lang follows the words on screen, not the words that were asked for', () => {
  test('a reader arriving set to Tamil is `lang="en"` until the Tamil words land', async () => {
    localStorage.setItem(KEY_LOCALE, 'ta')
    mount()

    // ⚠ The defect: `lang` was set from the REQUESTED locale on the first client render, so a
    // screen reader read English aloud in a Tamil voice for the length of the download.
    expect(word()).toBe(EXPECTED.en)
    expect(htmlLang()).toBe('en')

    await land('ta')

    expect(word()).toBe(EXPECTED.ta)
    expect(htmlLang()).toBe('ta')
  })

  test('a chunk that fails leaves `lang` on the language actually being read', async () => {
    localStorage.setItem(KEY_LOCALE, 'ms')
    mount()
    await lose('ms')

    expect(word()).toBe(EXPECTED.en)
    expect(htmlLang()).toBe('en')
  })
})

// ── C ────────────────────────────────────────────────────────────────────────────────────────
describe('a browser with site data blocked still gets a working app', () => {
  /** Safari private mode / "block all cookies": `localStorage` EXISTS and throws when touched. */
  function blockStorage(): jest.SpyInstance[] {
    return [
      jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new DOMException('The operation is insecure.', 'SecurityError')
      }),
      jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new DOMException('The operation is insecure.', 'SecurityError')
      }),
    ]
  }

  test('the module can be EVALUATED with storage blocked — the blank-page defect', () => {
    const spies = blockStorage()
    try {
      // ⚠ This is the whole of C, and it happens before React exists. `i18n.tsx` reads
      // `localStorage` as the module is evaluated, to start the catalogue fetch early. With site
      // data blocked that throw escaped the module body, the bundle never finished evaluating,
      // and the reader got a BLANK DOCUMENT — not an error screen, nothing. `theme.ts` has
      // wrapped the identical call in try/catch since F1, with a comment saying exactly this.
      expect(() => {
        jest.isolateModules(() => {
          require('@/lib/i18n')
        })
      }).not.toThrow()
    } finally {
      spies.forEach((s) => s.mockRestore())
    }
  })

  test('the reader gets English and a switcher that works, it just does not persist', async () => {
    const spies = blockStorage()
    try {
      mount()
      expect(word()).toBe(EXPECTED.en)

      fireEvent.change(switcher(), { target: { value: 'ms' } })
      await land('ms')

      // The words follow the choice for this tab; only the memory of it is lost.
      expect(word()).toBe(EXPECTED.ms)
      expect(committedLocale()).toBe('ms')
      expect(switcher().value).toBe('ms')
    } finally {
      spies.forEach((s) => s.mockRestore())
    }
  })
})
