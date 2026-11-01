'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { getReport, type ReportDetail } from '@/lib/api'
import { getSession } from '@/lib/supabase'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import ReportView from '@/components/ReportView'
import { useT } from '@/lib/i18n'

export default function ReportPage() {
  const params = useParams()
  const reportId = Number(params.id)
  const { t } = useT()
  const [report, setReport] = useState<ReportDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadReport() {
      try {
        const { session } = await getSession()
        if (!session?.access_token) {
          setError(t('report.loginRequired'))
          setLoading(false)
          return
        }
        const data = await getReport(reportId, { token: session.access_token })
        setReport(data)
      } catch {
        setError(t('report.loadFailed'))
      } finally {
        setLoading(false)
      }
    }
    loadReport()
  }, [reportId])

  return (
    <main className="min-h-screen bg-ground-50">
      {/* Header — hidden in print. Shown while loading and on an error too (Mobile M3): those
          states used to be a bare page with no way to the menu. */}
      <div className="print:hidden">
        <AppHeader />
      </div>

      {loading ? (
        <div className="flex min-h-[60dvh] items-center justify-center px-4">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-brand-shape border-t-transparent mb-4" />
            <p className="text-ground-600">{t('report.loading')}</p>
          </div>
        </div>
      ) : error || !report ? (
        <div className="flex min-h-[60dvh] items-center justify-center px-4">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-ground-900 mb-4 break-words">
              {error || t('report.notFound')}
            </h1>
            <Link href="/dashboard" className="btn-primary">
              {t('report.backToDashboard')}
            </Link>
          </div>
        </div>
      ) : (
        <ReportView report={report} />
      )}

      <div className="print:hidden">
        <AppFooter />
      </div>
    </main>
  )
}
