/**
 * Sprint T3 (M1): Last seen, relative to now — an i18n key and its variables, never words.
 */
import { SEEN_AS_DATE_DAYS, seenAgo } from '../lastSeen'

const NOW = Date.parse('2026-11-09T12:00:00Z')   // 20:00 on 9 November in Kuala Lumpur (UTC+8)
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

  // T3 review fix 4: days are calendar days in Asia/Kuala_Lumpur, not 24-hour gaps.
  it('47 hours back across two Malaysian midnights is "2 days ago", not "Yesterday"', () => {
    // 21:00 on 7 November in Kuala Lumpur, read at 20:00 on the 9th: the 8th and the 9th began since.
    expect(seenAgo(back(47 * HOUR), NOW)).toEqual({ key: 'days', n: 2 })
    expect(seenAgo('2026-11-07T13:00:00Z', NOW)).toEqual({ key: 'days', n: 2 })
  })

  it('under 24 hours back across a Malaysian midnight is "Yesterday", not a count of hours', () => {
    // 23:00 on 8 November in Kuala Lumpur, read at 20:00 on the 9th (21 hours).
    expect(seenAgo(back(21 * HOUR), NOW)).toEqual({ key: 'yesterday' })
    // 23:30 read at 08:00 the next morning (8.5 hours), KL time.
    const morning = Date.parse('2026-11-09T00:00:00Z')            // 08:00 on the 9th in KL
    expect(seenAgo('2026-11-08T15:30:00Z', morning)).toEqual({ key: 'yesterday' })
  })

  it('the same Malaysian day is hours, and under an hour stays minutes across midnight', () => {
    const morning = Date.parse('2026-11-09T00:00:00Z')            // 08:00 on the 9th in KL
    expect(seenAgo('2026-11-08T16:30:00Z', morning)).toEqual({ key: 'hours', n: 7 })   // 00:30 KL
    const justAfter = Date.parse('2026-11-08T16:10:00Z')          // 00:10 on the 9th in KL
    expect(seenAgo('2026-11-08T15:50:00Z', justAfter)).toEqual({ key: 'minutes', n: 20 })
    // Midnight UTC is 08:00 in Kuala Lumpur: no day turns there.
    expect(seenAgo('2026-11-08T23:00:00Z', Date.parse('2026-11-09T01:00:00Z'))).toEqual({ key: 'hours', n: 2 })
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
