/**
 * THE GIFT IN A LINK — `?programme=<code>` on the Programme-scope list pages (TD-296, 2026-09-28).
 *
 * Pure string work, no React, on purpose: the payment-run page builds its way back with this, and
 * that route IS the median of the first-load-JS budget (256 kB). A module that also held the hook
 * would carry React state and the router into it for the sake of one string (the same measurement
 * that split `programmeScopeCore` out of `programmeScope`).
 *
 * ⚠ THE CODE IN A URL IS A REQUEST, NEVER AN ANSWER. It is read once on mount into the scope's
 * `select`, and from there it meets the same guard as every other pick: a code the caller's scopes
 * list does not hold resolves to NOTHING — the page asks or redirects — and never to "the only
 * one" (the 2026-09-03 defect). The server re-fences `?programme=` on the caller's own organisation
 * at every endpoint, so a hand-edited link reaches exactly what the fence already allowed.
 */
import type { VisibleNavGroup } from '@/lib/navigation'

/** The query key. The same name every endpoint already takes, so the two read the same. */
export const GIFT_PARAM = 'programme'

/** `href` carrying `code` as its gift (any other query kept, e.g. `?tab=year`). With no code the
 *  gift is TAKEN OUT — a link never claims a gift nobody chose, and "All gifts" (TD-302) must
 *  leave an address that names none. */
export function withGift(href: string, code: string | null | undefined): string {
  const at = href.indexOf('?')
  if (!code && at < 0) return href
  const params = new URLSearchParams(at < 0 ? '' : href.slice(at + 1))
  if (code) params.set(GIFT_PARAM, code)
  else params.delete(GIFT_PARAM)
  const query = params.toString()
  return `${at < 0 ? href : href.slice(0, at)}${query ? `?${query}` : ''}`
}

/** The gift a URL's query names, or `''`. */
export function giftIn(search: string): string {
  return (new URLSearchParams(search).get(GIFT_PARAM) ?? '').trim()
}

/**
 * The rail's Programme rows, each carrying the gift — so moving Overview → Applications → Payments
 * keeps it in the address bar. Rows of the other scopes are untouched: an organisation page is not
 * about one gift, and a link there that named one would be a claim the page ignores.
 */
export function withGiftHrefs(groups: VisibleNavGroup[], code: string): VisibleNavGroup[] {
  if (!code) return groups
  return groups.map((g) => ({
    ...g,
    items: g.items.map((i) => (i.scope === 'programme' ? { ...i, href: withGift(i.href, code) } : i)),
  }))
}
