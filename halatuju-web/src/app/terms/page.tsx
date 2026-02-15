import Link from 'next/link'

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <h1 className="text-xl font-semibold text-gray-900">Terms of Service</h1>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
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
    </main>
  )
}
