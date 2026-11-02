'use client'

import Link from 'next/link'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { PHONE_GUTTER } from '@/lib/phoneSection'   // rule 15 (Mobile M4c)
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'

export default function GetStartedPage() {
  const { t } = useT()
  const { showAuthGate } = useAuth()

  return (
    <div className="min-h-screen flex flex-col bg-ground-50">
      <AppHeader />
      <main className={`flex-1 flex items-center justify-center ${PHONE_GUTTER} py-6 md:py-12`}>
        {/* Rule 15 (Mobile M4c): the page itself on a phone, the white card from md. */}
        <div className="w-full max-w-md md:rounded-2xl md:border md:bg-ground-0 md:p-8 md:shadow-sm">
          <h1 className="text-xl font-bold text-ground-900">{t('getStarted.title')}</h1>
          <p className="text-sm text-ground-600 mt-1">{t('getStarted.tagline')}</p>

          <button
            onClick={() => showAuthGate('profile')}
            className="mt-6 w-full bg-brand-fill text-brand-fill-ink font-semibold py-3 rounded-xl hover:bg-brand-fill-hover transition-colors"
          >
            {t('getStarted.student')}
          </button>

          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-ground-200" />
            <span className="text-xs text-ground-400">{t('getStarted.or')}</span>
            <div className="flex-1 h-px bg-ground-200" />
          </div>

          <Link
            href="/sponsor/register"
            className="block w-full text-center border border-primary-300 text-primary-700 font-semibold py-3 rounded-xl hover:bg-primary-50 transition-colors"
          >
            {t('getStarted.sponsor')}
          </Link>

          <div className="border-t mt-6 pt-4 flex items-center justify-between gap-3">
            <span className="min-w-0 text-sm text-ground-600">{t('getStarted.haveAccount')}</span>
            <button
              onClick={() => showAuthGate('profile')}
              className="min-h-11 shrink-0 whitespace-nowrap text-sm font-semibold text-primary-600 border border-ground-200 rounded-lg px-4 py-1.5 hover:bg-ground-50 md:min-h-0"
            >
              {t('header.login.label')}
            </button>
          </div>
          <p className="text-xs text-ground-400 mt-3">{t('getStarted.partnerNote')}</p>
        </div>
      </main>
      <AppFooter />
    </div>
  )
}
