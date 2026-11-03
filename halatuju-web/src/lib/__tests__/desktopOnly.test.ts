/**
 * Mobile M7b: the shell's small desktop-only list (`lib/desktopOnly.ts`) is EXACTLY `mobileClass.ts`'s desktop
 * class — every desktop-only route gets the panel and no other route does — and the panel's English reason is the
 * route's own `why`, word for word, with a Malay and a Tamil one beside it.
 */
import { DESKTOP_ONLY, desktopOnlyRoute } from '@/lib/desktopOnly'
import { MOBILE_CLASS } from '@/lib/mobileClass'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const desktop = Object.entries(MOBILE_CLASS).filter(([, e]) => e.cls === 'desktop')

it('the list is the desktop class, no more and no less', () => {
  expect(Object.keys(DESKTOP_ONLY).sort()).toEqual(desktop.map(([r]) => r).sort())
  expect(desktop.length).toBeGreaterThanOrEqual(6)
})

it('every route of the app: the panel on a desktop-only route, never on any other', () => {
  const sample = (route: string) => route.replace(/\[\.\.\.[^\]]+\]/g, 'a/b').replace(/\[[^\]]+\]/g, '12')
  for (const [route, e] of Object.entries(MOBILE_CLASS)) {
    expect(`${route} -> ${desktopOnlyRoute(sample(route))}`).toBe(`${route} -> ${e.cls === 'desktop' ? route : null}`)
  }
  // A trailing slash is the same page; a page UNDER a desktop-only route is its own route.
  expect(desktopOnlyRoute('/admin/billing/')).toBe('/admin/billing')
  expect(desktopOnlyRoute('/admin/contracts/7/preview')).toBeNull()
})

it('the reason line is the route\'s own why in English, and translated in Malay and Tamil', () => {
  const why = (lang: unknown, key: string) =>
    ((lang as { admin: { desktopOnly: { why: Record<string, string> } } }).admin.desktopOnly.why)[key]
  for (const [route, e] of desktop) {
    const key = DESKTOP_ONLY[route]
    expect(why(en, key)).toBe((e as { why: string }).why)
    for (const lang of [ms, ta]) {
      expect(why(lang, key)).toBeTruthy()
      expect(why(lang, key)).not.toBe(why(en, key))
    }
  }
})
