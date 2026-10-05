/**
 * THE DRIFT TEST for the spending categories — the Overview chart's `CATEGORY_CODES`
 * (`components/admin/overview/OverviewSections.tsx`, named by its `drift-test:` marker).
 *
 * ⚠ THE HARM IS SILENT. The chart FILTERS the server's slices through that list, so a category the
 * model gains and the list lacks is money that vanishes from the donut while the total above it
 * still counts it. Request #28 (2026-10-06) added `micro_stall` to `SPEND_CATEGORY_CHOICES`; before
 * this test, nothing would have noticed the web list falling behind.
 *
 * Also pinned: every code has a label in all three locales on BOTH screens that name it — the
 * Overview chart and the sponsor's spending card.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { CATEGORY_CODES } from '@/components/admin/overview/OverviewSections'
import { pyChoiceValues, readApi } from '@/test/apiSource'

const modelCodes = pyChoiceValues(readApi('apps/scholarship/models/spending.py'),
                                  'SPEND_CATEGORY_CHOICES', false)

const resolve = (cat: unknown, key: string): unknown =>
  key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], cat)

describe('parse sanity — the model list was really found', () => {
  test('it holds the categories we know are there', () => {
    expect(modelCodes.length).toBeGreaterThanOrEqual(11)
    expect(modelCodes).toEqual(expect.arrayContaining(['food', 'micro_stall', 'transfer', 'unsorted']))
  })
})

describe('the chart list is the model list, plus the blank', () => {
  test('same codes, same order, and `none` last', () => {
    expect(CATEGORY_CODES).toEqual([...modelCodes, 'none'])
  })
})

describe('every category has words, in every locale, on both screens', () => {
  test.each([['en', en], ['ms', ms], ['ta', ta]] as const)('%s', (_name, cat) => {
    const missing = modelCodes.flatMap((c) => [
      `admin.programmeOverview.category.${c}`,
      `sponsorPortal.myStudents.detail.spend.cat.${c}`,
    ]).filter((k) => typeof resolve(cat, k) !== 'string' || !String(resolve(cat, k)).trim())
    expect(missing).toEqual([])
  })
})
