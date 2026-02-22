'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

export default function ContactPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('common.contact')}</h1>

          <p className="text-gray-600">
            HalaTuju is part of the Lentera Education Equity Programme, run by the
            Tamil Foundation (MCEF).
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Email</h2>
          <p className="text-gray-600">
            For enquiries, feedback, or data deletion requests:{' '}
            <a href="mailto:halatuju@tamilfoundation.org" className="text-primary-500 hover:underline">
              halatuju@tamilfoundation.org
            </a>
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Report an Issue</h2>
          <p className="text-gray-600">
            Found incorrect course data or a bug? Please email us with details and
            we will investigate promptly.
          </p>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}
