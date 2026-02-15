'use client'

import Link from 'next/link'

export default function SettingsPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <h1 className="text-xl font-semibold text-gray-900">Settings</h1>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 divide-y">
          <Link href="/onboarding/grades" className="block px-6 py-4 hover:bg-gray-50 transition-colors">
            <h3 className="font-medium text-gray-900">Edit Grades</h3>
            <p className="text-sm text-gray-500">Update your SPM grades and profile</p>
          </Link>
          <Link href="/saved" className="block px-6 py-4 hover:bg-gray-50 transition-colors">
            <h3 className="font-medium text-gray-900">Saved Courses</h3>
            <p className="text-sm text-gray-500">View your bookmarked courses</p>
          </Link>
          <Link href="/about" className="block px-6 py-4 hover:bg-gray-50 transition-colors">
            <h3 className="font-medium text-gray-900">About HalaTuju</h3>
            <p className="text-sm text-gray-500">Learn more about this project</p>
          </Link>
        </div>

        <div className="mt-8 bg-white rounded-xl border border-gray-200 divide-y">
          <Link href="/privacy" className="block px-6 py-4 hover:bg-gray-50 transition-colors">
            <h3 className="font-medium text-gray-900">Privacy Policy</h3>
          </Link>
          <Link href="/terms" className="block px-6 py-4 hover:bg-gray-50 transition-colors">
            <h3 className="font-medium text-gray-900">Terms of Service</h3>
          </Link>
        </div>
      </div>
    </main>
  )
}
