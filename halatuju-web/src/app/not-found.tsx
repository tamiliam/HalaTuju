'use client'

import Link from 'next/link'
import { useT } from '@/lib/i18n'

export default function NotFound() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-[#f8fafc] flex items-center justify-center px-6">
      <div className="text-center max-w-sm">
        <p className="text-6xl font-bold text-primary-500 mb-2">404</p>
        <h1 className="text-xl font-semibold text-gray-900 mb-2">{t('errors.pageNotFound')}</h1>
        <p className="text-gray-500 text-sm mb-6">
          {t('errors.pageNotFoundDesc')}
        </p>
        <Link
          href="/"
          className="inline-block px-5 py-2.5 bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {t('errors.backToHome')}
        </Link>
      </div>
    </main>
  )
}
