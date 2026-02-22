'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

export default function AboutPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('common.about')}</h1>

          <h2 className="text-lg font-semibold text-gray-900">What is HalaTuju?</h2>
          <p className="text-gray-600">
            HalaTuju is a free course recommendation tool for Malaysian SPM leavers.
            It helps students discover polytechnic, TVET, and university programmes
            they are eligible for based on their SPM results.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">How does it work?</h2>
          <p className="text-gray-600">
            Enter your SPM grades and profile information. Our eligibility engine
            checks your results against the entry requirements of over 800 courses
            across polytechnics, community colleges, TVET institutions, and public
            universities in Malaysia.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Who built this?</h2>
          <p className="text-gray-600">
            HalaTuju is part of the Lentera Education Equity Programme, designed to
            improve access to public tertiary education for Malaysian students.
            It is built and maintained by the Tamil Foundation.
          </p>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}
