/**
 * @jest-environment jsdom
 *
 * TD-360 Sprint 1 (2026-10-21): THE LANGUAGE SWITCHER, RENDERED, WHEN A LANGUAGE COMES IN SLICES.
 *
 * `messagesRegistry.test.ts` holds the registry's rules on their own; this file holds what a
 * reader SEES, on a real `I18nProvider` + `LanguageSelector`, with the network edge
 * (`lib/messageChunks.ts`) mocked so the test owns the clock and the slices cut from the REAL
 * files by the REAL loader script.
 *
 * ⚠ THE TESTS RUN IN ORDER AND SHARE ONE REGISTRY, ON PURPOSE. The registry is module state that
 * lives for the life of a tab, and the story told here is one tab's: a student browses in Malay
 * (no admin chunk is ever asked for), opens the console in the same tab (the owner-accepted brief
 * English, then Malay), then switches to Tamil on the console (nothing commits until core AND
 * admin are in; a lost admin chunk leaves the reader where they were and says so; a retry works).
 * React cannot be re-required per test, so the tab is not reset between them.
 *
 * ⚠ Plain DOM assertions — this project's jest setup does not load `@testing-library/jest-dom`.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'

import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { ToastProvider } from '@/components/Toast'
import LanguageSelector from '@/components/LanguageSelector'
import * as chunksModule from '@/lib/messageChunks'
import { I18nProvider, useT } from '@/lib/i18n'
import { KEY_LOCALE } from '@/lib/storage'

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

interface ChunkState { calls: string[]; waiting: Array<{ id: string; settle: (ok: boolean) => void }> }
const chunks = (chunksModule as unknown as { __state: ChunkState }).__state

type Tree = Record<string, unknown>
const at = (cat: unknown, key: string): unknown =>
  key.split('.').reduce<unknown>((cur, p) => (cur && typeof cur === 'object' ? (cur as Tree)[p] : undefined), cat)

/** A plain admin string whose three languages all differ — found in the files, never hardcoded. */
function adminProbeKey(): string {
  const out: string[] = []
  const walk = (o: Tree, prefix: string) => {
    for (const [k, v] of Object.entries(o)) {
      const key = `${prefix}.${k}`
      if (v && typeof v === 'object') walk(v as Tree, key)
      else out.push(key)
    }
  }
  walk((en as Tree).admin as Tree, 'admin')
  const found = out.find((k) => {
    const words = [at(en, k), at(ms, k), at(ta, k)]
    return words.every((w) => typeof w === 'string' && !w.includes('{')) && new Set(words).size === 3
  })
  if (!found) throw new Error('no admin key differs in all three languages')
  return found
}

const ADMIN_KEY = adminProbeKey()
const WORD = { en: at(en, 'common.save'), ms: at(ms, 'common.save'), ta: at(ta, 'common.save') }
const ADMIN = { en: at(en, ADMIN_KEY), ms: at(ms, ADMIN_KEY), ta: at(ta, ADMIN_KEY) }
/** Said in the language ON SCREEN when the failure happens — Malay, in test 3. */
const LOAD_FAILED_MS = at(ms, 'common.languageLoadFailed') as string

function Probe() {
  const { locale, t } = useT()
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="word">{t('common.save')}</span>
      <span data-testid="admin">{t(ADMIN_KEY)}</span>
    </div>
  )
}

function mount() {
  return render(
    <I18nProvider>
      <ToastProvider>
        <LanguageSelector />
        <Probe />
      </ToastProvider>
    </I18nProvider>,
  )
}

const word = () => screen.getByTestId('word').textContent
const adminWord = () => screen.getByTestId('admin').textContent
const committed = () => screen.getByTestId('locale').textContent
const switcher = () => screen.getByLabelText('Language') as HTMLSelectElement
const asked = (id: string) => chunks.calls.filter((c) => c === id).length

