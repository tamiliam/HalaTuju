'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

export default function CookiesPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('common.cookies')}</h1>
          <p className="text-sm text-gray-500">Last updated: March 2026</p>

          <h2 className="text-lg font-semibold text-gray-900">What Are Cookies?</h2>
          <p className="text-gray-600">
            Cookies are small text files stored on your device when you visit a website.
            They help the site remember your preferences and improve your experience.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Cookies We Use</h2>
          <p className="text-gray-600">
            HalaTuju uses only essential cookies required for the site to function properly:
          </p>
          <ul className="list-disc pl-6 text-gray-600 space-y-1">
            <li><strong>Authentication cookies</strong> &mdash; to keep you signed in securely (managed by Supabase).</li>
            <li><strong>Language preference</strong> &mdash; to remember your chosen language (stored in localStorage).</li>
            <li><strong>Profile data</strong> &mdash; your SPM or STPM grades and quiz answers are stored locally on your device so you do not need to re-enter them.</li>
          </ul>

          <h2 className="text-lg font-semibold text-gray-900">Third-Party Cookies</h2>
          <p className="text-gray-600">
            HalaTuju does not use any advertising, tracking, or analytics cookies.
            We do not share your data with third parties.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Managing Cookies</h2>
          <p className="text-gray-600">
            You can clear your browser cookies at any time through your browser settings.
            You can also clear your HalaTuju profile data from the Settings page.
          </p>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}
