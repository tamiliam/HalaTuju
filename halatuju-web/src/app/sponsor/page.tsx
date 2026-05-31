'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { signInWithGoogle } from '@/lib/supabase'
import { KEY_SPONSOR_SIGNIN } from '@/lib/storage'
import { getSponsorMe, registerSponsor, type SponsorAccount } from '@/lib/api'

export default function SponsorPortalPage() {
  const { t } = useT()
  const { isLoading, isAnonymous, token } = useAuth()

  const [account, setAccount] = useState<SponsorAccount | null>(null)
  const [loadingAccount, setLoadingAccount] = useState(true)
  const [name, setName] = useState('')
  const [organisation, setOrganisation] = useState('')
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  // Fetch the caller's sponsor account once they're signed in (non-anonymous).
  useEffect(() => {
    if (isLoading) return
    if (isAnonymous || !token) {
      setLoadingAccount(false)
      return
    }
    setLoadingAccount(true)
    getSponsorMe({ token })
      .then((a) => setAccount(a))
      .catch(() => setError(t('sponsorPortal.loadFailed')))
      .finally(() => setLoadingAccount(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, isAnonymous, token])

  const handleSignIn = async () => {
    try {
      sessionStorage.setItem(KEY_SPONSOR_SIGNIN, '1')
    } catch { /* sessionStorage unavailable — sign-in still works, defaults to /dashboard */ }
    await signInWithGoogle()
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || submitting || !token) return
    setSubmitting(true)
    setError('')
    try {
      const a = await registerSponsor(
        { name: name.trim(), organisation: organisation.trim(), note: note.trim() },
        { token },
      )
      setAccount(a)
    } catch {
      setError(t('sponsorPortal.registerFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const isRegistered = !!account?.id
  const canRegister = !!name.trim() && !submitting

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <AppHeader />
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border p-8">
          {(isLoading || loadingAccount) ? (
            <p className="text-center text-gray-500">{t('common.loading')}</p>
          ) : isAnonymous ? (
            /* ── Not signed in ── */
            <div className="text-center">
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.signInTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.signInBody')}</p>
              <button
                onClick={handleSignIn}
                className="mt-6 w-full bg-primary-500 text-white font-semibold py-3 rounded-xl hover:bg-primary-600 transition-colors"
              >
                {t('sponsorPortal.signInGoogle')}
              </button>
              <p className="text-xs text-gray-400 mt-4">{t('sponsorPortal.privacyNote')}</p>
            </div>
          ) : !isRegistered ? (
            /* ── Signed in, not yet registered ── */
            <>
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.registerTitle')}</h1>
              <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.registerIntro')}</p>
              <form onSubmit={handleRegister} className="mt-5 space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorPortal.name')} *</label>
                  <input value={name} onChange={(e) => setName(e.target.value)} className="input w-full" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorPortal.organisation')}</label>
                  <input value={organisation} onChange={(e) => setOrganisation(e.target.value)} className="input w-full" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorPortal.note')}</label>
                  <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3}
                    placeholder={t('sponsorPortal.notePlaceholder')} className="input w-full" />
                </div>
                {error && <p className="text-sm text-red-600">{error}</p>}
                <button type="submit" disabled={!canRegister}
                  className="w-full bg-primary-500 text-white font-semibold py-3 rounded-xl hover:bg-primary-600 transition-colors disabled:opacity-50">
                  {submitting ? t('sponsorPortal.submitting') : t('sponsorPortal.submit')}
                </button>
              </form>
            </>
          ) : account?.status === 'pending' ? (
            /* ── Registered, awaiting admin vetting ── */
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-xl">⏳</div>
              <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorPortal.pendingTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.pendingBody')}</p>
              <Link href="/" className="inline-block mt-5 text-sm font-semibold text-primary-600 hover:underline">
                {t('sponsorPortal.backHome')}
              </Link>
            </div>
          ) : account?.status === 'approved' ? (
            /* ── Approved — browsing arrives in E2 ── */
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-700 text-xl">✓</div>
              <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorPortal.approvedTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.approvedBody')}</p>
              <div className="mt-5 rounded-xl bg-gray-50 border border-dashed border-gray-200 px-4 py-5 text-sm text-gray-500">
                {t('sponsorPortal.comingSoon')}
              </div>
            </div>
          ) : (
            /* ── Rejected or suspended — neutral, non-final wording ── */
            <div className="text-center">
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.inactiveTitle')}</h1>
              <p className="text-sm text-gray-600 mt-2">{t('sponsorPortal.inactiveBody')}</p>
              <Link href="/" className="inline-block mt-5 text-sm font-semibold text-primary-600 hover:underline">
                {t('sponsorPortal.backHome')}
              </Link>
            </div>
          )}
        </div>
      </main>
      <AppFooter />
    </div>
  )
}
