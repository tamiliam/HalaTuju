/**
 * @jest-environment node
 *
 * A4.2 Language: one test per string / item.
 *  - TD-455 saved-page toasts, TD-456 course-page labels + merit row, TD-463 award schedule sentence,
 *    TD-346 "applications with us" wording. (TD-388 lives in app/settings/page.hydration.test.tsx.)
 */
import { readFileSync } from 'fs'
import { join } from 'path'

import en from '../../messages/en.json'
import ms from '../../messages/ms.json'
import ta from '../../messages/ta.json'
import { scheduleSentence, monthName } from '../awardSchedule'

type Dict = Record<string, unknown>
const CATALOGUES: Record<'en' | 'ms' | 'ta', Dict> = { en, ms, ta } as never

function get(cat: Dict, key: string): string {
  let cur: unknown = cat
  for (const part of key.split('.')) cur = (cur as Dict)?.[part]
  return typeof cur === 'string' ? cur : ''
}
const src = (rel: string) => readFileSync(join(__dirname, '..', '..', rel), 'utf8').replace(/\r\n/g, '\n')
const tFor = (l: 'en' | 'ms' | 'ta') => (key: string, params: Record<string, string> = {}) =>
  get(CATALOGUES[l], key).replace(/\{(\w+)\}/g, (_, k) => params[k] ?? `{${k}}`)

const TD455 = ['saved.removedToast', 'saved.removeFailed', 'saved.statusFailed']
const TD456 = [
  'level', 'field', 'department', 'duration', 'semestersValue', 'wbl', 'yes', 'no', 'category', 'stream',
  'streamScience', 'streamArts', 'streamBoth', 'avgMerit', 'moreInfo', 'loadingCourse', 'notFoundTitle',
  'backToDashboard', 'subjectKey', 'allStates', 'allDistricts', 'noSchools', 'chanceHigh', 'chanceFair',
  'chanceLow', 'meritYou', 'meritNeed',
].map(k => `courseDetail.${k}`)
const TD463 = ['scholarship.award.bursary.scheduleLine', 'scholarship.award.bursary.scheduleLineNoStart']

describe('every A4.2 string exists in en, ms and ta', () => {
  it.each([...TD455, ...TD456, ...TD463])('%s', (key) => {
    for (const l of ['en', 'ms', 'ta'] as const) expect(get(CATALOGUES[l], key)).not.toBe('')
  })
  it.each([...TD455, ...TD463, 'courseDetail.moreInfo', 'courseDetail.chanceHigh', 'courseDetail.avgMerit'])(
    '%s is translated, not copied English', (key) => {
      expect(get(ms, key)).not.toBe(get(en, key))
      expect(get(ta, key)).not.toBe(get(en, key))
    })
  it('Tamil strings carry Tamil script, and placeholders match English', () => {
    for (const key of [...TD455, ...TD456, ...TD463]) {
      const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join()
      for (const l of ['ms', 'ta'] as const) expect(ph(get(CATALOGUES[l], key))).toBe(ph(get(en, key)))
      expect(get(ta, key)).toMatch(/[஀-௿]/)
    }
  })
})

describe('TD-455: the saved page raises no English toast literal', () => {
  const page = src('app/saved/page.tsx')
  it('no showToast string literal is left', () => {
    expect(page).not.toMatch(/showToast\(\s*['"`]/)
  })
  it.each(TD455)('%s is used by the page', (key) => {
    expect(page).toContain(`t('${key}')`)
  })
})

describe('TD-456: the course pages and the card hold no English label literal', () => {
  const files = ['app/course/[id]/page.tsx', 'app/stpm/[id]/page.tsx', 'components/CourseDetailShared.tsx',
    'components/course/PreUInstitutions.tsx', 'components/CourseCard.tsx']
  const LITERALS = [
    'label="Level"', 'label="Field"', 'label="Department"', 'label="Duration"', 'label="WBL"',
    'label="Category"', 'label="Stream"', "'Avg. Merit'", '>Avg. Merit<', '>All States<', '>All Districts<',
    'No schools match', '>Subject Key<', 'Course not found</h1>', 'Loading course details',
    "'High Chance'", "'Fair Chance'", "'Low Chance'", ' You: ', ' Need: ',
  ]
  const code = (text: string) => text.split('\n').filter(l => {
    const s = l.trim()
    return !s.startsWith('//') && !s.startsWith('*') && !s.startsWith('{/*')
  })
  it.each(LITERALS)('no %j', (lit) => {
    for (const f of files) expect(code(src(f)).filter(l => l.includes(lit))).toEqual([])
  })
  it('"More Info" and "Back to Dashboard" are catalogue words, not bare JSX text', () => {
    for (const f of files) {
      expect(code(src(f)).filter(l => /^\s*(More Info|Back to Dashboard)\s*$/.test(l))).toEqual([])
    }
  })
  it('the merit label row is 12 px or more (text-xs), not 9-11 px', () => {
    const card = src('components/CourseCard.tsx')
    const row = card.slice(card.indexOf('{/* Label row */}'))
    expect(row).not.toMatch(/text-\[(9|10|11)px\]/)
    expect(row).toContain('text-xs font-semibold')
  })
})

describe('TD-463: the award schedule sentence is composed in the reader language', () => {
  const parts = { monthly_amount: '250', count: 12, start_month: 7, total: '3000' }
  it('English', () => {
    expect(scheduleSentence(parts, tFor('en'), 'en'))
      .toBe('RM250 per month × 12 payments, starting July (total RM3000).')
  })
  it('Malay', () => {
    const s = scheduleSentence(parts, tFor('ms'), 'ms')
    expect(s).toContain('RM250 sebulan × 12 bayaran')
    expect(s).toContain('(jumlah RM3000)')
    expect(s).not.toMatch(/per month|payments/)
  })
  it('Tamil', () => {
    const s = scheduleSentence(parts, tFor('ta'), 'ta')
    expect(s).toContain('RM250')
    expect(s).toMatch(/12 [஀-௿]+/)
    expect(s).not.toMatch(/per month|payments/)
  })
  it('names the month in the reader language', () => {
    expect(monthName(7, 'en')).toBe('July')
    expect(monthName(7, 'ta')).toMatch(/[஀-௿]/)
  })
  it('a row with no first month drops the starting clause', () => {
    expect(scheduleSentence({ ...parts, start_month: 0 }, tFor('en'), 'en'))
      .toBe('RM250 per month × 12 payments (total RM3000).')
  })
  it('the award page uses the composed sentence when the server serves parts', () => {
    expect(src('app/scholarship/award/page.tsx')).toContain('scheduleSentence(preview.payment_schedule_parts')
  })
})

describe('TD-346: "open" no longer claims what a submitted application is not', () => {
  const KEY = 'scholarship.application.multiple.body'
  it('English says "with us"', () => {
    expect(get(en, KEY)).toContain('{count} applications with us')
    expect(get(en, KEY)).not.toMatch(/\bopen\b/)
  })
  it('Malay says "dengan kami", not "terbuka"', () => {
    expect(get(ms, KEY)).toContain('{count} permohonan dengan kami')
    expect(get(ms, KEY)).not.toContain('terbuka')
  })
  it('Tamil says the applications are with us, not "open"', () => {
    expect(get(ta, KEY)).toContain('எங்களிடம் {count}')
    expect(get(ta, KEY)).not.toContain('திறந்திருக்கின்றன')
  })
})
