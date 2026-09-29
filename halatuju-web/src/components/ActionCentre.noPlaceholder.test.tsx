/**
 * @jest-environment jsdom
 *
 * TD-306 — A STUDENT NEVER READS A RAW "{placeholder}".
 *
 * `high_utility_expense` quotes "the household income of RM {income} a month you reported". It was
 * raised for households with no income on file, the item's params had no `income`, and
 * `interpolateMessage` leaves an unknown placeholder untouched — so the student read "RM {income}".
 * Two fixes, both pinned here:
 *   1. the api raises `high_utility_expense_noincome` instead (no figure in its copy) — rendered below
 *      in English and Tamil from the REAL catalogues;
 *   2. belt and braces, the Action Centre paints item copy through `itemCopy`: a description with an
 *      unfilled placeholder is dropped whole (title only), a title loses just the placeholder, and it
 *      warns. The sweep runs EVERY known code, in all three languages, with EMPTY params, and refuses
 *      a `{` or `}`, and any description that is not either fully filled or absent (review F3).
 * `interpolateMessage` itself is unchanged: the pages that `.replace('{n}', …)` after `t()` rely on
 * the placeholder surviving it, and one of them is pinned at the bottom.
 */
import { render, screen } from '@testing-library/react'

import ActionCentre from './ActionCentre'
import * as api from '@/lib/api'
import type { ResolutionItem } from '@/lib/api'
import { KNOWN_CODES, itemCopy, titleSourceFor } from '@/lib/actionCentre'
import { PLATFORM, brandingParams, interpolateMessage, type Locale } from '@/lib/branding'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const CATALOGUES: Record<Locale, unknown> = { en, ms, ta }
let locale: Locale = 'en'

/** The real `t()`: catalogue lookup, branding tokens beneath the call-site params. */
const lookupIn = (loc: Locale) => (key: string, params?: Record<string, string>): string => {
  const value = key.split('.').reduce<unknown>(
    (node, part) => (node && typeof node === 'object' ? (node as Record<string, unknown>)[part] : undefined),
    CATALOGUES[loc])
  return typeof value === 'string'
    ? interpolateMessage(value, { ...brandingParams(PLATFORM, loc), ...params })
    : key
}
const lookup = (key: string, params?: Record<string, string>) => lookupIn(locale)(key, params)

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getResolutionItems: jest.fn(),
  resolveResolutionItem: jest.fn(),
  listDocuments: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({ ...jest.requireActual('@/lib/i18n'), useT: () => ({ t: lookup, locale }) }))
jest.mock('./DocumentHelpCoach', () => ({
  __esModule: true, default: () => null, CoachCard: () => null,
}))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>

const CLARIFY = (code: string, params: ResolutionItem['params']): ResolutionItem => ({
  id: 41, fact: 'income', code, params,
  prompt: '', kind: 'clarify', doc_type: '', status: 'open',
  source: 'check2' as ResolutionItem['source'], resolution_text: '',
  created_at: '2026-09-29T09:00:00.000Z', resolved_at: null,
})

const mount = async (item: ResolutionItem, title: string) => {
  mockApi.getResolutionItems.mockResolvedValue({ open: [item], resolved: [] })
  mockApi.listDocuments.mockResolvedValue({ documents: [] })
  const view = render(<ActionCentre token="test-token" studentName="Test Student 06" applicationId={6} />)
  await screen.findByText(title)
  return view.container.textContent || ''
}

let warn: jest.SpyInstance
beforeEach(() => {
  jest.clearAllMocks()
  locale = 'en'
  warn = jest.spyOn(console, 'warn').mockImplementation(() => {})
})
afterEach(() => warn.mockRestore())

describe('high_utility_expense_noincome, as the student reads it', () => {
  it('English: states the bills, quotes no income, and no brace survives', async () => {
    const text = await mount(CLARIFY('high_utility_expense_noincome', { amount: 400 }),
                             'Why are your utility bills this high?')
    expect(text).toContain('about RM 400 a month, which looks high')
    expect(text).not.toMatch(/income|[{}]/)
    expect(text).not.toContain('scholarship.actionCentre.item')
    expect(warn).not.toHaveBeenCalled()
  })

  it('Tamil: the same ask, in Tamil, and no brace survives', async () => {
    locale = 'ta'
    const text = await mount(CLARIFY('high_utility_expense_noincome', { amount: 400 }),
                             'உங்கள் பயன்பாட்டு பில்கள் ஏன் இவ்வளவு அதிகம்?')
    expect(text).toContain('RM 400 ஆகும், இது அதிகமாகத் தெரிகிறது')
    expect(text).not.toMatch(/[{}]/)
    expect(warn).not.toHaveBeenCalled()
  })

  it('a pre-TD-306 plain row with no income on it shows its title alone, and says so in a warning',
     async () => {
    const text = await mount(CLARIFY('high_utility_expense', { amount: 400 }),
                             'Why are your utility bills this high?')
    expect(text).not.toMatch(/[{}]/)
    expect(text).not.toContain('household income')        // the holed description is not painted
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('{income}'))
  })
})

describe('the sweep: every known code, every language, EMPTY params', () => {
  const LOCALES: Locale[] = ['en', 'ms', 'ta']
  it.each(LOCALES)('%s — no brace anywhere; a description is fully filled or absent', (loc) => {
    const t = lookupIn(loc)
    const leaks: string[] = []
    let dropped = 0
    let swept = 0
    for (const code of KNOWN_CODES) {
      const src = titleSourceFor({ source: 'check2', code, prompt: '' })
      if (src.kind !== 'i18n') continue
      swept++
      const { title, desc } = itemCopy(t, src, {})
      if (/[{}]/.test(title + desc)) leaks.push(`${code}: brace in "${title}" / "${desc}"`)
      const raw = t(src.descKey, {})
      if (desc === '' && raw !== '') dropped++
      else if (desc !== raw) leaks.push(`${code}: description with debris: "${desc}"`)
    }
    expect(leaks).toEqual([])
    expect(swept).toBeGreaterThanOrEqual(89)   // floor: 90 known codes, less the bank task's card
    expect(dropped).toBeGreaterThan(0)         // teeth: some descriptions DO need params
  })

  it('the sweep has teeth: the raw catalogue DOES carry placeholders for empty params', () => {
    const raw = lookupIn('en')('scholarship.actionCentre.item.high_utility_expense.desc', {})
    expect(raw).toContain('{income}')
  })
})

describe('itemCopy leaves a fully-filled string exactly as t() gave it', () => {
  it('byte-identical when every placeholder is filled', () => {
    const t = lookupIn('en')
    const src = titleSourceFor({ source: 'check2', code: 'high_utility_expense', prompt: '' })
    if (src.kind !== 'i18n') throw new Error('known code')
    const params = { amount: '400', income: '1200' }
    expect(itemCopy(t, src, params)).toEqual(
      { title: t(src.titleKey, params), desc: t(src.descKey, params) })
    expect(warn).not.toHaveBeenCalled()
  })
})

describe('interpolateMessage callers outside the Action Centre are unaffected', () => {
  it("the sponsor page's `t(...).replace('{n}', …)` still finds its placeholder", () => {
    const line = lookupIn('en')('sponsorPortal.community.line1')
    expect(line).toContain('{n}')
    expect(line.replace('{n}', '12')).toBe("You're one of 12 sponsors")
  })
})
