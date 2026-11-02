'use client'

/**
 * THE SPONSOR TAB BAR — three tabs at the foot of every approved sponsor's portal page on a phone
 * (Mobile M5, owner-approved 2026-11-02): My Giving · Students · My Account. The portal's only
 * navigation below `md` — the desktop keeps its top row.
 *
 * Mounted ONLY by `SponsorShell` when the portal shows its tabs (an approved sponsor with the pool
 * live). The details form, the terms wizard and the pending / inactive screens draw no tabs: there is
 * nothing to navigate to until those are done (the same enforcement the shell always relied on).
 *
 * ⚠ IT IS THE STUDENT BAR'S PATTERN, NOT THE STUDENT BAR. It carries the same `data-tab-bar` marker,
 * so every rule in `globals.css` ("THE STUDENT TAB BAR") applies unchanged: phones only, never without
 * `:has()`, replaced by a page's own bar (`data-page-bar` — the fund bar, the terms wizard's bars),
 * hidden while a field is focused, the page padded by its height, the toast lifted (`--bottom-bar`),
 * never on paper. `data-tab-bar="sponsor"` only switches the grid to three columns. `StudentTabBar` is
 * never drawn on a sponsor route (the guard in `mobileStandard.test.ts`).
 *
 * ⚠ WEIGHT: eager — it IS the navigation (the M2 lesson). Three existing words (`sponsorPortal.nav.*`,
 * the shell already shows them) and three short icon paths; its look is CSS.
 */
import Link from 'next/link'
import { useT } from '@/lib/i18n'

/** Heart, two people, a person — 24 px outline icons. */
const ICON = [
  'M12 20.5s-7.5-4.6-9.2-9.4A4.8 4.8 0 0112 7.3a4.8 4.8 0 019.2 3.8c-1.7 4.8-9.2 9.4-9.2 9.4z',
  'M9 11.2a3.2 3.2 0 100-6.4 3.2 3.2 0 000 6.4zM3 19.5c.6-3.3 3-5 6-5s5.4 1.7 6 5M16 4.9a3.2 3.2 0 010 6.2M17.5 14.7c2 .5 3.2 2.2 3.5 4.8',
  'M12 11.6a3.6 3.6 0 100-7.2 3.6 3.6 0 000 7.2zM4.5 20c.8-3.8 3.7-5.8 7.5-5.8s6.7 2 7.5 5.8',
]

/** The three tabs and when each is current — shared with the desktop row so they can never disagree. */
export const SPONSOR_TABS = [
  { href: '/sponsor', key: 'sponsorPortal.nav.giving' },
  { href: '/sponsor/students', key: 'sponsorPortal.nav.students' },
  { href: '/sponsor/account', key: 'sponsorPortal.nav.account' },
] as const

/** My Giving is current on its own page and on a supported student's page (it is where she came from). */
export const sponsorTabCurrent = (href: string, path: string) =>
  href === '/sponsor' ? path === '/sponsor' || path.startsWith('/sponsor/my-students')
    : path.startsWith(href)

export default function SponsorTabBar({ path }: { path: string }) {
  const { t } = useT()
  return (
    <nav data-tab-bar="sponsor" aria-label={t('common.menu')}>
      {SPONSOR_TABS.map((tab, i) => (
        // `prefetch={false}`: the same reason as the student bar (no route fetches on every view).
        <Link key={tab.href} href={tab.href} prefetch={false}
          aria-current={sponsorTabCurrent(tab.href, path) ? 'page' : undefined}>
          <svg viewBox="0 0 24 24" aria-hidden><path d={ICON[i]} /></svg>
          {t(tab.key)}
        </Link>
      ))}
    </nav>
  )
}
