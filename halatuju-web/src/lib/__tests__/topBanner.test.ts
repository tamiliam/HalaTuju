/**
 * @jest-environment jsdom
 *
 * Staff nudges (2026-11-08): the top-banner slot's dismissals — per browser, per account, for N days
 * (the profile banner) or until the next sign-in (Phase B's overdue banner).
 */
import { bannerKey, dismiss, isDismissed } from '@/lib/topBanner'

const DAY = 24 * 60 * 60 * 1000
const SEVEN = { kind: 'days', days: 7 } as const

beforeEach(() => window.localStorage.clear())

it('keys a banner per account', () => {
  expect(bannerKey('profile', 7)).toBe('halatuju.banner.profile.7')
  dismiss(bannerKey('profile', 7), SEVEN, 1000)
  expect(isDismissed(bannerKey('profile', 7), SEVEN, 2000)).toBe(true)
  expect(isDismissed(bannerKey('profile', 8), SEVEN, 2000)).toBe(false)
})

it('hides for seven days, then the banner returns', () => {
  const key = bannerKey('profile', 1)
  const t0 = Date.UTC(2026, 10, 8)
  expect(isDismissed(key, SEVEN, t0)).toBe(false)
  dismiss(key, SEVEN, t0)
  expect(isDismissed(key, SEVEN, t0 + 6 * DAY)).toBe(true)
  expect(isDismissed(key, SEVEN, t0 + 7 * DAY - 1)).toBe(true)
  expect(isDismissed(key, SEVEN, t0 + 7 * DAY)).toBe(false)
  // A clock set back before the dismissal does not hide it for ever.
  expect(isDismissed(key, SEVEN, t0 - DAY)).toBe(false)
})

it('until the next sign-in: a new sign-in stamp brings it back', () => {
  const key = bannerKey('overdue', 1)
  dismiss(key, { kind: 'signIn', stamp: 'a' })
  expect(isDismissed(key, { kind: 'signIn', stamp: 'a' })).toBe(true)
  expect(isDismissed(key, { kind: 'signIn', stamp: 'b' })).toBe(false)
  expect(isDismissed(key, { kind: 'signIn', stamp: '' })).toBe(false)
})

it('a garbled or missing value shows the banner', () => {
  window.localStorage.setItem(bannerKey('profile', 1), 'nonsense')
  expect(isDismissed(bannerKey('profile', 1), SEVEN)).toBe(false)
})

it('storage that throws (Safari private mode) shows the banner and never throws', () => {
  const get = jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied') })
  const set = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied') })
  expect(() => dismiss(bannerKey('profile', 1), SEVEN)).not.toThrow()
  expect(isDismissed(bannerKey('profile', 1), SEVEN)).toBe(false)
  get.mockRestore(); set.mockRestore()
})
