'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { DESKTOP_ONLY } from '@/lib/desktopOnly'

/**
 * The "use a computer for this page" panel (Mobile M7b; owner: on a phone the panel REPLACES a desktop-only page,
 * with one way back). Drawn by `AppShell` for the routes in `lib/desktopOnly.ts` and shown BELOW md BY WIDTH only
 * (`md:hidden` here, `max-md:hidden` on the page) — CSS, so there is no flash and the page is rendered once, never
 * twice. Layout, not access: who may open the page is the page's own gate, untouched.
 *
 * ONE way back, 44 px: the page you came from when there is one in this tab, else the console's start page
 * (`/admin`, which sends each role to its own landing).
 */
export function cameFromThisSite(): boolean {
  if (typeof window === 'undefined' || window.history.length <= 1 || !document.referrer) return false
  try { return new URL(document.referrer).origin === window.location.origin } catch { return false }
}

export function DesktopOnly({ route }: { route: string }) {
  const { t } = useT()
  const router = useRouter()
  // Known only in the browser: the server and the first paint draw the start-page link. Back only when this tab
  // came from HalaTuju itself — `history.length` also counts other sites, so a contract link opened from Gmail
  // would otherwise send Back to Gmail (M7b review). Anything else gets the start-page link.
  const [canGoBack, setCanGoBack] = useState(false)
  useEffect(() => { setCanGoBack(cameFromThisSite()) }, [])
  const back = 'inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-brand-fill px-4 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover'
  return (
    <section className="px-1 pb-6 pt-8 text-center md:hidden" data-desktop-only={route}
      aria-labelledby="desktop-only-title">
      <div aria-hidden className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl bg-info-50 text-brand-fill">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
          strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></svg>
      </div>
      <h1 id="desktop-only-title" className="text-xl font-semibold text-ground-900">{t('admin.desktopOnly.title')}</h1>
      <p className="mt-2 text-sm text-ground-600">{t('admin.desktopOnly.body')}</p>
      <div className="mt-5">
        {canGoBack ? (
          <button type="button" onClick={() => router.back()} className={back} data-desktop-only-back>
            ‹ {t('common.back')}
          </button>
        ) : (
          <Link href="/admin" className={back} data-desktop-only-back>‹ {t('admin.desktopOnly.home')}</Link>
        )}
      </div>
      <p className="mt-4 text-xs text-ground-500" data-desktop-only-why>
        {t('admin.desktopOnly.whyLabel')} {t(`admin.desktopOnly.why.${DESKTOP_ONLY[route]}`)}
      </p>
    </section>
  )
}
