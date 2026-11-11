'use client'

/**
 * The signed-in sponsor portal's chrome (Mobile M5) — moved out of `sponsor/(portal)/layout.tsx`, which
 * keeps every gating decision (details → terms → status → pool) and only draws this.
 *
 * - **Phone (below `md`):** a slim header — the logo and "Sponsor", nothing else when the tabs are shown;
 *   the theme, the language and Log out live in My Account (owner, 2026-11-02). On the screens WITHOUT
 *   tabs (details form, terms wizard, pending, inactive) the header keeps a 44 px Log out, the only way
 *   out there. The tabs (`SponsorTabBar`) are the navigation.
 * - **From `md`:** the top row as before M5 — logo, the three tabs, the theme select, Log out — plus the
 *   language select (TD-469, owner D10 2026-11-11).
 */
import { type ReactNode } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import BrandLogo from '@/components/BrandLogo'
import LanguageSelector from '@/components/LanguageSelector'
import ThemeSelector from '@/components/ThemeSelector'
import SponsorTabBar, { SPONSOR_TABS, sponsorTabCurrent } from '@/components/sponsor/SponsorTabBar'
import SponsorLogOut from '@/components/sponsor/SponsorLogOut'
import { PHONE_GUTTER } from '@/lib/phoneSection'
import { useT } from '@/lib/i18n'

/** `path` is for the design sandbox only (its address is `/sandbox/…`, and Next's pathname context does
 *  not reach a surface), so a surface can name the tab it shows; the portal never passes it. */
export default function SponsorShell({ children, nav = false, path }: { children: ReactNode; nav?: boolean; path?: string }) {
  const { t } = useT()
  const realPath = usePathname() || ''
  const here = path ?? realPath

  return (
    // Sponsor portal typeface (owner 2026-07-18): Inter — crisp at small sizes, trustworthy
    // for the money/facts. Scoped here; the rest of HalaTuju stays on Lexend. (--font-inter
    // is registered in the root layout.) Inter HAS tabular figures, so money here keeps Inter:
    // `--figures-face` is what `.tabular-nums` paints in (globals.css, TD-310).
    <div className="min-h-screen flex flex-col bg-ground-50"
      style={{
        // Tamil first and Tamil-only (unicode-range): Tamil letters in Mukta Malar, the rest Inter.
        fontFamily: 'var(--font-tamil), var(--font-inter), system-ui, sans-serif',
        '--figures-face': 'var(--font-tamil), var(--font-inter), system-ui, sans-serif',
      } as React.CSSProperties}>
      <header className="bg-ground-0 border-b sticky top-0 z-20 pt-[env(safe-area-inset-top)]">
        <div className={`container mx-auto ${PHONE_GUTTER} h-14 flex items-center justify-between`}>
          <Link href="/sponsor" className="flex min-h-11 items-center gap-2 shrink-0">
            <BrandLogo width={100} height={36} />
            <span className="text-sm font-semibold text-primary-600">{t('sponsorAuth.badge')}</span>
          </Link>
          {/* Phone, no tabs: Log out is the only way out of these screens. */}
          {!nav && (
            <SponsorLogOut className="md:hidden -mr-2 inline-flex min-h-11 items-center px-2 text-sm text-ground-500 hover:text-ground-700" />
          )}
          {/* From md: the top row as it always was. */}
          <div className="hidden md:flex items-center gap-1">
            {nav && (
              <nav aria-label={t('common.menu')} className="flex items-center gap-1">
                {SPONSOR_TABS.map((tb) => (
                  <Link
                    key={tb.href} href={tb.href}
                    aria-current={sponsorTabCurrent(tb.href, here) ? 'page' : undefined}
                    className={`px-3 py-2 text-sm font-medium rounded-lg ${
                      sponsorTabCurrent(tb.href, here) ? 'text-primary-600 bg-primary-50' : 'text-ground-600 hover:bg-ground-50'
                    }`}
                  >
                    {t(tb.key)}
                  </Link>
                ))}
              </nav>
            )}
            {/* TD-469 (owner D10, option A): the language select, as the student desktop row shows it.
                On a phone it is in My Account (Mobile M5). */}
            <div className="ml-2"><LanguageSelector /></div>
            {/* Light / Dark / Auto (Layer 1 F7d). On a phone it is in My Account (Mobile M5). */}
            <div className="ml-2"><ThemeSelector /></div>
            <SponsorLogOut className="ml-2 px-3 py-2 text-sm text-ground-400 hover:text-ground-600" />
          </div>
        </div>
      </header>
      <main className={`flex-1 container mx-auto ${PHONE_GUTTER} pt-1 pb-6 md:py-8`}>{children}</main>
      {nav && (
        <footer className={`container mx-auto ${PHONE_GUTTER} py-4 md:py-6 text-center text-xs text-ground-400`}>
          <Link href="/sponsor/trust" className="inline-flex min-h-11 items-center text-ground-500 hover:text-primary-600 underline">
            {t('sponsorPortal.trust.footerLink')}
          </Link>
          <span className="mx-2">·</span>
          <Link href="/privacy" className="inline-flex min-h-11 items-center hover:text-ground-600">
            {t('sponsorAuth.privacyNotice')}
          </Link>
        </footer>
      )}
      {nav && <SponsorTabBar path={here} />}
    </div>
  )
}

/** A single card of content (details form, terms wizard, pending, inactive, coming soon): the card it
 *  always was from `md`; on a phone the content sits straight on the 16 px gutter (rule 15). */
export function SponsorCard({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center justify-center py-4 md:px-2 md:py-8">
      <div className="w-full max-w-md md:bg-ground-0 md:rounded-2xl md:shadow-sm md:border md:p-8">{children}</div>
    </div>
  )
}
