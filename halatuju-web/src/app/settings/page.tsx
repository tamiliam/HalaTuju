'use client'

import { useState } from 'react'
import { useT, LOCALE_LABELS } from '@/lib/i18n'
import { clearAll } from '@/lib/storage'
import LanguageSelector from '@/components/LanguageSelector'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'

// Manually bumped at release (no central runtime version source yet — see TD-076).
const VERSION = '2.26.1'

export default function SettingsPage() {
  const { t, locale } = useT()
  const [cleared, setCleared] = useState(false)

  const handleClearData = () => {
    if (!window.confirm(t('settings.clearConfirm'))) return
    clearAll()
    setCleared(true)
  }

  return (
    <main className="min-h-screen bg-ground-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-lg space-y-6">
        {/* Language */}
        <section className="bg-ground-0 rounded-xl border border-ground-200 p-5">
          <h2 className="font-semibold text-ground-900 mb-1">{t('settings.language')}</h2>
          <p className="text-sm text-ground-500 mb-3">{t('settings.languageDesc')}</p>
          <LanguageSelector />
        </section>

        {/* Clear Data */}
        <section className="bg-ground-0 rounded-xl border border-ground-200 p-5">
          <h2 className="font-semibold text-ground-900 mb-1">{t('settings.clearData')}</h2>
          <p className="text-sm text-ground-500 mb-3">{t('settings.clearDataDesc')}</p>
          {cleared ? (
            <p className="text-sm text-positive-600 font-medium">{t('settings.dataCleared')}</p>
          ) : (
            <button
              onClick={handleClearData}
              className="px-4 py-2 text-sm font-medium text-critical-600 border border-critical-200 rounded-lg hover:bg-critical-50 transition-colors"
            >
              {t('settings.clearButton')}
            </button>
          )}
        </section>

        {/* About */}
        <section className="bg-ground-0 rounded-xl border border-ground-200 p-5">
          <h2 className="font-semibold text-ground-900 mb-3">{t('settings.aboutTitle')}</h2>
          <div className="space-y-2 text-sm text-ground-600">
            <div className="flex justify-between">
              <span>{t('settings.version')}</span>
              <span className="font-mono text-ground-900">{VERSION}</span>
            </div>
            <div className="flex justify-between">
              <span>{t('settings.currentLanguage')}</span>
              <span className="text-ground-900">{LOCALE_LABELS[locale]}</span>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-ground-100 space-y-2">
            <p className="text-xs text-ground-400">{t('settings.builtBy')}</p>
            <p className="text-xs text-ground-400">{t('common.copyright')}</p>
          </div>
        </section>
      </div>

      <AppFooter />
    </main>
  )
}
