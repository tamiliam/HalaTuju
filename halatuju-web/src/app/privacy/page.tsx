import Link from 'next/link'

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <h1 className="text-xl font-semibold text-gray-900">Privacy Policy</h1>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
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
            For privacy-related enquiries, please contact the HalaTuju team through
            the Lentera Programme.
          </p>
        </div>
      </div>
    </main>
  )
}
