'use client'

import Link from 'next/link'
import { useT } from '@/lib/i18n'

/**
 * THE SPONSOR PORTAL'S OWN 404 — same reason as the console's: the root 404's way out is the
 * PUBLIC site, and a signed-in sponsor who lands on it is pushed out of the portal although
 * their session is untouched.
 *
 * ⚠ **`/sponsor` IS A LITERAL HERE, AND THAT IS CORRECT** — unlike the admin console, which the
 * registry derives per role (`lib/adminLanding.ts`), the sponsor portal has exactly ONE landing
 * and every sponsor sees the same one. There is no role to derive from and nothing to get wrong.
 * If the portal ever grows a second entrance, this is the line that has to stop being a literal.
 *
 * ⚠ It renders inside `app/sponsor/layout.tsx` (`SponsorAuthProvider`) but reads nothing from it:
 * the destination is the same signed in or out, and a 404 is not the place to find out which.
 */
export default function SponsorNotFound() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-ground-50 flex items-center justify-center px-6">
      <div className="text-center max-w-sm" data-testid="sponsor-not-found">
        <p className="text-6xl font-bold text-primary-600 mb-2">404</p>
        <h1 className="text-xl font-semibold text-ground-900 mb-2">{t('errors.pageNotFound')}</h1>
        <p className="text-ground-500 text-sm mb-6">{t('errors.pageNotFoundDesc')}</p>
        <Link
          href="/sponsor"
          className="inline-block px-5 py-2.5 bg-brand-fill hover:bg-brand-fill-hover text-brand-fill-ink text-sm font-medium rounded-lg transition-colors"
        >
          {t('errors.backToPortal')}
        </Link>
      </div>
    </main>
  )
}
