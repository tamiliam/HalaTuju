'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

export default function PrivacyPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('common.privacy')}</h1>
          <p className="text-sm text-gray-500">Last updated: February 2026</p>

          <h2 className="text-lg font-semibold text-gray-900">Data We Collect</h2>
          <p className="text-gray-600">
            HalaTuju collects your SPM grades, gender, nationality, and optional
            quiz responses to provide course recommendations. If you create an
            account, we store your phone number or Google account identifier for
            authentication.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">How We Use Your Data</h2>
          <p className="text-gray-600">
            Your data is used solely to generate personalised course recommendations.
            We do not sell, share, or disclose your personal information to third
            parties.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Data Storage</h2>
          <p className="text-gray-600">
            Your data is stored securely on Supabase (Singapore region) with
            row-level security policies. You may request deletion of your account
            and data at any time.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Contact</h2>
          <p className="text-gray-600">
            For privacy-related enquiries, please contact us at{' '}
            <a href="mailto:halatuju@tamilfoundation.org" className="text-primary-500 hover:underline">
              halatuju@tamilfoundation.org
            </a>.
          </p>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}
