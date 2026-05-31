'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { sponsorSignOut } from '@/lib/sponsor-supabase'
import { registerSponsor } from '@/lib/api'
import { SPONSOR_SOURCES } from '@/lib/sponsorAuth'
import { formatPhone, isValidPhone } from '@/lib/scholarship'
import { KEY_SPONSOR_PENDING } from '@/lib/storage'

export default function SponsorPortalPage() {
  const { t } = useT()
  const router = useRouter()
  const { isLoading, isSignedIn, session, token, account, refreshAccount } = useSponsorAuth()

  // Complete-details form state (used when registered=false or profile incomplete).
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [source, setSource] = useState('')
  const [consent, setConsent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const prefilled = useRef(false)

  const isRegistered = !!account?.id
  const profileComplete = !!account?.profile_complete
  const needsDetails = isSignedIn && account != null && (!isRegistered || !profileComplete)

  // One-time pre-fill of the details form from the stash / session / account.
  useEffect(() => {
    if (prefilled.current || !needsDetails) return
    let stash: { name?: string; phone?: string; source?: string } = {}
    try {
      const raw = sessionStorage.getItem(KEY_SPONSOR_PENDING)
      if (raw) stash = JSON.parse(raw)
    } catch { /* ignore malformed stash */ }
    const metaName = (session?.user?.user_metadata?.full_name as string) || (session?.user?.user_metadata?.name as string) || ''
    setName(account?.name || stash.name || metaName || '')
    setPhone(account?.phone || stash.phone || '')
    setSource(account?.source || stash.source || '')
    prefilled.current = true
  }, [needsDetails, account, session])

  const canSubmit = !!name.trim() && isValidPhone(phone) && !!source && consent && !submitting

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit || !token) return
    setSubmitting(true)
    setError('')
    try {
      await registerSponsor({ name: name.trim(), phone, source, consent: true }, { token })
      try { sessionStorage.removeItem(KEY_SPONSOR_PENDING) } catch { /* ignore */ }
      await refreshAccount()
    } catch {
      setError(t('sponsorAuth.registerFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleSignOut = async () => {
    await sponsorSignOut()
    router.replace('/sponsor/login')
  }

  const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      {/* Slim sponsor top bar */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Image src="/logo-icon.png" alt="HalaTuju" width={100} height={36} />
            <span className="text-sm font-semibold text-blue-600">{t('sponsorAuth.badge')}</span>
          </Link>
          {isSignedIn && (
            <button onClick={handleSignOut} className="text-sm text-red-600 hover:text-red-800">{t('header.logout')}</button>
          )}
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border p-8">
          {isLoading ? (
            <p className="text-center text-gray-500">{t('common.loading')}</p>
          ) : !isSignedIn ? (
            /* ── Not signed in ── */
            <div className="text-center">
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.signInTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.signInBody')}</p>
              <Link href="/sponsor/login" className="mt-6 block w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition-colors">
                {t('sponsorAuth.signIn')}
              </Link>
              <p className="text-sm text-gray-500 mt-4">
                {t('sponsorAuth.noAccount')}{' '}
                <Link href="/sponsor/register" className="font-semibold text-blue-600 hover:underline">{t('sponsorAuth.createAccount')}</Link>
              </p>
            </div>
          ) : needsDetails ? (
            /* ── Signed in, details incomplete (e.g. via Google) ── */
            <>
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.completeTitle')}</h1>
              <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.completeBody')}</p>
              <form onSubmit={handleSubmit} className="mt-5 space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.fullName')} *</label>
                  <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.phone')} *</label>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-sm text-gray-600 whitespace-nowrap">🇲🇾 +60</span>
                    <input inputMode="tel" value={phone} onChange={(e) => setPhone(formatPhone(e.target.value))} placeholder="012-345 6789" className={inputCls} />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorAuth.source')} *</label>
                  <select value={source} onChange={(e) => setSource(e.target.value)} className={inputCls}>
                    <option value="">{t('sponsorAuth.sourcePlaceholder')}</option>
                    {SPONSOR_SOURCES.map((s) => <option key={s} value={s}>{t(`sponsorAuth.sourceOption.${s}`)}</option>)}
                  </select>
                </div>
                <label className="flex items-start gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
                  <span>{t('sponsorAuth.consent')}{' '}
                    <Link href="/privacy" className="text-blue-600 hover:underline">{t('sponsorAuth.privacyNotice')}</Link>.
                  </span>
                </label>
                {error && <p className="text-sm text-red-600">{error}</p>}
                <button type="submit" disabled={!canSubmit}
                  className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50">
                  {submitting ? t('sponsorAuth.submitting') : t('sponsorAuth.submitDetails')}
                </button>
              </form>
            </>
          ) : account?.status === 'pending' ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-xl">⏳</div>
              <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorPortal.pendingTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.pendingBody')}</p>
            </div>
          ) : account?.status === 'approved' ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-700 text-xl">✓</div>
              <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorPortal.approvedTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.approvedBody')}</p>
              <div className="mt-5 rounded-xl bg-gray-50 border border-dashed border-gray-200 px-4 py-5 text-sm text-gray-500">
                {t('sponsorPortal.comingSoon')}
              </div>
            </div>
          ) : (
            <div className="text-center">
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.inactiveTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.inactiveBody')}</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
