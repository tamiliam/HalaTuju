'use client'

// TD-416: the shell itself shows sponsor* words, so it loads their slice before it renders. Each
// page imports it too, so the slice is counted in that page's first-load JS (TD-304), not hidden here.
import '@/lib/messagesSponsor'
import { useEffect, useState, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { wasScopeSuperseded } from '@/lib/sessionPolicy'
import { getStudentsWaitingCount } from '@/lib/api'
import SponsorLanding from '@/components/SponsorLanding'
import SponsorDetailsForm from '@/components/SponsorDetailsForm'
import SponsorTermsWizard from '@/components/sponsors/SponsorTermsWizard'
import SponsorNotifyPrefs from '@/components/SponsorNotifyPrefs'
// The chrome (header, desktop tabs, phone tab bar, footer) and the single-card frame — Mobile M5.
import SponsorShell, { SponsorCard } from '@/components/sponsor/SponsorShell'
import { SponsorPortalProvider, useSponsorPortal } from '@/lib/sponsor-portal-context'

const Chrome = SponsorShell
const CardWrap = SponsorCard

/**
 * The signed-in sponsor portal shell. Gates by account state and renders the
 * three-tab chrome (My Giving · Students · My Account) for approved sponsors only —
 * `SponsorShell` draws it (Mobile M5: a slim header and a bottom tab bar on a phone,
 * the old top row from md).
 * Signed-out visitors get the public marketing landing; the auth screens
 * (/sponsor/login, /register, /auth/callback) live OUTSIDE this route group so
 * they are not gated. Everything ships dark behind SPONSOR_POOL_ENABLED — when the
 * flag is off, the pool probe 404s and we fall back to the existing "coming soon".
 */
export default function SponsorPortalLayout({ children }: { children: ReactNode }) {
  const { t } = useT()
  const router = useRouter()
  const { isLoading, isSignedIn, account, token, refreshAccount } = useSponsorAuth()

  // Public "students waiting" counter for the signed-out landing (mirrors /scholarship).
  const [waitingCount, setWaitingCount] = useState(0)
  useEffect(() => {
    let cancelled = false
    getStudentsWaitingCount()
      .then((d) => { if (!cancelled) setWaitingCount(d.count) })
      .catch(() => { /* leave at 0; the landing still renders */ })
    return () => { cancelled = true }
  }, [])

  // If this sponsor session was just ended because the same account signed into the
  // partner console, send the tab to /sponsor/login (outside this layout) so it shows
  // the "signed out elsewhere" note — rather than silently dropping to the landing.
  useEffect(() => {
    if (!isSignedIn && wasScopeSuperseded('sponsor')) router.replace('/sponsor/login')
  }, [isSignedIn, router])

  // Signed-out → public marketing landing, rendered immediately (no auth spinner).
  if (!isSignedIn) return <SponsorLanding count={waitingCount} />

  // Signed in: hold only while the account finishes loading.
  if (isLoading) return <Chrome><Centered>{t('common.loading')}</Centered></Chrome>

  const isRegistered = !!account?.id
  const profileComplete = !!account?.profile_complete
  const needsDetails = account != null && (!isRegistered || !profileComplete)

  if (needsDetails) return <Chrome><CardWrap><SponsorDetailsForm /></CardWrap></Chrome>

  // Terms acceptance sits HERE — after details, before the vetting statuses.
  //
  // `needs_terms` is computed entirely on the server (`sponsor_terms.acceptance_state`, gated on
  // SPONSOR_TERMS_ENABLED), so this branch never decides anything: it renders what the account
  // payload reports. Chrome WITHOUT `nav` means no tabs are drawn, so there is nothing to click
  // away to — the same enforcement SponsorDetailsForm already relies on.
  //
  // ⚠ Placed above the status branches on purpose, but it can only fire for a sponsor who could
  // otherwise reach the portal: showing a suspended account a terms wizard instead of "your access
  // is inactive" would be worse than useless, and the server never sets needs_terms for one.
  if (account?.terms?.needs_terms) {
    return (
      <Chrome><CardWrap>
        <SponsorTermsWizard token={token} accountName={account?.name || ''}
          onAccepted={refreshAccount} />
      </CardWrap></Chrome>
    )
  }

  if (account?.status === 'pending') {
    return (
      <Chrome><CardWrap>
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-caution-100 text-caution-700 text-xl">⏳</div>
          <h1 className="text-xl font-bold text-ground-900 mt-3">{t('sponsorPortal.pendingTitle')}</h1>
          <p className="text-sm text-ground-600 mt-2">{t('sponsorPortal.pendingBody')}</p>
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
        <h1 className="text-xl font-bold text-ground-900">{t('sponsorPortal.inactiveTitle')}</h1>
        <p className="text-sm text-ground-600 mt-2">{t('sponsorPortal.inactiveBody')}</p>
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
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-positive-100 text-positive-700 text-xl">✓</div>
          <h1 className="text-xl font-bold text-ground-900 mt-3">{t('sponsorPortal.approvedTitle')}</h1>
          <p className="text-sm text-ground-600 mt-2">{t('sponsorPortal.approvedBody')}</p>
          <div className="mt-5 rounded-xl bg-ground-50 border border-dashed border-ground-200 px-4 py-5 text-sm text-ground-500">
            {t('sponsorPortal.comingSoon')}
          </div>
          <div className="mt-5"><SponsorNotifyPrefs /></div>
        </div>
      </CardWrap></Chrome>
    )
  }

  return <Chrome nav>{children}</Chrome>
}

function Centered({ children }: { children: ReactNode }) {
  return <p className="text-center text-sm text-ground-400 mt-12">{children}</p>
}