async function settle(id: string, ok = true): Promise<void> {
  const i = chunks.waiting.findIndex((w) => w.id === id)
  if (i < 0) throw new Error(`no request for ${id} is in the air. Asked for: [${chunks.calls.join(', ')}]`)
  const [w] = chunks.waiting.splice(i, 1)
  await act(async () => {
    w.settle(ok)
    for (let n = 0; n < 10; n += 1) await Promise.resolve()
  })
}

beforeAll(() => {
  localStorage.clear()
})

test('the probes can tell the three languages apart', () => {
  expect(new Set(Object.values(WORD)).size).toBe(3)
  expect(new Set(Object.values(ADMIN)).size).toBe(3)
})

test('1. a STUDENT tree switching to Malay asks for Malay core and never for an admin chunk', async () => {
  const view = mount()
  fireEvent.change(switcher(), { target: { value: 'ms' } })
  expect(chunks.calls).toEqual(['ms:core'])
  await settle('ms:core')
  expect(committed()).toBe('ms')
  expect(word()).toBe(WORD.ms)
  expect(chunks.calls.some((c) => c.endsWith(':admin'))).toBe(false)
  view.unmount()
})

test('2. opening the console in the same tab: admin words in English at once, then Malay (owner-accepted)', async () => {
  const view = mount()
  expect(word()).toBe(WORD.ms)

  // What the admin layout's `import '@/lib/messagesAdmin'` does, as its module is evaluated.
  await act(async () => { await import('@/lib/messagesAdmin') })

  // Malay is already in memory, so its admin chunk is asked for at once — no switch needed.
  expect(asked('ms:admin')).toBe(1)
  // ⚠ Never a raw dotted key: an ABSENT namespace answers in English until the slice lands.
  expect(adminWord()).toBe(ADMIN.en)
  expect(word()).toBe(WORD.ms)
  expect(committed()).toBe('ms')

  await settle('ms:admin')
  expect(adminWord()).toBe(ADMIN.ms)
  expect(word()).toBe(WORD.ms)
  view.unmount()
})

test('3. on the console, a switch to Tamil commits only when core AND admin are in hand', async () => {
  const view = mount()
  fireEvent.change(switcher(), { target: { value: 'ta' } })
  expect(chunks.calls.slice(-2).sort()).toEqual(['ta:admin', 'ta:core'])

  await settle('ta:core')
  // Half a language is not committed: the reader still reads Malay, the control says it is working.
  expect(committed()).toBe('ms')
  expect(word()).toBe(WORD.ms)
  expect(adminWord()).toBe(ADMIN.ms)
  expect(switcher().getAttribute('aria-busy')).toBe('true')

  // The admin chunk is lost (a tab held open across a deploy): nothing moves, and it is SAID.
  await settle('ta:admin', false)
  expect(committed()).toBe('ms')
  expect(switcher().value).toBe('ms')
  expect(word()).toBe(WORD.ms)
  expect(localStorage.getItem(KEY_LOCALE)).toBe('ms')
  expect(screen.getByText(LOAD_FAILED_MS)).toBeTruthy()

  // A retry asks for the lost slice only, and then Tamil is whole.
  fireEvent.change(switcher(), { target: { value: 'ta' } })
  expect(asked('ta:core')).toBe(1)
  expect(asked('ta:admin')).toBe(2)
  await settle('ta:admin')
  expect(committed()).toBe('ta')
  expect(word()).toBe(WORD.ta)
  expect(adminWord()).toBe(ADMIN.ta)
  expect(localStorage.getItem(KEY_LOCALE)).toBe('ta')
  view.unmount()
})

test('4. switching back is instant: everything is in memory, nothing is fetched', async () => {
  const view = mount()
  const before = chunks.calls.length
  fireEvent.change(switcher(), { target: { value: 'ms' } })
  expect(word()).toBe(WORD.ms)
  expect(adminWord()).toBe(ADMIN.ms)
  fireEvent.change(switcher(), { target: { value: 'en' } })
  expect(word()).toBe(WORD.en)
  expect(adminWord()).toBe(ADMIN.en)
  expect(chunks.calls.length).toBe(before)
  view.unmount()
})
