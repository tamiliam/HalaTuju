/**
 * Sprint T3 (M1): Last seen, relative to now — an i18n key and its variables, never words.
 */
import { SEEN_AS_DATE_DAYS, seenAgo } from '../lastSeen'

const NOW = Date.parse('2026-11-09T12:00:00Z')
const back = (ms: number) => new Date(NOW - ms).toISOString()
const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR

describe('seenAgo', () => {
  it.each([
    [0, { key: 'now' }],
    [59_000, { key: 'now' }],
    [MIN, { key: 'minute' }],
    [2 * MIN, { key: 'minutes', n: 2 }],
    [59 * MIN, { key: 'minutes', n: 59 }],
    [HOUR, { key: 'hour' }],
    [5 * HOUR + 10 * MIN, { key: 'hours', n: 5 }],
    [DAY, { key: 'yesterday' }],
    [2 * DAY, { key: 'days', n: 2 }],
    [(SEEN_AS_DATE_DAYS - 1) * DAY, { key: 'days', n: SEEN_AS_DATE_DAYS - 1 }],
  ])('%p ms back reads %p', (ms, want) => {
    expect(seenAgo(back(ms), NOW)).toEqual(want)
  })

  it('a month or more back is the date itself', () => {
    const at = back(SEEN_AS_DATE_DAYS * DAY)
    expect(seenAgo(at, NOW)).toEqual({ key: 'on', date: new Date(at) })
  })

  it('a time a little in the future reads "now", never a negative count', () => {
    expect(seenAgo(new Date(NOW + 5 * MIN).toISOString(), NOW)).toEqual({ key: 'now' })
  })

  it('an unreadable value answers null, so the page says "not recorded"', () => {
    expect(seenAgo('not a date', NOW)).toBeNull()
  })
})
