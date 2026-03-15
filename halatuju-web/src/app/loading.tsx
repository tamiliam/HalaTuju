'use client'

import { useT } from '@/lib/i18n'

export default function Loading() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-[#f8fafc] flex items-center justify-center">
      <div className="text-center">
        <div className="w-10 h-10 border-3 border-primary-200 border-t-primary-500 rounded-full animate-spin mx-auto mb-4" />
        <p className="text-gray-500 text-sm">{t('common.loading')}</p>
      </div>
    </main>
  )
}
