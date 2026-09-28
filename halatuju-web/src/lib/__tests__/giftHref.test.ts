/**
 * `giftHref` — the gift in a link (TD-296, 2026-09-28). Pure strings; the rendered behaviour is
 * pinned per page in the `page.url.test.tsx` files and in `AppShell.test.tsx`.
 */
import { giftIn, withGift, withGiftHrefs } from '@/lib/giftHref'
import { visibleNav } from '@/lib/navigation'

describe('withGift', () => {
  it('adds the gift to a bare path', () => {
    expect(withGift('/admin/payments', 'bp-sabah')).toBe('/admin/payments?programme=bp-sabah')
  })

  it('keeps any other query, and replaces an earlier gift rather than adding a second', () => {
    expect(withGift('/admin/programme?tab=year', 'bp')).toBe('/admin/programme?tab=year&programme=bp')
    expect(withGift('/admin/payments?programme=old', 'new')).toBe('/admin/payments?programme=new')
  })

  it('never claims a gift nobody chose', () => {
    expect(withGift('/admin/payments', '')).toBe('/admin/payments')
    expect(withGift('/admin/payments', undefined)).toBe('/admin/payments')
    expect(withGift('/admin/payments', null)).toBe('/admin/payments')
  })

  it('encodes, and giftIn reads it back', () => {
    const href = withGift('/admin/payments', 'a b&c')
    expect(giftIn(href.slice(href.indexOf('?')))).toBe('a b&c')
  })
})

describe('giftIn', () => {
  it('is empty when the query names no gift', () => {
    expect(giftIn('')).toBe('')
    expect(giftIn('?tab=year')).toBe('')
    expect(giftIn('?programme=')).toBe('')
  })
})

describe('withGiftHrefs — only the Programme rows carry it', () => {
  const groups = visibleNav({ role: 'super', probes: { requests: 'live', billing: 'live' },
    pathname: '/admin/scholarship', programmeChosen: true })
  const hrefs = (gs: ReturnType<typeof visibleNav>, scope: string) =>
    gs.flatMap((g) => g.items).filter((i) => i.scope === scope).map((i) => i.href)

  it('every Programme row names the gift; no other row changes', () => {
    const out = withGiftHrefs(groups, 'bp-sabah')
    const programme = hrefs(out, 'programme')
    // A floor, so an empty group can never pass this vacuously: the five list pages.
    expect(programme).toHaveLength(5)
    for (const h of programme) expect(h).toMatch(/\?programme=bp-sabah$/)
    for (const scope of ['platform', 'organisation']) {
      expect(hrefs(out, scope)).toEqual(hrefs(groups, scope))
      expect(hrefs(out, scope).length).toBeGreaterThan(0)
    }
  })

  it('with no gift the rail is untouched', () => {
    expect(withGiftHrefs(groups, '')).toBe(groups)
  })
})
