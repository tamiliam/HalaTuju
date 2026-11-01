'use client'

import Markdown from 'react-markdown'
import BrandLogo from '@/components/BrandLogo'
import type { ReportDetail } from '@/lib/api'
import { useT } from '@/lib/i18n'

const localeMap: Record<string, string> = { en: 'en-MY', ms: 'ms-MY', ta: 'ta-MY' }

/**
 * A student's report, as `/report/[id]` shows it once it has loaded (Mobile M3: lifted out of the
 * page so the design sandbox can mount the real view with a fixture, never a real sign-in).
 *
 * On a phone: 16 px gutters and a 16 px card (it was 24 + 32, leaving ~278 px for the text), a
 * 44 px "Download PDF" button, and `break-words` so a long word or link never widens the page.
 * ⚠ NO TABLES TO FRAME: react-markdown is used WITHOUT remark-gfm, so a pipe table in a report is
 * drawn as plain lines of text (which wrap). If GFM is ever added, frame `table` in a sideways-
 * scrolling box here first (mobile-standard rule 7).
 */
export default function ReportView({ report }: { report: ReportDetail }) {
  const { t, locale } = useT()
  const formattedDate = new Date(report.created_at).toLocaleDateString(localeMap[locale] || 'en-MY', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  return (
    <>
      {/* Print action bar */}
      <div className="print:hidden container mx-auto px-4 pt-4 sm:px-6">
        <button
          onClick={() => window.print()}
          className="btn-primary min-h-11 text-sm px-4 py-2"
        >
          {t('report.downloadPdf')}
        </button>
      </div>

      {/* Report Content */}
      <div className="container mx-auto max-w-3xl px-4 py-6 sm:px-6 md:py-8">
        {/* Report Header */}
        <div className="bg-ground-0 rounded-xl border border-ground-200 p-4 mb-6 sm:p-6 print:border-0 print:p-0 print:mb-4">
          <div className="flex items-center gap-3 mb-4 print:mb-2">
            <BrandLogo
              width={75}
              height={40}
              className="hidden print:block"
            />
            <div className="min-w-0">
              <h1 className="text-2xl font-bold text-ground-900 break-words print:text-xl">
                {report.title}
              </h1>
              <p className="text-sm text-ground-500">
                {formattedDate}
              </p>
            </div>
          </div>
        </div>

        {/* Markdown Report Body */}
        <div className="bg-ground-0 rounded-xl border border-ground-200 p-4 sm:p-8 print:border-0 print:p-0">
          <article className="prose prose-gray max-w-none break-words
            prose-headings:text-ground-900 prose-headings:font-semibold
            prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-4
            prose-h3:text-lg prose-h3:mt-6 prose-h3:mb-3
            prose-p:text-ground-700 prose-p:leading-relaxed
            prose-li:text-ground-700
            prose-strong:text-ground-900
            print:prose-sm"
          >
            <Markdown>{report.markdown}</Markdown>
          </article>
        </div>

        {/* Footer — print only */}
        <div className="hidden print:block mt-8 pt-4 border-t text-center text-xs text-ground-400">
          <p>{t('report.footerText', { date: formattedDate })}</p>
        </div>
      </div>
    </>
  )
}
