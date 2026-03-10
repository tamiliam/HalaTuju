'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

export default function AboutPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-6">
          <h1 className="text-2xl font-bold text-gray-900">{t('common.about')}</h1>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">{t('about.problemTitle')}</h2>
            <p className="text-gray-600">{t('about.problemP1')}</p>
            <p className="text-gray-600">{t('about.problemP2')}</p>
            <p className="text-gray-700 font-medium">{t('about.problemTagline')}</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">{t('about.whatTitle')}</h2>
            <p className="text-gray-600">{t('about.whatDesc')}</p>
            <p className="text-gray-700 font-medium">{t('about.whatTagline')}</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">{t('about.whoTitle')}</h2>
            <p className="text-gray-600">{t('about.whoP1')}</p>
            <p className="text-gray-600">{t('about.whoP2')}</p>
          </section>

          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">{t('about.helpTitle')}</h2>
            <div className="space-y-3">
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-700"><span className="font-semibold">{t('about.helpParents')}</span> {t('about.helpParentsDesc')}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-700"><span className="font-semibold">{t('about.helpTeachers')}</span> {t('about.helpTeachersDesc')}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-700"><span className="font-semibold">{t('about.helpEveryone')}</span> {t('about.helpEveryoneDesc')}</p>
              </div>
            </div>
            <p className="text-gray-600">{t('about.helpClosing')}</p>
          </section>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}
