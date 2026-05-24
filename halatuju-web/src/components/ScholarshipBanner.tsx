'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { getMyScholarshipApplications } from '@/lib/api'

/**
 * Dashboard banner that surfaces a live B40 application when there's something
 * for the student to act on or celebrate — shortlisted (complete your follow-up)
 * or accepted (confirmed). Self-contained: it fetches the caller's application
 * and renders nothing for everyone else (no application, or still submitted).
 */
export default function ScholarshipBanner() {
  const { status, token } = useAuth()
  const { t } = useT()
  const [appStatus, setAppStatus] = useState<string | null>(null)

  useEffect(() => {
    if (status !== 'ready' || !token) return
    let active = true
    getMyScholarshipApplications({ token })
      .then((res) => { if (active) setAppStatus(res.applications[0]?.status ?? null) })
      .catch(() => { /* non-blocking — the banner just stays hidden */ })
    return () => { active = false }
  }, [status, token])

  if (appStatus !== 'shortlisted' && appStatus !== 'accepted') return null

  return (
    <Link
      href="/scholarship/application"
      className="mb-6 flex items-center gap-3 rounded-2xl border border-primary-200 bg-primary-50 px-4 py-3 transition-colors hover:bg-primary-100"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-500 text-white">
        <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </span>
      <span className="min-w-0 leading-tight">
        <span className="block text-sm font-semibold text-gray-900">{t(`scholarship.banner.${appStatus}Title`)}</span>
        <span className="block text-xs text-gray-600">{t(`scholarship.banner.${appStatus}Body`)}</span>
      </span>
      <svg className="ml-auto h-5 w-5 shrink-0 text-primary-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </Link>
  )
}
