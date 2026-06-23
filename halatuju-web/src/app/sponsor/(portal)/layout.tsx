'use client'

import { useEffect, useState, type ReactNode } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname, useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { sponsorSignOut } from '@/lib/sponsor-supabase'
import { getStudentsWaitingCount } from '@/lib/api'
import SponsorLanding from '@/components/SponsorLanding'
import SponsorDetailsForm from '@/components/SponsorDetailsForm'
import SponsorNotifyPrefs from '@/components/SponsorNotifyPrefs'
import { SponsorPortalProvider, useSponsorPortal } from '@/lib/sponsor-portal-context'

/**
 * The signed-in sponsor portal shell. Gates by account state and renders the
 * three-tab chrome (My Giving · Students · My Account) for approved sponsors only.
 * Signed-out visitors get the public marketing landing; the auth screens
 * (/sponsor/login, /register, /auth/callback) live OUTSIDE this route group so
 * they are not gated. Everything ships dark behind SPONSOR_POOL_ENABLED — when the
 * flag is off, the pool probe 404s and we fall back to the existing "coming soon".
 */
export default function SponsorPortalLayout({ children }: { children: ReactNode }) {
  const { t } = useT()
  const { isLoading, isSignedIn, account } = useSponsorAuth()

  // Public "students waiting" counter for the signed-out landing (mirrors /scholarship).
  const [waitingCount, setWaitingCount] = useState(0)
  useEffect(() => {
    let cancelled = false
    getStudentsWaitingCount()
      .then((d) => { if (!cancelled) setWaitingCount(d.count) })
      .catch(() => { /* leave at 0; the landing still renders */ })
    return () => { cancelled = true }
  }, [])

  // Signed-out → public marketing landing, rendered immediately (no auth spinner).
  if (!isSignedIn) return <SponsorLanding count={waitingCount} />

  // Signed in: hold only while the account finishes loading.
  if (isLoading) return <Chrome><Centered>{t('common.loading')}</Centered></Chrome>

  const isRegistered = !!account?.id
  const profileComplete = !!account?.profile_complete
  const needsDetails = account != null && (!isRegistered || !profileComplete)

  if (needsDetails) return <Chrome><CardWrap><SponsorDetailsForm /></CardWrap></Chrome>

  if (account?.status === 'pending') {
    return (
      <Chrome><CardWrap>
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-xl">⏳</div>
          <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorPortal.pendingTitle')}</h1>
          <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.pendingBody')}</p>
        </div>
      </CardWrap></Chrome>
    )
  }

  if (account?.status === 'approved') {
    return (
      <SponsorPortalProvider>
        <ApprovedPortal>{children}</ApprovedPortal>
      </SponsorPortalProvider>
    )
  }

  return (
    <Chrome><CardWrap>
      <div className="text-center">
        <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.inactiveTitle')}</h1>
        <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.inactiveBody')}</p>
      </div>
    </CardWrap></Chrome>
  )
}

/** Approved sponsor: decide between the dark "coming soon" and the live tabbed portal. */
function ApprovedPortal({ children }: { children: ReactNode }) {
  const { t } = useT()
  const { ready, poolUnavailable } = useSponsorPortal()

  if (!ready) return <Chrome><Centered>{t('common.loading')}</Centered></Chrome>

  // SPONSOR_POOL_ENABLED off → the pre-feature "coming soon" + notification prefs.
  if (poolUnavailable) {
    return (
      <Chrome><CardWrap>
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-700 text-xl">✓</div>
          <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorPortal.approvedTitle')}</h1>
          <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.approvedBody')}</p>
          <div className="mt-5 rounded-xl bg-gray-50 border border-dashed border-gray-200 px-4 py-5 text-sm text-gray-500">
            {t('sponsorPortal.comingSoon')}
          </div>
          <div className="mt-5"><SponsorNotifyPrefs /></div>
        </div>
      </CardWrap></Chrome>
    )
  }

  return <Chrome nav>{children}</Chrome>
}

/** Top bar (+ optional tab nav) shared by every signed-in sponsor screen. */
function Chrome({ children, nav = false }: { children: ReactNode; nav?: boolean }) {
  const { t } = useT()
  const router = useRouter()
  const pathname = usePathname()

  const signOut = async () => {
    await sponsorSignOut()
    router.replace('/sponsor/login')
  }

  const tabs = [
    { href: '/sponsor', label: t('sponsorPortal.nav.giving') },
    { href: '/sponsor/students', label: t('sponsorPortal.nav.students') },
    { href: '/sponsor/account', label: t('sponsorPortal.nav.account') },
  ]
  const active = (href: string) =>
    href === '/sponsor' ? pathname === '/sponsor' : pathname.startsWith(href)

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <header className="bg-white border-b sticky top-0 z-20">
        <div className="container mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <Link href="/sponsor" className="flex items-center gap-2 shrink-0">
            <Image src="/logo-icon.png" alt="HalaTuju" width={100} height={36} />
            <span className="text-sm font-semibold text-blue-600">{t('sponsorAuth.badge')}</span>
          </Link>
          <div className="flex items-center gap-0.5 sm:gap-1">
            {nav && (
              <nav aria-label={t('sponsorPortal.account.title')} className="flex items-center gap-0.5 sm:gap-1">
                {tabs.map((tb) => (
                  <Link
                    key={tb.href} href={tb.href}
                    aria-current={active(tb.href) ? 'page' : undefined}
                    className={`px-2.5 sm:px-3 py-2 text-sm font-medium rounded-lg ${
                      active(tb.href) ? 'text-blue-600 bg-blue-50' : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {tb.label}
                  </Link>
                ))}
              </nav>
            )}
            <button onClick={signOut} className="ml-1 sm:ml-2 px-2.5 sm:px-3 py-2 text-sm text-gray-400 hover:text-gray-600">
              {t('header.logout')}
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1 container mx-auto px-4 sm:px-6 py-6 sm:py-8">{children}</main>
      {nav && (
        <footer className="container mx-auto px-4 sm:px-6 py-6 text-center text-xs text-gray-400">
          <Link href="/sponsor/trust" className="text-gray-500 hover:text-blue-600 underline">
            {t('sponsorPortal.trust.footerLink')}
          </Link>
        </footer>
      )}
    </div>
  )
}

function CardWrap({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center justify-center px-2 py-8">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border p-8">{children}</div>
    </div>
  )
}

function Centered({ children }: { children: ReactNode }) {
  return <p className="text-center text-sm text-gray-400 mt-12">{children}</p>
}
