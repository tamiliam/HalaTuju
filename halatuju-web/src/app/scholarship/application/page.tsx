'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { getMyScholarshipApplications, type ScholarshipApplication } from '@/lib/api'
import ScholarshipNextSteps from '@/components/ScholarshipNextSteps'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'

/**
 * The post-submission home for an applicant. A shortlisted student completes
 * their follow-up (quiz, deeper info, documents, consent) here; anyone else
 * sees a neutral "received" status. Unauthenticated visitors are sent to apply.
 *
 * Wrapped in the standard AppHeader/AppFooter so it never looks like a dead-end
 * page — the student keeps full site navigation after submitting.
 */
export default function ScholarshipApplicationPage() {
  const { t } = useT()
  const { status, token, profile } = useAuth()
  const router = useRouter()
  const [app, setApp] = useState<ScholarshipApplication | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    if (status === 'loading') return
    if (status === 'anonymous' || status === 'needs-nric' || !token) {
      router.replace('/scholarship/apply')
      return
    }
    getMyScholarshipApplications({ token })
      .then((res) => { if (active) setApp(res.applications[0] ?? null) })
      .catch(() => { if (active) setApp(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [status, token, router])

  // Where our communications will go — the verified account email (the profile's
  // contact email if set, otherwise the Google sign-in address).
  const commsEmail = profile?.contact_email || profile?.email || ''

  // The shortlisted view needs the extra width for the desktop step-rail.
  // Other status cards (received/accepted/none) keep the narrower max-w-2xl.
  const isShortlisted = app?.status === 'shortlisted'

  function wrap(children: React.ReactNode) {
    return (
      <div className="flex min-h-screen flex-col">
        <AppHeader />
        <main className={`container mx-auto w-full flex-1 px-6 py-10 ${isShortlisted ? 'max-w-2xl lg:max-w-4xl' : 'max-w-2xl'}`}>
          <h1 className="mb-6 text-2xl font-bold text-gray-900">{t('scholarship.application.title')}</h1>
          {children}
        </main>
        <AppFooter />
      </div>
    )
  }

  // Email note + onward navigation, shown under the status card so the page is
  // never a dead end.
  function nav() {
    return (
      <>
        {commsEmail && (
          <p className="mt-4 text-sm text-gray-500">
            {t('scholarship.application.emailNote', { email: commsEmail })}
          </p>
        )}
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/search" className="btn-primary inline-block">
            {t('scholarship.application.browseCta')}
          </Link>
          <Link href="/" className="inline-block rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
            {t('scholarship.application.homeCta')}
          </Link>
        </div>
      </>
    )
  }

  if (status === 'loading' || loading) {
    return wrap(<p className="text-gray-500">{t('scholarship.apply.loading')}</p>)
  }

  if (!app) {
    return wrap(
      <div className="rounded-2xl border bg-white p-6 text-center shadow-sm">
        <p className="mb-4 text-gray-700">{t('scholarship.application.none')}</p>
        <Link href="/scholarship/apply" className="btn-primary inline-block">
          {t('scholarship.application.applyCta')}
        </Link>
      </div>
    )
  }

  if (app.status === 'shortlisted') {
    return wrap(<ScholarshipNextSteps initialApp={app} token={token} />)
  }

  // accepted — the admin has verified & confirmed this applicant.
  if (app.status === 'accepted') {
    return wrap(
      <div className="rounded-2xl border border-primary-200 bg-primary-50 p-6">
        <div className="mb-2 flex items-center gap-2">
          <svg className="h-6 w-6 shrink-0 text-primary-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h2 className="font-semibold text-gray-900">{t('scholarship.application.acceptedTitle')}</h2>
        </div>
        <p className="text-gray-700">{t('scholarship.application.acceptedBody')}</p>
        {nav()}
      </div>
    )
  }

  // submitted / rejected / withdrawn — keep it neutral (the decision email is
  // sent separately; we don't expose a raw "rejected" status here).
  return wrap(
    <div className="rounded-2xl border border-green-200 bg-green-50 p-6">
      <h2 className="mb-2 font-semibold text-gray-900">{t('scholarship.application.receivedTitle')}</h2>
      <p className="text-gray-700">{t('scholarship.application.receivedBody')}</p>
      {nav()}
    </div>
  )
}
