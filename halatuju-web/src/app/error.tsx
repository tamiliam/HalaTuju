'use client'

import { useT } from '@/lib/i18n'

export default function Error({
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-ground-50 flex items-center justify-center px-6">
      <div className="text-center max-w-sm">
        <p className="text-5xl font-bold text-primary-500 mb-2">{t('errors.oops')}</p>
        <h1 className="text-xl font-semibold text-ground-900 mb-2">{t('errors.somethingWentWrong')}</h1>
        <p className="text-ground-500 text-sm mb-6">
          {t('errors.unexpectedError')}
        </p>
        <button
          onClick={reset}
          className="inline-block px-5 py-2.5 bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {t('errors.tryAgain')}
        </button>
      </div>
    </main>
  )
}
