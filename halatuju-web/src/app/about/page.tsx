'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { PHONE_GUTTER } from '@/lib/phoneSection'   // rule 15 (Mobile M4c)
import { useT } from '@/lib/i18n'

export default function AboutPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-ground-50">
      <AppHeader />

      <div className={`container mx-auto ${PHONE_GUTTER} py-6 max-w-2xl md:py-8`}>
        {/* Rule 15 (Mobile M4c): the page itself on a phone, the white card from md. */}
        <div className="space-y-6 md:rounded-xl md:border md:border-ground-200 md:bg-ground-0 md:p-6">
          <h1 className="text-2xl font-bold text-ground-900">{t('common.about')}</h1>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-ground-900">{t('about.problemTitle')}</h2>
            <p className="text-ground-600">{t('about.problemP1')}</p>
            <p className="text-ground-600">{t('about.problemP2')}</p>
            <p className="text-ground-700 font-medium">{t('about.problemTagline')}</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-ground-900">{t('about.whatTitle')}</h2>
            <p className="text-ground-600">{t('about.whatDesc')}</p>
            <p className="text-ground-700 font-medium">{t('about.whatTagline')}</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-ground-900">{t('about.whoTitle')}</h2>
            <p className="text-ground-600">{t('about.whoP1')}</p>
            <p className="text-ground-600">{t('about.whoP2')}</p>
          </section>

          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-ground-900">{t('about.helpTitle')}</h2>
            <div className="space-y-3">
              <div className="bg-ground-50 rounded-lg p-4">
                <p className="text-ground-700"><span className="font-semibold">{t('about.helpParents')}</span> {t('about.helpParentsDesc')}</p>
              </div>
              <div className="bg-ground-50 rounded-lg p-4">
                <p className="text-ground-700"><span className="font-semibold">{t('about.helpTeachers')}</span> {t('about.helpTeachersDesc')}</p>
              </div>
              <div className="bg-ground-50 rounded-lg p-4">
                <p className="text-ground-700"><span className="font-semibold">{t('about.helpEveryone')}</span> {t('about.helpEveryoneDesc')}</p>
              </div>
            </div>
            <p className="text-ground-600">{t('about.helpClosing')}</p>
          </section>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}
