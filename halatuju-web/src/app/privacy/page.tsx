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
          <p className="text-sm text-gray-500">Last updated: March 2026</p>

          <h2 className="text-lg font-semibold text-gray-900">Data We Collect</h2>
          <p className="text-gray-600">
            HalaTuju collects the following data to provide personalised course
            recommendations:
          </p>
          <ul className="list-disc pl-6 text-gray-600 space-y-1">
            <li><strong>IC number (NRIC)</strong> &mdash; collected at sign-up to verify student identity. Your IC is stored securely and displayed only as a masked value (e.g. ****-**-1234).</li>
            <li><strong>Examination grades</strong> &mdash; SPM or STPM grades you enter to check course eligibility.</li>
            <li><strong>Profile information</strong> &mdash; name, gender, nationality, state, contact details, and family background (optional fields you may choose to fill).</li>
            <li><strong>Quiz responses</strong> &mdash; optional career interest quiz answers used to rank courses by fit.</li>
            <li><strong>Authentication identifiers</strong> &mdash; your phone number or Google account identifier for sign-in.</li>
          </ul>

          <h2 className="text-lg font-semibold text-gray-900">How We Use Your Data</h2>
          <p className="text-gray-600">
            Your data is used solely to generate personalised course recommendations
            and to track your application journey. We do not sell, share, or disclose
            your personal information to third parties.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Data Storage</h2>
          <p className="text-gray-600">
            Your data is stored securely on Supabase (Singapore region) with
            row-level security policies. All sensitive data, including your IC
            number, is protected by encryption at rest and in transit. You may
            request deletion of your account and data at any time.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Contact</h2>
          <p className="text-gray-600">
            For privacy-related enquiries, please{' '}
            <a href="/contact" className="text-primary-500 hover:underline">
              contact us
            </a>.
          </p>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}
