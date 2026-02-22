'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

export default function TermsPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('common.terms')}</h1>
          <p className="text-sm text-gray-500">Last updated: February 2026</p>

          <h2 className="text-lg font-semibold text-gray-900">Acceptance of Terms</h2>
          <p className="text-gray-600">
            By using HalaTuju, you agree to these terms of service. HalaTuju is
            provided free of charge as a public service tool.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Recommendations Disclaimer</h2>
          <p className="text-gray-600">
            Course recommendations are generated based on publicly available entry
            requirements. HalaTuju does not guarantee admission to any course or
            institution. Always verify requirements directly with the institution
            before applying.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Limitation of Liability</h2>
          <p className="text-gray-600">
            HalaTuju is provided &ldquo;as is&rdquo; without warranty of any kind.
            We are not liable for any decisions made based on the recommendations
            provided by this tool.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Changes to Terms</h2>
          <p className="text-gray-600">
            We may update these terms from time to time. Continued use of HalaTuju
            constitutes acceptance of any changes.
          </p>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}
