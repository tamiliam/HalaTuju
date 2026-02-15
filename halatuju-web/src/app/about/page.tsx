import Link from 'next/link'

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <h1 className="text-xl font-semibold text-gray-900">About HalaTuju</h1>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
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
          </p>
        </div>
      </div>
    </main>
  )
}
