/**
 * The desktop-only console routes (Mobile M7b) — the ones `mobileClass.ts` classes `desktop`, each with the key of
 * its reason in the message catalogue. Kept here, small, because `AppShell` (every admin route) needs only this:
 * importing `mobileClass.ts` would ship the whole route table to every console page.
 * `desktopOnly.test.ts` holds this list EQUAL to `mobileClass.ts`'s desktop class, and the English reason equal to
 * the route's own `why`, so the two can never disagree.
 */
export const DESKTOP_ONLY: Record<string, string> = {
  '/admin/billing-rates': 'billingRates',
  '/admin/billing': 'billing',
  '/admin/course-data': 'courseData',
  '/admin/contracts': 'contracts',
  '/admin/contracts/[id]': 'contract',
  '/admin/sponsors/terms/[id]': 'sponsorTerms',
}

/** The desktop-only route a pathname is (`/admin/contracts/12` → `/admin/contracts/[id]`), or null. EXACT routes
 *  only: `/admin/billing` is not `/admin/billing-rates`, and a page under a route is its own route. */
export function desktopOnlyRoute(pathname: string): string | null {
  const path = (pathname || '').replace(/\/+$/, '')
  for (const route of Object.keys(DESKTOP_ONLY)) {
    const re = new RegExp(`^${route.replace(/\[[^\]]+\]/g, '[^/]+')}$`)
    if (re.test(path)) return route
  }
  return null
}
