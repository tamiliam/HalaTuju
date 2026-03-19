'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import Markdown from 'react-markdown'
import { getReport, type ReportDetail } from '@/lib/api'
import { getSession } from '@/lib/supabase'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

const localeMap: Record<string, string> = { en: 'en-MY', ms: 'ms-MY', ta: 'ta-MY' }

export default function ReportPage() {
  const params = useParams()
  const reportId = Number(params.id)
  const { t, locale } = useT()
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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mb-4" />
          <p className="text-gray-600">{t('report.loading')}</p>
        </div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            {error || t('report.notFound')}
          </h1>
          <Link href="/dashboard" className="btn-primary">
            {t('report.backToDashboard')}
          </Link>
        </div>
      </div>
    )
  }

  const formattedDate = new Date(report.created_at).toLocaleDateString(localeMap[locale] || 'en-MY', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header — hidden in print */}
      <div className="print:hidden">
        <AppHeader />
      </div>

      {/* Print action bar */}
      <div className="print:hidden container mx-auto px-6 pt-4">
        <button
          onClick={() => window.print()}
          className="btn-primary text-sm px-4 py-2"
        >
          {t('report.downloadPdf')}
        </button>
      </div>

      {/* Report Content */}
      <div className="container mx-auto px-6 py-8 max-w-3xl">
        {/* Report Header */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6 print:border-0 print:p-0 print:mb-4">
          <div className="flex items-center gap-3 mb-4 print:mb-2">
            <Image
              src="/logo-icon.png"
              alt="HalaTuju"
              width={75}
              height={40}
              className="hidden print:block"
            />
            <div>
              <h1 className="text-2xl font-bold text-gray-900 print:text-xl">
                {report.title}
              </h1>
              <p className="text-sm text-gray-500">
                {formattedDate}
              </p>
            </div>
          </div>
        </div>

        {/* Markdown Report Body */}
        <div className="bg-white rounded-xl border border-gray-200 p-8 print:border-0 print:p-0">
          <article className="prose prose-gray max-w-none
            prose-headings:text-gray-900 prose-headings:font-semibold
            prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-4
            prose-h3:text-lg prose-h3:mt-6 prose-h3:mb-3
            prose-p:text-gray-700 prose-p:leading-relaxed
            prose-li:text-gray-700
            prose-strong:text-gray-900
            print:prose-sm"
          >
            <Markdown>{report.markdown}</Markdown>
          </article>
        </div>

        {/* Footer — print only */}
        <div className="hidden print:block mt-8 pt-4 border-t text-center text-xs text-gray-400">
          <p>{t('report.footerText', { date: formattedDate })}</p>
        </div>
      </div>

      <div className="print:hidden">
        <AppFooter />
      </div>
    </main>
  )
}
