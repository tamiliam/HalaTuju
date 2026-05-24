'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { getMyScholarshipApplications, type ScholarshipApplication } from '@/lib/api'
import ScholarshipNextSteps from '@/components/ScholarshipNextSteps'

/**
 * The post-submission home for an applicant. A shortlisted student completes
 * their follow-up (quiz, deeper info, documents, consent) here; anyone else
 * sees a neutral "received" status. Unauthenticated visitors are sent to apply.
 */
export default function ScholarshipApplicationPage() {
  const { t } = useT()
  const { status, token } = useAuth()
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

  function wrap(children: React.ReactNode) {
    return (
      <main className="container mx-auto px-6 py-10 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('scholarship.application.title')}</h1>
        {children}
      </main>
    )
  }

  if (status === 'loading' || loading) {
    return wrap(<p className="text-gray-500">{t('scholarship.apply.loading')}</p>)
  }

  if (!app) {
    return wrap(
      <div className="bg-white border rounded-2xl p-6 text-center shadow-sm">
        <p className="text-gray-700 mb-4">{t('scholarship.application.none')}</p>
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
      <div className="bg-primary-50 border border-primary-200 rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-2">
          <svg className="w-6 h-6 text-primary-600 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h2 className="font-semibold text-gray-900">{t('scholarship.application.acceptedTitle')}</h2>
        </div>
        <p className="text-gray-700">{t('scholarship.application.acceptedBody')}</p>
      </div>
    )
  }

  // submitted / rejected / withdrawn — keep it neutral (the decision email is
  // sent separately; we don't expose a raw "rejected" status here).
  return wrap(
    <div className="bg-green-50 border border-green-200 rounded-2xl p-6">
      <h2 className="font-semibold text-gray-900 mb-2">{t('scholarship.application.receivedTitle')}</h2>
      <p className="text-gray-700">{t('scholarship.application.receivedBody')}</p>
    </div>
  )
}
