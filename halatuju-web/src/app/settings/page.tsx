'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useT, LOCALE_LABELS } from '@/lib/i18n'
import LanguageSelector from '@/components/LanguageSelector'

const VERSION = '1.15.0'

export default function SettingsPage() {
  const { t, locale } = useT()
  const [cleared, setCleared] = useState(false)

  const handleClearData = () => {
    if (!window.confirm(t('settings.clearConfirm'))) return
    localStorage.removeItem('halatuju_stream')
    localStorage.removeItem('halatuju_grades')
    localStorage.removeItem('halatuju_profile')
    localStorage.removeItem('halatuju_quiz_signals')
    setCleared(true)
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-4 flex items-center gap-4">
          <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <h1 className="text-xl font-semibold text-gray-900">{t('common.settings')}</h1>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 max-w-lg space-y-6">
        {/* Language */}
        <section className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-1">{t('settings.language')}</h2>
          <p className="text-sm text-gray-500 mb-3">{t('settings.languageDesc')}</p>
          <LanguageSelector />
        </section>

        {/* Clear Data */}
        <section className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-1">{t('settings.clearData')}</h2>
          <p className="text-sm text-gray-500 mb-3">{t('settings.clearDataDesc')}</p>
          {cleared ? (
            <p className="text-sm text-green-600 font-medium">{t('settings.dataCleared')}</p>
          ) : (
            <button
              onClick={handleClearData}
              className="px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
            >
              {t('settings.clearButton')}
            </button>
          )}
        </section>

        {/* About */}
        <section className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-3">{t('settings.aboutTitle')}</h2>
          <div className="space-y-2 text-sm text-gray-600">
            <div className="flex justify-between">
              <span>{t('settings.version')}</span>
              <span className="font-mono text-gray-900">{VERSION}</span>
            </div>
            <div className="flex justify-between">
              <span>{t('settings.currentLanguage')}</span>
              <span className="text-gray-900">{LOCALE_LABELS[locale]}</span>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="text-xs text-gray-400">{t('settings.builtBy')}</p>
            <p className="text-xs text-gray-400">{t('common.copyright')}</p>
          </div>
        </section>
      </div>
    </main>
  )
}
